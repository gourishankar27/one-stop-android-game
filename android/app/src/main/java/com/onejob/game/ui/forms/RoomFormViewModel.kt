package com.onejob.game.ui.forms

import androidx.lifecycle.SavedStateHandle
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.onejob.game.data.ConnectionStatus
import com.onejob.game.data.GameRepository
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.flow.stateIn

enum class FormKind { CREATE, JOIN }

data class RoomFormUiState(
    val name: String = "",
    val roomCode: String = "",
    val checked: Boolean = false,
    val nameIssue: DraftIssue? = null,
    val codeIssue: DraftIssue? = null,
    val connectionStatus: ConnectionStatus = ConnectionStatus.UNAVAILABLE,
) {
    val draftValid: Boolean get() = checked && nameIssue == null && codeIssue == null
}

class RoomFormViewModel(
    private val kind: FormKind,
    repository: GameRepository,
    private val savedState: SavedStateHandle,
) : ViewModel() {
    private val name = savedState.getStateFlow(NAME, "")
    private val roomCode = savedState.getStateFlow(CODE, "")
    private val checked = savedState.getStateFlow(CHECKED, false)

    val uiState: StateFlow<RoomFormUiState> = combine(
        name,
        roomCode,
        checked,
        repository.connectionStatus,
    ) { name, code, checked, connection ->
        state(name, code, checked, connection)
    }.stateIn(
        viewModelScope,
        SharingStarted.WhileSubscribed(5_000),
        state(name.value, roomCode.value, checked.value, repository.connectionStatus.value),
    )

    fun onNameChanged(value: String) {
        savedState[NAME] = value
    }

    fun onRoomCodeChanged(value: String) {
        savedState[CODE] = value
    }

    fun onCheckDraft() {
        savedState[CHECKED] = true
    }

    private fun state(
        name: String,
        code: String,
        checked: Boolean,
        connection: ConnectionStatus,
    ) = RoomFormUiState(
        name = name,
        roomCode = code,
        checked = checked,
        nameIssue = if (checked) DraftValidation.name(name) else null,
        codeIssue = if (checked && kind == FormKind.JOIN) DraftValidation.roomCode(code) else null,
        connectionStatus = connection,
    )

    companion object {
        // Only nonsecret draft inputs/check presentation are saved, never repository/session state.
        internal const val NAME = "draft.name"
        internal const val CODE = "draft.code"
        internal const val CHECKED = "draft.checked"
    }
}
