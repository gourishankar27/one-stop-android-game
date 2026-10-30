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

private class LifecycleUiRepository(private val host: Boolean=true) : GameRepository by UnavailableGameRepository() {
    private val ids=(1..3).map { "00000000-0000-0000-0000-00000000000$it" }
    private var round="00000000-0000-0000-0000-000000000099"
    override val connection=MutableStateFlow(ConnectionState(ConnectionStatus.CONNECTED))
    override val session=MutableStateFlow(SessionState())
    var again=0;var returns=0;var acknowledgements=0;var ready=0
    fun show(stage: String, remaining: Long=3000, nextRound: Int?=null) {
        if(nextRound!=null) round="00000000-0000-0000-0000-000000000$nextRound"
        val terminal=stage in setOf("finished","aborted")
        val result=if(!terminal)null else RoundResult(if(stage=="aborted")"aborted" else "victory",
            if(stage=="aborted")"briefing_timeout" else "survived",if(stage=="aborted")0 else 60000,73,3,2,
            ids.mapIndexed { index,id->ResultPlayer(id,"Crew ${index+1}") })
        val public=PublicRound(round,stage,if(stage=="finished")600 else 0,
            if(stage=="finished")0 else 60000,if(stage=="countdown" || stage=="paused")remaining else null,
            if(stage=="paused")"countdown" else null,73,40,emptyList(),result)
        val roles=listOf(StationRole.PILOT)
        val metadata=listOf(RoleInstruction(StationRole.PILOT,"Pilot",listOf("Read your own station")))
        val briefing=stage in setOf("briefing","aborted")
        session.value=SessionState(SessionIdentity("ABCD23",ids[0]),
            LobbyPayload("ABCD23",stage,ids[if(host)0 else 1],ids.mapIndexed { index,id->LobbyPlayer(id,"Crew ${index+1}",true,false) },false),
            assigned=RoleAssignedPayload(round,roles,metadata),roleState=RoleStatePayload(public,
                OwnedStations(pilot=PilotView(LaneValue.CENTER,true,0,PilotCooldowns(0,0),emptyList())),
                BriefingStatus(!briefing,if(briefing)ids else emptyList(),if(briefing)60000 else 0,!briefing,false)))
        connection.value=ConnectionState(ConnectionStatus.CONNECTED)
    }
    fun allReady() {
        session.value=session.value.copy(lobby=session.value.lobby!!.let { lobby->
            lobby.copy(players=lobby.players.map { it.copy(ready=true) },can_start=true)
        })
    }
    fun lobby() { session.value=SessionState(session.value.identity,session.value.lobby!!.let {
        it.copy(stage="lobby",can_start=false,players=it.players.map { p->p.copy(ready=false) }) }) }
    override suspend fun setReady(ready: Boolean): CommandResult { this.ready++;return CommandResult.Accepted("ready",Operation.READY) }
    override suspend fun playAgain(): CommandResult { again++;return CommandResult.Accepted("again",Operation.PLAY_AGAIN) }
    override suspend fun returnToLobby(): CommandResult { returns++;return CommandResult.Accepted("lobby",Operation.RETURN_TO_LOBBY) }
    override suspend fun acknowledgeBriefing(roundId: String): CommandResult {
        assertEquals(round,roundId);acknowledgements++;return CommandResult.Accepted("read",Operation.BRIEFING)
    }
}

class LifecycleUiTest {
    @get:Rule val compose=createComposeRule()
    private fun show(repo: LifecycleUiRepository) { compose.setContent { OneJobTheme { OneJobApp(repo) } } }

    @Test fun countdownUsesServerValuesAndPauseNeverRunsAClientClock() {
        val repo=LifecycleUiRepository();repo.show("countdown");show(repo)
        compose.onNodeWithTag("serverCountdown").assertTextEquals("3")
        compose.onNodeWithTag("moveLeft").assertDoesNotExist()
        compose.mainClock.advanceTimeBy(10000)
        compose.onNodeWithTag("serverCountdown").assertTextEquals("3")
        compose.runOnIdle { repo.show("paused",1000) }
        compose.onNodeWithTag("serverCountdown").assertTextEquals("1")
        compose.onNodeWithTag("countdownPaused").assertIsDisplayed()
        compose.runOnIdle { repo.show("running") }
        compose.onNodeWithTag("moveLeft").performScrollTo().assertIsDisplayed()
        compose.onNodeWithTag("serverCountdown").assertDoesNotExist()
    }

