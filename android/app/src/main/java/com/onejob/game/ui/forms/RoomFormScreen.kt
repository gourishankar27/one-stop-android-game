package com.onejob.game.ui.forms

import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalSoftwareKeyboardController
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardCapitalization
import com.onejob.game.R
import com.onejob.game.data.ConnectionStatus
import com.onejob.game.ui.ShellPage

@Composable
fun RoomFormScreen(
    kind: FormKind,
    state: RoomFormUiState,
    onNameChanged: (String) -> Unit,
    onCodeChanged: (String) -> Unit,
    onCheckDraft: () -> Unit,
    onBack: () -> Unit,
) {
    val keyboard = LocalSoftwareKeyboardController.current
    val checkDraft = { onCheckDraft(); keyboard?.hide(); Unit }
    ShellPage(if (kind == FormKind.CREATE) R.string.create_title else R.string.join_title, onBack) {
        Text(stringResource(R.string.local_draft), style = MaterialTheme.typography.titleMedium)
        Text(stringResource(R.string.form_description))
        Text(stringResource(when (state.connectionStatus) {
            ConnectionStatus.UNAVAILABLE -> R.string.connection_unavailable
            ConnectionStatus.CONNECTING -> R.string.connection_connecting
            ConnectionStatus.CONNECTED -> R.string.connection_connected
            ConnectionStatus.RECONNECTING -> R.string.connection_reconnecting
            ConnectionStatus.SESSION_EXPIRED -> R.string.connection_expired
        }))
        OutlinedTextField(
            value = state.name,
            onValueChange = onNameChanged,
            label = { Text(stringResource(R.string.player_name)) },
            supportingText = { DraftHint(state.nameIssue, R.string.name_hint) },
            isError = state.nameIssue != null,
            singleLine = true,
            keyboardOptions = KeyboardOptions(
                imeAction = if (kind == FormKind.JOIN) ImeAction.Next else ImeAction.Done,
            ),
            keyboardActions = KeyboardActions(onDone = { checkDraft() }),
            modifier = Modifier.fillMaxWidth().testTag("nameInput"),
        )
        if (kind == FormKind.JOIN) {
            OutlinedTextField(
                value = state.roomCode,
                onValueChange = onCodeChanged,
                label = { Text(stringResource(R.string.room_code)) },
                supportingText = { DraftHint(state.codeIssue, R.string.code_hint) },
                isError = state.codeIssue != null,
                singleLine = true,
                keyboardOptions = KeyboardOptions(
                    capitalization = KeyboardCapitalization.Characters, imeAction = ImeAction.Done,
                ),
                keyboardActions = KeyboardActions(onDone = { checkDraft() }),
                modifier = Modifier.fillMaxWidth().testTag("codeInput"),
            )
        }
        Button(onClick = checkDraft, modifier = Modifier.fillMaxWidth()) {
            Text(stringResource(R.string.check_draft))
        }
        if (state.draftValid) {
            Text(stringResource(R.string.draft_valid))
        }
    }
}

@Composable
private fun DraftHint(issue: DraftIssue?, defaultHint: Int) {
    Text(stringResource(when (issue) {
        null -> defaultHint
        DraftIssue.NAME_REQUIRED -> R.string.name_required
        DraftIssue.NAME_TOO_LONG -> R.string.name_too_long
        DraftIssue.NAME_CONTROL_CHARACTER -> R.string.name_control
        DraftIssue.NAME_INVALID_UNICODE -> R.string.name_unicode
        DraftIssue.ROOM_CODE_INVALID -> R.string.code_invalid
    }))
}
