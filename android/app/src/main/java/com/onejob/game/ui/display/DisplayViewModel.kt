package com.onejob.game.ui.display

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.onejob.game.data.ConnectionStatus
import com.onejob.game.data.GameRepository
import com.onejob.game.data.protocol.LobbyPayload
import com.onejob.game.data.protocol.PublicRound
import com.onejob.game.data.repository.ConnectionState
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.launch

/** Public DTOs only: this presentation model cannot supply a station control. */
data class DisplayUiState(
    val connection: ConnectionState = ConnectionState(),
    val roomCode: String? = null,
    val lobby: LobbyPayload? = null,
    val public: PublicRound? = null,
    val restored: Boolean = false,
)

class DisplayViewModel(private val repository: GameRepository) : ViewModel() {
    private val _ui = MutableStateFlow(render())
    val uiState = _ui.asStateFlow()
    init {
        viewModelScope.launch {
            combine(repository.connection, repository.session) { _, _ -> render() }
                .collect { _ui.value = it }
        }
    }
    private fun render(): DisplayUiState {
        val session = repository.session.value
        val connection = repository.connection.value
        val ready = connection.status == ConnectionStatus.CONNECTED &&
            session.identity?.kind == "display" && session.publicSnapshotReceived && session.lobby != null
        return DisplayUiState(connection, session.identity?.roomCode,
            session.lobby.takeIf { ready }, session.publicRound.takeIf { ready }, ready)
    }
}
