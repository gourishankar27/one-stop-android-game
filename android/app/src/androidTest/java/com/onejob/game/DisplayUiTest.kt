package com.onejob.game

import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createComposeRule
import com.onejob.game.app.OneJobApp
import com.onejob.game.data.*
import com.onejob.game.data.protocol.*
import com.onejob.game.data.repository.*
import com.onejob.game.ui.theme.OneJobTheme
import kotlinx.coroutines.flow.MutableStateFlow
import org.junit.Assert.*
import org.junit.Rule
import org.junit.Test

private class DisplayUiRepository : GameRepository by UnavailableGameRepository() {
    override val connection=MutableStateFlow(ConnectionState(ConnectionStatus.CONNECTED))
    override val session=MutableStateFlow(SessionState())
    val players=(1..2).map { LobbyPlayer("00000000-0000-0000-0000-00000000000$it","Crew $it",true,false) }
    var joins=0;var leaves=0;var code=""
    override suspend fun joinDisplay(roomCode:String):CommandResult {
        joins++;code=roomCode;show();return CommandResult.Accepted("join",Operation.JOIN_DISPLAY)
    }
    override suspend fun leave():CommandResult {
        leaves++;session.value=SessionState();connection.value=ConnectionState(ConnectionStatus.DISCONNECTED)
        return CommandResult.Accepted("leave",Operation.LEAVE)
    }
    fun show(stage:String="lobby",countdown:Long?=null,result:RoundResult?=null) {
        session.value=SessionState(SessionIdentity("ABCD23",null,"display"),
            LobbyPayload("ABCD23",stage,players[0].player_id,players,false),
            if(stage=="lobby") null else PublicRound("00000000-0000-0000-0000-000000000099",stage,42,55800,countdown,
                if(stage=="paused") "countdown" else null,73,64,
                if(stage=="running") listOf(PublicWarning(9,"asteroid","Asteroid approach")) else emptyList(),result),
            assigned=RoleAssignedPayload("00000000-0000-0000-0000-000000000099",listOf(StationRole.PILOT),
                listOf(RoleInstruction(StationRole.PILOT,"PRIVATE_SENTINEL",listOf("PRIVATE_SENTINEL")))),
            publicSnapshotReceived=true)
    }
}

class DisplayUiTest {
    @get:Rule val compose=createComposeRule()
    private fun show(repo:DisplayUiRepository) {compose.setContent {OneJobTheme {OneJobApp(repo)}}}
    private fun noControls() {
        for(tag in listOf("readyButton","startButton","readStation","acknowledgeBriefing","moveLeft","engineOutput","shieldToggle","resultsReady","playAgain","returnToLobby"))
            compose.onNodeWithTag(tag).assertDoesNotExist()
        compose.onNodeWithText("PRIVATE_SENTINEL").assertDoesNotExist()
    }
    @Test fun displayAdmissionHasOnlyCodeAndOpensPublicLobby() {
        val repo=DisplayUiRepository();show(repo)
        compose.onNodeWithText("Join display").performClick()
        compose.onNodeWithTag("nameInput").assertDoesNotExist()
        compose.onNodeWithTag("codeInput").performTextInput("abcd23")
        compose.onNodeWithTag("submitAdmission").performScrollTo().performClick()
        compose.waitUntil {repo.joins==1}
        assertEquals("ABCD23",repo.code)
        compose.onNodeWithTag("displayCode").assertTextEquals("ABCD23")
        compose.onNodeWithText("Waiting for players to start").assertIsDisplayed();noControls()
    }
    @Test fun publicStagesWarningsAndResultsNeverRenderStationControlsOrLocalClock() {
        val repo=DisplayUiRepository();repo.show();show(repo);noControls()
        compose.runOnIdle {repo.show("countdown",3000)}
        compose.onNodeWithTag("displayCountdown").performScrollTo().assertTextEquals("3")
        compose.mainClock.advanceTimeBy(10000)
        compose.onNodeWithTag("displayCountdown").assertTextEquals("3")
        compose.runOnIdle {repo.show("paused",1000)}
        compose.onNodeWithTag("displayCountdown").assertTextEquals("1")
        compose.runOnIdle {repo.show("running")}
        compose.onNodeWithTag("displayWarning-9").performScrollTo().assertTextEquals("Asteroid approach")
        compose.onNodeWithTag("displayHull").performScrollTo().assertTextEquals("73%")
        compose.runOnIdle {repo.show("finished",result=RoundResult("victory","survived",60000,73,4,1,repo.players.map {ResultPlayer(it.player_id,it.name)}))}
        compose.onNodeWithTag("displayResult").performScrollTo().assertTextEquals("Survived together")
        compose.onNodeWithTag("displayResultCounts").performScrollTo().assertTextEquals("Resolved: 4 · Failed: 1");noControls()
        compose.runOnIdle {repo.show()}
        compose.onNodeWithText("Waiting for players to start").performScrollTo().assertIsDisplayed()
    }
    @Test fun recoveryHidesOldPublicStateAndLeaveRequiresConfirmation() {
        val repo=DisplayUiRepository();repo.show("running");show(repo)
        compose.onNodeWithTag("displayHull").performScrollTo().assertTextEquals("73%")
        compose.runOnIdle {repo.connection.value=ConnectionState(ConnectionStatus.RECONNECTING);repo.session.value=SessionState()}
        compose.onNodeWithTag("displayHull").assertDoesNotExist()
        compose.onNodeWithText("Restoring the public view…").performScrollTo().assertIsDisplayed()
        compose.runOnIdle {repo.show("running");repo.connection.value=ConnectionState(ConnectionStatus.CONNECTED)}
        compose.onNodeWithTag("displayHull").performScrollTo().assertTextEquals("73%")
        compose.onNodeWithText("Leave room").performScrollTo().performClick();assertEquals(0,repo.leaves)
        compose.onNodeWithText("Leave now").performClick()
        compose.waitUntil {repo.leaves==1};compose.onNodeWithText("Join display").assertIsDisplayed()
    }
}
