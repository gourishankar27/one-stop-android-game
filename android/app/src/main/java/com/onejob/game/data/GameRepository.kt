package com.onejob.game.data

import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import com.onejob.game.data.protocol.PlayerAction
import com.onejob.game.data.repository.CommandResult
import com.onejob.game.data.repository.ConnectionProblem
import com.onejob.game.data.repository.ConnectionState
import com.onejob.game.data.repository.SessionState
import java.io.Closeable

enum class ConnectionStatus {
    UNAVAILABLE,
    CONNECTING,
    CONNECTED,
    RECONNECTING,
    SESSION_EXPIRED,
    DISCONNECTED,
    PROTOCOL_ERROR,
}

/** Typed client intents and allowlisted authoritative snapshots; no client simulation. */
interface GameRepository : Closeable {
    val connectionStatus: StateFlow<ConnectionStatus>
    val connection: StateFlow<ConnectionState>
    val session: StateFlow<SessionState>
    suspend fun connect(): CommandResult
    suspend fun ping(): CommandResult
    suspend fun create(name: String): CommandResult
    suspend fun join(roomCode: String, name: String): CommandResult
    suspend fun setReady(ready: Boolean): CommandResult
    suspend fun start(): CommandResult
    suspend fun requestState(): CommandResult
    suspend fun acknowledgeBriefing(roundId: String): CommandResult
    suspend fun submitAction(roundId: String, sequence: Long, action: PlayerAction): CommandResult
    suspend fun leave(): CommandResult
    suspend fun disconnect(): CommandResult
}

/** Explicit unavailable implementation for previews, tests and unconfigured callers. */
class UnavailableGameRepository : GameRepository {
    override val connectionStatus: StateFlow<ConnectionStatus> =
        MutableStateFlow(ConnectionStatus.UNAVAILABLE).asStateFlow()
    override val connection = MutableStateFlow(ConnectionState(ConnectionStatus.UNAVAILABLE, ConnectionProblem.CONFIGURATION)).asStateFlow()
    override val session = MutableStateFlow(SessionState()).asStateFlow()
    private fun unavailable() = CommandResult.NotSent(ConnectionProblem.CONFIGURATION)
    override suspend fun connect() = unavailable()
    override suspend fun ping() = unavailable()
    override suspend fun create(name: String) = unavailable()
    override suspend fun join(roomCode: String, name: String) = unavailable()
    override suspend fun setReady(ready: Boolean) = unavailable()
    override suspend fun start() = unavailable()
    override suspend fun requestState() = unavailable()
    override suspend fun acknowledgeBriefing(roundId: String) = unavailable()
    override suspend fun submitAction(roundId: String, sequence: Long, action: PlayerAction) = unavailable()
    override suspend fun leave() = unavailable()
    override suspend fun disconnect() = unavailable()
    override fun close() = Unit
}
