package ai.pickup.app.ui.onboarding

import ai.pickup.app.AppGraph
import ai.pickup.app.auth.PhoneAuth
import ai.pickup.app.data.ApiException
import ai.pickup.app.data.AssistantPatch
import ai.pickup.app.data.ContactBody
import ai.pickup.app.data.LineDto
import ai.pickup.app.data.MePatch
import ai.pickup.app.data.PublicConfig
import ai.pickup.app.telephony.PhoneUtils
import ai.pickup.app.util.Format
import android.app.Activity
import android.content.Context
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.google.firebase.auth.PhoneAuthProvider
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import kotlinx.serialization.json.contentOrNull
import kotlinx.serialization.json.jsonPrimitive

enum class Step { Welcome, Phone, Code, Profile, Permissions, Forwarding, Verify, Demo, Done }

sealed interface VerifyState {
    data object Idle : VerifyState
    data object Calling : VerifyState
    data object Success : VerifyState
    data class Failed(val message: String) : VerifyState
}

data class OnboardingState(
    val step: Step = Step.Welcome,
    val config: PublicConfig? = null,
    val phoneInput: String = "",
    val phoneE164: String? = null,
    val code: String = "",
    val resendInSeconds: Int = 0,
    val name: String = "",
    val languages: List<String> = listOf("en-IN", "hi-IN"),
    val voice: String = "ritu",
    val line: LineDto? = null,
    val dialed: Set<String> = emptySet(),
    val simCount: Int = 1,
    val simPass: Int = 1,
    val verify: VerifyState = VerifyState.Idle,
    val busy: Boolean = false,
    val error: String? = null,
    /** The server has no assistant number free yet; setup can be finished later from home. */
    val waitingForNumber: Boolean = false,
) {
    val useFirebase: Boolean get() = config?.authModes?.contains("firebase") == true
    val betaOnly: Boolean get() = config?.authModes?.let { "beta" in it && "firebase" !in it && "dev" !in it } == true
    val devCodeHint: String? get() = config?.devCodeHint
}

class OnboardingViewModel(private val graph: AppGraph, private val forcedStep: Step? = null) : ViewModel() {
    private val repo = graph.repository
    private val phoneAuth = PhoneAuth()
    private var verificationId: String? = null
    private var resendToken: PhoneAuthProvider.ForceResendingToken? = null
    private var countdown: Job? = null
    private var verifyJob: Job? = null

    private val _state = MutableStateFlow(OnboardingState(step = forcedStep ?: Step.Welcome))
    val state: StateFlow<OnboardingState> = _state

    init {
        viewModelScope.launch {
            val config = runCatching { repo.config() }.getOrNull()
            _state.update { it.copy(config = config) }
            if (!graph.store.access().isNullOrBlank()) resumeSignedIn()
        }
        // The forwarding test succeeds the moment the backend sees the forwarded call.
        viewModelScope.launch {
            graph.live.events.collect { event ->
                if (event["type"]?.jsonPrimitive?.contentOrNull == "line.verified") onVerified()
            }
        }
    }

    private suspend fun resumeSignedIn() {
        val me = runCatching { repo.me() }.getOrNull() ?: return
        val line = runCatching { repo.currentLine() }.getOrNull()
        val step = forcedStep ?: when {
            me.name.isNullOrBlank() -> Step.Profile
            line == null -> Step.Permissions
            line.status != "verified" -> Step.Forwarding
            else -> Step.Demo
        }
        _state.update { it.copy(step = step, name = me.name ?: "", line = line, phoneE164 = me.phone) }
    }

    fun go(step: Step) = _state.update { it.copy(step = step, error = null) }
    fun clearError() = _state.update { it.copy(error = null) }
    fun onPhoneChange(value: String) = _state.update { it.copy(phoneInput = value.filter { c -> c.isDigit() || c == '+' || c == ' ' }.take(16), error = null) }
    fun onNameChange(value: String) = _state.update { it.copy(name = value.take(60)) }
    fun onVoice(voice: String) = _state.update { it.copy(voice = voice) }
    fun toggleLanguage(code: String) = _state.update {
        val next = if (code in it.languages) it.languages - code else it.languages + code
        it.copy(languages = next.ifEmpty { listOf("en-IN") }.take(3))
    }

