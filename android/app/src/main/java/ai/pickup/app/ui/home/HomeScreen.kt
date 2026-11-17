package ai.pickup.app.ui.home

import ai.pickup.app.AppGraph
import ai.pickup.app.data.AssistantDto
import ai.pickup.app.data.AssistantPatch
import ai.pickup.app.data.CallSummary
import ai.pickup.app.data.Entitlement
import ai.pickup.app.data.LineDto
import ai.pickup.app.data.Stats
import ai.pickup.app.data.UserDto
import ai.pickup.app.telephony.PhoneUtils
import ai.pickup.app.ui.components.CategoryAvatar
import ai.pickup.app.ui.components.EmptyState
import ai.pickup.app.ui.components.LiveDot
import ai.pickup.app.ui.components.Pill
import ai.pickup.app.ui.components.SectionHeader
import ai.pickup.app.ui.components.StatTile
import ai.pickup.app.ui.theme.LocalPickupColors
import ai.pickup.app.util.Format
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Call
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.Search
import androidx.compose.material3.AssistChip
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilledTonalButton
import androidx.compose.material3.FilterChip
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.material3.pulltorefresh.PullToRefreshBox
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.lifecycle.ViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.Job
import kotlinx.coroutines.async
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import kotlinx.serialization.json.contentOrNull
import kotlinx.serialization.json.jsonPrimitive
import java.time.LocalTime

data class HomeState(
    val user: UserDto? = null,
    val line: LineDto? = null,
    val assistant: AssistantDto? = null,
    val entitlement: Entitlement? = null,
    val stats: Stats? = null,
    val live: List<CallSummary> = emptyList(),
    val calls: List<CallSummary> = emptyList(),
    val nextCursor: String? = null,
    val filter: String? = null,
    val query: String = "",
    val searching: Boolean = false,
    val refreshing: Boolean = false,
    val loaded: Boolean = false,
    val error: String? = null,
)

class HomeViewModel(private val graph: AppGraph) : ViewModel() {
    private val repo = graph.repository
    private val _state = MutableStateFlow(HomeState())
    val state: StateFlow<HomeState> = _state
    private var reloadJob: Job? = null

    init {
        refresh()
        viewModelScope.launch { repo.user.collect { u -> _state.update { it.copy(user = u) } } }
        viewModelScope.launch {
            graph.live.events.collect { event ->
                when (event["type"]?.jsonPrimitive?.contentOrNull) {
                    "call.started", "call.state", "call.ended", "intent", "summary" -> scheduleReload()
                }
            }
        }
    }

    private fun scheduleReload() {
        reloadJob?.cancel()
        reloadJob = viewModelScope.launch {
            delay(400)
            loadCalls()
        }
    }

    fun refresh() {
        _state.update { it.copy(refreshing = true, error = null) }
        viewModelScope.launch {
            try {
                val line = async { runCatching { repo.currentLine() }.getOrNull() }
                val assistant = async { runCatching { repo.assistant() }.getOrNull() }
                val ent = async { runCatching { repo.entitlement() }.getOrNull() }
                val stats = async { runCatching { repo.stats() }.getOrNull() }
                loadCalls()
                _state.update {
                    it.copy(line = line.await(), assistant = assistant.await(), entitlement = ent.await(), stats = stats.await(), refreshing = false, loaded = true)
                }
                repo.refreshPolicy()
            } catch (e: Exception) {
                _state.update { it.copy(refreshing = false, loaded = true, error = e.message) }
            }
        }
    }

    private suspend fun loadCalls() {
        val s = _state.value
        try {
            val category = s.filter?.takeIf { it != "unread" }
            val page = repo.calls(query = s.query, category = category)
            val live = runCatching { repo.liveCalls() }.getOrDefault(emptyList())
            val items = if (s.filter == "unread") page.items.filter { it.unread } else page.items
            _state.update { it.copy(calls = items, nextCursor = page.nextCursor, live = live, loaded = true) }
        } catch (e: Exception) {
            _state.update { it.copy(error = e.message, loaded = true) }
        }
    }

