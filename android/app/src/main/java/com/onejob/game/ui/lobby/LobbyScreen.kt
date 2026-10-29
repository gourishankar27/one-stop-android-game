package com.onejob.game.ui.lobby

import androidx.activity.compose.BackHandler
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.key
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.res.stringResource
import com.onejob.game.R
import com.onejob.game.data.ConnectionStatus
import com.onejob.game.ui.ShellPage
import com.onejob.game.ui.connection.ConnectionFeedback

@Composable
fun LobbyScreen(state: LobbyUiState, onReady: () -> Unit, onStart: () -> Unit, onLeave: () -> Unit,
                onDismissLeave: () -> Unit, onConfirmLeave: () -> Unit, onRetry: () -> Unit) {
    BackHandler(onBack = onLeave)
    ShellPage(R.string.live_lobby_title, onLeave) {
        ConnectionFeedback(state.connection)
        if (state.roomCode != null) {
            Text(stringResource(R.string.room_code))
            Text(state.roomCode, style = MaterialTheme.typography.displayMedium, modifier = Modifier.testTag("lobbyCode"))
        } else Text(stringResource(R.string.lobby_restoring))
        for (member in state.members) key(member.id) {
            Column(Modifier.fillMaxWidth().testTag("member-" + member.id)) {
                Text(member.name, style = MaterialTheme.typography.titleLarge)
                if (member.local) Text(stringResource(R.string.you_label))
                if (member.host) Text(stringResource(R.string.host_label))
                Text(stringResource(if (member.connected) R.string.member_connected else R.string.member_disconnected))
                Text(stringResource(if (member.ready) R.string.member_ready else R.string.member_not_ready))
            }
        }
        Button(onClick = onReady, enabled = state.canReady, modifier = Modifier.fillMaxWidth().testTag("readyButton")) {
            Text(stringResource(if (state.localReady) R.string.not_ready_action else R.string.ready_action))
        }
        Button(onClick = onStart, enabled = state.canStart, modifier = Modifier.fillMaxWidth().testTag("startButton")) {
            Text(stringResource(R.string.start_round))
        }
        state.startBlock?.let { Text(stringResource(when (it) {
            StartBlock.CONNECTION -> R.string.start_connection
            StartBlock.SNAPSHOT -> R.string.lobby_restoring
            StartBlock.HOST_ONLY -> R.string.start_host_only
            StartBlock.TWO_PLAYERS -> R.string.start_two_players
            StartBlock.CONNECTED -> R.string.start_wait_connected
            StartBlock.READY -> R.string.start_wait_ready
            StartBlock.SERVER -> R.string.start_server_wait
        })) }
        if (state.pending != null) Text(stringResource(R.string.lobby_command_pending))
        LobbyFeedbackText(state.feedback)
        if (state.connection.status != ConnectionStatus.CONNECTED) {
            OutlinedButton(onClick = onRetry, enabled = state.pending == null, modifier = Modifier.fillMaxWidth()) {
                Text(stringResource(R.string.retry_connection))
            }
        }
        OutlinedButton(onClick = onLeave, enabled = state.pending != LobbyOperation.LEAVE, modifier = Modifier.fillMaxWidth()) {
            Text(stringResource(R.string.leave_room))
        }
    }
    if (state.confirmLeave) AlertDialog(
        onDismissRequest = onDismissLeave,
        title = { Text(stringResource(R.string.leave_title)) },
        text = { Text(stringResource(R.string.leave_description)) },
        confirmButton = { TextButton(onClick = onConfirmLeave) { Text(stringResource(R.string.confirm_leave)) } },
        dismissButton = { TextButton(onClick = onDismissLeave) { Text(stringResource(R.string.stay_room)) } },
    )
}