    fun onCodeChange(value: String, activity: Activity?) {
        val digits = value.filter { it.isDigit() }.take(6)
        _state.update { it.copy(code = digits, error = null) }
        if (digits.length == 6) submitCode()
    }

    fun submitPhone(activity: Activity?) {
        val input = _state.value.phoneInput.trim()
        val phone = Format.normalizeIndianMobile(input)
            ?: input.takeIf { it.startsWith("+") }?.let { "+" + it.filter { c -> c.isDigit() } }?.takeIf { it.length >= 9 }
        if (phone == null) {
            _state.update { it.copy(error = "Enter your 10-digit mobile number") }
            return
        }
        val modes = _state.value.config?.authModes.orEmpty()
        if (_state.value.config != null && modes.isEmpty()) {
            _state.update { it.copy(error = "Sign-in isn't set up on this server yet.") }
            return
        }
        if ("dev" !in modes && "beta" !in modes && !graph.firebaseAvailable) {
            _state.update { it.copy(error = "This build can't send codes yet: add google-services.json and rebuild.") }
            return
        }
        _state.update { it.copy(phoneE164 = phone, busy = true, error = null) }
        if (_state.value.useFirebase && activity != null && graph.firebaseAvailable) {
            sendFirebaseCode(activity, phone)
        } else {
            _state.update { it.copy(busy = false, step = Step.Code, code = "") }
            startCountdown()
        }
    }

    private fun sendFirebaseCode(activity: Activity, phone: String) {
        phoneAuth.sendCode(activity, phone, resendToken) { event ->
            when (event) {
                is PhoneAuth.Event.CodeSent -> {
                    verificationId = event.verificationId
                    resendToken = event.resendToken
                    _state.update { it.copy(busy = false, step = Step.Code, code = "") }
                    startCountdown()
                }
                is PhoneAuth.Event.AutoVerified -> finishSignIn { repo.signInFirebase(event.idToken) }
                is PhoneAuth.Event.Failed -> _state.update { it.copy(busy = false, error = event.message) }
            }
        }
    }

    fun resend(activity: Activity?) {
        val phone = _state.value.phoneE164 ?: return
        if (_state.value.useFirebase && activity != null && graph.firebaseAvailable) {
            _state.update { it.copy(busy = true) }
            sendFirebaseCode(activity, phone)
        } else {
            startCountdown()
        }
    }

    private fun startCountdown() {
        countdown?.cancel()
        countdown = viewModelScope.launch {
            for (s in 30 downTo 0) {
                _state.update { it.copy(resendInSeconds = s) }
                delay(1000)
            }
        }
    }

    fun submitCode() {
        val s = _state.value
        val phone = s.phoneE164 ?: return
        if (s.code.length != 6 || s.busy) return
        val id = verificationId
        if (s.useFirebase && id != null) {
            finishSignIn { repo.signInFirebase(phoneAuth.verifyCode(id, s.code)) }
        } else {
            finishSignIn { repo.signInDev(phone, s.code) }
        }
    }

    private fun finishSignIn(block: suspend () -> Any) {
        _state.update { it.copy(busy = true, error = null) }
        viewModelScope.launch {
            try {
                block()
                graph.live.start()
                val me = repo.me()
                if (me.onboardingCompleted) {
                    _state.update { it.copy(busy = false, step = Step.Done) }
                } else {
                    resumeSignedIn()
                    _state.update { it.copy(busy = false) }
                }
            } catch (e: Exception) {
                _state.update { it.copy(busy = false, code = "", error = e.message ?: "That code didn't work") }
            }
        }
    }