    fun loadMore() {
        val cursor = _state.value.nextCursor ?: return
        viewModelScope.launch {
            runCatching { repo.calls(query = _state.value.query, category = _state.value.filter?.takeIf { it != "unread" }, cursor = cursor) }
                .onSuccess { page -> _state.update { it.copy(calls = it.calls + page.items, nextCursor = page.nextCursor) } }
        }
    }

    fun setFilter(filter: String?) {
        _state.update { it.copy(filter = filter) }
        viewModelScope.launch { loadCalls() }
    }

    fun setSearching(on: Boolean) {
        _state.update { it.copy(searching = on, query = if (on) it.query else "") }
        if (!on) viewModelScope.launch { loadCalls() }
    }

    fun setQuery(q: String) {
        _state.update { it.copy(query = q) }
        scheduleReload()
    }

    fun setActive(active: Boolean) = updateAssistant(
        if (active) AssistantPatch(screeningMode = "assistant_first", snoozeMinutes = 0) else AssistantPatch(screeningMode = "off")
    )

    fun snooze(minutes: Int) = updateAssistant(AssistantPatch(snoozeMinutes = minutes))

    private fun updateAssistant(patch: AssistantPatch) {
        viewModelScope.launch {
            runCatching { repo.updateAssistant(patch) }
                .onSuccess { a -> _state.update { it.copy(assistant = a) } }
                .onFailure { e -> _state.update { it.copy(error = e.message) } }
        }
    }
}

private val FILTERS = listOf(
    null to "All",
    "unread" to "Unread",
    "delivery" to "Deliveries",
    "bank_finance" to "Banks",
    "personal" to "Personal",
    "recruiter" to "Jobs",
    "sales" to "Sales",
    "scam" to "Scams",
)

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun HomeScreen(vm: HomeViewModel, onOpenCall: (String) -> Unit, onOpenLive: (String) -> Unit, onFixSetup: () -> Unit) {
    val state by vm.state.collectAsStateWithLifecycle()
    val context = LocalContext.current
    LaunchedEffect(Unit) { vm.refresh() }

    Column(Modifier.fillMaxSize()) {
        TopAppBar(
            title = {
                if (state.searching) {
                    OutlinedTextField(
                        value = state.query,
                        onValueChange = vm::setQuery,
                        placeholder = { Text("Search names, companies, topics") },
                        singleLine = true,
                        modifier = Modifier.fillMaxWidth(),
                    )
                } else {
                    Column {
                        Text("${Format.greeting(LocalTime.now().hour)}${Format.firstName(state.user?.name).let { if (it.isBlank()) "" else ", $it" }}", style = MaterialTheme.typography.titleLarge)
                    }
                }
            },
            actions = {
                IconButton(onClick = { vm.setSearching(!state.searching) }) {
                    Icon(if (state.searching) Icons.Filled.Close else Icons.Filled.Search, contentDescription = if (state.searching) "Close search" else "Search")
                }
            },
            colors = TopAppBarDefaults.topAppBarColors(containerColor = MaterialTheme.colorScheme.background),
        )
        PullToRefreshBox(isRefreshing = state.refreshing, onRefresh = vm::refresh, modifier = Modifier.fillMaxSize()) {
            LazyColumn(Modifier.fillMaxSize(), contentPadding = androidx.compose.foundation.layout.PaddingValues(horizontal = 16.dp, vertical = 8.dp)) {
                if (!state.searching) {
                    item("status") { StatusCard(state, onToggle = vm::setActive, onSnooze = vm::snooze, onFixSetup = onFixSetup) }
                    items(state.live, key = { "live-${it.id}" }) { call -> LiveBanner(call) { onOpenLive(call.id) } }
                    state.stats?.takeIf { it.callsHandled > 0 }?.let { stats ->
                        item("stats") {
                            Row(Modifier.fillMaxWidth().padding(vertical = 16.dp, horizontal = 4.dp), horizontalArrangement = Arrangement.SpaceBetween) {
                                StatTile("${stats.callsHandled}", "calls handled")
                                StatTile("${stats.spamBlocked}", "spam stopped")
                                StatTile("${stats.minutesSaved} min", "of your time saved")
                            }
                        }
                    }
                    item("filters") {
                        Row(Modifier.horizontalScroll(rememberScrollState()).padding(vertical = 4.dp), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                            FILTERS.forEach { (key, label) ->
                                FilterChip(selected = state.filter == key, onClick = { vm.setFilter(key) }, label = { Text(label) })
                            }
                        }
                    }
                }
                if (state.loaded && state.calls.isEmpty()) {
                    item("empty") {
                        EmptyState(
                            icon = Icons.Filled.Call,
                            title = if (state.query.isNotBlank() || state.filter != null) "No calls match" else "No calls yet",
                            body = if (state.query.isNotBlank() || state.filter != null) "Try another filter or search."
                            else "When someone calls and you don't pick up, your assistant answers and the summary shows up here.",
                            action = state.line?.let { line ->
                                @Composable {
                                    FilledTonalButton(onClick = { PhoneUtils.startSafely(context, PhoneUtils.callIntent(line.assistantNumber)) }) {
                                        Text("Call my assistant to try it")
                                    }
                                }
                            },
                        )
                    }
                }
                var lastDay: String? = null
                state.calls.forEach { call ->
                    val day = Format.dayLabel(call.startedAt)
                    if (day != lastDay) {
                        lastDay = day
                        item("day-$day-${call.id}") { SectionHeader(day) }
                    }
                    item(call.id) { CallRow(call) { onOpenCall(call.id) } }
                }
                if (state.nextCursor != null) {
                    item("more") {
                        LaunchedEffect(state.calls.size) { vm.loadMore() }
                        Spacer(Modifier.height(48.dp))
                    }
                }
            }
        }
    }
}

