@file:kotlinx.serialization.UseSerializers(
    com.onejob.game.data.protocol.StrictStringSerializer::class,
    com.onejob.game.data.protocol.StrictIntSerializer::class,
    com.onejob.game.data.protocol.StrictLongSerializer::class,
    com.onejob.game.data.protocol.StrictBooleanSerializer::class,
)

package com.onejob.game.data.protocol

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

@Serializable data class NoncePayload(val nonce: String)
@Serializable data class NamePayload(val name: String)
@Serializable data class JoinPayload(val room_code: String, val name: String)
@Serializable data class DisplayJoinPayload(val room_code: String)
@Serializable data class ReadyPayload(val ready: Boolean)
@Serializable class EmptyPayload
@Serializable data class ResumePayload(val resume_token: String) {
    override fun toString() = "ResumePayload(redacted)"
}

@Serializable
sealed class ClientMessage {
    val version: Int = 1
    abstract val request_id: String

    @Serializable @SerialName("ping")
    data class Ping(override val request_id: String, val payload: NoncePayload) : ClientMessage()
    @Serializable @SerialName("create_room")
    data class Create(override val request_id: String, val payload: NamePayload) : ClientMessage()
    @Serializable @SerialName("join_room")
    data class Join(override val request_id: String, val payload: JoinPayload) : ClientMessage()
    @Serializable @SerialName("join_display")
    data class JoinDisplay(override val request_id: String, val payload: DisplayJoinPayload) : ClientMessage()
    @Serializable @SerialName("resume_session")
    data class Resume(override val request_id: String, val payload: ResumePayload) : ClientMessage()
    @Serializable @SerialName("player_ready")
    data class Ready(override val request_id: String, val payload: ReadyPayload) : ClientMessage()
    @Serializable @SerialName("leave_room")
    data class Leave(override val request_id: String, val payload: EmptyPayload = EmptyPayload()) : ClientMessage()
    @Serializable @SerialName("request_state")
    data class State(override val request_id: String, val payload: EmptyPayload = EmptyPayload()) : ClientMessage()
    @Serializable @SerialName("start_game")
    data class Start(override val request_id: String, val payload: EmptyPayload = EmptyPayload()) : ClientMessage()
    @Serializable @SerialName("play_again")
    data class PlayAgain(override val request_id: String, val payload: EmptyPayload = EmptyPayload()) : ClientMessage()
    @Serializable @SerialName("return_to_lobby")
    data class ReturnToLobby(override val request_id: String, val payload: EmptyPayload = EmptyPayload()) : ClientMessage()
    @Serializable @SerialName("briefing_ready")
    data class Briefing(override val request_id: String, val payload: RoundPayload) : ClientMessage()
    @Serializable @SerialName("player_action")
    data class Action(override val request_id: String, val payload: ActionPayload) : ClientMessage()
}

@Serializable data class ActionPayload(val round_id: String, val client_action_seq: Long, val action: PlayerAction)

@Serializable sealed interface PlayerAction {
    @Serializable @SerialName("move_lane") data class MoveLane(val direction: Direction) : PlayerAction
    @Serializable @SerialName("evade") data object Evade : PlayerAction
    @Serializable @SerialName("set_engine_power") data class SetEnginePower(val value: Int) : PlayerAction
    @Serializable @SerialName("engine_boost") data object EngineBoost : PlayerAction
    @Serializable @SerialName("coolant") data object Coolant : PlayerAction
    @Serializable @SerialName("emergency_shutdown") data object EmergencyShutdown : PlayerAction
    @Serializable @SerialName("set_shield") data class SetShield(val active: Boolean, val facing: Facing) : PlayerAction
    @Serializable @SerialName("recharge_shield") data object RechargeShield : PlayerAction
    @Serializable @SerialName("shield_boost") data object ShieldBoost : PlayerAction
}
@Serializable enum class Direction { @SerialName("left") LEFT, @SerialName("right") RIGHT }
@Serializable enum class Facing {
    @SerialName("front") FRONT, @SerialName("left") LEFT,
    @SerialName("right") RIGHT, @SerialName("rear") REAR,
}

