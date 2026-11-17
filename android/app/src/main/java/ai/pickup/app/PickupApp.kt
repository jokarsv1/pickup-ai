package ai.pickup.app

import ai.pickup.app.data.ApiClient
import ai.pickup.app.data.LiveEvents
import ai.pickup.app.data.Repository
import ai.pickup.app.data.SessionStore
import ai.pickup.app.notify.CallNotifications
import android.app.Application
import androidx.lifecycle.DefaultLifecycleObserver
import androidx.lifecycle.LifecycleOwner
import androidx.lifecycle.ProcessLifecycleOwner
import com.google.firebase.FirebaseApp
import com.google.firebase.messaging.FirebaseMessaging
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.launch

/** Manual dependency graph: small enough not to need a DI framework. */
class AppGraph(app: Application) {
    val scope = CoroutineScope(SupervisorJob() + Dispatchers.Default)
    val store = SessionStore(app)
    val api = ApiClient(store)
    val repository = Repository(api, store)
    val live = LiveEvents(api, scope)
    val firebaseAvailable: Boolean = FirebaseApp.getApps(app).isNotEmpty()
}

class PickupApp : Application() {
    lateinit var graph: AppGraph
        private set

    override fun onCreate() {
        super.onCreate()
        graph = AppGraph(this)
        CallNotifications.createChannels(this)
        graph.api.onSignedOut = { graph.store.clearSession() }

        // Live events over WebSocket while the app is visible; push messages otherwise.
        ProcessLifecycleOwner.get().lifecycle.addObserver(object : DefaultLifecycleObserver {
            override fun onStart(owner: LifecycleOwner) {
                graph.scope.launch {
                    if (!graph.store.access().isNullOrBlank()) {
                        graph.live.start()
                        graph.repository.refreshPolicy()
                    }
                }
            }

            override fun onStop(owner: LifecycleOwner) = graph.live.stop()
        })

        if (graph.firebaseAvailable) {
            FirebaseMessaging.getInstance().token.addOnSuccessListener { token ->
                graph.scope.launch {
                    graph.store.saveFcmToken(token)
                    runCatching { graph.repository.registerDevice(token) }
                }
            }
        }
    }
}
