package com.onejob.game.data.protocol

import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.decodeFromJsonElement
import kotlinx.serialization.json.intOrNull
import kotlinx.serialization.json.jsonObject

enum class ProtocolIssue { MALFORMED, UNSUPPORTED_VERSION, UNKNOWN_TYPE, OVERSIZE }
sealed interface DecodedFrame {
    data class Message(val message: ServerMessage) : DecodedFrame
    data class Invalid(val issue: ProtocolIssue) : DecodedFrame
}

class ProtocolCodec {
    val json = Json {
        classDiscriminator = "type"
        ignoreUnknownKeys = true
        isLenient = false
        coerceInputValues = false
        encodeDefaults = true
        explicitNulls = true
    }

    fun encode(message: ClientMessage): String {
        require(message.version == 1) { "Unsupported version" }
        require(requestId.matches(message.request_id)) { "Invalid request identifier" }
        when (message) {
            is ClientMessage.Ping -> require(scalarLength(message.payload.nonce) in 1..64)
            is ClientMessage.Create -> require(nameValid(message.payload.name))
            is ClientMessage.Join -> require(nameValid(message.payload.name) && code.matches(message.payload.room_code))
            is ClientMessage.JoinDisplay -> require(code.matches(message.payload.room_code))
            is ClientMessage.Resume -> require(scalarLength(message.payload.resume_token) in 1..256)
            is ClientMessage.Briefing -> require(uuid.matches(message.payload.round_id))
            is ClientMessage.Action -> {
                require(uuid.matches(message.payload.round_id) && message.payload.client_action_seq >= 1)
                val action = message.payload.action
                if (action is PlayerAction.SetEnginePower) require(action.value in 0..100)
            }
            else -> Unit
        }
        val text = json.encodeToString<ClientMessage>(message)
        require(text.toByteArray(Charsets.UTF_8).size <= MAX_FRAME_BYTES) { "Frame too large" }
        return text
    }

    fun decode(text: String): DecodedFrame {
        if (text.toByteArray(Charsets.UTF_8).size > MAX_FRAME_BYTES) return DecodedFrame.Invalid(ProtocolIssue.OVERSIZE)
        return try {
            if (!boundedUniqueJson(text)) return DecodedFrame.Invalid(ProtocolIssue.MALFORMED)
            val objectValue = json.parseToJsonElement(text) as? JsonObject
                ?: return DecodedFrame.Invalid(ProtocolIssue.MALFORMED)
            val version = objectValue["version"] as? JsonPrimitive
            if (version == null || version.isString || version.intOrNull == null) {
                return DecodedFrame.Invalid(ProtocolIssue.MALFORMED)
            }
            if (version.intOrNull != 1) return DecodedFrame.Invalid(ProtocolIssue.UNSUPPORTED_VERSION)
            val type = objectValue["type"] as? JsonPrimitive
            if (type == null || !type.isString) return DecodedFrame.Invalid(ProtocolIssue.MALFORMED)
            if (type.content !in serverKinds) return DecodedFrame.Invalid(ProtocolIssue.UNKNOWN_TYPE)
            if (type.content == "role_state") {
                val stations = objectValue.getValue("payload").jsonObject.getValue("stations").jsonObject
                require(stations.keys.all { it in setOf("pilot", "engineer", "shields") })
                require(stations.values.all { it is JsonObject })
            }
            val message = json.decodeFromJsonElement<ServerMessage>(objectValue)
            validate(message)
            DecodedFrame.Message(message)
        } catch (_: Exception) {
            // Serialization errors can contain input snippets. They never leave this boundary.
            DecodedFrame.Invalid(ProtocolIssue.MALFORMED)
        }
    }