    @Test fun snapshotResultsRematchTwiceAndReturnOnlyAfterServerTransitions() {
        val repo=LifecycleUiRepository();repo.show("finished");show(repo)
        for(cycle in 0..1) {
            compose.onNodeWithTag("terminalSummary").performScrollTo().assertTextEquals("Survived together")
            compose.onNodeWithTag("resultCounts").performScrollTo().assertTextEquals("Resolved: 3 · Failed: 2")
            compose.onNodeWithTag("playAgain").performScrollTo().assertIsNotEnabled()
            compose.onNodeWithTag("resultsReady").performScrollTo().performClick()
            compose.waitUntil { repo.ready==cycle+1 }
            compose.onNodeWithTag("resultsReady").assertTextEquals("Ready for another round")
            compose.runOnIdle { repo.allReady() }
            compose.onNodeWithTag("playAgain").performScrollTo().assertIsEnabled().performClick()
            compose.waitUntil { repo.again==cycle+1 }
            compose.onNodeWithTag("terminalSummary").performScrollTo().assertIsDisplayed()
            compose.runOnIdle { repo.show("briefing",nextRound=100+cycle) }
            compose.onNodeWithTag("readStation").performScrollTo().assertIsEnabled().performClick()
            compose.onNodeWithTag("acknowledgeBriefing").performScrollTo().performClick()
            compose.waitUntil { repo.acknowledgements==cycle+1 }
            compose.onNodeWithTag("stationTitle").performScrollTo().assertTextEquals("Pilot")
            compose.runOnIdle { repo.show("countdown") }
            compose.onNodeWithTag("serverCountdown").assertTextEquals("3")
            compose.runOnIdle { repo.show("running") }
            compose.onNodeWithTag("moveLeft").performScrollTo().assertIsDisplayed()
            compose.runOnIdle { repo.show("finished") }
        }
        compose.onNodeWithTag("returnToLobby").performScrollTo().performClick()
        compose.waitUntil { repo.returns==1 }
        compose.onNodeWithTag("terminalSummary").performScrollTo().assertIsDisplayed()
        compose.runOnIdle { repo.lobby() }
        compose.onNodeWithTag("lobbyCode").assertTextEquals("ABCD23")
        compose.onNodeWithTag("readyButton").performScrollTo().assertTextEquals("Ready up")
        compose.onNodeWithTag("resultCounts").assertDoesNotExist()
    }

    @Test fun guestsCanReadyButOnlyHostSeesRoundManagement() {
        val repo=LifecycleUiRepository(false);repo.show("finished");show(repo)
        compose.onNodeWithTag("playAgain").assertDoesNotExist()
        compose.onNodeWithTag("returnToLobby").assertDoesNotExist()
        compose.onNodeWithTag("resultsReady").performScrollTo().assertIsEnabled().performClick()
        compose.waitUntil { repo.ready==1 }
        assertEquals(0,repo.again+repo.returns)
    }

    @Test fun terminalReconnectAndBriefingAbortRestoreResultsWithoutAnEvent() {
        val repo=LifecycleUiRepository();repo.show("finished");show(repo)
        compose.onNodeWithTag("terminalSummary").performScrollTo().assertIsDisplayed()
        compose.runOnIdle {
            repo.connection.value=ConnectionState(ConnectionStatus.RECONNECTING)
            repo.session.value=SessionState(repo.session.value.identity)
        }
        compose.onNodeWithText("Restoring the server result…").assertIsDisplayed()
        compose.onNodeWithTag("terminalSummary").assertDoesNotExist()
        compose.runOnIdle { repo.show("finished") }
        compose.onNodeWithTag("terminalSummary").performScrollTo().assertTextEquals("Survived together")
        compose.runOnIdle { repo.show("aborted",nextRound=103) }
        compose.onNodeWithTag("terminalSummary").performScrollTo().assertTextEquals("Round aborted")
        compose.onNodeWithTag("readStation").assertDoesNotExist()
    }
}
