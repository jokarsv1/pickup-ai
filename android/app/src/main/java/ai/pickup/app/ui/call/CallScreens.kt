package ai.pickup.app.ui.call

import ai.pickup.app.AppGraph
import ai.pickup.app.data.CallActionDto
import ai.pickup.app.data.CallDetail
import ai.pickup.app.data.RuleDto
import ai.pickup.app.data.TranscriptLine
import ai.pickup.app.telephony.PhoneUtils
import ai.pickup.app.ui.components.CategoryAvatar
import ai.pickup.app.ui.components.LiveDot
import ai.pickup.app.ui.components.Pill
import ai.pickup.app.ui.components.SectionHeader
import ai.pickup.app.ui.components.categoryStyle
import ai.pickup.app.ui.theme.LocalPickupColors
import ai.pickup.app.util.Format
import android.content.Context
import android.media.AudioAttributes
import android.media.MediaPlayer
import android.net.Uri
import androidx.compose.foundation.background
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.automirrored.filled.Send
import androidx.compose.material.icons.filled.Alarm
import androidx.compose.material.icons.filled.Block
import androidx.compose.material.icons.filled.Call
import androidx.compose.material.icons.filled.CallEnd
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material.icons.filled.Pause
import androidx.compose.material.icons.filled.PersonAdd
import androidx.compose.material.icons.filled.PlayArrow
import androidx.compose.material.icons.filled.Star
import androidx.compose.material.icons.filled.StarBorder
import androidx.compose.material3.AssistChip
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SuggestionChip
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.lifecycle.ViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import kotlinx.serialization.json.contentOrNull
import kotlinx.serialization.json.intOrNull
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonPrimitive

data class CallState(
    val call: CallDetail? = null,
    val transcript: List<TranscriptLine> = emptyList(),
    val replies: List<String> = emptyList(),
    val sending: Boolean = false,
    val joining: Boolean = false,
    val notice: String? = null,
    val error: String? = null,
) {
    val isLive: Boolean get() = call?.state in setOf("ringing", "live")
}

class CallViewModel(private val graph: AppGraph, val callId: String) : ViewModel() {
    private val repo = graph.repository
    private val _state = MutableStateFlow(CallState())
    val state: StateFlow<CallState> = _state

    init {
        load()
        viewModelScope.launch {
            graph.live.events.collect { event ->
                if (event["call_id"]?.jsonPrimitive?.contentOrNull != callId) return@collect
                when (event["type"]?.jsonPrimitive?.contentOrNull) {
                    "transcript" -> {
                        val line = TranscriptLine(
                            seq = event["seq"]?.jsonPrimitive?.intOrNull ?: -1,
                            speaker = event["speaker"]?.jsonPrimitive?.contentOrNull ?: "assistant",
                            text = event["text"]?.jsonPrimitive?.contentOrNull ?: "",
                        )
                        _state.update { s -> if (s.transcript.any { it.seq == line.seq }) s else s.copy(transcript = (s.transcript + line).sortedBy { it.seq }) }
                    }
                    "intent" -> {
                        val replies = runCatching { event["suggested_replies"]!!.jsonArray.mapNotNull { it.jsonPrimitive.contentOrNull } }.getOrDefault(emptyList())
                        val title = event["title"]?.jsonPrimitive?.contentOrNull
                        val reason = event["reason"]?.jsonPrimitive?.contentOrNull
                        _state.update { s -> s.copy(replies = replies, call = s.call?.let { c -> c.copy(title = title ?: c.title, reason = reason ?: c.reason) }) }
                    }
                    "call.state", "call.ended", "summary" -> load()
                    "takeover.ringing" -> _state.update { it.copy(notice = "Your phone will ring. Answer it to talk to the caller.") }
                }
            }
        }
    }

