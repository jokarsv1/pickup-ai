package ai.pickup.app.ui.onboarding

import ai.pickup.app.data.ForwardingCode
import ai.pickup.app.telephony.PhoneUtils
import ai.pickup.app.ui.components.PrimaryButton
import ai.pickup.app.ui.components.StepIndicator
import ai.pickup.app.ui.theme.LocalPickupColors
import android.Manifest
import android.app.Activity
import android.content.ClipData
import android.content.ClipboardManager
import android.content.Context
import android.content.ContextWrapper
import android.os.Build
import android.widget.Toast
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.animation.AnimatedContent
import androidx.compose.foundation.background
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.systemBarsPadding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Bolt
import androidx.compose.material.icons.filled.Call
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material.icons.filled.Contacts
import androidx.compose.material.icons.filled.ContentCopy
import androidx.compose.material.icons.filled.NotificationsActive
import androidx.compose.material.icons.filled.Phone
import androidx.compose.material.icons.filled.Shield
import androidx.compose.material.icons.filled.SimCard
import androidx.compose.material.icons.filled.Translate
import androidx.compose.material.icons.filled.Warning
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.FilledTonalButton
import androidx.compose.material3.FilterChip
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.compose.LifecycleEventEffect
import androidx.lifecycle.compose.collectAsStateWithLifecycle

private val LANGUAGES = listOf(
    "en-IN" to "English",
    "hi-IN" to "हिन्दी Hindi",
    "ta-IN" to "தமிழ் Tamil",
    "te-IN" to "తెలుగు Telugu",
    "kn-IN" to "ಕನ್ನಡ Kannada",
    "mr-IN" to "मराठी Marathi",
    "bn-IN" to "বাংলা Bengali",
    "gu-IN" to "ગુજરાતી Gujarati",
    "ml-IN" to "മലയാളം Malayalam",
)

private val VOICES = listOf(
    "ritu" to "Ritu · female",
    "priya" to "Priya · female",
    "kavya" to "Kavya · female",
    "shubh" to "Shubh · male",
    "aditya" to "Aditya · male",
    "rahul" to "Rahul · male",
)

fun Context.findActivity(): Activity? {
    var ctx: Context? = this
    while (ctx is ContextWrapper) {
        if (ctx is Activity) return ctx
        ctx = ctx.baseContext
    }
    return null
}

@Composable
fun OnboardingRoute(vm: OnboardingViewModel, onFinished: () -> Unit) {
    val state by vm.state.collectAsStateWithLifecycle()
    AnimatedContent(targetState = state.step, label = "onboarding") { step ->
        when (step) {
            Step.Welcome -> WelcomeScreen(vm, state)
            Step.Phone -> PhoneScreen(vm, state)
            Step.Code -> CodeScreen(vm, state)
            Step.Profile -> ProfileScreen(vm, state)
            Step.Permissions -> PermissionsScreen(vm, state)
            Step.Forwarding -> ForwardingScreen(vm, state)
            Step.Verify -> VerifyScreen(vm, state)
            Step.Demo -> DemoScreen(vm)
            Step.Done -> DoneScreen(vm, onFinished)
        }
    }
}

