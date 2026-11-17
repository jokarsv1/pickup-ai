package ai.pickup.app.tile

import ai.pickup.app.PickupApp
import ai.pickup.app.data.AppJson
import ai.pickup.app.data.AssistantPatch
import ai.pickup.app.data.ScreeningPolicyDto
import android.service.quicksettings.Tile
import android.service.quicksettings.TileService
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.time.OffsetDateTime

/** Quick Settings tile: tap to pause the assistant for 8 hours (calls ring normally), tap again to resume. */
class AssistantTileService : TileService() {

    override fun onStartListening() {
        super.onStartListening()
        val app = application as PickupApp
        app.graph.scope.launch {
            val active = isActive(app)
            withContext(Dispatchers.Main) { render(active) }
        }
    }

    override fun onClick() {
        super.onClick()
        val app = application as PickupApp
        app.graph.scope.launch {
            val currentlyActive = isActive(app)
            val minutes = if (currentlyActive) 8 * 60 else 0
            runCatching { app.graph.repository.updateAssistant(AssistantPatch(snoozeMinutes = minutes)) }
            val active = isActive(app)
            withContext(Dispatchers.Main) { render(active) }
        }
    }

    private suspend fun isActive(app: PickupApp): Boolean {
        val json = app.graph.store.policyJson.first() ?: return false
        val policy = runCatching { AppJson.decodeFromString(ScreeningPolicyDto.serializer(), json) }.getOrNull() ?: return false
        if (policy.lineStatus != "verified" || policy.screeningMode == "off") return false
        val snoozedUntil = policy.snoozeUntil?.let { runCatching { OffsetDateTime.parse(it).toInstant().toEpochMilli() }.getOrNull() }
        return snoozedUntil == null || snoozedUntil < System.currentTimeMillis()
    }

    private fun render(active: Boolean) {
        val tile = qsTile ?: return
        tile.state = if (active) Tile.STATE_ACTIVE else Tile.STATE_INACTIVE
        tile.subtitle = if (active) "Answering unknown calls" else "Paused"
        tile.updateTile()
    }
}