@Composable
private fun StatusCard(state: HomeState, onToggle: (Boolean) -> Unit, onSnooze: (Int) -> Unit, onFixSetup: () -> Unit) {
    val colors = LocalPickupColors.current
    val assistant = state.assistant
    val line = state.line
    val snoozedFor = Format.until(assistant?.snoozeUntil)
    val setupDone = line?.status == "verified"
    val active = setupDone && assistant?.screeningMode != "off" && snoozedFor == null
    val (title, subtitle, dot) = when {
        line == null || !setupDone -> Triple("Finish setting up", "Forwarding isn't confirmed yet, so calls still ring you.", colors.warning)
        assistant?.screeningMode == "off" -> Triple("Assistant is off", "Your phone rings for every call. Calls you decline still reach your assistant.", MaterialTheme.colorScheme.outline)
        snoozedFor != null -> Triple("Paused for $snoozedFor", "Calls ring you normally until then.", colors.warning)
        assistant?.screeningMode == "ring_first" -> Triple("Ring first, then assistant", "Your phone rings first. Calls you miss go to your assistant.", colors.success)
        else -> Triple("Answering unknown calls", "Saved contacts ring you. Everyone else talks to your assistant first.", colors.success)
    }
    Card(colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceContainerLowest), modifier = Modifier.fillMaxWidth()) {
        Column(Modifier.padding(16.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Box(Modifier.size(10.dp).clip(CircleShape).background(dot))
                Spacer(Modifier.width(10.dp))
                Column(Modifier.weight(1f)) {
                    Text(title, style = MaterialTheme.typography.titleMedium)
                    Text(subtitle, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
                if (setupDone) Switch(checked = active, onCheckedChange = onToggle)
            }
            Spacer(Modifier.height(12.dp))
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                if (!setupDone) {
                    FilledTonalButton(onClick = onFixSetup) { Text("Continue setup") }
                } else if (snoozedFor != null) {
                    AssistChip(onClick = { onSnooze(0) }, label = { Text("Resume now") })
                } else if (active) {
                    AssistChip(onClick = { onSnooze(60) }, label = { Text("Pause 1 hour") })
                    AssistChip(onClick = { onSnooze(minutesUntilMorning()) }, label = { Text("Pause until 8 AM") })
                }
            }
            state.entitlement?.let { ent -> PlanLine(ent) }
        }
    }
}

