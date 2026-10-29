package com.onejob.game.ui.roles

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.onejob.game.data.ConnectionStatus
import com.onejob.game.data.GameRepository
import com.onejob.game.data.protocol.RoleInstruction
import com.onejob.game.data.protocol.StationRole
import com.onejob.game.data.repository.ConnectionState
import com.onejob.game.ui.lobby.LobbyFeedback
import com.onejob.game.ui.lobby.feedback
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.launch

data class RoleUiState(
    val connection: ConnectionState,
    val roomCode: String? = null,
    val roundId: String? = null,
    val instructions: List<RoleInstruction> = emptyList(),
    val selected: StationRole? = null,
    val read: Set<StationRole> = emptySet(),
    val pending: Boolean = false,
    val acknowledged: Boolean = false,
    val held: Boolean = false,
    val paused: Boolean = false,
    val abortReason: String? = null,
    val waitingCount: Int = 0,
    val canRead: Boolean = false,
    val canAcknowledge: Boolean = false,
    val feedback: LobbyFeedback? = null,
)

/** Only metadata already allowlisted by the server/repository reaches this presentation. */
class RoleViewModel(private val repository: GameRepository) : ViewModel() {
    private var roundId: String? = null
    private var selected: StationRole? = null
    private var read = emptySet<StationRole>()
    private var pending = false
    private var feedback: LobbyFeedback? = null
    private var epoch = 0L
    private val _ui = MutableStateFlow(render())
    val uiState = _ui.asStateFlow()
    init {
        viewModelScope.launch {
            combine(repository.connection, repository.session) { connection, session -> connection to session }
                .collect { refresh() }
        }
    }
    fun select(role: StationRole) {
        if (_ui.value.instructions.any { it.role == role }) { selected = role; refresh() }
    }
    fun confirmRead() {
        val role = selected ?: return
        if (!_ui.value.canRead) return
        read = read + role
        refresh()
    }
    fun acknowledge() {
        if (!_ui.value.canAcknowledge) return
        val id = _ui.value.roundId ?: return
        val requestEpoch = ++epoch
        pending = true
        feedback = null
        refresh()
        viewModelScope.launch {
            val result = repository.acknowledgeBriefing(id)
            if (requestEpoch == epoch && id == roundId) {
                pending = false
                feedback = result.feedback()
                refresh()
            }
        }
    }
    private fun refresh() { _ui.value = render() }
    private fun render(): RoleUiState {
        val connection = repository.connection.value
        val session = repository.session.value
        val assigned = session.assigned
        val state = session.roleState
        if (connection.status != ConnectionStatus.CONNECTED || assigned == null || state == null ||
            assigned.instructions.map { it.role } != assigned.roles ||
            assigned.round_id != state.public.round_id || assigned.roles.toSet() != state.stations.roles().toSet()) {
            if (selected != null || pending || read.isNotEmpty()) epoch++
            selected = null; read = emptySet(); pending = false
            return RoleUiState(connection, session.identity?.roomCode)
        }
        if (roundId != assigned.round_id) {
            epoch++; roundId = assigned.round_id; read = emptySet(); feedback = null; pending = false
        }
        if (selected !in assigned.roles) selected = assigned.roles.first()
        val active = state.public.stage == "briefing" && !state.briefing.acknowledged && !state.briefing.complete && !pending
        return RoleUiState(
            connection, session.identity?.roomCode, roundId, assigned.instructions, selected,
            read, pending, state.briefing.acknowledged, state.briefing.held_for_gameplay,
            state.public.stage == "paused", state.public.result?.reason,
            state.briefing.waiting_player_ids.size,
            active && selected !in read, active && read.containsAll(assigned.roles), feedback,
        )
    }
}
