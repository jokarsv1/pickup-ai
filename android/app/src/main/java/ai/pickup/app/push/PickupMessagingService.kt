package ai.pickup.app.push

import ai.pickup.app.PickupApp
import ai.pickup.app.data.AppJson
import ai.pickup.app.notify.CallNotifications
import com.google.firebase.messaging.FirebaseMessagingService
import com.google.firebase.messaging.RemoteMessage
import kotlinx.coroutines.launch
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.contentOrNull
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive

/** Data-only pushes from the backend; the app draws the notification itself. */
class PickupMessagingService : FirebaseMessagingService() {

    override fun onNewToken(token: String) {
        val app = application as PickupApp
        app.graph.scope.launch {
            app.graph.store.saveFcmToken(token)
            runCatching { app.graph.repository.registerDevice(token) }
        }
    }

    override fun onMessageReceived(message: RemoteMessage) {
        val data = message.data
        val callId = data["call_id"]
        when (data["type"]) {
            "call.started" -> if (callId != null) {
                CallNotifications.showLive(
                    this, callId, data["caller_display"] ?: "Incoming call", null, emptyList(), emptyList(),
                    statusText = "Your assistant picked up",
                )
            }
            "call.live" -> if (callId != null) {
                val lines = parseArray(data["lines"]).mapNotNull { element ->
                    runCatching {
                        val obj = element.jsonObject
                        CallNotifications.Line(obj["s"]?.jsonPrimitive?.contentOrNull ?: "assistant", obj["t"]?.jsonPrimitive?.contentOrNull ?: "")
                    }.getOrNull()
                }
                val replies = parseArray(data["replies"]).mapNotNull { runCatching { it.jsonPrimitive.contentOrNull }.getOrNull() }
                CallNotifications.showLive(this, callId, data["title"] ?: "Live call", data["reason"], lines, replies)
            }
            "takeover.ringing" -> if (callId != null) {
                CallNotifications.showLive(
                    this, callId, "Connecting you", null, emptyList(), emptyList(), liveControls = false,
                    statusText = "Your phone will ring. Answer it to talk to the caller.",
                )
            }
            "summary" -> if (callId != null) {
                val title = data["title"] ?: "Call summary"
                val summary = data["summary"] ?: "Your assistant handled a call."
                val isSpam = data["is_spam"] == "true"
                val callback = parseArray(data["actions"]).firstNotNullOfOrNull { element ->
                    runCatching {
                        val obj = element.jsonObject
                        if (obj["type"]?.jsonPrimitive?.contentOrNull == "call_back") obj["payload"]?.jsonObject?.get("number")?.jsonPrimitive?.contentOrNull else null
                    }.getOrNull()
                }
                CallNotifications.showSummary(this, callId, title, summary, callback, isSpam)
            }
            "line.verified" -> CallNotifications.showSetup(this, "Your assistant is live", "Unknown callers will now reach Pickup.")
        }
        if (data["type"] in setOf("line.verified", "summary")) {
            val app = application as PickupApp
            app.graph.scope.launch { app.graph.repository.refreshPolicy() }
        }
    }

    private fun parseArray(raw: String?): JsonArray =
        raw?.let { runCatching { AppJson.parseToJsonElement(it).jsonArray }.getOrNull() } ?: JsonArray(emptyList())
}