    fun load() {
        viewModelScope.launch {
            runCatching { repo.call(callId) }
                .onSuccess { call ->
                    _state.update { s ->
                        s.copy(
                            call = call,
                            transcript = (call.transcript + s.transcript).distinctBy { it.seq }.sortedBy { it.seq },
                            replies = if (call.suggestedReplies.isNotEmpty()) call.suggestedReplies else s.replies,
                            error = null,
                        )
                    }
                }
                .onFailure { e -> _state.update { it.copy(error = e.message) } }
        }
    }

    fun say(text: String) {
        if (text.isBlank()) return
        _state.update { it.copy(sending = true) }
        viewModelScope.launch {
            runCatching { repo.say(callId, text.trim()) }
                .onSuccess { _state.update { it.copy(sending = false, notice = "Your assistant will say it now") } }
                .onFailure { e -> _state.update { it.copy(sending = false, error = e.message) } }
        }
    }

    fun takeOver() {
        _state.update { it.copy(joining = true) }
        viewModelScope.launch {
            runCatching { repo.takeOver(callId) }
                .onSuccess { _state.update { it.copy(notice = "Connecting you. Your phone will ring in a few seconds.") } }
                .onFailure { e -> _state.update { it.copy(joining = false, error = e.message) } }
        }
    }

    fun end() = viewModelScope.launch { runCatching { repo.endCall(callId) }.onFailure { e -> _state.update { it.copy(error = e.message) } } }

    fun rate(stars: Int) = viewModelScope.launch {
        runCatching { repo.rate(callId, stars) }.onSuccess { _state.update { s -> s.copy(call = s.call?.copy(rating = stars), notice = "Thanks for the feedback") } }
    }

    fun runAction(context: Context, action: CallActionDto) {
        val number = action.payload["number"]?.jsonPrimitive?.contentOrNull
        when (action.type) {
            "reminder" -> PhoneUtils.startSafely(context, PhoneUtils.reminderIntent(action.title, action.payload["due_at"]?.jsonPrimitive?.contentOrNull))
            "call_back" -> number?.let { PhoneUtils.startSafely(context, PhoneUtils.callIntent(it)) }
            "save_contact" -> number?.let {
                PhoneUtils.startSafely(context, PhoneUtils.saveContactIntent(action.payload["name"]?.jsonPrimitive?.contentOrNull ?: "", it))
            }
            "block" -> number?.let { alwaysDecline(it) }
        }
        viewModelScope.launch {
            runCatching { repo.markAction(callId, action.id, "done") }
            load()
        }
    }

    private fun alwaysDecline(number: String) = viewModelScope.launch {
        runCatching {
            val rules = repo.rules().filterNot { it.matchType == "number" && it.matchValue == number }
            repo.saveRules(rules + RuleDto(matchType = "number", matchValue = number, action = "decline"))
        }.onSuccess { _state.update { it.copy(notice = "Your assistant will turn this number away from now on") } }
    }

    fun delete(onDone: () -> Unit) = viewModelScope.launch { runCatching { repo.deleteCall(callId) }.onSuccess { onDone() } }

    fun consumeNotice() = _state.update { it.copy(notice = null, error = null) }

    suspend fun recordingSource(): Pair<String, String?> = repo.recordingUrl(callId) to repo.accessToken()
}

