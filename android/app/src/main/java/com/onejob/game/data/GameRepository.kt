package com.onejob.game.data

import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow

enum class ConnectionStatus {
    UNAVAILABLE,
    CONNECTING,
    CONNECTED,
    RECONNECTING,
    SESSION_EXPIRED,
}

/** Client connection state only. Authoritative session snapshots arrive with networking. */
interface GameRepository {
    val connectionStatus: StateFlow<ConnectionStatus>
}

/** The foundation has no transport or commands to create/join a room. */
class UnavailableGameRepository : GameRepository {
    override val connectionStatus: StateFlow<ConnectionStatus> =
        MutableStateFlow(ConnectionStatus.UNAVAILABLE).asStateFlow()
}
