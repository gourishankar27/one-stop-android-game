package com.onejob.game

import androidx.compose.foundation.layout.Column
import androidx.compose.runtime.getValue
import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onNodeWithText
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.onejob.game.data.ConnectionStatus
import com.onejob.game.data.repository.ConnectionProblem
import com.onejob.game.data.repository.ConnectionState
import com.onejob.game.ui.connection.ConnectionFeedback
import com.onejob.game.ui.theme.OneJobTheme
import kotlinx.coroutines.flow.MutableStateFlow
import org.junit.Rule
import org.junit.Test

class ConnectionFeedbackTest {
    @get:Rule val compose = createComposeRule()

    @Test
    fun lifecycleCollectedConnectionFeedbackDistinguishesRecoveryProtocolAndUncertainty() {
        val states = MutableStateFlow(ConnectionState(ConnectionStatus.CONNECTING))
        compose.setContent {
            val state by states.collectAsStateWithLifecycle()
            OneJobTheme { Column { ConnectionFeedback(state) } }
        }
        compose.onNodeWithText("Connection: connecting").assertIsDisplayed()
        compose.runOnIdle { states.value = ConnectionState(ConnectionStatus.RECONNECTING, ConnectionProblem.NETWORK, 1) }
        compose.onNodeWithText("Connection: reconnecting").assertIsDisplayed()
        compose.onNodeWithText("The connection was interrupted. Retry or disconnect.").assertIsDisplayed()
        compose.runOnIdle { states.value = ConnectionState(ConnectionStatus.PROTOCOL_ERROR, ConnectionProblem.PROTOCOL) }
        compose.onNodeWithText("Connection: protocol error").assertIsDisplayed()
        compose.runOnIdle { states.value = ConnectionState(ConnectionStatus.CONNECTED, ConnectionProblem.COMMAND_UNCERTAIN) }
        compose.onNodeWithText("The reply did not arrive. The command may have happened; it will not be resent automatically.").assertIsDisplayed()
        compose.runOnIdle { states.value = ConnectionState(ConnectionStatus.UNAVAILABLE, ConnectionProblem.CONFIGURATION) }
        compose.onNodeWithText("Configure a valid debug endpoint before connecting.").assertIsDisplayed()
    }
}
