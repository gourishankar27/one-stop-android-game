package com.onejob.game.ui.roles

import androidx.activity.compose.BackHandler
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.res.pluralStringResource
import androidx.compose.ui.res.stringResource
import com.onejob.game.R
import com.onejob.game.data.protocol.StationRole
import com.onejob.game.ui.ShellPage
import com.onejob.game.ui.connection.ConnectionFeedback
import com.onejob.game.ui.lobby.LobbyFeedbackText
import com.onejob.game.ui.theme.RoleIdentity

@Composable
fun RoleScreen(state: RoleUiState, confirmLeave: Boolean, onSelect: (StationRole) -> Unit,
               onRead: () -> Unit, onAcknowledge: () -> Unit, onLeave: () -> Unit,
               onDismissLeave: () -> Unit, onConfirmLeave: () -> Unit) {
    BackHandler(onBack = onLeave)
    ShellPage(R.string.role_briefing_title, onLeave) {
        ConnectionFeedback(state.connection)
        state.roomCode?.let { Text(it, modifier = Modifier.testTag("briefingRoomCode")) }
        if (state.instructions.isEmpty()) {
            Text(stringResource(R.string.role_restoring))
        } else {
            Text(stringResource(R.string.role_privacy_hint))
            if (state.instructions.size == 2) Text(stringResource(R.string.two_station_hint))
            for (instruction in state.instructions) {
                OutlinedButton(onClick = { onSelect(instruction.role) }, modifier = Modifier.fillMaxWidth().testTag("station-" + instruction.role.name)) {
                    Text(instruction.title)
                }
            }
            val instruction = state.instructions.first { it.role == state.selected }
            RoleIdentity(instruction.role)
            Text(instruction.title, style = MaterialTheme.typography.headlineMedium, modifier = Modifier.testTag("stationTitle"))
            for (step in instruction.steps) Text(step)
            Button(onClick = onRead, enabled = state.canRead, modifier = Modifier.fillMaxWidth().testTag("readStation")) {
                Text(stringResource(if (instruction.role in state.read) R.string.station_read else R.string.confirm_station_read, instruction.title))
            }
            when {
                state.abortReason != null -> Text(stringResource(when (state.abortReason) {
                    "briefing_timeout" -> R.string.briefing_timeout
                    "player_left" -> R.string.briefing_player_left
                    "disconnect_timeout" -> R.string.briefing_disconnect_timeout
                    else -> R.string.briefing_aborted
                }))
                state.paused -> Text(stringResource(R.string.briefing_paused))
                state.held -> Text(stringResource(R.string.briefing_held))
                state.acknowledged -> Text(pluralStringResource(R.plurals.briefing_acknowledged, state.waitingCount, state.waitingCount))
                else -> Text(stringResource(R.string.briefing_deadline_hint))
            }
            Button(onClick = onAcknowledge, enabled = state.canAcknowledge, modifier = Modifier.fillMaxWidth().testTag("acknowledgeBriefing")) {
                Text(stringResource(R.string.acknowledge_briefing))
            }
            if (state.pending) Text(stringResource(R.string.lobby_command_pending))
            LobbyFeedbackText(state.feedback)
        }
        OutlinedButton(onClick = onLeave, modifier = Modifier.fillMaxWidth()) { Text(stringResource(R.string.leave_room)) }
    }
    if (confirmLeave) AlertDialog(
        onDismissRequest = onDismissLeave,
        title = { Text(stringResource(R.string.leave_title)) },
        text = { Text(stringResource(R.string.leave_description)) },
        confirmButton = { TextButton(onClick = onConfirmLeave) { Text(stringResource(R.string.confirm_leave)) } },
        dismissButton = { TextButton(onClick = onDismissLeave) { Text(stringResource(R.string.stay_room)) } },
    )
}
