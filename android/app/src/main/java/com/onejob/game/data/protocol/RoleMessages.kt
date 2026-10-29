@file:kotlinx.serialization.UseSerializers(
    com.onejob.game.data.protocol.StrictStringSerializer::class,
    com.onejob.game.data.protocol.StrictIntSerializer::class,
    com.onejob.game.data.protocol.StrictLongSerializer::class,
    com.onejob.game.data.protocol.StrictBooleanSerializer::class,
)

package com.onejob.game.data.protocol

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

@Serializable enum class StationRole {
    @SerialName("pilot") PILOT, @SerialName("engineer") ENGINEER, @SerialName("shields") SHIELDS,
}
@Serializable enum class LaneValue {
    @SerialName("left") LEFT, @SerialName("center") CENTER, @SerialName("right") RIGHT,
}
@Serializable data class RoundPayload(val round_id: String)
@Serializable data class RoleInstruction(val role: StationRole, val title: String, val steps: List<String>) {
    override fun toString() = "RoleInstruction(redacted)"
}
@Serializable data class RoleAssignedPayload(val round_id: String, val roles: List<StationRole>, val instructions: List<RoleInstruction>) {
    override fun toString() = "RoleAssignedPayload(redacted)"
}
@Serializable data class PilotCooldowns(val move_lane: Long, val evade: Long)
@Serializable data class EngineerCooldowns(val engine_boost: Long, val coolant: Long)
@Serializable data class ShieldsCooldowns(val recharge_shield: Long, val shield_boost: Long)
@Serializable data class PilotHazard(val emergency_id: Long, val impact_lane: LaneValue, val deadline_remaining_ms: Long)
@Serializable data class EngineerInstruction(val emergency_id: Long, val target_max_output: Int?, val target_max_temperature: Int?, val deadline_remaining_ms: Long)
@Serializable data class ShieldsInstruction(val emergency_id: Long, val required_facing: Facing?, val deactivate: Boolean, val deadline_remaining_ms: Long)
@Serializable data class PilotView(val lane: LaneValue, val maneuver_ready: Boolean, val evade_remaining_ticks: Long, val cooldowns: PilotCooldowns, val hazards: List<PilotHazard>) {
    override fun toString() = "PilotView(redacted)"
}
@Serializable data class EngineerView(val output: Int, val temperature: Int, val available_power: Int, val cooldowns: EngineerCooldowns, val boost_remaining_ticks: Long, val instructions: List<EngineerInstruction>) {
    override fun toString() = "EngineerView(redacted)"
}
@Serializable data class ShieldsView(val energy: Int, val active: Boolean, val facing: Facing, val cooldowns: ShieldsCooldowns, val recharge_remaining_ticks: Long, val boost_remaining_ticks: Long, val instructions: List<ShieldsInstruction>) {
    override fun toString() = "ShieldsView(redacted)"
}
@Serializable data class OwnedStations(val pilot: PilotView? = null, val engineer: EngineerView? = null, val shields: ShieldsView? = null) {
    fun roles() = listOfNotNull(if (pilot != null) StationRole.PILOT else null, if (engineer != null) StationRole.ENGINEER else null, if (shields != null) StationRole.SHIELDS else null)
    override fun toString() = "OwnedStations(redacted)"
}
@Serializable data class BriefingStatus(val acknowledged: Boolean, val waiting_player_ids: List<String>, val remaining_ms: Long, val complete: Boolean, val held_for_gameplay: Boolean)
@Serializable data class RoleStatePayload(val public: PublicRound, val stations: OwnedStations, val briefing: BriefingStatus) {
    override fun toString() = "RoleStatePayload(redacted)"
}