    private fun validate(message: ServerMessage) {
        require(message.reply_to == null || requestId.matches(message.reply_to!!))
        require(message.room_revision == null || message.room_revision!! >= 0)
        when (message) {
            is ServerMessage.Pong -> require(scalarLength(message.payload.nonce) in 1..64 && message.reply_to != null)
            is ServerMessage.SessionAccepted -> {
                val payload = message.payload
                require(message.reply_to != null && message.room_revision != null)
                require(code.matches(payload.room_code))
                require(if (payload.kind == "display") payload.player_id == null
                    else payload.kind == "player" && payload.player_id?.let { uuid.matches(it) } == true)
                require(scalarLength(payload.resume_token) in 1..256)
            }
            is ServerMessage.Ack -> {
                require(message.reply_to != null && message.room_revision != null)
                if (message.payload.operation == "player_action") {
                    require((message.payload.client_action_seq ?: 0) >= 1 &&
                        (message.payload.applied_tick ?: -1) >= 0)
                } else require(message.payload.client_action_seq == null && message.payload.applied_tick == null)
            }
            is ServerMessage.ActionRejected -> {
                require(message.reply_to != null && message.room_revision != null)
                require(message.payload.client_action_seq >= 1 && uuid.matches(message.payload.round_id))
                require(message.payload.code.isNotBlank())
            }
            is ServerMessage.Error -> require(message.payload.code.isNotBlank())
            is ServerMessage.Lobby -> {
                val payload = message.payload
                require(message.room_revision != null && code.matches(payload.room_code) && payload.stage in stages)
                require(payload.players.size in 1..3)
                require(payload.players.all { uuid.matches(it.player_id) && nameValid(it.name) })
                val ids = payload.players.map { it.player_id }
                require(ids.toSet().size == ids.size)
                require(payload.host_player_id == null || payload.host_player_id in ids)
            }
            is ServerMessage.PublicState -> { require(message.room_revision != null); message.payload.public?.let(::validatePublic) }
            is ServerMessage.EmergencyEvent -> {
                require(message.reply_to == null && message.room_revision != null)
                require(uuid.matches(message.payload.round_id) && message.payload.emergency_id > 0)
                require(message.payload.kind in emergencyKinds && message.payload.status in setOf("started", "resolved", "failed"))
            }
            is ServerMessage.GameOver -> {
                require(message.reply_to == null && message.room_revision != null && uuid.matches(message.payload.round_id))
                validateResult(message.payload.result)
            }
            is ServerMessage.RoleAssigned -> {
                require(message.reply_to == null)
                val assigned = message.payload
                require(message.room_revision != null && uuid.matches(assigned.round_id))
                require(validOwnedRoles(assigned.roles) && assigned.roles.distinct().size == assigned.roles.size)
                require(assigned.instructions.map { it.role } == assigned.roles)
                require(assigned.instructions.all { scalarLength(it.title) in 1..64 && it.title.isNotBlank() &&
                    it.steps.size in 1..4 && it.steps.all { step -> scalarLength(step) in 1..256 && step.isNotBlank() } })
            }
            is ServerMessage.RoleState -> {
                require(message.room_revision != null)
                val payload = message.payload
                validatePublic(payload.public)
                require(payload.last_client_action_seq >= 0)
                require(validOwnedRoles(payload.stations.roles()))
                val briefing = payload.briefing
                require(briefing.remaining_ms >= 0 && briefing.waiting_player_ids.size <= 3)
                require(briefing.waiting_player_ids.all { uuid.matches(it) } && briefing.waiting_player_ids.distinct().size == briefing.waiting_player_ids.size)
                require(briefing.complete == briefing.waiting_player_ids.isEmpty())
                require(!briefing.held_for_gameplay || (briefing.complete &&
                    (payload.public.stage == "briefing" || payload.public.paused_from == "briefing")))
                payload.stations.pilot?.let { view ->
                    require(view.evade_remaining_ticks >= 0 && view.cooldowns.move_lane >= 0 && view.cooldowns.evade >= 0)
                    require(view.hazards.all { it.emergency_id > 0 && it.deadline_remaining_ms >= 0 })
                }
                payload.stations.engineer?.let { view ->
                    require(view.output in 0..100 && view.temperature in 0..1000 && view.boost_remaining_ticks >= 0)
                    require(view.cooldowns.coolant >= 0 && view.cooldowns.engine_boost >= 0)
                    require(view.instructions.all { it.emergency_id > 0 && it.deadline_remaining_ms >= 0 &&
                        (it.target_max_output == null || it.target_max_output in 0..100) &&
                        (it.target_max_temperature == null || it.target_max_temperature in 0..1000) })
                }
                payload.stations.shields?.let { view ->
                    require(view.energy in 0..1000 && view.recharge_remaining_ticks >= 0 && view.boost_remaining_ticks >= 0)
                    require(view.cooldowns.recharge_shield >= 0 && view.cooldowns.shield_boost >= 0)
                    require(view.instructions.all { it.emergency_id > 0 && it.deadline_remaining_ms >= 0 })
                }
            }
        }
    }

