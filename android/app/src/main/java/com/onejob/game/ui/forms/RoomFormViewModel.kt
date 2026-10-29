package com.onejob.game.ui.forms

import androidx.lifecycle.SavedStateHandle
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.onejob.game.data.ConnectionStatus
import com.onejob.game.data.GameRepository
import com.onejob.game.data.repository.ConnectionState
import com.onejob.game.ui.lobby.LobbyFeedback
import com.onejob.game.ui.lobby.feedback
import kotlinx.coroutines.Job
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.launch
import java.util.Locale

enum class FormKind { CREATE, JOIN }

data class RoomFormUiState(
    val name: String = "",
    val roomCode: String = "",
    val checked: Boolean = false,
    val nameIssue: DraftIssue? = null,
    val codeIssue: DraftIssue? = null,
    val connection: ConnectionState = ConnectionState(),
    val pending: Boolean = false,
    val admitted: Boolean = false,
    val exiting: Boolean = false,
    val exited: Boolean = false,
    val feedback: LobbyFeedback? = null,
) {
    val draftValid: Boolean get() = checked && nameIssue == null && codeIssue == null
    val connectionStatus: ConnectionStatus get() = connection.status
    val canSubmit: Boolean get() = !pending && !exiting && !admitted && feedback != LobbyFeedback.UNCERTAIN
}

class RoomFormViewModel(
    private val kind: FormKind,
    private val repository: GameRepository,
    private val savedState: SavedStateHandle,
) : ViewModel() {
    private val name = savedState.getStateFlow(NAME, "")
    private val roomCode = savedState.getStateFlow(CODE, "")
    private val checked = savedState.getStateFlow(CHECKED, false)
    private var pending = false
    private var exiting = false
    private var exited = false
    private var feedback: LobbyFeedback? = null
    private var submission: Job? = null
    private val _ui = MutableStateFlow(render())
    val uiState = _ui.asStateFlow()

    init {
        viewModelScope.launch {
            combine(name, roomCode, checked, repository.connection, repository.session) { _, _, _, _, _ -> Unit }
                .collect { refresh() }
        }
    }
    fun onNameChanged(value: String) { if (!pending && !exiting) { savedState[NAME] = value; refresh() } }
    fun onRoomCodeChanged(value: String) { if (!pending && !exiting) { savedState[CODE] = value; refresh() } }
    fun onCheckDraft() { savedState[CHECKED] = true; refresh() }
    fun onSubmit() {
        if (!_ui.value.canSubmit || repository.session.value.identity != null) return
        onCheckDraft()
        if (!_ui.value.draftValid) return
        val submittedName = name.value.trim()
        val submittedCode = roomCode.value.trim().uppercase(Locale.ROOT)
        pending = true
        feedback = null
        refresh()
        submission = viewModelScope.launch {
            val result = if (kind == FormKind.CREATE) repository.create(submittedName) else repository.join(submittedCode, submittedName)
            feedback = result.feedback()
            pending = false
            refresh()
        }
    }
    fun resetAttempt() {
        if (pending || exiting || repository.session.value.identity != null) return
        pending = true
        refresh()
        viewModelScope.launch {
            repository.disconnect()
            feedback = null
            pending = false
            refresh()
        }
    }
    fun cancel() {
        if (exiting || exited) return
        exiting = true
        submission?.cancel()
        pending = true
        refresh()
        viewModelScope.launch {
            if (repository.session.value.identity != null) repository.leave() else repository.disconnect()
            pending = false
            exited = true
            refresh()
        }
    }
    private fun refresh() { _ui.value = render() }
    private fun render() = RoomFormUiState(
        name.value, roomCode.value, checked.value,
        if (checked.value) DraftValidation.name(name.value) else null,
        if (checked.value && kind == FormKind.JOIN) DraftValidation.roomCode(roomCode.value) else null,
        repository.connection.value, pending, repository.session.value.identity != null && !exiting,
        exiting, exited, feedback,
    )
    companion object {
        // Never persist pending commands, credentials or authoritative session state.
        internal const val NAME = "draft.name"
        internal const val CODE = "draft.code"
        internal const val CHECKED = "draft.checked"
    }
}
