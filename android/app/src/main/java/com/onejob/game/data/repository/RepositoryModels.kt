package com.onejob.game.data.repository

import com.onejob.game.data.ConnectionStatus
import com.onejob.game.data.network.Endpoint
import com.onejob.game.data.protocol.LobbyPayload
import com.onejob.game.data.protocol.PublicRound
import com.onejob.game.data.protocol.RoleAssignedPayload
import com.onejob.game.data.protocol.RoleStatePayload
import com.onejob.game.data.protocol.EmergencyEventPayload

enum class Operation { CONNECT, PING, CREATE, JOIN, JOIN_DISPLAY, RESUME, READY, START, STATE, LEAVE, ACTION, BRIEFING, PLAY_AGAIN, RETURN_TO_LOBBY }
enum class ConnectionProblem {
    CONFIGURATION, NETWORK, BACKPRESSURE, COMMAND_UNCERTAIN, HEARTBEAT_TIMEOUT,
    PROTOCOL, UNSUPPORTED_VERSION, RECONNECT_EXHAUSTED, ADMISSION_REQUIRED, SNAPSHOT_TIMEOUT,
}
enum class RemoteCode {
    INVALID_MESSAGE, UNSUPPORTED_VERSION, UNKNOWN_TYPE, NOT_AUTHENTICATED, ROOM_NOT_FOUND,
    ROOM_FULL, DISPLAY_FULL, NOT_CONTROLLER, ROOM_STARTED, CAPACITY, NOT_HOST, NOT_READY, INVALID_STAGE, INVALID_ACTION,
    NOT_ROLE_OWNER, INSUFFICIENT_POWER, COOLDOWN, STALE_ROUND, STALE_ACTION,
    REQUEST_ID_CONFLICT, RATE_LIMITED, SESSION_EXPIRED, FEATURE_UNAVAILABLE, INTERNAL_ERROR, UNKNOWN;

    companion object {
        fun fromWire(value: String) = entries.firstOrNull { it.name.lowercase() == value } ?: UNKNOWN
    }
}

data class ConnectionState(
    val status: ConnectionStatus = ConnectionStatus.DISCONNECTED,
    val problem: ConnectionProblem? = null,
    val retryAttempt: Int = 0,
)
data class SessionIdentity(val roomCode: String, val playerId: String?, val kind: String = "player")
/** Local receipt of a validated, correlated server reply; no replay or game authority. */
data class ActionReceipt(val roundId: String, val sequence: Long, val accepted: Boolean)
data class SessionState(
    val identity: SessionIdentity? = null,
    val lobby: LobbyPayload? = null,
    val publicRound: PublicRound? = null,
    val assigned: RoleAssignedPayload? = null,
    val roleState: RoleStatePayload? = null,
    val emergencyEvent: EmergencyEventPayload? = null,
    val publicSnapshotReceived: Boolean = false,
)

sealed interface CommandResult {
    data object LeftLocally : CommandResult
    data class Accepted(val requestId: String, val operation: Operation, val revision: Long? = null,
                        val sequence: Long? = null, val appliedTick: Long? = null) : CommandResult
    data class Rejected(val requestId: String, val code: RemoteCode) : CommandResult
    data class Uncertain(val requestId: String, val operation: Operation) : CommandResult
    data class NotSent(val problem: ConnectionProblem) : CommandResult
}

/** Never placed into UI state, navigation, saved state or diagnostic output. */
internal class Credential(val endpoint: Endpoint, val identity: SessionIdentity, val token: String) {
    override fun toString() = "Credential(redacted)"
}
internal class MemoryCredentialStore {
    var value: Credential? = null
        private set
    fun save(credential: Credential) { value = credential }
    fun clear() { value = null }
    override fun toString() = "MemoryCredentialStore(redacted)"
}

/** Equal revision is allowed for distinct kinds. A new round retires previously seen rounds. */
internal class RevisionGate {
    private val revisions = mutableMapOf<String, Long>()
    private val roomRevisions = mutableMapOf<String, Long>()
    private var activeRound: String? = null
    private val retiredRounds = ArrayDeque<String>()
    fun accept(kind: String, room: String, round: String?, revision: Long): Boolean {
        if (revision < (roomRevisions[room] ?: -1)) return false
        if (round != null) {
            if (round in retiredRounds) return false
            if (activeRound != null && activeRound != round) {
                retiredRounds.addLast(activeRound!!)
                if (retiredRounds.size > 16) retiredRounds.removeFirst()
            }
            activeRound = round
        }
        val key = "$kind/$room/${round.orEmpty()}"
        val previous = revisions[key]
        if (previous != null && revision <= previous) return false
        revisions[key] = revision
        roomRevisions[room] = revision
        if (roomRevisions.size > 8) roomRevisions.remove(roomRevisions.keys.first())
        if (revisions.size > 32) revisions.remove(revisions.keys.first())
        return true
    }
    fun clear() { revisions.clear(); roomRevisions.clear(); activeRound = null; retiredRounds.clear() }
    fun retireRound() {
        activeRound?.let {
            retiredRounds.addLast(it)
            if (retiredRounds.size > 16) retiredRounds.removeFirst()
        }
        activeRound = null
    }
}
