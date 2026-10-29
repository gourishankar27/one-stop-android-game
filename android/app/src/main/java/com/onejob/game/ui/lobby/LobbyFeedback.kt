package com.onejob.game.ui.lobby

import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.res.stringResource
import com.onejob.game.R
import com.onejob.game.data.repository.CommandResult
import com.onejob.game.data.repository.RemoteCode

enum class LobbyFeedback {
    ROOM_NOT_FOUND, ROOM_FULL, ROOM_STARTED, CAPACITY, INVALID_INPUT, NOT_HOST,
    NOT_READY, FEATURE_UNAVAILABLE, UNCERTAIN, NOT_SENT, EXPIRED, REJECTED, LEFT, LEFT_UNCERTAIN,
}

fun CommandResult.feedback(): LobbyFeedback? = when (this) {
    is CommandResult.Accepted, CommandResult.LeftLocally -> null
    is CommandResult.Uncertain -> LobbyFeedback.UNCERTAIN
    is CommandResult.NotSent -> LobbyFeedback.NOT_SENT
    is CommandResult.Rejected -> when (code) {
        RemoteCode.ROOM_NOT_FOUND -> LobbyFeedback.ROOM_NOT_FOUND
        RemoteCode.ROOM_FULL -> LobbyFeedback.ROOM_FULL
        RemoteCode.ROOM_STARTED -> LobbyFeedback.ROOM_STARTED
        RemoteCode.CAPACITY -> LobbyFeedback.CAPACITY
        RemoteCode.INVALID_MESSAGE -> LobbyFeedback.INVALID_INPUT
        RemoteCode.NOT_HOST -> LobbyFeedback.NOT_HOST
        RemoteCode.NOT_READY -> LobbyFeedback.NOT_READY
        RemoteCode.FEATURE_UNAVAILABLE -> LobbyFeedback.FEATURE_UNAVAILABLE
        RemoteCode.SESSION_EXPIRED, RemoteCode.NOT_AUTHENTICATED -> LobbyFeedback.EXPIRED
        else -> LobbyFeedback.REJECTED
    }
}

@Composable
fun LobbyFeedbackText(feedback: LobbyFeedback?) {
    if (feedback != null) Text(stringResource(when (feedback) {
        LobbyFeedback.ROOM_NOT_FOUND -> R.string.error_room_not_found
        LobbyFeedback.ROOM_FULL -> R.string.error_room_full
        LobbyFeedback.ROOM_STARTED -> R.string.error_room_started
        LobbyFeedback.CAPACITY -> R.string.error_capacity
        LobbyFeedback.INVALID_INPUT -> R.string.error_input
        LobbyFeedback.NOT_HOST -> R.string.start_host_only
        LobbyFeedback.NOT_READY -> R.string.start_wait_ready
        LobbyFeedback.FEATURE_UNAVAILABLE -> R.string.round_unavailable
        LobbyFeedback.UNCERTAIN -> R.string.command_uncertain
        LobbyFeedback.NOT_SENT -> R.string.admission_not_sent
        LobbyFeedback.EXPIRED -> R.string.membership_expired
        LobbyFeedback.REJECTED -> R.string.command_rejected
        LobbyFeedback.LEFT -> R.string.left_room
        LobbyFeedback.LEFT_UNCERTAIN -> R.string.left_uncertain
    }))
}
