package ai.pickup.app.data

import android.util.Log
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharedFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.launch
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.jsonObject
import okhttp3.Request
import okhttp3.Response
import okhttp3.WebSocket
import okhttp3.WebSocketListener

/**
 * Live events while the app is open (call started, transcript lines, caller intent, summary).
 * When the app is in the background, the same events arrive as push messages instead.
 */
class LiveEvents(private val api: ApiClient, private val scope: CoroutineScope) {
    private val _events = MutableSharedFlow<JsonObject>(extraBufferCapacity = 128)
    val events: SharedFlow<JsonObject> = _events

    private val _connected = MutableStateFlow(false)
    val connected: StateFlow<Boolean> = _connected

    private var socket: WebSocket? = null
    private var job: Job? = null
    private var wanted = false
    private var attempt = 0

    fun start() {
        wanted = true
        if (job?.isActive == true || socket != null) return
        job = scope.launch { open() }
    }

    fun stop() {
        wanted = false
        job?.cancel()
        socket?.close(1000, "background")
        socket = null
        _connected.value = false
    }

    private suspend fun open() {
        val ticket = try {
            api.postEmpty<TicketDto>("/v1/stream/ticket").ticket
        } catch (e: Exception) {
            scheduleReconnect()
            return
        }
        val wsUrl = api.baseUrl().replaceFirst("https://", "wss://").replaceFirst("http://", "ws://") + "/v1/stream?ticket=$ticket"
        val request = Request.Builder().url(wsUrl).build()
        socket = api.http.newWebSocket(request, object : WebSocketListener() {
            override fun onOpen(webSocket: WebSocket, response: Response) {
                attempt = 0
                _connected.value = true
            }

            override fun onMessage(webSocket: WebSocket, text: String) {
                if (text == "pong") return
                runCatching { AppJson.parseToJsonElement(text).jsonObject }.onSuccess { _events.tryEmit(it) }
            }

            override fun onClosed(webSocket: WebSocket, code: Int, reason: String) {
                socket = null
                _connected.value = false
                if (wanted) scope.launch { scheduleReconnect() }
            }

            override fun onFailure(webSocket: WebSocket, t: Throwable, response: Response?) {
                Log.w("LiveEvents", "Stream failed: ${t.message}")
                socket = null
                _connected.value = false
                if (wanted) scope.launch { scheduleReconnect() }
            }
        })
    }

    private suspend fun scheduleReconnect() {
        if (!wanted) return
        attempt += 1
        delay((1000L shl minOf(attempt, 5)).coerceAtMost(30_000L))
        if (wanted && socket == null) open()
    }
}
