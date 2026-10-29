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
import androidx.activity.compose.BackHandler
import com.onejob.game.ui.connection.ConnectionFeedback
import com.onejob.game.ui.lobby.LobbyFeedback
import com.onejob.game.ui.lobby.LobbyFeedbackText
import com.onejob.game.ui.ShellPage

@Composable
fun RoomFormScreen(
    kind: FormKind,
    state: RoomFormUiState,
    onNameChanged: (String) -> Unit,
    onCodeChanged: (String) -> Unit,
    onSubmit: () -> Unit,
    onResetAttempt: () -> Unit,
    onBack: () -> Unit,
) {
    val keyboard = LocalSoftwareKeyboardController.current
    val submit = { onSubmit(); keyboard?.hide(); Unit }
    BackHandler(onBack = onBack)
    ShellPage(if (kind == FormKind.CREATE) R.string.create_title else R.string.join_title, onBack) {
        Text(stringResource(R.string.form_description))
        ConnectionFeedback(state.connection)
        OutlinedTextField(
            value = state.name,
            onValueChange = onNameChanged,
            label = { Text(stringResource(R.string.player_name)) },
            supportingText = { DraftHint(state.nameIssue, R.string.name_hint) },
            isError = state.nameIssue != null,
            singleLine = true,
            enabled = !state.pending && !state.exiting,
            keyboardOptions = KeyboardOptions(
                imeAction = if (kind == FormKind.JOIN) ImeAction.Next else ImeAction.Done,
            ),
            keyboardActions = KeyboardActions(onDone = { submit() }),
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
                enabled = !state.pending && !state.exiting,
                keyboardOptions = KeyboardOptions(
                    capitalization = KeyboardCapitalization.Characters, imeAction = ImeAction.Done,
                ),
                keyboardActions = KeyboardActions(onDone = { submit() }),
                modifier = Modifier.fillMaxWidth().testTag("codeInput"),
            )
        }
        Button(onClick = submit, enabled = state.canSubmit, modifier = Modifier.fillMaxWidth().testTag("submitAdmission")) {
            Text(stringResource(if (kind == FormKind.CREATE) R.string.submit_create else R.string.submit_join))
        }
        if (state.pending) Text(stringResource(R.string.admission_pending))
        LobbyFeedbackText(state.feedback)
        if (state.feedback == LobbyFeedback.UNCERTAIN) {
            Button(onClick = onResetAttempt, enabled = !state.pending && !state.exiting, modifier = Modifier.fillMaxWidth()) {
                Text(stringResource(R.string.reset_attempt))
            }
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
