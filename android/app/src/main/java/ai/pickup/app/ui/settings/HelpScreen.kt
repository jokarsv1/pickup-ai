package ai.pickup.app.ui.settings

import ai.pickup.app.BuildConfig
import ai.pickup.app.telephony.PhoneUtils
import ai.pickup.app.ui.components.SectionHeader
import ai.pickup.app.ui.theme.LocalPickupColors
import ai.pickup.app.util.Format
import android.Manifest
import android.os.Build
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material.icons.filled.Warning
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilledTonalButton
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle

private data class Check(val title: String, val ok: Boolean, val detail: String)

/**
 * "Check my setup": what's working and what isn't, in plain words, with the fix next to it.
 * "Report a problem" sends the user's note with these same details, so support can answer
 * without a back-and-forth (Equal AI's users said support never replied).
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun HelpScreen(vm: SettingsViewModel, onBack: () -> Unit, onRerunSetup: () -> Unit) {
    val state by vm.state.collectAsStateWithLifecycle()
    val context = LocalContext.current
    LaunchedEffect(Unit) { vm.load() }
    val line = state.line
    val activeSims = PhoneUtils.activeSimCount(context)
    val notifications = Build.VERSION.SDK_INT < Build.VERSION_CODES.TIRAMISU ||
        PhoneUtils.hasPermission(context, Manifest.permission.POST_NOTIFICATIONS)
    val checks = listOf(
        Check(
            "Call screening is allowed",
            PhoneUtils.isScreeningRoleHeld(context),
            "Pickup needs this to send unknown callers to your assistant. Tap Set up again to allow it.",
        ),
        Check("Notifications are on", notifications, "Without them you won't see who's calling. Turn them on in Android settings."),
        Check(
            "Forwarding is confirmed",
            line?.status == "verified",
            if (line == null) "You haven't set up your assistant number yet." else "Run the test call in Set up again.",
        ),
        Check(
            "Calls are reaching your assistant",
            line != null && !line.forwardingProblem,
            "Your carrier may have turned forwarding off. Dial the codes again in Set up again.",
        ),
        Check(
            "Every SIM is set up",
            line == null || line.simCount >= activeSims,
            "This phone has $activeSims SIMs. Set up forwarding on each, or calls to the other SIM always ring.",
        ),
    )
    var message by remember { mutableStateOf("") }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Check my setup") },
                navigationIcon = { IconButton(onClick = onBack) { Icon(Icons.AutoMirrored.Filled.ArrowBack, "Back") } },
            )
        },
    ) { padding ->
        Column(Modifier.fillMaxSize().padding(padding).verticalScroll(rememberScrollState()).padding(16.dp)) {
            state.message?.let { msg ->
                Card(colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.secondaryContainer), modifier = Modifier.fillMaxWidth()) {
                    Row(Modifier.padding(12.dp), verticalAlignment = Alignment.CenterVertically) {
                        Text(msg, Modifier.weight(1f))
                        TextButton(onClick = vm::consumeMessage) { Text("OK") }
                    }
                }
                Spacer(Modifier.height(8.dp))
            }
            Card(colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceContainerLowest), modifier = Modifier.fillMaxWidth()) {
                Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                    checks.forEach { check -> CheckRow(check) }
                    line?.lastForwardedAt?.let {
                        Text(
                            "Last call your assistant answered: ${Format.dateTime(it)}",
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }
                }
            }
            Spacer(Modifier.height(12.dp))
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                FilledTonalButton(onClick = onRerunSetup) { Text("Set up again") }
                OutlinedButton(onClick = { PhoneUtils.openDialer(context, "*#67#") }) { Text("Ask my carrier") }
            }
            Text(
                "\"Ask my carrier\" dials *#67#: your carrier shows where declined calls go. It should be your assistant's number.",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                modifier = Modifier.padding(top = 8.dp),
            )

            SectionHeader("Report a problem")
            Text(
                "Tell us what happened. Your setup details above are sent with it, so you don't have to explain them.",
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            Spacer(Modifier.height(8.dp))
            OutlinedTextField(
                value = message,
                onValueChange = { message = it.take(2000) },
                placeholder = { Text("For example: a call from my bank didn't reach the assistant at 3 PM") },
                modifier = Modifier.fillMaxWidth(),
                minLines = 3,
            )
            Spacer(Modifier.height(8.dp))
            FilledTonalButton(
                onClick = {
                    val diagnostics = checks.associate { it.title to it.ok.toString() } + mapOf(
                        "app_version" to BuildConfig.VERSION_NAME,
                        "android" to "${Build.VERSION.RELEASE} (API ${Build.VERSION.SDK_INT})",
                        "device" to "${Build.MANUFACTURER} ${Build.MODEL}",
                        "carrier" to (PhoneUtils.carrierName(context) ?: "unknown"),
                        "active_sims" to activeSims.toString(),
                    )
                    vm.reportProblem(message.trim(), diagnostics) { message = "" }
                },
                enabled = message.trim().length >= 3 && !state.saving,
            ) { Text("Send") }
        }
    }
}

@Composable
private fun CheckRow(check: Check) {
    val colors = LocalPickupColors.current
    Row(verticalAlignment = Alignment.Top) {
        Icon(
            if (check.ok) Icons.Filled.CheckCircle else Icons.Filled.Warning,
            if (check.ok) "OK" else "Needs attention",
            tint = if (check.ok) colors.success else colors.warning,
        )
        Spacer(Modifier.width(12.dp))
        Column {
            Text(check.title, style = MaterialTheme.typography.titleSmall)
            if (!check.ok) Text(check.detail, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
    }
}
