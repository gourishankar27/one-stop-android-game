package com.onejob.game

import com.onejob.game.data.ConnectionStatus
import com.onejob.game.data.GameRepository
import com.onejob.game.data.UnavailableGameRepository
import com.onejob.game.data.protocol.LobbyPayload
import com.onejob.game.data.protocol.LobbyPlayer
import com.onejob.game.data.repository.*
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.flow.MutableStateFlow

class LobbyTestRepository : GameRepository by UnavailableGameRepository() {
    override val connection = MutableStateFlow(ConnectionState(ConnectionStatus.DISCONNECTED))
    override val session = MutableStateFlow(SessionState())
    var admission = CompletableDeferred<CommandResult>()
    var admissionCalls = 0
    var submittedName = ""
    var submittedCode = ""
    var disconnects = 0
    var leaves = 0
    var starts = 0
    var playAgains = 0
    var returns = 0
    var lifecycleResult = CompletableDeferred<CommandResult>().apply { complete(CommandResult.Accepted("again", Operation.PLAY_AGAIN)) }
    var leaveResult: CommandResult = CommandResult.Accepted("leave", Operation.LEAVE)
    val ready = mutableListOf<Boolean>()
    var readyResult = CompletableDeferred<CommandResult>().apply { complete(CommandResult.Accepted("ready", Operation.READY)) }
    override suspend fun create(name: String): CommandResult { admissionCalls++; submittedName = name; return admission.await() }
    override suspend fun join(roomCode: String, name: String): CommandResult { submittedCode = roomCode; return create(name) }
    override suspend fun joinDisplay(roomCode: String): CommandResult { submittedCode = roomCode; return create("") }
    override suspend fun setReady(ready: Boolean): CommandResult { this.ready += ready; return readyResult.await() }
    override suspend fun start(): CommandResult { starts++; return CommandResult.Rejected("start", RemoteCode.FEATURE_UNAVAILABLE) }
    override suspend fun playAgain(): CommandResult { playAgains++; return lifecycleResult.await() }
    override suspend fun returnToLobby(): CommandResult { returns++; return lifecycleResult.await() }
    override suspend fun leave(): CommandResult {
        leaves++; session.value = SessionState(); connection.value = ConnectionState(ConnectionStatus.DISCONNECTED)
        return leaveResult
    }
    override suspend fun disconnect(): CommandResult {
        disconnects++; session.value = SessionState(); connection.value = ConnectionState(ConnectionStatus.DISCONNECTED)
        return CommandResult.LeftLocally
    }
    fun seed(host: Boolean = true, allReady: Boolean = false, count: Int = 2, canStart: Boolean = allReady) {
        val ids = (1..count).map { "00000000-0000-0000-0000-00000000000$it" }
        val players = ids.map { LobbyPlayer(it, "Crew", true, allReady) }
        session.value = SessionState(SessionIdentity("ABCD23", ids.first()), LobbyPayload("ABCD23", "lobby", ids[if (host) 0 else 1], players, canStart))
        connection.value = ConnectionState(ConnectionStatus.CONNECTED)
    }
}
