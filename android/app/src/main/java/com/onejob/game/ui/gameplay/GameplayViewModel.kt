package com.onejob.game.ui.gameplay

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.onejob.game.data.ConnectionStatus
import com.onejob.game.data.GameRepository
import com.onejob.game.data.protocol.*
import com.onejob.game.data.repository.CommandResult
import com.onejob.game.data.repository.ConnectionState
import com.onejob.game.data.repository.RemoteCode
import kotlinx.coroutines.channels.Channel
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.launch

enum class ActionFeedback { ACCEPTED, POWER, COOLDOWN, INVALID, STALE, NOT_OWNED, UNCERTAIN, NOT_SENT }

data class GameplayUiState(
    val connection: ConnectionState,
    val roomCode: String? = null,
    val snapshot: RoleStatePayload? = null,
    val instructions: List<RoleInstruction> = emptyList(),
    val selected: StationRole? = null,
    val pending: Set<String> = emptySet(),
    val outputDraft: Int? = null,
    val feedback: ActionFeedback? = null,
    val canControl: Boolean = false,
    val emergencyEvent: EmergencyEventPayload? = null,
)

/** Presentation and bounded intents only. All resource arithmetic stays on the server. */
class GameplayViewModel(
    private val repository: GameRepository,
    private val now: () -> Long = { System.nanoTime() / 1_000_000 },
) : ViewModel() {
    private data class Output(val epoch: Long, val generation: Long, val round: String, val value: Int)
    private val output = Channel<Output>(Channel.CONFLATED)
    private var outputGeneration = 0L
    private var epoch = 0L
    private var availability: String? = null
    private var round: String? = null
    private var selected: StationRole? = null
    private var pending = emptySet<String>()
    private var draft: Int? = null
    private var feedback: ActionFeedback? = null
    private val _ui = MutableStateFlow(GameplayUiState(repository.connection.value))
    val uiState = _ui.asStateFlow()

    init {
        viewModelScope.launch {
            combine(repository.connection, repository.session) { connection, session -> connection to session }
                .collect { refresh() }
        }
        viewModelScope.launch {
            var lastSent: Long? = null
            for (first in output) {
                lastSent?.let { delay((100 - (now() - it)).coerceAtLeast(0)) }
                var latest = first
                while (true) latest = output.tryReceive().getOrNull() ?: break
                if (latest.epoch != epoch || latest.generation != outputGeneration ||
                    latest.round != round || !canUse(StationRole.ENGINEER)) continue
                lastSent = now()
                pending = pending + "output"
                refresh()
                send(PlayerAction.SetEnginePower(latest.value), "output", latest.epoch)
                if (latest.epoch == epoch && latest.generation == outputGeneration && draft == latest.value) {
                    draft = null
                    refresh()
                }
            }
        }
    }

    fun select(role: StationRole) {
        if (_ui.value.instructions.any { it.role == role }) { selected = role; refresh() }
    }

    fun setOutput(value: Int) {
        if (value !in 0..100 || !canUse(StationRole.ENGINEER) || "shutdown" in pending) return
        draft = value
        output.trySend(Output(epoch, outputGeneration, round ?: return, value))
        refresh()
    }

    fun act(action: PlayerAction) {
        if (action is PlayerAction.SetEnginePower) { setOutput(action.value); return }
        val (role, key) = action.identity()
        if (!canUse(role) || key in pending) return
        if (action == PlayerAction.EmergencyShutdown) {
            outputGeneration++
            while (output.tryReceive().isSuccess) { /* discard output queued before shutdown */ }
            draft = null
        }
        val requestEpoch = epoch
        pending = pending + key
        feedback = null
        refresh()
        viewModelScope.launch { send(action, key, requestEpoch) }
    }

    private fun canUse(role: StationRole) = _ui.value.canControl &&
        _ui.value.instructions.any { it.role == role }

    private suspend fun send(action: PlayerAction, key: String, requestEpoch: Long) {
        val id = round ?: return
        if (requestEpoch != epoch) return
        val result = repository.performAction(id, action)
        if (requestEpoch != epoch || id != round) return
        pending = pending - key
        feedback = when (result) {
            is CommandResult.Accepted -> ActionFeedback.ACCEPTED
            is CommandResult.Uncertain -> ActionFeedback.UNCERTAIN
            is CommandResult.Rejected -> when (result.code) {
                RemoteCode.INSUFFICIENT_POWER -> ActionFeedback.POWER
                RemoteCode.COOLDOWN -> ActionFeedback.COOLDOWN
                RemoteCode.NOT_ROLE_OWNER -> ActionFeedback.NOT_OWNED
                RemoteCode.STALE_ACTION, RemoteCode.STALE_ROUND -> ActionFeedback.STALE
                else -> ActionFeedback.INVALID
            }
            else -> ActionFeedback.NOT_SENT
        }
        refresh()
    }

    private fun refresh() {
        val connection = repository.connection.value
        val session = repository.session.value
        val assigned = session.assigned
        val state = session.roleState
        val valid = connection.status == ConnectionStatus.CONNECTED && assigned != null && state != null &&
            assigned.round_id == state.public.round_id &&
            assigned.instructions.map { it.role } == assigned.roles &&
            assigned.roles.toSet() == state.stations.roles().toSet()
        val key = if (valid) "${assigned!!.round_id}/${state!!.public.stage}" else null
        if (availability != key) {
            availability = key
            epoch++
            outputGeneration++
            while (output.tryReceive().isSuccess) { /* never replay stale input after recovery */ }
            pending = emptySet(); draft = null; feedback = null
        }
        if (!valid) {
            selected = null
            _ui.value = GameplayUiState(connection, session.identity?.roomCode)
            return
        }
        assigned!!; state!!
        if (round != assigned.round_id) round = assigned.round_id
        if (selected !in assigned.roles) selected = assigned.roles.first()
        _ui.value = GameplayUiState(connection, session.identity?.roomCode, state,
            assigned.instructions, selected, pending, draft, feedback,
            state.public.stage == "running",
            session.emergencyEvent?.takeIf { it.round_id == state.public.round_id })
    }

    override fun onCleared() { output.close() }
}

private fun PlayerAction.identity(): Pair<StationRole, String> = when (this) {
    is PlayerAction.MoveLane -> StationRole.PILOT to "move"
    PlayerAction.Evade -> StationRole.PILOT to "evade"
    is PlayerAction.SetEnginePower -> StationRole.ENGINEER to "output"
    PlayerAction.EngineBoost -> StationRole.ENGINEER to "engineBoost"
    PlayerAction.Coolant -> StationRole.ENGINEER to "coolant"
    PlayerAction.EmergencyShutdown -> StationRole.ENGINEER to "shutdown"
    is PlayerAction.SetShield -> StationRole.SHIELDS to "shield"
    PlayerAction.RechargeShield -> StationRole.SHIELDS to "recharge"
    PlayerAction.ShieldBoost -> StationRole.SHIELDS to "shieldBoost"
}
