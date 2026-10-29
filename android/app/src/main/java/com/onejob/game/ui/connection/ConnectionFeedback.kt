package com.onejob.game.ui.connection

import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.res.stringResource
import com.onejob.game.R
import com.onejob.game.data.ConnectionStatus
import com.onejob.game.data.repository.ConnectionProblem
import com.onejob.game.data.repository.ConnectionState

@Composable
fun ConnectionFeedback(state: ConnectionState, result: ProbeResult = ProbeResult.NONE) {
    Text(stringResource(when (state.status) {
        ConnectionStatus.CONNECTING -> R.string.connection_connecting
        ConnectionStatus.CONNECTED -> R.string.connection_connected
        ConnectionStatus.RECONNECTING -> R.string.connection_reconnecting
        ConnectionStatus.SESSION_EXPIRED -> R.string.connection_expired
        ConnectionStatus.DISCONNECTED -> R.string.connection_disconnected
        ConnectionStatus.PROTOCOL_ERROR -> R.string.connection_protocol_error
        ConnectionStatus.UNAVAILABLE -> R.string.connection_server_unavailable
    }))
    state.problem?.let { problem ->
        Text(stringResource(when (problem) {
            ConnectionProblem.CONFIGURATION -> R.string.endpoint_configuration
            ConnectionProblem.COMMAND_UNCERTAIN -> R.string.command_uncertain
            ConnectionProblem.PROTOCOL, ConnectionProblem.UNSUPPORTED_VERSION -> R.string.protocol_problem
            ConnectionProblem.RECONNECT_EXHAUSTED -> R.string.reconnect_exhausted
            ConnectionProblem.ADMISSION_REQUIRED -> R.string.admission_required
            else -> R.string.network_problem
        }))
    }
    if (result != ProbeResult.NONE) {
        Text(stringResource(when (result) {
            ProbeResult.SUCCEEDED -> R.string.probe_success
            ProbeResult.REJECTED -> R.string.probe_rejected
            ProbeResult.UNCERTAIN -> R.string.command_uncertain
            ProbeResult.NOT_SENT -> R.string.probe_not_sent
            ProbeResult.DISCONNECTED -> R.string.connection_disconnected
            ProbeResult.NONE -> R.string.probe_not_sent
        }))
    }
}