// ------------------------------------------------------------------------------------- Live call

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun LiveCallScreen(vm: CallViewModel, onBack: () -> Unit, onOpenDetail: (String) -> Unit) {
    val state by vm.state.collectAsStateWithLifecycle()
    val call = state.call
    var draft by remember { mutableStateOf("") }
    val listState = rememberLazyListState()
    LaunchedEffect(state.transcript.size) { if (state.transcript.isNotEmpty()) listState.animateScrollToItem(state.transcript.size - 1) }
    LaunchedEffect(call?.state) { if (call != null && call.state in setOf("processing", "summarized")) onOpenDetail(call.id) }

    Scaffold(
        topBar = {
            TopAppBar(
                navigationIcon = { IconButton(onClick = onBack) { Icon(Icons.AutoMirrored.Filled.ArrowBack, "Back") } },
                title = {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        if (state.isLive) {
                            LiveDot()
                            Spacer(Modifier.width(8.dp))
                        }
                        Text(call?.title ?: "Live call", maxLines = 1)
                    }
                },
            )
        },
        bottomBar = {
            Column(Modifier.navigationBarsPadding().imePadding().padding(horizontal = 16.dp, vertical = 8.dp)) {
                if (state.isLive) {
                    val replies = (state.replies + listOf("Please leave a message", "I'll call back in 10 minutes")).distinct().take(5)
                    Row(Modifier.horizontalScroll(rememberScrollState()), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        replies.forEach { reply -> SuggestionChip(onClick = { vm.say(reply) }, label = { Text(reply) }) }
                    }
                    Spacer(Modifier.height(8.dp))
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        OutlinedTextField(
                            value = draft,
                            onValueChange = { draft = it.take(300) },
                            placeholder = { Text("Tell your assistant what to say") },
                            modifier = Modifier.weight(1f),
                            maxLines = 3,
                        )
                        IconButton(onClick = { vm.say(draft); draft = "" }, enabled = draft.isNotBlank() && !state.sending) {
                            Icon(Icons.AutoMirrored.Filled.Send, "Send")
                        }
                    }
                    Spacer(Modifier.height(8.dp))
                    Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                        Button(onClick = vm::takeOver, enabled = !state.joining, modifier = Modifier.weight(1f).height(52.dp)) {
                            Icon(Icons.Filled.Call, null)
                            Spacer(Modifier.width(8.dp))
                            Text("Join call")
                        }
                        OutlinedButton(onClick = { vm.end() }, modifier = Modifier.weight(1f).height(52.dp)) {
                            Icon(Icons.Filled.CallEnd, null)
                            Spacer(Modifier.width(8.dp))
                            Text("End")
                        }
                    }
                } else if (call != null) {
                    Button(onClick = { onOpenDetail(call.id) }, modifier = Modifier.fillMaxWidth().height(52.dp)) { Text("See the summary") }
                }
            }
        },
    ) { padding ->
        Column(Modifier.fillMaxSize().padding(padding)) {
            if (call != null) IntentCard(call)
            (state.notice ?: state.error)?.let { message ->
                Surface(color = MaterialTheme.colorScheme.secondaryContainer, shape = RoundedCornerShape(12.dp), modifier = Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 4.dp)) {
                    Row(Modifier.padding(12.dp), verticalAlignment = Alignment.CenterVertically) {
                        Text(message, modifier = Modifier.weight(1f), style = MaterialTheme.typography.bodyMedium)
                        TextButton(onClick = vm::consumeNotice) { Text("OK") }
                    }
                }
            }
            LazyColumn(state = listState, modifier = Modifier.weight(1f).fillMaxWidth(), contentPadding = androidx.compose.foundation.layout.PaddingValues(16.dp)) {
                items(state.transcript, key = { it.seq }) { line -> Bubble(line) }
                if (state.transcript.isEmpty()) {
                    item { Text("Your assistant just picked up. The conversation will appear here.", color = MaterialTheme.colorScheme.onSurfaceVariant) }
                }
            }
        }
    }
}

@Composable
private fun IntentCard(call: CallDetail) {
    val style = categoryStyle(call.category, call.isSpam)
    Card(colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceContainerLowest), modifier = Modifier.fillMaxWidth().padding(16.dp)) {
        Row(Modifier.padding(16.dp), verticalAlignment = Alignment.CenterVertically) {
            CategoryAvatar(call.category, call.isSpam)
            Spacer(Modifier.width(12.dp))
            Column(Modifier.weight(1f)) {
                Text(call.reason ?: "Finding out why they're calling…", style = MaterialTheme.typography.titleMedium)
                Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                    if (call.category != null) Pill(call.categoryLabel ?: style.label, style.color)
                    if (call.urgency == "high") Pill("Urgent", LocalPickupColors.current.live)
                    call.callerNumber?.let { Text(it, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant) }
                }
            }
        }
    }
}

