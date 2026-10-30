package com.onejob.game.ui.lobby

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.onejob.game.data.ConnectionStatus
import com.onejob.game.data.GameRepository
import com.onejob.game.data.repository.CommandResult
import com.onejob.game.data.repository.ConnectionProblem
import com.onejob.game.data.repository.ConnectionState
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.launch

enum class LobbyOperation { READY, START, LEAVE, RETRY, PLAY_AGAIN, RETURN_TO_LOBBY }
enum class StartBlock { CONNECTION, SNAPSHOT, HOST_ONLY, TWO_PLAYERS, CONNECTED, READY, SERVER }
data class LobbyMemberUi(val id: String, val name: String, val connected: Boolean, val ready: Boolean, val host: Boolean, val local: Boolean)
data class LobbyUiState(
    val connection: ConnectionState,
    val keepLobby: Boolean = false,
    val roomCode: String? = null,
    val members: List<LobbyMemberUi> = emptyList(),
    val localReady: Boolean = false,
    val canReady: Boolean = false,
    val canStart: Boolean = false,
    val startBlock: StartBlock? = StartBlock.SNAPSHOT,
    val pending: LobbyOperation? = null,
    val confirmLeave: Boolean = false,
    val feedback: LobbyFeedback? = null,
    val canPlayAgain: Boolean = false,
    val canReturnToLobby: Boolean = false,
)

/** Presentation only. The repository/server own membership, readiness and permission. */
class LobbyViewModel(private val repository: GameRepository) : ViewModel() {
    private var admitted = repository.session.value.identity != null || repository.connection.value.status == ConnectionStatus.RECONNECTING
    private var leaving = false
    private var pending: LobbyOperation? = null
    private var confirmLeave = false
    private var feedback: LobbyFeedback? = null
    private var commandEpoch = 0L
    private val _ui = MutableStateFlow(render())
    val uiState = _ui.asStateFlow()

    init {
        viewModelScope.launch {
            combine(repository.connection, repository.session) { connection, session -> connection to session }
                .collect { refresh() }
        }
    }

    fun toggleReady() {
        if (!_ui.value.canReady) return
        command(LobbyOperation.READY) { repository.setReady(!_ui.value.localReady) }
    }
    fun start() {
        if (!_ui.value.canStart) return
        command(LobbyOperation.START) { repository.start() }
    }
    fun playAgain() {
        if (_ui.value.canPlayAgain) command(LobbyOperation.PLAY_AGAIN) { repository.playAgain() }
    }
    fun returnToLobby() {
        if (_ui.value.canReturnToLobby) command(LobbyOperation.RETURN_TO_LOBBY) { repository.returnToLobby() }
    }
    fun retry() {
        if (pending != null) return
        command(LobbyOperation.RETRY) { repository.connect() }
    }
    fun askLeave() { if (pending != LobbyOperation.LEAVE) { confirmLeave = true; refresh() } }
    fun dismissLeave() { confirmLeave = false; refresh() }
    fun confirmLeave() {
        if (!confirmLeave || pending == LobbyOperation.LEAVE) return
        // An in-flight command may already have happened; leave never resends it.
        confirmLeave = false
        leaving = true
        commandEpoch++
        pending = LobbyOperation.LEAVE
        refresh()
        viewModelScope.launch {
            val result = repository.leave()
            feedback = if (result is CommandResult.Accepted) LobbyFeedback.LEFT else LobbyFeedback.LEFT_UNCERTAIN
            pending = null
            admitted = false
            leaving = false
            refresh()
        }
    }
    private fun command(operation: LobbyOperation, action: suspend () -> CommandResult) {
        if (pending != null) return
        pending = operation
        val epoch = ++commandEpoch
        feedback = null
        refresh()
        viewModelScope.launch {
            val result = action()
            // A completed earlier command must not overwrite leave feedback/pending.
            if (commandEpoch == epoch) {
                pending = null
                feedback = result.feedback()
                refresh()
            }
        }
    }
    private fun refresh() { _ui.value = render() }
    private fun render(): LobbyUiState {
        val connection = repository.connection.value
        val session = repository.session.value
        if (session.identity != null && !admitted && !leaving) feedback = null
        when {
            leaving -> admitted = false
            session.identity != null -> admitted = true
            connection.status in setOf(ConnectionStatus.SESSION_EXPIRED, ConnectionStatus.DISCONNECTED, ConnectionStatus.PROTOCOL_ERROR) -> admitted = false
            connection.problem in setOf(ConnectionProblem.ADMISSION_REQUIRED, ConnectionProblem.CONFIGURATION) -> admitted = false
            connection.status == ConnectionStatus.RECONNECTING || connection.problem == ConnectionProblem.RECONNECT_EXHAUSTED -> admitted = true
        }
        val identity = session.identity
        val lobby = session.lobby
        val connected = connection.status == ConnectionStatus.CONNECTED && lobby != null && identity != null
        val members = lobby?.players.orEmpty().map {
            LobbyMemberUi(it.player_id, it.name, it.connected, it.ready, it.player_id == lobby?.host_player_id, it.player_id == identity?.playerId)
        }
        val local = members.firstOrNull { it.local }
        val host = local?.host == true
        val block = when {
            connection.status != ConnectionStatus.CONNECTED -> StartBlock.CONNECTION
            lobby == null || local == null -> StartBlock.SNAPSHOT
            !host -> StartBlock.HOST_ONLY
            members.size < 2 -> StartBlock.TWO_PLAYERS
            members.any { !it.connected } -> StartBlock.CONNECTED
            members.any { !it.ready } -> StartBlock.READY
            !lobby.can_start || lobby.stage !in setOf("lobby", "finished", "aborted") -> StartBlock.SERVER
            else -> null
        }
        val notice = if (connection.status == ConnectionStatus.SESSION_EXPIRED) LobbyFeedback.EXPIRED else feedback
        return LobbyUiState(
            connection, admitted || pending == LobbyOperation.LEAVE, identity?.roomCode,
            members, local?.ready == true,
            connected && lobby?.stage in setOf("lobby", "finished", "aborted") && local?.connected == true && pending == null && !leaving,
            connected && host && lobby?.can_start == true && lobby.stage == "lobby" && pending == null && !leaving,
            block, pending, confirmLeave, notice,
            connected && host && lobby?.stage in setOf("finished", "aborted") && lobby?.can_start == true && pending == null && !leaving,
            connected && host && lobby?.stage in setOf("finished", "aborted") && pending == null && !leaving,
        )
    }
}
