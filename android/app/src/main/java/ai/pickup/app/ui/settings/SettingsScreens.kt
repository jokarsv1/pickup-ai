package ai.pickup.app.ui.settings

import ai.pickup.app.AppGraph
import ai.pickup.app.BuildConfig
import ai.pickup.app.billing.BillingManager
import ai.pickup.app.data.AssistantDto
import ai.pickup.app.data.AssistantOptions
import ai.pickup.app.data.AssistantPatch
import ai.pickup.app.data.Entitlement
import ai.pickup.app.data.LineDto
import ai.pickup.app.data.LinePatch
import ai.pickup.app.data.RuleDto
import ai.pickup.app.data.UserDto
import ai.pickup.app.telephony.PhoneUtils
import ai.pickup.app.ui.components.SectionHeader
import ai.pickup.app.ui.onboarding.findActivity
import ai.pickup.app.util.Format
import android.content.Context
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.selection.selectable
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilledTonalButton
import androidx.compose.material3.FilterChip
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.ListItem
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.RadioButton
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Slider
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableFloatStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.unit.dp
import androidx.lifecycle.ViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.async
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

data class SettingsState(
    val user: UserDto? = null,
    val assistant: AssistantDto? = null,
    val line: LineDto? = null,
    val entitlement: Entitlement? = null,
    val options: AssistantOptions? = null,
    val rules: List<RuleDto> = emptyList(),
    val saving: Boolean = false,
    val message: String? = null,
)

class SettingsViewModel(private val graph: AppGraph) : ViewModel() {
    private val repo = graph.repository
    private val _state = MutableStateFlow(SettingsState())
    val state: StateFlow<SettingsState> = _state

    init {
        load()
        viewModelScope.launch { repo.user.collect { u -> _state.update { it.copy(user = u) } } }
    }

    fun load() = viewModelScope.launch {
        val assistant = async { runCatching { repo.assistant() }.getOrNull() }
        val line = async { runCatching { repo.currentLine() }.getOrNull() }
        val ent = async { runCatching { repo.entitlement() }.getOrNull() }
        val options = async { runCatching { repo.options() }.getOrNull() }
        val rules = async { runCatching { repo.rules() }.getOrDefault(emptyList()) }
        _state.update {
            it.copy(assistant = assistant.await(), line = line.await(), entitlement = ent.await(), options = options.await(), rules = rules.await())
        }
    }

    fun update(patch: AssistantPatch, message: String? = null) = viewModelScope.launch {
        _state.update { it.copy(saving = true) }
        runCatching { repo.updateAssistant(patch) }
            .onSuccess { a -> _state.update { it.copy(assistant = a, saving = false, message = message) } }
            .onFailure { e -> _state.update { it.copy(saving = false, message = e.message) } }
    }

    fun setRingSeconds(seconds: Int) = viewModelScope.launch {
        val line = _state.value.line ?: return@launch
        runCatching { repo.updateLine(line.id, LinePatch(ringSeconds = seconds)) }.onSuccess { l -> _state.update { it.copy(line = l) } }
    }

    fun setCategoryRule(category: String, action: String) = viewModelScope.launch {
        val others = _state.value.rules.filterNot { it.matchType == "category" && it.matchValue == category }
        val next = if (action == "handle") others else others + RuleDto(matchType = "category", matchValue = category, action = action)
        runCatching { repo.saveRules(next) }.onSuccess { saved -> _state.update { it.copy(rules = saved) } }
    }

    fun removeRule(rule: RuleDto) = viewModelScope.launch {
        val next = _state.value.rules.filterNot { it.matchType == rule.matchType && it.matchValue == rule.matchValue }
        runCatching { repo.saveRules(next) }.onSuccess { saved -> _state.update { it.copy(rules = saved) } }
    }

    fun rename(name: String) = viewModelScope.launch {
        runCatching { repo.updateMe(ai.pickup.app.data.MePatch(name = name)) }.onSuccess { _state.update { it.copy(message = "Saved") } }
    }

    fun testForwarding() = viewModelScope.launch {
        val line = _state.value.line ?: return@launch
        runCatching { repo.startVerification(line.id) }
            .onSuccess { _state.update { it.copy(message = "Calling you now. Leave it: Pickup will decline it and it should reach your assistant.") } }
            .onFailure { e -> _state.update { it.copy(message = e.message) } }
    }

    fun signOut(onDone: () -> Unit) = viewModelScope.launch {
        graph.live.stop()
        repo.signOut()
        onDone()
    }