@Composable
private fun Bubble(line: TranscriptLine) {
    val isCaller = line.speaker == "caller"
    val isOwner = line.speaker == "owner"
    val bg = when {
        isCaller -> MaterialTheme.colorScheme.surfaceContainerHigh
        isOwner -> MaterialTheme.colorScheme.tertiaryContainer
        else -> MaterialTheme.colorScheme.primaryContainer
    }
    val label = when {
        isCaller -> "Caller"
        isOwner -> "You"
        else -> "Your assistant"
    }
    Column(Modifier.fillMaxWidth().padding(vertical = 4.dp), horizontalAlignment = if (isCaller) Alignment.Start else Alignment.End) {
        Text(label, style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
        Surface(color = bg, shape = RoundedCornerShape(16.dp), modifier = Modifier.widthIn(max = 300.dp)) {
            Text(line.text, style = MaterialTheme.typography.bodyLarge, modifier = Modifier.padding(horizontal = 14.dp, vertical = 10.dp))
        }
    }
}

// ------------------------------------------------------------------------------------- Detail

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun CallDetailScreen(vm: CallViewModel, onBack: () -> Unit, onOpenLive: (String) -> Unit) {
    val state by vm.state.collectAsStateWithLifecycle()
    val context = LocalContext.current
    val call = state.call
    LaunchedEffect(call?.state) { if (call != null && state.isLive) onOpenLive(call.id) }

    Scaffold(
        topBar = {
            TopAppBar(
                navigationIcon = { IconButton(onClick = onBack) { Icon(Icons.AutoMirrored.Filled.ArrowBack, "Back") } },
                title = { Text(call?.title ?: "Call", maxLines = 1) },
                actions = { IconButton(onClick = { vm.delete(onBack) }) { Icon(Icons.Filled.Delete, "Delete call") } },
            )
        },
    ) { padding ->
        if (call == null) {
            Box(Modifier.fillMaxSize().padding(padding), contentAlignment = Alignment.Center) {
                if (state.error != null) Text(state.error!!) else CircularProgressIndicator()
            }
            return@Scaffold
        }
        Column(Modifier.fillMaxSize().padding(padding).verticalScroll(rememberScrollState()).padding(horizontal = 16.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.padding(vertical = 8.dp)) {
                CategoryAvatar(call.category, call.isSpam, size = 56.dp)
                Spacer(Modifier.width(14.dp))
                Column(Modifier.weight(1f)) {
                    Text(call.title, style = MaterialTheme.typography.titleLarge)
                    Text(
                        listOfNotNull(call.callerNumber, Format.dateTime(call.startedAt), Format.duration(call.durationSeconds).ifBlank { null }).joinToString(" · "),
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
            }
            Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                val style = categoryStyle(call.category, call.isSpam)
                Pill(call.categoryLabel ?: style.label, style.color)
                if (call.isSpam) Pill("Likely spam", LocalPickupColors.current.spam)
                if (call.direction == "outbound") Pill("Your assistant called them", MaterialTheme.colorScheme.primary)
            }
            Spacer(Modifier.height(16.dp))
            Card(colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceContainerLowest), modifier = Modifier.fillMaxWidth()) {
                Column(Modifier.padding(16.dp)) {
                    Text("Summary", style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    Spacer(Modifier.height(6.dp))
                    Text(call.summary ?: if (call.state == "processing") "Writing the summary…" else (call.reason ?: "No summary for this call."), style = MaterialTheme.typography.bodyLarge)
                }
            }
            val open = call.actions.filter { it.status == "open" }
            if (open.isNotEmpty() || call.callerNumber != null) {
                SectionHeader("Next steps")
                Row(Modifier.horizontalScroll(rememberScrollState()), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    open.forEach { action ->
                        AssistChip(onClick = { vm.runAction(context, action) }, label = { Text(action.title) }, leadingIcon = { Icon(actionIcon(action.type), null, Modifier.size(18.dp)) })
                    }
                    val callbackNumber = call.callerNumber
                    if (open.none { it.type == "call_back" } && callbackNumber != null && !call.isSpam) {
                        AssistChip(
                            onClick = { PhoneUtils.startSafely(context, PhoneUtils.callIntent(callbackNumber)) },
                            label = { Text("Call back") },
                            leadingIcon = { Icon(Icons.Filled.Call, null, Modifier.size(18.dp)) },
                        )
                    }
                }
            }
            if (call.hasRecording) {
                SectionHeader("Recording")
                RecordingPlayer(vm)
            }
            if (state.transcript.isNotEmpty()) {
                SectionHeader("Conversation")
                state.transcript.forEach { Bubble(it) }
            }
            SectionHeader("How did your assistant do?")
            Row {
                (1..5).forEach { star ->
                    IconButton(onClick = { vm.rate(star) }) {
                        Icon(
                            if ((call.rating ?: 0) >= star) Icons.Filled.Star else Icons.Filled.StarBorder,
                            contentDescription = "$star stars",
                            tint = MaterialTheme.colorScheme.tertiary,
                        )
                    }
                }
            }
            (state.notice ?: state.error)?.let { Text(it, color = MaterialTheme.colorScheme.primary, modifier = Modifier.padding(vertical = 8.dp)) }
            Spacer(Modifier.height(32.dp))
        }
    }
}

private fun actionIcon(type: String) = when (type) {
    "reminder" -> Icons.Filled.Alarm
    "save_contact" -> Icons.Filled.PersonAdd
    "block" -> Icons.Filled.Block
    else -> Icons.Filled.Call
}

/** Streams the recording from the backend with the user's token; no file is kept on the phone. */
@Composable
private fun RecordingPlayer(vm: CallViewModel) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    var player by remember { mutableStateOf<MediaPlayer?>(null) }
    var playing by remember { mutableStateOf(false) }
    var preparing by remember { mutableStateOf(false) }
    DisposableEffect(Unit) { onDispose { player?.release() } }

    Row(
        Modifier.fillMaxWidth().clip(RoundedCornerShape(16.dp)).background(MaterialTheme.colorScheme.surfaceContainerLowest).padding(12.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Button(
            onClick = {
                val current = player
                if (current != null) {
                    if (current.isPlaying) current.pause() else current.start()
                    playing = current.isPlaying
                    return@Button
                }
                preparing = true
                scope.launch {
                    val (url, token) = vm.recordingSource()
                    val mp = MediaPlayer()
                    mp.setAudioAttributes(AudioAttributes.Builder().setContentType(AudioAttributes.CONTENT_TYPE_SPEECH).build())
                    mp.setDataSource(context, Uri.parse(url), token?.let { mapOf("Authorization" to "Bearer $it") } ?: emptyMap())
                    mp.setOnPreparedListener { it.start(); preparing = false; playing = true }
                    mp.setOnCompletionListener { playing = false }
                    mp.setOnErrorListener { _, _, _ -> preparing = false; playing = false; true }
                    mp.prepareAsync()
                    player = mp
                }
            },
            colors = ButtonDefaults.buttonColors(),
        ) {
            if (preparing) CircularProgressIndicator(Modifier.size(18.dp), strokeWidth = 2.dp, color = MaterialTheme.colorScheme.onPrimary)
            else Icon(if (playing) Icons.Filled.Pause else Icons.Filled.PlayArrow, if (playing) "Pause" else "Play")
        }
        Spacer(Modifier.width(12.dp))
        Text(if (playing) "Playing" else "Listen to the call", style = MaterialTheme.typography.bodyMedium)
    }
}