private fun minutesUntilMorning(): Int {
    val now = LocalTime.now()
    val minutesNow = now.hour * 60 + now.minute
    val target = 8 * 60
    return if (minutesNow < target) target - minutesNow else 24 * 60 - minutesNow + target
}

@Composable
private fun PlanLine(ent: Entitlement) {
    val text = when (ent.level) {
        "trial" -> Format.until(ent.trialEndsAt)?.let { "Pro trial: $it left" }
        "free" -> "Free plan: ${ent.callsLeftThisMonth ?: 0} calls left this month"
        "limited" -> "Free calls used up: your assistant only takes messages until next month"
        else -> null
    } ?: return
    Spacer(Modifier.height(10.dp))
    Text(text, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.primary)
}

@Composable
private fun LiveBanner(call: CallSummary, onClick: () -> Unit) {
    Card(
        onClick = onClick,
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.tertiaryContainer),
        modifier = Modifier.fillMaxWidth().padding(top = 12.dp),
    ) {
        Row(Modifier.padding(16.dp), verticalAlignment = Alignment.CenterVertically) {
            LiveDot(12.dp)
            Spacer(Modifier.width(12.dp))
            Column(Modifier.weight(1f)) {
                Text("Live: ${call.title}", style = MaterialTheme.typography.titleMedium, color = MaterialTheme.colorScheme.onTertiaryContainer)
                Text(
                    call.reason ?: "Your assistant is talking to them",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onTertiaryContainer,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                )
            }
            Text("Listen", style = MaterialTheme.typography.labelLarge, color = MaterialTheme.colorScheme.onTertiaryContainer)
        }
    }
}

@Composable
fun CallRow(call: CallSummary, onClick: () -> Unit) {
    val colors = LocalPickupColors.current
    Row(
        Modifier
            .fillMaxWidth()
            .clip(MaterialTheme.shapes.medium)
            .clickable(onClick = onClick)
            .padding(vertical = 10.dp, horizontal = 4.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        CategoryAvatar(call.category, call.isSpam)
        Spacer(Modifier.width(12.dp))
        Column(Modifier.weight(1f)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text(
                    call.title,
                    style = MaterialTheme.typography.titleMedium,
                    fontWeight = if (call.unread) FontWeight.Bold else FontWeight.SemiBold,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                    modifier = Modifier.weight(1f, fill = false),
                )
                if (call.direction == "outbound") {
                    Spacer(Modifier.width(6.dp))
                    Pill("Made for you", MaterialTheme.colorScheme.primary)
                }
                if (call.isSpam) {
                    Spacer(Modifier.width(6.dp))
                    Pill("Spam", colors.spam)
                }
                if (call.urgency == "high" && !call.isSpam) {
                    Spacer(Modifier.width(6.dp))
                    Pill("Urgent", colors.live)
                }
            }
            Text(
                call.summary ?: call.reason ?: if (call.state in setOf("processing", "ended")) "Summarising…" else "Your assistant answered",
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                maxLines = 2,
                overflow = TextOverflow.Ellipsis,
            )
        }
        Spacer(Modifier.width(8.dp))
        Column(horizontalAlignment = Alignment.End) {
            Text(Format.clock(call.startedAt), style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
            if (call.unread) {
                Spacer(Modifier.height(6.dp))
                Box(Modifier.size(8.dp).clip(CircleShape).background(MaterialTheme.colorScheme.primary))
            }
        }
    }
}