    private fun validOwnedRoles(roles: List<StationRole>): Boolean = roles.size == 1 ||
        (roles.size == 2 && roles.toSet() == setOf(StationRole.ENGINEER, StationRole.SHIELDS))

    private fun validatePublic(view: PublicRound) {
        require(uuid.matches(view.round_id) && view.stage in stages - "lobby")
        require(view.tick_index >= 0 && view.remaining_ms >= 0)
        require(view.hull_percent in 0..100 && view.shield_percent in 0..100)
        require(view.countdown_remaining_ms == null || view.countdown_remaining_ms >= 0)
        require(view.paused_from == null || view.paused_from in stages)
        require(view.warnings.size <= 2 && view.warnings.map { it.emergency_id }.distinct().size == view.warnings.size)
        require(view.warnings.all { it.emergency_id >= 1 && it.kind in emergencyKinds && it.label.isNotBlank() && scalarLength(it.label) <= 64 })
        view.result?.let(::validateResult)
    }

    private fun validateResult(result: RoundResult) {
        require(result.survived_ms in 0..120_000 && result.survived_ms % 100 == 0L)
        require(result.final_hull_percent in 0..100 && result.resolved_count >= 0 && result.failed_count >= 0)
        require(result.players.size in 2..3 && result.players.map { it.player_id.lowercase() }.distinct().size == result.players.size)
        require(result.players.all { uuid.matches(it.player_id) && nameValid(it.name) })
        when (result.outcome) {
            "victory" -> require(result.reason == "survived" && result.survived_ms >= 60_000)
            "defeat" -> require(result.reason == "hull_destroyed" && result.final_hull_percent == 0)
            "aborted" -> require(result.reason in setOf("disconnect_timeout", "player_left", "briefing_timeout", "server_overload"))
            else -> error("Invalid outcome")
        }
    }

    /** Bound parser nesting and reject duplicate keys, including escaped aliases. */
    private fun boundedUniqueJson(text: String): Boolean {
        class Context(val objectValue: Boolean, val keys: MutableSet<String> = mutableSetOf(), var key: Boolean = true)
        val stack = ArrayDeque<Context>()
        var index = 0
        while (index < text.length) {
            when (text[index]) {
                '"' -> {
                    val start = index++
                    var escaped = false
                    while (index < text.length) {
                        val character = text[index]
                        if (!escaped && character == '"') break
                        escaped = !escaped && character == '\\'
                        index++
                    }
                    if (index >= text.length) return false
                    val context = stack.lastOrNull()
                    if (context?.objectValue == true && context.key) {
                        val key = json.decodeFromString<String>(text.substring(start, index + 1))
                        if (!context.keys.add(key)) return false
                        context.key = false
                    }
                }
                '{', '[' -> {
                    stack.addLast(Context(text[index] == '{'))
                    if (stack.size > 64) return false
                }
                '}', ']' -> {
                    if (stack.isEmpty() || stack.last().objectValue != (text[index] == '}')) return false
                    stack.removeLast()
                }
                ',' -> if (stack.lastOrNull()?.objectValue == true) stack.last().key = true
            }
            index++
        }
        return stack.isEmpty()
    }

    companion object {
        const val MAX_FRAME_BYTES = 16 * 1024
        private val requestId = Regex("[A-Za-z0-9_-]{1,64}")
        private val code = Regex("[ABCDEFGHJKLMNPQRSTUVWXYZ23456789]{6}")
        private val uuid = Regex("[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}")
        private val stages = setOf("lobby", "briefing", "countdown", "running", "paused", "finished", "aborted")
        private val serverKinds = setOf("pong", "session_accepted", "ack", "action_rejected", "error", "lobby_state", "public_state", "role_assigned", "role_state", "emergency_event", "game_over")
        private val emergencyKinds = setOf("asteroid", "overheating", "shield_overload")

        private fun scalarLength(value: String): Int {
            var index = 0
            while (index < value.length) {
                if (Character.isHighSurrogate(value[index])) {
                    require(index + 1 < value.length && Character.isLowSurrogate(value[index + 1]))
                    index += 2
                } else {
                    require(!Character.isLowSurrogate(value[index]))
                    index++
                }
            }
            return value.codePointCount(0, value.length)
        }

        private fun nameValid(value: String): Boolean = scalarLength(value.trim()) in 1..20 &&
            value.none { Character.isISOControl(it) }
    }
}
