package com.onejob.game.ui.lifecycle

import androidx.activity.compose.BackHandler
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.res.stringResource
import com.onejob.game.R
import com.onejob.game.data.ConnectionStatus
import com.onejob.game.data.protocol.RoleInstruction
import com.onejob.game.data.protocol.RoleStatePayload
import com.onejob.game.ui.ShellPage
import com.onejob.game.ui.connection.ConnectionFeedback
import com.onejob.game.ui.lobby.*

@Composable
fun CountdownScreen(snapshot: RoleStatePayload?, instructions: List<RoleInstruction>, room: LobbyUiState,
                    onLeave: () -> Unit, onDismissLeave: () -> Unit, onConfirmLeave: () -> Unit) {
    BackHandler(onBack = onLeave)
    ShellPage(R.string.countdown_title, onLeave) {
        ConnectionFeedback(room.connection)
        if (snapshot == null) Text(stringResource(R.string.countdown_restoring))
        else {
            val public = snapshot.public
            val remaining = public.countdown_remaining_ms
            if (remaining != null) Text(((remaining + 999) / 1000).toString(),
                style = MaterialTheme.typography.displayLarge, modifier = Modifier.testTag("serverCountdown"))
            Text(instructions.joinToString(" + ") { it.title }, modifier = Modifier.testTag("countdownRoles"))
            Text(stringResource(R.string.countdown_server_hint))
            if (public.stage == "paused") Text(stringResource(R.string.countdown_paused),
                modifier = Modifier.testTag("countdownPaused"))
        }
        OutlinedButton(onClick = onLeave, modifier = Modifier.fillMaxWidth()) { Text(stringResource(R.string.leave_room)) }
    }
    LifecycleLeaveDialog(room.confirmLeave, onDismissLeave, onConfirmLeave)
}

@Composable
fun ResultsScreen(snapshot: RoleStatePayload?, room: LobbyUiState, onReady: () -> Unit,
                  onPlayAgain: () -> Unit, onReturn: () -> Unit, onRetry: () -> Unit,
                  onLeave: () -> Unit, onDismissLeave: () -> Unit, onConfirmLeave: () -> Unit) {
    BackHandler(onBack = onLeave)
    ShellPage(R.string.round_results_title, onLeave) {
        ConnectionFeedback(room.connection)
        room.roomCode?.let { Text(it, modifier = Modifier.testTag("resultsRoomCode")) }
        val result = snapshot?.public?.result
        if (result == null) Text(stringResource(R.string.results_restoring))
        else {
            Text(stringResource(when (result.outcome) {
                "victory" -> R.string.game_victory
                "defeat" -> R.string.game_defeat
                else -> R.string.game_aborted
            }), style = MaterialTheme.typography.headlineMedium,
                modifier = Modifier.testTag("terminalSummary"))
            Text(stringResource(when (result.reason) {
                "survived" -> R.string.game_survived
                "hull_destroyed" -> R.string.game_hull_destroyed
                "briefing_timeout" -> R.string.briefing_timeout
                "player_left" -> R.string.game_player_left
                "disconnect_timeout" -> R.string.briefing_disconnect_timeout
                else -> R.string.game_overload
            }))
            Text(stringResource(R.string.game_terminal_values, result.survived_ms / 1000, result.final_hull_percent),
                modifier = Modifier.testTag("resultValues"))
            Text(stringResource(R.string.result_counts, result.resolved_count, result.failed_count),
                modifier = Modifier.testTag("resultCounts"))
            Text(stringResource(R.string.result_crew, result.players.joinToString(", ") { it.name }))
            Text(stringResource(R.string.result_ready_hint))
            for (member in room.members) {
                Text(stringResource(if (member.ready) R.string.result_member_ready else R.string.result_member_waiting,
                    member.name), modifier = Modifier.testTag("resultMember-${member.id}"))
            }
            Button(onClick = onReady, enabled = room.canReady,
                modifier = Modifier.fillMaxWidth().testTag("resultsReady")) {
                Text(stringResource(if (room.localReady) R.string.not_ready_action else R.string.result_ready))
            }
            if (room.members.any { it.local && it.host }) {
                Button(onClick = onPlayAgain, enabled = room.canPlayAgain,
                    modifier = Modifier.fillMaxWidth().testTag("playAgain")) { Text(stringResource(R.string.play_again)) }
                OutlinedButton(onClick = onReturn, enabled = room.canReturnToLobby,
                    modifier = Modifier.fillMaxWidth().testTag("returnToLobby")) { Text(stringResource(R.string.return_to_lobby)) }
                if (!room.canPlayAgain) Text(stringResource(R.string.result_wait_ready))
            } else Text(stringResource(R.string.result_wait_host))
        }
        if (room.pending != null) Text(stringResource(R.string.lobby_command_pending))
        LobbyFeedbackText(room.feedback)
        if (room.connection.status != ConnectionStatus.CONNECTED) {
            OutlinedButton(onClick = onRetry, enabled = room.pending == null) { Text(stringResource(R.string.retry_connection)) }
        }
        OutlinedButton(onClick = onLeave, modifier = Modifier.fillMaxWidth()) { Text(stringResource(R.string.leave_room)) }
    }
    LifecycleLeaveDialog(room.confirmLeave, onDismissLeave, onConfirmLeave)
}

@Composable
private fun LifecycleLeaveDialog(show: Boolean, dismiss: () -> Unit, confirm: () -> Unit) {
    if (show) AlertDialog(onDismissRequest = dismiss,
        title = { Text(stringResource(R.string.leave_title)) },
        text = { Text(stringResource(R.string.leave_description)) },
        confirmButton = { TextButton(onClick = confirm) { Text(stringResource(R.string.confirm_leave)) } },
        dismissButton = { TextButton(onClick = dismiss) { Text(stringResource(R.string.stay_room)) } })
}