@Composable
private fun StepLayout(
    stepIndex: Int?,
    title: String,
    body: String?,
    error: String? = null,
    footer: @Composable ColumnScope.() -> Unit,
    content: @Composable ColumnScope.() -> Unit,
) {
    Column(
        Modifier
            .fillMaxSize()
            .background(MaterialTheme.colorScheme.background)
            .systemBarsPadding()
            .imePadding()
            .padding(horizontal = 24.dp)
    ) {
        Column(Modifier.weight(1f).verticalScroll(rememberScrollState())) {
            Spacer(Modifier.height(16.dp))
            if (stepIndex != null) {
                StepIndicator(stepIndex, 6)
                Spacer(Modifier.height(28.dp))
            }
            Text(title, style = MaterialTheme.typography.headlineMedium)
            if (body != null) {
                Spacer(Modifier.height(8.dp))
                Text(body, style = MaterialTheme.typography.bodyLarge, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
            Spacer(Modifier.height(24.dp))
            content()
            if (error != null) {
                Spacer(Modifier.height(12.dp))
                Text(error, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodyMedium)
            }
            Spacer(Modifier.height(24.dp))
        }
        Column(Modifier.padding(bottom = 16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) { footer() }
    }
}

@Composable
private fun WelcomeScreen(vm: OnboardingViewModel, state: OnboardingState) {
    var showServer by remember { mutableStateOf(false) }
    Column(
        Modifier
            .fillMaxSize()
            .background(MaterialTheme.colorScheme.background)
            .systemBarsPadding()
            .padding(horizontal = 24.dp)
    ) {
        Column(Modifier.weight(1f).verticalScroll(rememberScrollState())) {
            Spacer(Modifier.height(48.dp))
            Box(
                Modifier
                    .size(64.dp)
                    .clip(RoundedCornerShape(20.dp))
                    .background(MaterialTheme.colorScheme.primary)
                    .pointerInput(Unit) { detectTapGestures(onLongPress = { showServer = true }) },
                contentAlignment = Alignment.Center,
            ) {
                Icon(Icons.Filled.Call, contentDescription = "Pickup", tint = MaterialTheme.colorScheme.onPrimary, modifier = Modifier.size(32.dp))
            }
            Spacer(Modifier.height(32.dp))
            Text("Let AI take your calls.", style = MaterialTheme.typography.displaySmall)
            Spacer(Modifier.height(12.dp))
            Text(
                "Pickup answers the calls you can't or don't want to take, finds out who's calling and why, and tells you in seconds.",
                style = MaterialTheme.typography.bodyLarge,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            Spacer(Modifier.height(36.dp))
            Benefit(Icons.Filled.Shield, "Spam and scams never reach you", "Loan offers, fake KYC and 'parcel seized' calls end with your assistant.")
            Benefit(Icons.Filled.Bolt, "Live transcript, one-tap replies", "Read the call as it happens. Tell your assistant what to say, or join in.")
            Benefit(Icons.Filled.Translate, "Speaks like your callers", "Hindi, English, Hinglish and more Indian languages.")
        }
        Column(Modifier.padding(bottom = 16.dp), horizontalAlignment = Alignment.CenterHorizontally) {
            PrimaryButton("Get started", onClick = { vm.go(Step.Phone) })
            Spacer(Modifier.height(10.dp))
            Text("Free for 7 days. No card needed.", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
    }
    if (showServer) ServerDialog(onDismiss = { showServer = false }, onSave = { vm.setServer(it); showServer = false })
}

@Composable
private fun Benefit(icon: ImageVector, title: String, body: String) {
    Row(Modifier.padding(vertical = 10.dp)) {
        Box(Modifier.size(40.dp).clip(CircleShape).background(MaterialTheme.colorScheme.primaryContainer), contentAlignment = Alignment.Center) {
            Icon(icon, null, tint = MaterialTheme.colorScheme.primary, modifier = Modifier.size(22.dp))
        }
        Spacer(Modifier.width(14.dp))
        Column {
            Text(title, style = MaterialTheme.typography.titleMedium)
            Text(body, style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
    }
}

@Composable
private fun ServerDialog(onDismiss: () -> Unit, onSave: (String) -> Unit) {
    var url by remember { mutableStateOf("") }
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("Developer: server address") },
        text = {
            OutlinedTextField(
                value = url,
                onValueChange = { url = it },
                placeholder = { Text("https://your-server.example.com") },
                singleLine = true,
                keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Uri),
            )
        },
        confirmButton = { TextButton(onClick = { onSave(url) }) { Text("Save") } },
        dismissButton = { TextButton(onClick = { onSave("") }) { Text("Use default") } },
    )
}

@Composable
private fun PhoneScreen(vm: OnboardingViewModel, state: OnboardingState) {
    val activity = LocalContext.current.findActivity()
    StepLayout(
        stepIndex = 0,
        title = "What's your mobile number?",
        body = if (state.betaOnly) "Use the number of the SIM in this phone." else "Use the number of the SIM in this phone. We'll text you a 6-digit code.",
        error = state.error,
        footer = {
            PrimaryButton("Send code", onClick = { vm.submitPhone(activity) }, loading = state.busy, enabled = state.phoneInput.count { it.isDigit() } >= 10)
            TextButton(onClick = { vm.go(Step.Welcome) }, modifier = Modifier.fillMaxWidth()) { Text("Back") }
        },
    ) {
        OutlinedTextField(
            value = state.phoneInput,
            onValueChange = vm::onPhoneChange,
            prefix = { Text("+91 ") },
            placeholder = { Text("98765 43210") },
            singleLine = true,
            textStyle = MaterialTheme.typography.titleLarge,
            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Phone, imeAction = ImeAction.Done),
            modifier = Modifier.fillMaxWidth(),
        )
    }
}

@Composable
private fun CodeScreen(vm: OnboardingViewModel, state: OnboardingState) {
    val activity = LocalContext.current.findActivity()
    StepLayout(
        stepIndex = 0,
        title = if (state.betaOnly) "Enter your beta code" else "Enter the code",
        body = if (state.betaOnly) "Pickup is in private beta. Enter the code you were given for ${state.phoneE164 ?: "this number"}."
        else "We sent a 6-digit code to ${state.phoneE164 ?: "your phone"}.",
        error = state.error,
        footer = {
            PrimaryButton("Verify", onClick = vm::submitCode, loading = state.busy, enabled = state.code.length == 6)
            TextButton(onClick = { vm.go(Step.Phone) }, modifier = Modifier.fillMaxWidth()) { Text("Change number") }
        },
    ) {
        OutlinedTextField(
            value = state.code,
            onValueChange = { vm.onCodeChange(it, activity) },
            placeholder = { Text("······") },
            singleLine = true,
            textStyle = MaterialTheme.typography.headlineMedium.copy(letterSpacing = 12.sp, fontFamily = FontFamily.Monospace),
            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.NumberPassword, imeAction = ImeAction.Done),
            modifier = Modifier.fillMaxWidth(),
        )
        Spacer(Modifier.height(12.dp))
        if (state.resendInSeconds > 0) {
            Text("Resend code in 0:%02d".format(state.resendInSeconds), color = MaterialTheme.colorScheme.onSurfaceVariant)
        } else {
            TextButton(onClick = { vm.resend(activity) }) { Text("Resend code") }
        }
        state.devCodeHint?.takeIf { !state.useFirebase }?.let {
            Spacer(Modifier.height(8.dp))
            Text("Development server: the code is $it", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.tertiary)
        }
    }
}

@OptIn(ExperimentalLayoutApi::class)
@Composable
private fun ProfileScreen(vm: OnboardingViewModel, state: OnboardingState) {
    StepLayout(
        stepIndex = 1,
        title = "Make it yours",
        body = "Your assistant introduces itself as yours, in your callers' language.",
        error = state.error,
        footer = { PrimaryButton("Continue", onClick = vm::saveProfile, loading = state.busy, enabled = state.name.isNotBlank()) },
    ) {
        OutlinedTextField(
            value = state.name,
            onValueChange = vm::onNameChange,
            label = { Text("Your name") },
            placeholder = { Text("How callers know you") },
            singleLine = true,
            keyboardOptions = KeyboardOptions(imeAction = ImeAction.Done),
            modifier = Modifier.fillMaxWidth(),
        )
        Spacer(Modifier.height(24.dp))
        Text("Languages your callers speak", style = MaterialTheme.typography.titleMedium)
        Text("Pick up to three. Your assistant mixes them naturally, like Hinglish.", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        Spacer(Modifier.height(8.dp))
        FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            LANGUAGES.forEach { (code, label) ->
                FilterChip(selected = code in state.languages, onClick = { vm.toggleLanguage(code) }, label = { Text(label) })
            }
        }
        Spacer(Modifier.height(24.dp))
        Text("Voice", style = MaterialTheme.typography.titleMedium)
        Spacer(Modifier.height(8.dp))
        FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            VOICES.forEach { (id, label) ->
                FilterChip(selected = state.voice == id, onClick = { vm.onVoice(id) }, label = { Text(label) })
            }
        }
    }
}

@Composable
private fun PermissionsScreen(vm: OnboardingViewModel, state: OnboardingState) {
    val context = LocalContext.current
    var tick by remember { mutableIntStateOf(0) }
    LifecycleEventEffect(Lifecycle.Event.ON_RESUME) { tick++ }
    val roleLauncher = rememberLauncherForActivityResult(ActivityResultContracts.StartActivityForResult()) { tick++ }
    val notifLauncher = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { tick++ }
    val contactsLauncher = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { granted ->
        if (granted) vm.syncContacts(context)
        tick++
    }
    val phoneLauncher = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { tick++ }

    // Re-read on every resume and after every permission result.
    val screening = remember(tick) { PhoneUtils.isScreeningRoleHeld(context) }
    val notifications = remember(tick) {
        Build.VERSION.SDK_INT < Build.VERSION_CODES.TIRAMISU || PhoneUtils.hasPermission(context, Manifest.permission.POST_NOTIFICATIONS)
    }
    val contacts = remember(tick) { PhoneUtils.hasPermission(context, Manifest.permission.READ_CONTACTS) }
    val phone = remember(tick) { PhoneUtils.hasPermission(context, Manifest.permission.READ_PHONE_STATE) }

    StepLayout(
        stepIndex = 2,
        title = "A few permissions",
        body = "Each one has a single job. Pickup never reads your messages or your call history.",
        error = state.error,
        footer = {
            PrimaryButton("Continue", onClick = { vm.permissionsDone(context) }, enabled = screening, loading = state.busy)
            if (!screening) {
                Text(
                    "Call screening is required. It's how Pickup sends unknown callers to your assistant.",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    textAlign = TextAlign.Center,
                    modifier = Modifier.fillMaxWidth(),
                )
            }
        },
    ) {
        PermissionRow(Icons.Filled.Shield, "Screen calls", "Lets Pickup decline unknown callers so your carrier forwards them to your assistant.", screening, required = true) {
            PhoneUtils.screeningRoleIntent(context)?.let { roleLauncher.launch(it) }
                ?: Toast.makeText(context, "This phone doesn't support call screening apps", Toast.LENGTH_LONG).show()
        }
        PermissionRow(Icons.Filled.NotificationsActive, "Notifications", "See who's calling and why, live, and reply in one tap.", notifications) {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) notifLauncher.launch(Manifest.permission.POST_NOTIFICATIONS)
        }
        PermissionRow(Icons.Filled.Contacts, "Contacts", "Friends and family always ring through, and your assistant knows their names.", contacts) {
            contactsLauncher.launch(Manifest.permission.READ_CONTACTS)
        }
        PermissionRow(Icons.Filled.SimCard, "Phone", "Checks how many SIMs you use, so no call is ever lost on a dual-SIM phone.", phone) {
            phoneLauncher.launch(Manifest.permission.READ_PHONE_STATE)
        }
    }
}

@Composable
private fun PermissionRow(icon: ImageVector, title: String, body: String, granted: Boolean, required: Boolean = false, onAllow: () -> Unit) {
    Card(
        modifier = Modifier.fillMaxWidth().padding(vertical = 6.dp),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceContainerLowest),
    ) {
        Row(Modifier.padding(16.dp), verticalAlignment = Alignment.CenterVertically) {
            Icon(icon, null, tint = MaterialTheme.colorScheme.primary)
            Spacer(Modifier.width(14.dp))
            Column(Modifier.weight(1f)) {
                Text(title + if (required) " (required)" else "", style = MaterialTheme.typography.titleMedium)
                Text(body, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
            Spacer(Modifier.width(8.dp))
            if (granted) {
                Icon(Icons.Filled.CheckCircle, "Allowed", tint = LocalPickupColors.current.success)
            } else {
                FilledTonalButton(onClick = onAllow) { Text("Allow") }
            }
        }
    }
}

@Composable
private fun ForwardingScreen(vm: OnboardingViewModel, state: OnboardingState) {
    val context = LocalContext.current
    val line = state.line
    val codes = line?.activationCodes.orEmpty()
    val passDone = codes.isNotEmpty() && codes.all { "${state.simPass}:${it.key}" in state.dialed }
    val lastPass = state.simPass >= state.simCount
    StepLayout(
        stepIndex = 3,
        title = "Point missed calls to your assistant",
        body = "Your carrier forwards calls you decline or miss. Tap Dial, then the green call button. Do it for each one.",
        error = state.error,
        footer = {
            if (passDone && !lastPass) {
                PrimaryButton("Next: set up SIM ${state.simPass + 1}", onClick = vm::nextSimPass)
            } else {
                PrimaryButton("I've dialed all three", onClick = vm::forwardingDone, enabled = passDone)
            }
        },
    ) {
        if (line != null) AssistantNumberCard(context, line.assistantNumberDisplay, line.assistantNumber)
        if (state.simCount > 1) {
            Spacer(Modifier.height(12.dp))
            Surface(color = MaterialTheme.colorScheme.tertiaryContainer, shape = RoundedCornerShape(12.dp)) {
                Text(
                    "You have ${state.simCount} SIMs. Setting up SIM ${state.simPass} of ${state.simCount}: when the dialer asks, choose SIM ${state.simPass}.",
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onTertiaryContainer,
                    modifier = Modifier.padding(12.dp),
                )
            }
        }
        Spacer(Modifier.height(12.dp))
        codes.forEachIndexed { index, code ->
            CodeCard(index + 1, code, dialed = "${state.simPass}:${code.key}" in state.dialed) { vm.dial(context, code.key, code.code) }
        }
        line?.carrierNote?.let {
            Spacer(Modifier.height(8.dp))
            Text(it, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
        Spacer(Modifier.height(4.dp))
        Text(
            "You can turn this off anytime from Settings (it dials ${line?.deactivationCode ?: "##004#"}).",
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
    }
}

@Composable
private fun AssistantNumberCard(context: Context, display: String, raw: String) {
    Card(colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.primaryContainer), modifier = Modifier.fillMaxWidth()) {
        Row(Modifier.padding(16.dp), verticalAlignment = Alignment.CenterVertically) {
            Column(Modifier.weight(1f)) {
                Text("Your assistant's number", style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.onPrimaryContainer)
                Text(display, style = MaterialTheme.typography.titleLarge, color = MaterialTheme.colorScheme.onPrimaryContainer)
            }
            IconButton(onClick = {
                context.getSystemService(ClipboardManager::class.java)?.setPrimaryClip(ClipData.newPlainText("Assistant number", raw))
                Toast.makeText(context, "Copied", Toast.LENGTH_SHORT).show()
            }) { Icon(Icons.Filled.ContentCopy, "Copy number", tint = MaterialTheme.colorScheme.onPrimaryContainer) }
        }
    }
}

@Composable
private fun CodeCard(number: Int, code: ForwardingCode, dialed: Boolean, onDial: () -> Unit) {
    Card(
        modifier = Modifier.fillMaxWidth().padding(vertical = 6.dp),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceContainerLowest),
    ) {
        Column(Modifier.padding(16.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Box(
                    Modifier.size(28.dp).clip(CircleShape).background(if (dialed) LocalPickupColors.current.success else MaterialTheme.colorScheme.primary),
                    contentAlignment = Alignment.Center,
                ) {
                    if (dialed) Icon(Icons.Filled.CheckCircle, null, tint = MaterialTheme.colorScheme.onPrimary, modifier = Modifier.size(18.dp))
                    else Text("$number", color = MaterialTheme.colorScheme.onPrimary, style = MaterialTheme.typography.labelLarge)
                }
                Spacer(Modifier.width(12.dp))
                Text(code.title, style = MaterialTheme.typography.titleMedium, modifier = Modifier.weight(1f))
            }
            Spacer(Modifier.height(6.dp))
            Text(code.description, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            Spacer(Modifier.height(10.dp))
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text(code.code, fontFamily = FontFamily.Monospace, fontWeight = FontWeight.Medium, modifier = Modifier.weight(1f))
                if (dialed) OutlinedButton(onClick = onDial) { Text("Dial again") } else FilledTonalButton(onClick = onDial) { Text("Dial") }
            }
        }
    }
}

@Composable
private fun VerifyScreen(vm: OnboardingViewModel, state: OnboardingState) {
    val verify = state.verify
    StepLayout(
        stepIndex = 4,
        title = when (verify) {
            VerifyState.Success -> "Your assistant is live"
            is VerifyState.Failed -> "Let's fix that"
            else -> "Let's test it"
        },
        body = when (verify) {
            VerifyState.Idle -> "We'll call you from your assistant's number. Don't answer: Pickup declines it for you, and your carrier should send it straight back to your assistant."
            VerifyState.Calling -> "Calling you now. Leave it; Pickup will decline it in a second."
            VerifyState.Success -> "Forwarding works. Unknown callers now reach your assistant instead of interrupting you."
            is VerifyState.Failed -> verify.message
        },
        footer = {
            when (verify) {
                VerifyState.Idle -> PrimaryButton("Call me now", onClick = vm::startVerify)
                VerifyState.Calling -> PrimaryButton("Waiting for the call…", onClick = {}, loading = true)
                VerifyState.Success -> PrimaryButton("Continue", onClick = { vm.go(Step.Demo) })
                is VerifyState.Failed -> {
                    PrimaryButton("Try again", onClick = vm::startVerify)
                    TextButton(onClick = { vm.go(Step.Forwarding) }, modifier = Modifier.fillMaxWidth()) { Text("Dial the codes again") }
                }
            }
            if (verify != VerifyState.Success) {
                TextButton(onClick = { vm.go(Step.Demo) }, modifier = Modifier.fillMaxWidth()) { Text("Skip for now") }
            }
        },
    ) {
        Box(Modifier.fillMaxWidth().padding(vertical = 24.dp), contentAlignment = Alignment.Center) {
            when (verify) {
                VerifyState.Calling -> CircularProgressIndicator(Modifier.size(72.dp), strokeWidth = 5.dp)
                VerifyState.Success -> Icon(Icons.Filled.CheckCircle, null, tint = LocalPickupColors.current.success, modifier = Modifier.size(96.dp))
                is VerifyState.Failed -> Icon(Icons.Filled.Warning, null, tint = LocalPickupColors.current.warning, modifier = Modifier.size(80.dp))
                VerifyState.Idle -> Icon(Icons.Filled.Phone, null, tint = MaterialTheme.colorScheme.primary, modifier = Modifier.size(80.dp))
            }
        }
        if (verify is VerifyState.Failed) {
            Text("Things to check", style = MaterialTheme.typography.titleMedium)
            Spacer(Modifier.height(6.dp))
            listOf(
                "After each code, your phone should show a 'registration successful' or similar message.",
                "Turn off other call screeners (Google Call Screen, Truecaller assistant): only one app can screen calls.",
                "Your carrier sends an SMS when forwarding turns on. If none came, dial the codes again.",
                "Prepaid plans without call forwarding need a carrier pack that allows it.",
            ).forEach { tip -> Text("• $tip", style = MaterialTheme.typography.bodyMedium, modifier = Modifier.padding(vertical = 3.dp)) }
        }
    }
}

@Composable
private fun DemoScreen(vm: OnboardingViewModel) {
    val context = LocalContext.current
    StepLayout(
        stepIndex = 5,
        title = "Hear your assistant",
        body = "Call your assistant's number yourself. You'll hear exactly what callers hear, and you can ask it to play a delivery agent or a bank.",
        footer = {
            PrimaryButton("Call my assistant", onClick = { vm.demoCall(context) })
            TextButton(onClick = { vm.go(Step.Done) }, modifier = Modifier.fillMaxWidth()) { Text("I'll try it later") }
        },
    ) {
        Box(Modifier.fillMaxWidth().padding(vertical = 24.dp), contentAlignment = Alignment.Center) {
            Icon(Icons.Filled.Call, null, tint = MaterialTheme.colorScheme.primary, modifier = Modifier.size(80.dp))
        }
        TextButton(onClick = { vm.go(Step.Done) }) { Text("Done trying it? Continue") }
    }
}

@Composable
private fun DoneScreen(vm: OnboardingViewModel, onFinished: () -> Unit) {
    StepLayout(
        stepIndex = null,
        title = "You're all set",
        body = "Here's how to get the most out of Pickup.",
        footer = { PrimaryButton("Go to Pickup", onClick = { vm.finish(onFinished) }) },
    ) {
        Benefit(Icons.Filled.NotificationsActive, "Watch calls live", "When your assistant answers, a live notification shows the transcript. Reply or join from there.")
        Benefit(Icons.Filled.Bolt, "Pause in one tap", "Add the 'Call assistant' tile to Quick Settings to pause Pickup in meetings you want to take calls in.")
        Benefit(Icons.Filled.Shield, "Teach it once", "Settings → Instructions: tell it how to handle deliveries, banks, sales calls and more.")
    }
}