    fun saveProfile() {
        val s = _state.value
        if (s.name.isBlank()) {
            _state.update { it.copy(error = "Tell your assistant your name") }
            return
        }
        _state.update { it.copy(busy = true) }
        viewModelScope.launch {
            try {
                repo.updateMe(MePatch(name = s.name.trim(), language = s.languages.first()))
                repo.updateAssistant(AssistantPatch(voice = s.voice, languages = s.languages))
                _state.update { it.copy(busy = false, step = Step.Permissions) }
            } catch (e: Exception) {
                _state.update { it.copy(busy = false, error = e.message) }
            }
        }
    }

    fun syncContacts(context: Context) {
        viewModelScope.launch {
            val grouped = PhoneUtils.readContacts(context).groupBy({ it.first }, { it.second })
            if (grouped.isNotEmpty()) runCatching { repo.syncContacts(grouped.map { (name, numbers) -> ContactBody(name, numbers.distinct()) }) }
        }
    }

    fun permissionsDone(context: Context) {
        val sims = PhoneUtils.activeSimCount(context)
        _state.update { it.copy(busy = true, simCount = sims) }
        viewModelScope.launch {
            try {
                val line = repo.currentLine() ?: repo.createLine(PhoneUtils.carrierName(context), sims, 20)
                repo.refreshPolicy()
                _state.update { it.copy(busy = false, line = line, waitingForNumber = false, step = if (line.status == "verified") Step.Demo else Step.Forwarding) }
            } catch (e: Exception) {
                _state.update { it.copy(busy = false, error = e.message, waitingForNumber = (e as? ApiException)?.status == 503) }
            }
        }
    }

    fun dial(context: Context, key: String, code: String) {
        PhoneUtils.openDialer(context, code)
        _state.update { it.copy(dialed = it.dialed + "${it.simPass}:$key") }
    }

    fun nextSimPass() = _state.update { it.copy(simPass = it.simPass + 1) }

    fun forwardingDone() {
        viewModelScope.launch {
            graph.store.saveConfiguredSims(_state.value.simCount)
            repo.refreshPolicy()
            _state.update { it.copy(step = Step.Verify, verify = VerifyState.Idle) }
        }
    }

    fun startVerify() {
        val line = _state.value.line ?: return
        verifyJob?.cancel()
        _state.update { it.copy(verify = VerifyState.Calling) }
        verifyJob = viewModelScope.launch {
            try {
                repo.refreshPolicy()
                repo.startVerification(line.id)
            } catch (e: Exception) {
                _state.update { it.copy(verify = VerifyState.Failed(e.message ?: "Couldn't start the test call")) }
                return@launch
            }
            repeat(40) {
                delay(3000)
                val current = runCatching { repo.currentLine() }.getOrNull()
                if (current?.status == "verified") {
                    onVerified()
                    return@launch
                }
            }
            _state.update {
                it.copy(verify = VerifyState.Failed("The test call didn't come back to your assistant. Check that you tapped Call for each code and saw a confirmation."))
            }
        }
    }

    private fun onVerified() {
        if (_state.value.verify == VerifyState.Success) return
        verifyJob?.cancel()
        viewModelScope.launch {
            graph.store.saveVerifyUntil(0)
            val line = runCatching { repo.currentLine() }.getOrNull()
            repo.refreshPolicy()
            _state.update { it.copy(verify = VerifyState.Success, line = line ?: it.line) }
        }
    }

    fun demoCall(context: Context) {
        val number = _state.value.line?.assistantNumber ?: return
        PhoneUtils.startSafely(context, PhoneUtils.callIntent(number))
    }

    fun finish(onDone: () -> Unit) {
        viewModelScope.launch {
            runCatching { repo.updateMe(MePatch(onboardingCompleted = true)) }
            repo.refreshPolicy()
            onDone()
        }
    }

    fun setServer(url: String) {
        viewModelScope.launch {
            graph.store.saveServer(url.trim().ifBlank { null })
            val config = runCatching { repo.config() }.getOrNull()
            _state.update { it.copy(config = config, error = if (config == null) "Can't reach that server" else null) }
        }
    }
}