    fun deleteAccount(onDone: () -> Unit) = viewModelScope.launch {
        runCatching { repo.deleteAccount() }
            .onSuccess { graph.live.stop(); onDone() }
            .onFailure { e -> _state.update { it.copy(message = e.message) } }
    }

    fun purchased(productId: String, token: String) = viewModelScope.launch {
        runCatching { repo.verifyPurchase(productId, token) }.onSuccess { e -> _state.update { it.copy(entitlement = e) } }
    }

    fun consumeMessage() = _state.update { it.copy(message = null) }
}

@OptIn(ExperimentalMaterial3Api::class, ExperimentalLayoutApi::class)
@Composable
fun SettingsScreen(
    vm: SettingsViewModel,
    onOpenInstructions: () -> Unit,
    onOpenPlan: () -> Unit,
    onRerunSetup: () -> Unit,
    onSignedOut: () -> Unit,
) {
    val state by vm.state.collectAsStateWithLifecycle()
    val context = LocalContext.current
    val assistant = state.assistant
    var confirm by remember { mutableStateOf<String?>(null) } // "signout" | "delete"
    var editingName by remember { mutableStateOf(false) }
    LaunchedEffect(Unit) { vm.load() }

    Column(Modifier.fillMaxSize()) {
        TopAppBar(title = { Text("Settings") }, colors = TopAppBarDefaults.topAppBarColors(containerColor = MaterialTheme.colorScheme.background))
        Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(horizontal = 16.dp)) {
            state.message?.let { msg ->
                Card(colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.secondaryContainer), modifier = Modifier.fillMaxWidth()) {
                    Row(Modifier.padding(12.dp), verticalAlignment = Alignment.CenterVertically) {
                        Text(msg, Modifier.weight(1f))
                        TextButton(onClick = vm::consumeMessage) { Text("OK") }
                    }
                }
            }
            Card(colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceContainerLowest), modifier = Modifier.fillMaxWidth().padding(top = 8.dp)) {
                ListItem(
                    headlineContent = { Text(state.user?.name ?: "Your name") },
                    supportingContent = { Text(Format.phone(state.user?.phone)) },
                    trailingContent = { TextButton(onClick = { editingName = true }) { Text("Edit") } },
                )
                HorizontalDivider()
                ListItem(
                    headlineContent = { Text(planTitle(state.entitlement)) },
                    supportingContent = { Text(planSubtitle(state.entitlement)) },
                    trailingContent = { TextButton(onClick = onOpenPlan) { Text("Plans") } },
                )
            }

            SectionHeader("How Pickup answers")
            val mode = assistant?.screeningMode ?: "assistant_first"
            ModeOption("Assistant answers unknown callers", "Saved contacts ring you. Everyone else talks to your assistant first.", mode == "assistant_first") {
                vm.update(AssistantPatch(screeningMode = "assistant_first"))
            }
            ModeOption("Ring me first", "Your phone rings for ${state.line?.ringSeconds ?: 20} seconds. Missed calls go to your assistant.", mode == "ring_first") {
                vm.update(AssistantPatch(screeningMode = "ring_first"))
            }
            ModeOption("Off", "Every call rings. Calls you decline still reach your assistant.", mode == "off") {
                vm.update(AssistantPatch(screeningMode = "off"))
            }
            state.line?.let { line -> RingTimeControl(context, line, vm) }
            SwitchRow("Screen saved contacts too", "Even people in your contacts talk to your assistant first.", assistant?.screenContacts == true) {
                vm.update(AssistantPatch(screenContacts = it))
            }
            SwitchRow("Connect urgent calls", "Your assistant puts genuine emergencies straight through to you.", assistant?.urgentPassthrough != false) {
                vm.update(AssistantPatch(urgentPassthrough = it))
            }
            SwitchRow("Record calls", "Recordings stay ${assistant?.retentionDays ?: 90} days, then they're deleted. Callers are told.", assistant?.recordCalls != false) {
                vm.update(AssistantPatch(recordCalls = it))
            }

            SectionHeader("Your assistant")
            ListItem(
                headlineContent = { Text("Instructions") },
                supportingContent = { Text("How to handle deliveries, banks, sales calls and more") },
                modifier = Modifier.clickable(onClick = onOpenInstructions),
            )
            Text("Voice", style = MaterialTheme.typography.titleSmall, modifier = Modifier.padding(start = 16.dp, top = 8.dp))
            FlowRow(Modifier.padding(horizontal = 16.dp), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                state.options?.voices?.forEach { v ->
                    FilterChip(selected = assistant?.voice == v.id, onClick = { vm.update(AssistantPatch(voice = v.id)) }, label = { Text(v.label) })
                }
            }
            Text("Languages", style = MaterialTheme.typography.titleSmall, modifier = Modifier.padding(start = 16.dp, top = 12.dp))
            FlowRow(Modifier.padding(horizontal = 16.dp), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                val selected = assistant?.languages.orEmpty()
                state.options?.languages?.forEach { (code, label) ->
                    FilterChip(
                        selected = code in selected,
                        onClick = {
                            val next = if (code in selected) selected - code else (selected + code).take(3)
                            vm.update(AssistantPatch(languages = next.ifEmpty { listOf("en-IN") }))
                        },
                        label = { Text(label) },
                    )
                }
            }

            SectionHeader("Call forwarding")
            val line = state.line
            ListItem(
                headlineContent = { Text(line?.assistantNumberDisplay ?: "Not set up") },
                supportingContent = {
                    Text(
                        when (line?.status) {
                            "verified" -> "Working. Last forwarded call: ${Format.dateTime(line.lastForwardedAt).ifBlank { "none yet" }}"
                            null -> "Set up your assistant number"
                            else -> "Not confirmed yet"
                        }
                    )
                },
                leadingContent = { if (line?.status == "verified") Icon(Icons.Filled.CheckCircle, null, tint = MaterialTheme.colorScheme.primary) },
            )
            Row(Modifier.padding(horizontal = 16.dp), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                FilledTonalButton(onClick = onRerunSetup) { Text("Set up again") }
                if (line != null) OutlinedButton(onClick = { vm.testForwarding() }) { Text("Test") }
                if (line != null) OutlinedButton(onClick = { PhoneUtils.openDialer(context, line.deactivationCode) }) { Text("Turn off") }
            }

            SectionHeader("Account")
            ListItem(headlineContent = { Text("Sign out") }, modifier = Modifier.clickable { confirm = "signout" })
            ListItem(
                headlineContent = { Text("Delete account", color = MaterialTheme.colorScheme.error) },
                supportingContent = { Text("Deletes your calls, recordings and settings") },
                modifier = Modifier.clickable { confirm = "delete" },
            )
            Text(
                "Pickup ${BuildConfig.VERSION_NAME}",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                modifier = Modifier.padding(16.dp),
            )
        }
    }

    if (editingName) {
        var name by remember { mutableStateOf(state.user?.name ?: "") }
        AlertDialog(
            onDismissRequest = { editingName = false },
            title = { Text("Your name") },
            text = { OutlinedTextField(value = name, onValueChange = { name = it.take(60) }, singleLine = true) },
            confirmButton = { TextButton(onClick = { vm.rename(name.trim()); editingName = false }) { Text("Save") } },
            dismissButton = { TextButton(onClick = { editingName = false }) { Text("Cancel") } },
        )
    }

    confirm?.let { kind ->
        val deleting = kind == "delete"
        AlertDialog(
            onDismissRequest = { confirm = null },
            title = { Text(if (deleting) "Delete your account?" else "Sign out?") },
            text = {
                Column {
                    Text("First turn off call forwarding, or missed calls will keep going to an assistant that isn't listening.")
                    Spacer(Modifier.height(12.dp))
                    OutlinedButton(onClick = { PhoneUtils.openDialer(context, state.line?.deactivationCode ?: "##004#") }) {
                        Text("Turn off forwarding (${state.line?.deactivationCode ?: "##004#"})")
                    }
                    if (deleting) {
                        Spacer(Modifier.height(12.dp))
                        Text("This permanently deletes your calls, recordings and settings.", color = MaterialTheme.colorScheme.error)
                    }
                }
            },
            confirmButton = {
                TextButton(onClick = {
                    confirm = null
                    if (deleting) vm.deleteAccount(onSignedOut) else vm.signOut(onSignedOut)
                }) { Text(if (deleting) "Delete" else "Sign out", color = MaterialTheme.colorScheme.error) }
            },
            dismissButton = { TextButton(onClick = { confirm = null }) { Text("Cancel") } },
        )
    }
}

