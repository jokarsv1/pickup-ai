package ai.pickup.app.notify

import ai.pickup.app.PickupApp
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.widget.Toast
import androidx.core.app.RemoteInput
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

/** Reply, Join and End straight from the notification, without opening the app. */
class NotificationActionReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        val callId = intent.getStringExtra(CallNotifications.EXTRA_CALL_ID) ?: return
        val app = context.applicationContext as PickupApp
        val pending = goAsync()
        app.graph.scope.launch {
            val message = try {
                when (intent.action) {
                    ACTION_REPLY -> {
                        val text = RemoteInput.getResultsFromIntent(intent)?.getCharSequence(CallNotifications.KEY_REPLY)?.toString()?.trim()
                        if (text.isNullOrEmpty()) null else {
                            app.graph.repository.say(callId, text)
                            "Sent: $text"
                        }
                    }
                    ACTION_JOIN -> {
                        app.graph.repository.takeOver(callId)
                        "Your phone will ring. Answer it to talk to the caller."
                    }
                    ACTION_END -> {
                        app.graph.repository.endCall(callId)
                        "Wrapping up the call"
                    }
                    else -> null
                }
            } catch (e: Exception) {
                e.message ?: "That didn't work"
            }
            if (message != null) {
                withContext(Dispatchers.Main) { Toast.makeText(context, message, Toast.LENGTH_SHORT).show() }
            }
            pending.finish()
        }
    }

    companion object {
        const val ACTION_REPLY = "ai.pickup.app.REPLY"
        const val ACTION_JOIN = "ai.pickup.app.JOIN"
        const val ACTION_END = "ai.pickup.app.END"
    }
}