@Serializable data class SessionPayload(
    val room_code: String, val kind: String, val player_id: String?, val resume_token: String,
) { override fun toString() = "SessionPayload(redacted)" }
@Serializable data class AckPayload(val operation: String, val client_action_seq: Long? = null, val applied_tick: Long? = null)
@Serializable data class ErrorPayload(val code: String, val message: String, val retryable: Boolean) {
    override fun toString() = "ErrorPayload(redacted)"
}
@Serializable data class ActionRejectedPayload(
    val code: String, val message: String, val client_action_seq: Long, val round_id: String,
) { override fun toString() = "ActionRejectedPayload(redacted)" }
@Serializable data class LobbyPlayer(val player_id: String, val name: String, val connected: Boolean, val ready: Boolean)
@Serializable data class LobbyPayload(
    val room_code: String, val stage: String, val host_player_id: String?,
    val players: List<LobbyPlayer>, val can_start: Boolean,
)
@Serializable data class PublicPayload(val public: PublicRound?)
@Serializable data class PublicRound(
    val round_id: String, val stage: String, val tick_index: Long, val remaining_ms: Long,
    val countdown_remaining_ms: Long?, val paused_from: String?, val hull_percent: Int,
    val shield_percent: Int, val warnings: List<PublicWarning>, val result: RoundResult?,
)
@Serializable data class PublicWarning(val emergency_id: Long, val kind: String, val label: String)
@Serializable data class EmergencyEventPayload(
    val round_id: String, val emergency_id: Long, val kind: String, val status: String,
)
@Serializable data class GameOverPayload(val round_id: String, val result: RoundResult)
@Serializable data class ResultPlayer(val player_id: String, val name: String)
@Serializable data class RoundResult(
    val outcome: String, val reason: String, val survived_ms: Long, val final_hull_percent: Int,
    val resolved_count: Long, val failed_count: Long, val players: List<ResultPlayer>,
)

@Serializable sealed interface ServerMessage {
    val version: Int
    val reply_to: String?
    val room_revision: Long?

    @Serializable @SerialName("pong") data class Pong(
        override val version: Int, override val reply_to: String?, override val room_revision: Long?, val payload: NoncePayload,
    ) : ServerMessage
    @Serializable @SerialName("session_accepted") data class SessionAccepted(
        override val version: Int, override val reply_to: String?, override val room_revision: Long?, val payload: SessionPayload,
    ) : ServerMessage
    @Serializable @SerialName("ack") data class Ack(
        override val version: Int, override val reply_to: String?, override val room_revision: Long?, val payload: AckPayload,
    ) : ServerMessage
    @Serializable @SerialName("action_rejected") data class ActionRejected(
        override val version: Int, override val reply_to: String?, override val room_revision: Long?, val payload: ActionRejectedPayload,
    ) : ServerMessage
    @Serializable @SerialName("error") data class Error(
        override val version: Int, override val reply_to: String?, override val room_revision: Long?, val payload: ErrorPayload,
    ) : ServerMessage
    @Serializable @SerialName("lobby_state") data class Lobby(
        override val version: Int, override val reply_to: String?, override val room_revision: Long?, val payload: LobbyPayload,
    ) : ServerMessage
    @Serializable @SerialName("public_state") data class PublicState(
        override val version: Int, override val reply_to: String?, override val room_revision: Long?, val payload: PublicPayload,
    ) : ServerMessage
    @Serializable @SerialName("role_assigned") data class RoleAssigned(
        override val version: Int, override val reply_to: String?, override val room_revision: Long?, val payload: RoleAssignedPayload,
    ) : ServerMessage
    @Serializable @SerialName("role_state") data class RoleState(
        override val version: Int, override val reply_to: String?, override val room_revision: Long?, val payload: RoleStatePayload,
    ) : ServerMessage
    @Serializable @SerialName("emergency_event") data class EmergencyEvent(
        override val version: Int, override val reply_to: String?, override val room_revision: Long?, val payload: EmergencyEventPayload,
    ) : ServerMessage
    @Serializable @SerialName("game_over") data class GameOver(
        override val version: Int, override val reply_to: String?, override val room_revision: Long?, val payload: GameOverPayload,
    ) : ServerMessage
}
