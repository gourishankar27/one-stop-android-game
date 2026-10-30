package com.onejob.game.ui.display

import androidx.activity.compose.BackHandler
import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.semantics.LiveRegionMode
import androidx.compose.ui.semantics.liveRegion
import com.onejob.game.R
import com.onejob.game.data.ConnectionStatus
import com.onejob.game.ui.ShellPage
import com.onejob.game.ui.connection.ConnectionFeedback
import com.onejob.game.ui.lobby.LobbyFeedbackText
import com.onejob.game.ui.lobby.LobbyUiState

@Composable
fun DisplayScreen(state: DisplayUiState, room: LobbyUiState, onRetry: () -> Unit,
                  onLeave: () -> Unit, onDismiss: () -> Unit, onConfirm: () -> Unit) {
    BackHandler(onBack = onLeave)
    ShellPage(R.string.display_title, onLeave, maxContentWidth = 1000.dp) {
        ConnectionFeedback(state.connection)
        state.roomCode?.let { Text(it, style = MaterialTheme.typography.headlineLarge,
            modifier = Modifier.testTag("displayCode")) }
        Text(stringResource(R.string.display_public_hint))
        if (!state.restored) Text(stringResource(R.string.display_restoring))
        else {
            val public = state.public
            if (public == null) Text(stringResource(R.string.display_lobby),
                style = MaterialTheme.typography.headlineMedium)
            else {
                Text(stringResource(when (public.stage) {
                    "briefing" -> R.string.role_briefing_title
                    "countdown" -> R.string.countdown_title
                    "paused" -> R.string.display_paused
                    "finished", "aborted" -> R.string.round_results_title
                    else -> R.string.display_running
                }), style = MaterialTheme.typography.headlineMedium, modifier = Modifier.testTag("displayStage"))
                public.countdown_remaining_ms?.let {
                    Text(((it + 999) / 1000).toString(), style = MaterialTheme.typography.displayLarge,
                        modifier = Modifier.testTag("displayCountdown"))
                }
                BoxWithConstraints(Modifier.fillMaxWidth()) {
                    val totals: @Composable () -> Unit = {
                        DisplayTotal(stringResource(R.string.display_time), "${public.remaining_ms / 1000} s", "displayTime")
                        DisplayTotal(stringResource(R.string.display_hull), "${public.hull_percent}%", "displayHull")
                        DisplayTotal(stringResource(R.string.display_shield), "${public.shield_percent}%", "displayShield")
                    }
                    if (maxWidth >= 600.dp) Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) { totals() }
                    else Column(verticalArrangement = Arrangement.spacedBy(12.dp)) { totals() }
                }
                for (warning in public.warnings) Text(warning.label,
                    style = MaterialTheme.typography.headlineSmall,
                    modifier = Modifier.testTag("displayWarning-${warning.emergency_id}")
                        .semantics { liveRegion = LiveRegionMode.Polite })
                public.result?.let { result ->
                    Text(stringResource(when (result.outcome) {
                        "victory" -> R.string.game_victory
                        "defeat" -> R.string.game_defeat
                        else -> R.string.game_aborted
                    }), style = MaterialTheme.typography.headlineLarge, modifier = Modifier.testTag("displayResult"))
                    Text(stringResource(when (result.reason) {
                        "survived" -> R.string.game_survived
                        "hull_destroyed" -> R.string.game_hull_destroyed
                        "briefing_timeout" -> R.string.briefing_timeout
                        "disconnect_timeout" -> R.string.briefing_disconnect_timeout
                        "player_left" -> R.string.game_player_left
                        else -> R.string.game_overload
                    }))
                    Text(stringResource(R.string.game_terminal_values, result.survived_ms / 1000, result.final_hull_percent))
                    Text(stringResource(R.string.result_counts, result.resolved_count, result.failed_count),
                        modifier = Modifier.testTag("displayResultCounts"))
                    Text(stringResource(R.string.result_crew, result.players.joinToString(", ") { it.name }))
                }
            }
            state.lobby?.players?.forEach { player ->
                Text(stringResource(if (player.connected) R.string.member_connected else R.string.member_disconnected) +
                    " · " + player.name + " · " + stringResource(if (player.ready) R.string.member_ready else R.string.member_not_ready),
                    modifier = Modifier.testTag("displayMember-${player.player_id}"))
            }
        }
        LobbyFeedbackText(room.feedback)
        if (state.connection.status != ConnectionStatus.CONNECTED) {
            OutlinedButton(onClick = onRetry, enabled = room.pending == null) { Text(stringResource(R.string.retry_connection)) }
        }
        OutlinedButton(onClick = onLeave, modifier = Modifier.fillMaxWidth()) { Text(stringResource(R.string.leave_room)) }
    }
    if (room.confirmLeave) AlertDialog(onDismissRequest = onDismiss,
        title = { Text(stringResource(R.string.leave_title)) },
        text = { Text(stringResource(R.string.display_leave_hint)) },
        confirmButton = { TextButton(onClick = onConfirm) { Text(stringResource(R.string.confirm_leave)) } },
        dismissButton = { TextButton(onClick = onDismiss) { Text(stringResource(R.string.stay_room)) } })
}

@Composable
private fun DisplayTotal(label: String, value: String, tag: String) {
    Column { Text(label, style = MaterialTheme.typography.titleLarge)
        Text(value, style = MaterialTheme.typography.displaySmall, modifier = Modifier.testTag(tag)) }
}
