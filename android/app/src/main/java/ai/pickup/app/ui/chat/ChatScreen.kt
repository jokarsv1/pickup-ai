package ai.pickup.app.ui.chat

import ai.pickup.app.AppGraph
import ai.pickup.app.data.ChatMessageDto
import ai.pickup.app.telephony.PhoneUtils
import android.app.Activity
import android.content.Intent
import android.speech.RecognizerIntent
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.Send
import androidx.compose.material.icons.filled.AutoAwesome
import androidx.compose.material.icons.filled.Mic
import androidx.compose.material3.AssistChip
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.SuggestionChip
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
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
import androidx.lifecycle.ViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.contentOrNull
import kotlinx.serialization.json.jsonPrimitive

data class ChatState(val messages: List<ChatMessageDto> = emptyList(), val sending: Boolean = false, val error: String? = null)

class ChatViewModel(private val graph: AppGraph) : ViewModel() {
    private val repo = graph.repository
    private val _state = MutableStateFlow(ChatState())
    val state: StateFlow<ChatState> = _state

    init {
        viewModelScope.launch { runCatching { repo.chatHistory() }.onSuccess { m -> _state.update { it.copy(messages = m) } } }
    }

    fun send(text: String) {
        val clean = text.trim()
        if (clean.isEmpty() || _state.value.sending) return
        val optimistic = ChatMessageDto(id = -System.currentTimeMillis(), role = "user", text = clean)
        _state.update { it.copy(messages = it.messages + optimistic, sending = true, error = null) }
        viewModelScope.launch {
            try {
                val reply = repo.chat(clean)
                _state.update { it.copy(messages = reply.messages, sending = false) }
                if (reply.clientActions.any { a -> a.type() in setOf("snooze", "settings_changed") }) repo.refreshPolicy()
            } catch (e: Exception) {
                _state.update { it.copy(sending = false, error = e.message) }
            }
        }
    }
}

private fun JsonObject.type(): String? = this["type"]?.jsonPrimitive?.contentOrNull
private fun JsonObject.str(key: String): String? = this[key]?.jsonPrimitive?.contentOrNull

private val SUGGESTIONS = listOf(
    "Call Apollo Clinic tomorrow at 10 and book a general checkup",
    "Remind me to call back the last caller at 6 pm",
    "Stop answering calls from banks",
    "Pause for 2 hours, I'm free now",
    "Who called me today?",
)

@OptIn(ExperimentalMaterial3Api::class, ExperimentalLayoutApi::class)
@Composable
fun ChatScreen(vm: ChatViewModel) {
    val state by vm.state.collectAsStateWithLifecycle()
    val context = LocalContext.current
    var draft by remember { mutableStateOf("") }
    val listState = rememberLazyListState()
    LaunchedEffect(state.messages.size) { if (state.messages.isNotEmpty()) listState.animateScrollToItem(state.messages.size - 1) }
    val speech = rememberLauncherForActivityResult(ActivityResultContracts.StartActivityForResult()) { result ->
        if (result.resultCode == Activity.RESULT_OK) {
            result.data?.getStringArrayListExtra(RecognizerIntent.EXTRA_RESULTS)?.firstOrNull()?.let { vm.send(it) }
        }
    }

    Column(Modifier.fillMaxSize().imePadding()) {
        TopAppBar(title = { Text("Ask Pickup") }, colors = TopAppBarDefaults.topAppBarColors(containerColor = MaterialTheme.colorScheme.background))
        if (state.sending) LinearProgressIndicator(Modifier.fillMaxWidth())
        LazyColumn(state = listState, modifier = Modifier.weight(1f).fillMaxWidth(), contentPadding = androidx.compose.foundation.layout.PaddingValues(16.dp)) {
            if (state.messages.isEmpty()) {
                item {
                    Column {
                        Icon(Icons.Filled.AutoAwesome, null, tint = MaterialTheme.colorScheme.primary)
                        Spacer(Modifier.height(8.dp))
                        Text("Your assistant can do more than answer.", style = MaterialTheme.typography.titleLarge)
                        Text(
                            "It can call people for you, set reminders, and change how it handles your calls. Try:",
                            style = MaterialTheme.typography.bodyMedium,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                        Spacer(Modifier.height(12.dp))
                        FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                            SUGGESTIONS.forEach { s -> SuggestionChip(onClick = { vm.send(s) }, label = { Text(s) }) }
                        }
                    }
                }
            }
            items(state.messages, key = { it.id }) { message ->
                val mine = message.role == "user"
                Column(Modifier.fillMaxWidth().padding(vertical = 4.dp), horizontalAlignment = if (mine) Alignment.End else Alignment.Start) {
                    Surface(
                        color = if (mine) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.surfaceContainerHigh,
                        shape = RoundedCornerShape(18.dp),
                        modifier = Modifier.widthIn(max = 320.dp),
                    ) {
                        Text(
                            message.text,
                            color = if (mine) MaterialTheme.colorScheme.onPrimary else MaterialTheme.colorScheme.onSurface,
                            modifier = Modifier.padding(horizontal = 14.dp, vertical = 10.dp),
                        )
                    }
                    if (message.clientActions.isNotEmpty()) {
                        Row(horizontalArrangement = Arrangement.spacedBy(8.dp), modifier = Modifier.padding(top = 4.dp)) {
                            message.clientActions.forEach { action ->
                                when (action.type()) {
                                    "reminder" -> AssistChip(
                                        onClick = { PhoneUtils.startSafely(context, PhoneUtils.reminderIntent(action.str("title") ?: "Reminder", action.str("due_at"))) },
                                        label = { Text("Add to calendar") },
                                    )
                                    "save_contact" -> AssistChip(
                                        onClick = { PhoneUtils.startSafely(context, PhoneUtils.saveContactIntent(action.str("name") ?: "", action.str("number") ?: "")) },
                                        label = { Text("Save contact") },
                                    )
                                    "outbound_scheduled" -> AssistChip(onClick = {}, label = { Text("Call scheduled · ${action.str("to") ?: ""}") })
                                }
                            }
                        }
                    }
                }
            }
        }
        state.error?.let { Text(it, color = MaterialTheme.colorScheme.error, modifier = Modifier.padding(horizontal = 16.dp)) }
        Row(Modifier.padding(horizontal = 12.dp, vertical = 8.dp), verticalAlignment = Alignment.CenterVertically) {
            IconButton(onClick = {
                val intent = Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH)
                    .putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
                    .putExtra(RecognizerIntent.EXTRA_LANGUAGE, "en-IN")
                    .putExtra(RecognizerIntent.EXTRA_PROMPT, "What should Pickup do?")
                runCatching { speech.launch(intent) }
            }) { Icon(Icons.Filled.Mic, "Speak") }
            OutlinedTextField(
                value = draft,
                onValueChange = { draft = it.take(2000) },
                placeholder = { Text("Ask Pickup to call, remind or change settings") },
                modifier = Modifier.weight(1f),
                maxLines = 4,
            )
            IconButton(onClick = { vm.send(draft); draft = "" }, enabled = draft.isNotBlank() && !state.sending) {
                Icon(Icons.AutoMirrored.Filled.Send, "Send")
            }
        }
    }
}
