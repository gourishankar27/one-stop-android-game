package com.onejob.game.ui.gameplay

import androidx.activity.compose.BackHandler
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Slider
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.res.stringResource
import com.onejob.game.R
import com.onejob.game.data.protocol.*
import com.onejob.game.ui.ShellPage
import com.onejob.game.ui.connection.ConnectionFeedback
import kotlin.math.roundToInt
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.semantics.LiveRegionMode
import androidx.compose.ui.semantics.liveRegion
import androidx.compose.ui.semantics.contentDescription
import com.onejob.game.ui.theme.RoleIdentity

@Composable
fun GameplayScreen(
    state: GameplayUiState,
    confirmLeave: Boolean,
    onSelect: (StationRole) -> Unit,
    onOutput: (Int) -> Unit,
    onAction: (PlayerAction) -> Unit,
    onLeave: () -> Unit,
    onDismissLeave: () -> Unit,
    onConfirmLeave: () -> Unit,
) {
    BackHandler(onBack = onLeave)
    ShellPage(R.string.game_title, onLeave) {
        ConnectionFeedback(state.connection)
        state.roomCode?.let { Text(it, modifier = Modifier.testTag("gameRoomCode")) }
        val snapshot = state.snapshot
        if (snapshot == null) {
            Text(stringResource(R.string.game_restoring))
        } else {
            val public = snapshot.public
            Text(stringResource(R.string.game_time, public.remaining_ms / 1000),
                modifier = Modifier.testTag("serverTime"))
            Text(stringResource(R.string.game_resources, public.hull_percent, public.shield_percent),
                modifier = Modifier.testTag("serverHull"))
            state.emergencyEvent?.let { event ->
                val kind = stringResource(when (event.kind) {
                    "asteroid" -> R.string.emergency_asteroid
                    "overheating" -> R.string.emergency_overheating
                    else -> R.string.emergency_overload
                })
                val status = stringResource(when (event.status) {
                    "started" -> R.string.emergency_started
                    "resolved" -> R.string.emergency_resolved
                    else -> R.string.emergency_failed
                })
                Row(modifier = Modifier.testTag("emergencyFeedback")) {
                    Text(stringResource(R.string.emergency_feedback, kind, status),
                        modifier = Modifier.testTag("emergencyEvent-${event.emergency_id}-${event.status}"))
                }
            }
            if (public.stage == "paused") Text(stringResource(R.string.game_paused))
            val result = public.result
            if (result != null) {
                Text(stringResource(when (result.outcome) {
                    "victory" -> R.string.game_victory
                    "defeat" -> R.string.game_defeat
                    else -> R.string.game_aborted
                }), style = MaterialTheme.typography.headlineMedium,
                    modifier = Modifier.testTag("terminalSummary"))
                Text(stringResource(when (result.reason) {
                    "survived" -> R.string.game_survived
                    "hull_destroyed" -> R.string.game_hull_destroyed
                    "server_overload" -> R.string.game_overload
                    "disconnect_timeout" -> R.string.briefing_disconnect_timeout
                    "player_left" -> R.string.game_player_left
                    else -> R.string.briefing_aborted
                }))
                Text(stringResource(R.string.game_terminal_values, result.survived_ms / 1000, result.final_hull_percent))
            } else {
                for (warning in public.warnings) {
                    Text(warning.label, color = MaterialTheme.colorScheme.error,
                        style = MaterialTheme.typography.titleMedium,
                        modifier = Modifier.testTag("publicWarning-${warning.emergency_id}")
                            .semantics { liveRegion = LiveRegionMode.Polite })
                }
                for (instruction in state.instructions) {
                    val urgent = when (instruction.role) {
                        StationRole.PILOT -> snapshot.stations.pilot?.hazards?.isNotEmpty() == true
                        StationRole.ENGINEER -> snapshot.stations.engineer?.instructions?.isNotEmpty() == true
                        StationRole.SHIELDS -> snapshot.stations.shields?.instructions?.isNotEmpty() == true
                    }
                    OutlinedButton(onClick = { onSelect(instruction.role) },
                        modifier = Modifier.fillMaxWidth().testTag("gameStation-" + instruction.role.name)) {
                        Text(if (urgent) stringResource(R.string.game_attention, instruction.title) else instruction.title)
                    }
                }
                state.selected?.let { RoleIdentity(it) }
                when (state.selected) {
                    StationRole.PILOT -> snapshot.stations.pilot?.let { view ->
                        for (hazard in view.hazards) {
                            Text(stringResource(R.string.warning_pilot_asteroid,
                                hazard.impact_lane.name.lowercase(), hazard.deadline_remaining_ms / 1000.0),
                                color = MaterialTheme.colorScheme.error,
                                modifier = Modifier.testTag("privateWarning-${hazard.emergency_id}"))
                        }
                        Text(stringResource(R.string.game_lane, view.lane.name.lowercase()))
                        Row {
                            ActionControl(stringResource(R.string.game_left), "moveLeft", "move", state,
                                view.cooldowns.move_lane, Modifier.weight(1f)) {
                                onAction(PlayerAction.MoveLane(Direction.LEFT))
                            }
                            ActionControl(stringResource(R.string.game_right), "moveRight", "move", state,
                                view.cooldowns.move_lane, Modifier.weight(1f)) {
                                onAction(PlayerAction.MoveLane(Direction.RIGHT))
                            }
                        }
                        Text(stringResource(R.string.game_evade_status, view.evade_remaining_ticks / 10.0))
                        ActionControl(stringResource(R.string.game_evade), "evade", "evade", state,
                            view.cooldowns.evade) { onAction(PlayerAction.Evade) }
                        Text(stringResource(if (view.maneuver_ready) R.string.game_maneuver_ready else R.string.game_maneuver_wait))
                    }
                    StationRole.ENGINEER -> snapshot.stations.engineer?.let { view ->
                        for (instruction in view.instructions) {
                            val maximumOutput = instruction.target_max_output ?: continue
                            Text(if (instruction.target_max_temperature != null)
                                stringResource(R.string.warning_engineer_heat,
                                    instruction.target_max_temperature, maximumOutput,
                                    instruction.deadline_remaining_ms / 1000.0)
                            else stringResource(R.string.warning_engineer_overload,
                                maximumOutput, instruction.deadline_remaining_ms / 1000.0),
                                color = MaterialTheme.colorScheme.error,
                                modifier = Modifier.testTag("privateWarning-${instruction.emergency_id}"))
                        }
                        Text(stringResource(R.string.game_engine_values, view.output, view.temperature, view.available_power),
                            modifier = Modifier.testTag("engineValues"))
                        state.outputDraft?.let { Text(stringResource(R.string.game_output_preview, it)) }
                        val outputLabel = stringResource(R.string.engine_output_accessibility)
                        Slider(value = (state.outputDraft ?: view.output).toFloat(),
                            onValueChange = { onOutput(it.roundToInt()) }, valueRange = 0f..100f,
                            steps = 99, enabled = state.canControl && "shutdown" !in state.pending,
                            modifier = Modifier.fillMaxWidth().testTag("engineOutput").semantics { contentDescription = outputLabel })
                        ActionControl(stringResource(R.string.game_engine_boost), "engineBoost", "engineBoost", state,
                            view.cooldowns.engine_boost) { onAction(PlayerAction.EngineBoost) }
                        ActionControl(stringResource(R.string.game_coolant), "coolant", "coolant", state,
                            view.cooldowns.coolant) { onAction(PlayerAction.Coolant) }
                        ActionControl(stringResource(R.string.game_shutdown), "shutdown", "shutdown", state, 0) {
                            onAction(PlayerAction.EmergencyShutdown)
                        }
                    }
                    StationRole.SHIELDS -> snapshot.stations.shields?.let { view ->
                        for (instruction in view.instructions) {
                            Text(if (instruction.deactivate)
                                stringResource(R.string.warning_shields_overload, instruction.deadline_remaining_ms / 1000.0)
                            else stringResource(R.string.warning_shields_asteroid,
                                instruction.required_facing?.name?.lowercase().orEmpty(), instruction.deadline_remaining_ms / 1000.0),
                                color = MaterialTheme.colorScheme.error,
                                modifier = Modifier.testTag("privateWarning-${instruction.emergency_id}"))
                        }
                        Text(stringResource(R.string.game_shield_values, view.energy, view.facing.name.lowercase()),
                            modifier = Modifier.testTag("shieldValues"))
                        ActionControl(stringResource(if (view.active) R.string.game_shield_off else R.string.game_shield_on),
                            "shieldToggle", "shield", state, 0) {
                            onAction(PlayerAction.SetShield(!view.active, view.facing))
                        }
                        for (facing in Facing.entries) {
                            ActionControl(stringResource(R.string.game_facing, facing.name.lowercase()),
                                "facing-" + facing.name, "shield", state, 0) {
                                onAction(PlayerAction.SetShield(view.active, facing))
                            }
                        }
                        ActionControl(stringResource(R.string.game_recharge), "recharge", "recharge", state,
                            view.cooldowns.recharge_shield) { onAction(PlayerAction.RechargeShield) }
                        ActionControl(stringResource(R.string.game_shield_boost), "shieldBoost", "shieldBoost", state,
                            view.cooldowns.shield_boost) { onAction(PlayerAction.ShieldBoost) }
                    }
                    null -> Unit
                }
            }
            state.feedback?.let { feedback ->
                Text(stringResource(when (feedback) {
                    ActionFeedback.ACCEPTED -> R.string.game_action_accepted
                    ActionFeedback.POWER -> R.string.game_power_rejected
                    ActionFeedback.COOLDOWN -> R.string.game_cooldown_rejected
                    ActionFeedback.NOT_OWNED -> R.string.game_ownership_rejected
                    ActionFeedback.STALE -> R.string.game_stale_rejected
                    ActionFeedback.UNCERTAIN -> R.string.game_action_uncertain
                    ActionFeedback.NOT_SENT -> R.string.game_action_not_sent
                    ActionFeedback.INVALID -> R.string.game_action_invalid
                }), modifier = Modifier.testTag("actionFeedback").semantics { liveRegion = LiveRegionMode.Polite })
            }
        }
        OutlinedButton(onClick = onLeave, modifier = Modifier.fillMaxWidth()) {
            Text(stringResource(R.string.leave_room))
        }
    }
    if (confirmLeave) AlertDialog(
        onDismissRequest = onDismissLeave,
        title = { Text(stringResource(R.string.leave_title)) },
        text = { Text(stringResource(R.string.leave_description)) },
        confirmButton = { TextButton(onClick = onConfirmLeave) { Text(stringResource(R.string.confirm_leave)) } },
        dismissButton = { TextButton(onClick = onDismissLeave) { Text(stringResource(R.string.stay_room)) } },
    )
}

@Composable
private fun ActionControl(
    label: String, tag: String, key: String, state: GameplayUiState,
    cooldown: Long, modifier: Modifier = Modifier, onClick: () -> Unit,
) {
    Button(onClick = onClick, enabled = state.canControl && key !in state.pending && cooldown == 0L,
        modifier = modifier.fillMaxWidth().testTag(tag)) {
        Text(if (cooldown > 0) stringResource(R.string.game_cooldown_label, label, cooldown / 10.0) else label)
    }
}
