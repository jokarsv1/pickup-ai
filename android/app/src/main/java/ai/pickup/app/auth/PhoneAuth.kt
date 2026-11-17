package ai.pickup.app.auth

import android.app.Activity
import com.google.android.gms.tasks.Task
import com.google.firebase.FirebaseException
import com.google.firebase.auth.FirebaseAuth
import com.google.firebase.auth.PhoneAuthCredential
import com.google.firebase.auth.PhoneAuthOptions
import com.google.firebase.auth.PhoneAuthProvider
import kotlinx.coroutines.suspendCancellableCoroutine
import java.util.concurrent.TimeUnit
import kotlin.coroutines.resume
import kotlin.coroutines.resumeWithException

/** Firebase phone sign-in. Android can read the SMS code automatically on most phones. */
class PhoneAuth {
    sealed interface Event {
        data class CodeSent(val verificationId: String, val resendToken: PhoneAuthProvider.ForceResendingToken) : Event
        data class AutoVerified(val idToken: String) : Event
        data class Failed(val message: String) : Event
    }

    private val auth: FirebaseAuth get() = FirebaseAuth.getInstance()

    fun sendCode(activity: Activity, phoneE164: String, resendToken: PhoneAuthProvider.ForceResendingToken?, onEvent: (Event) -> Unit) {
        val callbacks = object : PhoneAuthProvider.OnVerificationStateChangedCallbacks() {
            override fun onVerificationCompleted(credential: PhoneAuthCredential) {
                auth.signInWithCredential(credential)
                    .continueWithTask { it.result.user!!.getIdToken(true) }
                    .addOnSuccessListener { result -> result.token?.let { onEvent(Event.AutoVerified(it)) } }
                    .addOnFailureListener { onEvent(Event.Failed(it.message ?: "Couldn't verify your number")) }
            }

            override fun onVerificationFailed(e: FirebaseException) {
                onEvent(Event.Failed(e.message ?: "Couldn't send the code"))
            }

            override fun onCodeSent(verificationId: String, token: PhoneAuthProvider.ForceResendingToken) {
                onEvent(Event.CodeSent(verificationId, token))
            }
        }
        val builder = PhoneAuthOptions.newBuilder(auth)
            .setPhoneNumber(phoneE164)
            .setTimeout(60L, TimeUnit.SECONDS)
            .setActivity(activity)
            .setCallbacks(callbacks)
        if (resendToken != null) builder.setForceResendingToken(resendToken)
        PhoneAuthProvider.verifyPhoneNumber(builder.build())
    }

    /** Exchanges the typed code for a Firebase ID token the backend can verify. */
    suspend fun verifyCode(verificationId: String, code: String): String {
        val credential = PhoneAuthProvider.getCredential(verificationId, code)
        val result = auth.signInWithCredential(credential).await()
        val token = result.user?.getIdToken(true)?.await()?.token
        return token ?: throw IllegalStateException("Couldn't verify your number")
    }

    fun signOut() = runCatching { auth.signOut() }
}

suspend fun <T> Task<T>.await(): T = suspendCancellableCoroutine { cont ->
    addOnSuccessListener { if (cont.isActive) cont.resume(it) }
    addOnFailureListener { if (cont.isActive) cont.resumeWithException(it) }
    addOnCanceledListener { cont.cancel() }
}