private fun planTitle(ent: Entitlement?): String = when (ent?.level) {
    "pro" -> "Pickup Pro"
    "trial" -> "Pro trial"
    "free" -> "Free plan"
    "limited" -> "Free plan (calls used up)"
    else -> "Plan"
}

private fun planSubtitle(ent: Entitlement?): String = when (ent?.level) {
    "pro" -> Format.until(ent?.planExpiresAt)?.let { "Renews in $it" } ?: "Active"
    "trial" -> Format.until(ent?.trialEndsAt)?.let { "$it left in your trial" } ?: "Trial"
    "free", "limited" -> "${ent?.callsLeftThisMonth ?: 0} of your free calls left this month"
    else -> ""
}

@Composable
private fun ModeOption(title: String, body: String, selected: Boolean, onSelect: () -> Unit) {
    Row(
        Modifier.fillMaxWidth().selectable(selected = selected, onClick = onSelect, role = Role.RadioButton).padding(vertical = 8.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        RadioButton(selected = selected, onClick = null)
        Spacer(Modifier.width(12.dp))
        Column {
            Text(title, style = MaterialTheme.typography.titleMedium)
            Text(body, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
    }
}

@Composable
private fun SwitchRow(title: String, body: String, checked: Boolean, onChange: (Boolean) -> Unit) {
    Row(Modifier.fillMaxWidth().padding(vertical = 8.dp), verticalAlignment = Alignment.CenterVertically) {
        Column(Modifier.weight(1f)) {
            Text(title, style = MaterialTheme.typography.titleMedium)
            Text(body, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
        Spacer(Modifier.width(12.dp))
        Switch(checked = checked, onCheckedChange = onChange)
    }
}

@Composable
private fun RingTimeControl(context: Context, line: LineDto, vm: SettingsViewModel) {
    var seconds by remember(line.ringSeconds) { mutableFloatStateOf(line.ringSeconds.toFloat()) }
    Column(Modifier.padding(vertical = 4.dp)) {
        Text("Ring for ${seconds.toInt()} seconds before forwarding", style = MaterialTheme.typography.titleSmall)
        Slider(
            value = seconds,
            onValueChange = { seconds = it },
            valueRange = 5f..30f,
            steps = 4,
            onValueChangeFinished = { vm.setRingSeconds(seconds.toInt()) },
        )
        val code = line.activationCodes.firstOrNull { it.key == "no_answer" }?.code
        if (code != null && seconds.toInt() != line.ringSeconds) {
            Text("Saving…", style = MaterialTheme.typography.bodySmall)
        } else if (code != null) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text("Your carrier applies this when you dial ", style = MaterialTheme.typography.bodySmall)
                Text(code, style = MaterialTheme.typography.bodySmall, fontFamily = FontFamily.Monospace)
                TextButton(onClick = { PhoneUtils.openDialer(context, code) }) { Text("Dial") }
            }
        }
    }
}

// ------------------------------------------------------------------------------------- Instructions

private val CATEGORY_ACTIONS = listOf("handle" to "Handle it", "decline" to "Turn away", "ring_me" to "I'll call back", "connect" to "Connect me")

@OptIn(ExperimentalMaterial3Api::class, ExperimentalLayoutApi::class)
@Composable
fun InstructionsScreen(vm: SettingsViewModel, onBack: () -> Unit) {
    val state by vm.state.collectAsStateWithLifecycle()
    val assistant = state.assistant
    var custom by remember(assistant?.instructions) { mutableStateOf(assistant?.instructions ?: "") }
    var delivery by remember(assistant?.deliveryNote) { mutableStateOf(assistant?.deliveryNote ?: "") }
    var greeting by remember(assistant?.greeting) { mutableStateOf(assistant?.greeting ?: "") }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Instructions") },
                navigationIcon = { IconButton(onClick = onBack) { Icon(Icons.AutoMirrored.Filled.ArrowBack, "Back") } },
            )
        },
    ) { padding ->
        Column(Modifier.fillMaxSize().padding(padding).verticalScroll(rememberScrollState()).padding(horizontal = 16.dp)) {
            Text(
                "Your assistant follows these on every call. Plain words work best: 'If it's my landlord, say I'll call after 6'.",
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            SectionHeader("Ready-made packs")
            state.options?.packs?.forEach { pack ->
                val on = assistant?.packIds?.contains(pack.id) == true
                SwitchRow(pack.title, pack.subtitle, on) { enabled ->
                    val current = assistant?.packIds.orEmpty()
                    vm.update(AssistantPatch(packIds = if (enabled) current + pack.id else current - pack.id))
                }
            }
            SectionHeader("In your words")
            OutlinedTextField(
                value = custom,
                onValueChange = { custom = it.take(4000) },
                placeholder = { Text("e.g. If someone from my kid's school calls, connect them to me.") },
                modifier = Modifier.fillMaxWidth(),
                minLines = 4,
            )
            Spacer(Modifier.height(12.dp))
            OutlinedTextField(
                value = delivery,
                onValueChange = { delivery = it.take(300) },
                label = { Text("Delivery note") },
                placeholder = { Text("e.g. Leave parcels with the security guard at Gate 2") },
                modifier = Modifier.fillMaxWidth(),
            )
            Spacer(Modifier.height(12.dp))
            OutlinedTextField(
                value = greeting,
                onValueChange = { greeting = it.take(300) },
                label = { Text("Custom greeting (optional)") },
                placeholder = { Text("Hi, you've reached Asha's assistant. Who's calling?") },
                modifier = Modifier.fillMaxWidth(),
            )
            Spacer(Modifier.height(12.dp))
            FilledTonalButton(
                onClick = { vm.update(AssistantPatch(instructions = custom, deliveryNote = delivery, greeting = greeting.ifBlank { null }), message = "Saved. Your assistant will use this on the next call.") },
                enabled = !state.saving,
            ) { Text("Save") }

            SectionHeader("By type of call")
            state.options?.categories?.filterKeys { it != "other" }?.forEach { (category, label) ->
                val current = state.rules.firstOrNull { it.matchType == "category" && it.matchValue == category }?.action ?: "handle"
                Text(label, style = MaterialTheme.typography.titleSmall, modifier = Modifier.padding(top = 10.dp))
                FlowRow(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                    CATEGORY_ACTIONS.forEach { (action, actionLabel) ->
                        FilterChip(selected = current == action, onClick = { vm.setCategoryRule(category, action) }, label = { Text(actionLabel) })
                    }
                }
            }
            val numberRules = state.rules.filter { it.matchType == "number" }
            if (numberRules.isNotEmpty()) {
                SectionHeader("Specific numbers")
                numberRules.forEach { rule ->
                    ListItem(
                        headlineContent = { Text(rule.matchValue) },
                        supportingContent = { Text(CATEGORY_ACTIONS.firstOrNull { it.first == rule.action }?.second ?: rule.action) },
                        trailingContent = { TextButton(onClick = { vm.removeRule(rule) }) { Text("Remove") } },
                    )
                }
            }
            Spacer(Modifier.height(32.dp))
        }
    }
}

// ------------------------------------------------------------------------------------- Plans

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun PlanScreen(vm: SettingsViewModel, productIds: List<String>, onBack: () -> Unit) {
    val state by vm.state.collectAsStateWithLifecycle()
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    val billing = remember { BillingManager(context.applicationContext, scope) { productId, token -> vm.purchased(productId, token).join() } }
    val products by billing.products.collectAsStateWithLifecycle()
    val status by billing.status.collectAsStateWithLifecycle()
    LaunchedEffect(productIds) { billing.loadProducts(productIds) }
    DisposableEffect(Unit) { onDispose { billing.close() } }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Pickup Pro") },
                navigationIcon = { IconButton(onClick = onBack) { Icon(Icons.AutoMirrored.Filled.ArrowBack, "Back") } },
            )
        },
    ) { padding ->
        Column(Modifier.fillMaxSize().padding(padding).verticalScroll(rememberScrollState()).padding(16.dp)) {
            Text(planTitle(state.entitlement), style = MaterialTheme.typography.headlineSmall)
            Text(planSubtitle(state.entitlement), color = MaterialTheme.colorScheme.onSurfaceVariant)
            SectionHeader("Pro includes")
            listOf(
                "Unlimited calls answered by your assistant",
                "Live transcript, one-tap replies and Join call",
                "Your assistant makes calls for you",
                "Call recordings",
                "Every Indian language your assistant speaks",
            ).forEach { line ->
                Row(Modifier.padding(vertical = 4.dp), verticalAlignment = Alignment.CenterVertically) {
                    Icon(Icons.Filled.CheckCircle, null, tint = MaterialTheme.colorScheme.primary)
                    Spacer(Modifier.width(10.dp))
                    Text(line)
                }
            }
            Spacer(Modifier.height(16.dp))
            products.forEach { product ->
                Card(colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceContainerLowest), modifier = Modifier.fillMaxWidth().padding(vertical = 6.dp)) {
                    Row(Modifier.padding(16.dp), verticalAlignment = Alignment.CenterVertically) {
                        Column(Modifier.weight(1f)) {
                            Text(product.title, style = MaterialTheme.typography.titleMedium)
                            Text(product.price, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        }
                        FilledTonalButton(onClick = { context.findActivity()?.let { billing.buy(it, product) } }) { Text("Choose") }
                    }
                }
            }
            if (products.isEmpty()) {
                Text(status ?: "Loading plans…", color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
            status?.takeIf { products.isNotEmpty() }?.let { Text(it, color = MaterialTheme.colorScheme.primary, modifier = Modifier.padding(top = 8.dp)) }
        }
    }
}
