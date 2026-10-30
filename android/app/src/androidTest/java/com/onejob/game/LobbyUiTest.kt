package com.onejob.game

import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.test.espresso.Espresso
import com.onejob.game.app.OneJobApp
import com.onejob.game.data.ConnectionStatus
import com.onejob.game.data.GameRepository
import com.onejob.game.data.UnavailableGameRepository
import com.onejob.game.data.protocol.LobbyPayload
import com.onejob.game.data.protocol.LobbyPlayer
import com.onejob.game.data.repository.*
import com.onejob.game.ui.theme.OneJobTheme
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.flow.MutableStateFlow
import org.junit.Assert.*
import org.junit.Rule
import org.junit.Test

private class UiLobbyRepository : GameRepository by UnavailableGameRepository() {
    override val session = MutableStateFlow(SessionState())
    override val connection = MutableStateFlow(ConnectionState(ConnectionStatus.DISCONNECTED))
    var reply = CompletableDeferred<CommandResult>()
    var submittedName = ""
    var submittedCode = ""
    var submits = 0
    var readyRequests = 0
    var leaves = 0
    override suspend fun create(name: String): CommandResult { submittedName = name; submits++; return reply.await() }
    override suspend fun join(roomCode: String, name: String): CommandResult { submittedCode = roomCode; return create(name) }
    override suspend fun setReady(ready: Boolean): CommandResult { readyRequests++; return CommandResult.Accepted("ready", Operation.READY) }
    override suspend fun start() = CommandResult.Rejected("start", RemoteCode.FEATURE_UNAVAILABLE)
    override suspend fun leave(): CommandResult {
        leaves++; session.value = SessionState(); connection.value = ConnectionState(ConnectionStatus.DISCONNECTED)
        return CommandResult.Accepted("leave", Operation.LEAVE)
    }
    override suspend fun disconnect(): CommandResult { connection.value = ConnectionState(ConnectionStatus.DISCONNECTED); return CommandResult.LeftLocally }
    fun seed(host: Boolean = true, ready: Boolean = false) {
        val ids = listOf("00000000-0000-0000-0000-000000000001", "00000000-0000-0000-0000-000000000002")
        val players = ids.map { LobbyPlayer(it, "Crew", true, ready) }
        session.value = SessionState(SessionIdentity("ABCD23", ids[0]), LobbyPayload("ABCD23", "lobby", ids[if (host) 0 else 1], players, ready))
        connection.value = ConnectionState(ConnectionStatus.CONNECTED)
    }
}

class LobbyUiTest {
    @get:Rule val compose = createComposeRule()
    private fun show(repo: UiLobbyRepository) { compose.setContent { OneJobTheme { OneJobApp(repo) } } }
    private fun open(text: String) { compose.onNodeWithText(text).performScrollTo().performClick() }

    @Test fun admissionPreservesRejectedInputsAndNavigatesOnlyWithServerIdentity() {
        val repo = UiLobbyRepository(); show(repo)
        open("Join room")
        compose.onNodeWithTag("nameInput").performTextInput(" Crew ")
        compose.onNodeWithTag("codeInput").performTextInput(" abcd23 ")
        compose.onNodeWithTag("submitAdmission").performScrollTo().performClick().assertIsNotEnabled()
        compose.runOnIdle { assertEquals(1, repo.submits); assertEquals("Crew", repo.submittedName); assertEquals("ABCD23", repo.submittedCode) }
        compose.runOnIdle { repo.reply.complete(CommandResult.Rejected("join", RemoteCode.ROOM_FULL)) }
        compose.onNodeWithText("This room already has three players.").performScrollTo().assertIsDisplayed()
        compose.onNodeWithTag("nameInput").assertTextContains(" Crew ")
        compose.onNodeWithTag("codeInput").assertTextContains(" abcd23 ")
        compose.onNodeWithTag("lobbyCode").assertDoesNotExist()
        compose.runOnIdle { repo.reply = CompletableDeferred() }
        compose.onNodeWithTag("submitAdmission").performScrollTo().performClick()
        compose.runOnIdle { repo.seed(); repo.reply.complete(CommandResult.Accepted("join", Operation.JOIN)) }
        compose.onNodeWithTag("lobbyCode").assertTextEquals("ABCD23")
    }

    @Test fun duplicateRosterNamesReadyUpdatesAndUnavailableStartStayInLobby() {
        val repo = UiLobbyRepository().apply { seed() }; show(repo)
        compose.onAllNodesWithText("Crew").assertCountEquals(2)
        compose.onNodeWithTag("startButton").performScrollTo().assertIsNotEnabled()
        compose.onNodeWithTag("readyButton").performScrollTo().performClick()
        compose.runOnIdle { assertEquals(1, repo.readyRequests) }
        compose.onNodeWithTag("readyButton").assertTextContains("Ready up")
        compose.runOnIdle { repo.seed(ready = true) }
        compose.onNodeWithTag("readyButton").assertTextContains("Not ready")
        compose.onNodeWithTag("startButton").performScrollTo().assertIsEnabled().performClick()
        compose.onNodeWithText("This build supports lobbies. Starting a round is not available yet.").performScrollTo().assertIsDisplayed()
        compose.onNodeWithTag("lobbyCode").assertExists()
        compose.onNodeWithText("Role briefing preview").assertDoesNotExist()
    }

    @Test fun nonHostCannotStartAndBothBackAndLeaveRequireConfirmation() {
        val repo = UiLobbyRepository().apply { seed(host = false, ready = true) }; show(repo)
        compose.onNodeWithTag("startButton").performScrollTo().assertIsNotEnabled()
        compose.onNodeWithText("Only the host can start.").performScrollTo().assertIsDisplayed()
        Espresso.pressBack()
        compose.onNodeWithText("Leave this room?").assertIsDisplayed()
        compose.onNodeWithText("Stay").performClick()
        compose.runOnIdle { assertEquals(0, repo.leaves) }
        open("Leave room")
        compose.onNodeWithText("Leave now").performClick()
        compose.onNodeWithText("ONE JOB").assertIsDisplayed()
        compose.onNodeWithText("You left the room.").assertIsDisplayed()
        compose.runOnIdle { assertEquals(1, repo.leaves); assertNull(repo.session.value.identity) }
    }

    @Test fun expiryOrRoomRemovalReturnsHomeWithoutRecreatingMembership() {
        val repo = UiLobbyRepository().apply { seed() }; show(repo)
        compose.onNodeWithTag("lobbyCode").assertExists()
        compose.runOnIdle { repo.session.value = SessionState(); repo.connection.value = ConnectionState(ConnectionStatus.SESSION_EXPIRED) }
        compose.onNodeWithText("ONE JOB").assertIsDisplayed()
        compose.onNodeWithText("Your session ended or expired. The server may have restarted. Create or join a room again.").assertIsDisplayed()
        compose.runOnIdle { assertEquals(0, repo.submits) }
    }
}
