package com.onejob.game

import androidx.compose.ui.semantics.SemanticsActions
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createComposeRule
import com.onejob.game.app.OneJobApp
import com.onejob.game.data.ConnectionStatus
import com.onejob.game.data.GameRepository
import com.onejob.game.data.UnavailableGameRepository
import com.onejob.game.data.protocol.*
import com.onejob.game.data.repository.*
import com.onejob.game.ui.theme.OneJobTheme
import kotlinx.coroutines.flow.MutableStateFlow
import org.junit.Assert.*
import org.junit.Rule
import org.junit.Test

private const val GAME_ROUND = "00000000-0000-0000-0000-000000000099"
private const val GAME_PLAYER = "00000000-0000-0000-0000-000000000001"

private class ControlsUiRepository(dual: Boolean) : GameRepository by UnavailableGameRepository() {
    override val connection = MutableStateFlow(ConnectionState(ConnectionStatus.CONNECTED))
    override val session = MutableStateFlow(SessionState())
    val actions = mutableListOf<PlayerAction>()
    var reply: CommandResult = CommandResult.Accepted("action", Operation.ACTION)
    init {
        val roles = if (dual) listOf(StationRole.ENGINEER, StationRole.SHIELDS) else listOf(StationRole.PILOT)
        val metadata = roles.map { RoleInstruction(it, it.name.lowercase().replaceFirstChar(Char::uppercase), listOf("Own instruction")) }
        val public = PublicRound(GAME_ROUND, "running", 20, 88_000, null, null, 100, 60, emptyList(), null)
        val stations = if (dual) OwnedStations(
            engineer = EngineerView(40, 300, 5, EngineerCooldowns(0,0), 0,
                listOf(EngineerInstruction(1, 50, 500, 1000))),
            shields = ShieldsView(600, true, Facing.LEFT, ShieldsCooldowns(0,0), 0,0,emptyList()),
        ) else OwnedStations(pilot = PilotView(LaneValue.CENTER,false,0,PilotCooldowns(0,0),emptyList()))
        session.value = SessionState(identity = SessionIdentity("ABCD23",GAME_PLAYER),
            assigned = RoleAssignedPayload(GAME_ROUND,roles,metadata),
            roleState = RoleStatePayload(public,stations,BriefingStatus(true,emptyList(),0,true,false)))
    }
    override suspend fun performAction(roundId: String, action: PlayerAction): CommandResult {
        assertEquals(GAME_ROUND,roundId); actions += action; return reply
    }
}

class GameplayUiTest {
    @get:Rule val compose = createComposeRule()
    private fun show(repo: ControlsUiRepository) { compose.setContent { OneJobTheme { OneJobApp(repo) } } }

    @Test fun pilotHasOnlyOwnControlsAndEmitsTypedIntentWithoutOptimisticShipMutation() {
        val repo = ControlsUiRepository(false); show(repo)
        compose.onNodeWithTag("engineOutput").assertDoesNotExist()
        compose.onNodeWithTag("gameStation-SHIELDS").assertDoesNotExist()
        compose.onNodeWithTag("moveLeft").performScrollTo().performClick()
        compose.waitUntil { repo.actions.isNotEmpty() }
        compose.runOnIdle { assertEquals(PlayerAction.MoveLane(Direction.LEFT),repo.actions.single()) }
        compose.onNodeWithText("Lane: center").performScrollTo().assertIsDisplayed()
        compose.onNodeWithTag("actionFeedback").performScrollTo().assertTextEquals("Action accepted.")
        compose.runOnIdle {
            val state = repo.session.value.roleState!!
            repo.session.value = repo.session.value.copy(roleState = state.copy(stations = state.stations.copy(
                pilot = state.stations.pilot!!.copy(lane = LaneValue.LEFT))))
        }
        compose.onNodeWithText("Lane: left").performScrollTo().assertIsDisplayed()
    }

    @Test fun dualStationsKeepInactiveAttentionBadgeAndSliderIsOnlyAPreview() {
        val repo = ControlsUiRepository(true); show(repo)
        compose.onNodeWithTag("gameStation-PILOT").assertDoesNotExist()
        compose.onNodeWithTag("engineOutput").performScrollTo().performSemanticsAction(SemanticsActions.SetProgress) { it(75f) }
        compose.waitUntil { repo.actions.isNotEmpty() }
        compose.runOnIdle { assertEquals(PlayerAction.SetEnginePower(75),repo.actions.last()) }
        compose.onNodeWithTag("engineValues").performScrollTo().assertTextContains("Accepted output: 40", substring = true)
        compose.onNodeWithTag("gameStation-SHIELDS").performScrollTo().performClick()
        compose.onNodeWithTag("gameStation-ENGINEER").assertTextEquals("Engineer · attention")
        compose.onNodeWithTag("engineOutput").assertDoesNotExist()
        compose.onNodeWithTag("facing-RIGHT").performScrollTo().performClick()
        compose.waitUntil { repo.actions.size == 2 }
        compose.runOnIdle { assertEquals(PlayerAction.SetShield(true,Facing.RIGHT),repo.actions.last()) }
        compose.onNodeWithTag("shieldValues").performScrollTo().assertTextContains("Facing: left", substring = true)
    }

    @Test fun rejectedPowerIsVisibleAndDoesNotChangeAcceptedOutput() {
        val repo = ControlsUiRepository(true)
        repo.reply = CommandResult.Rejected("boost",RemoteCode.INSUFFICIENT_POWER)
        show(repo)
        compose.onNodeWithTag("engineBoost").performScrollTo().performClick()
        compose.onNodeWithTag("actionFeedback").performScrollTo()
            .assertTextEquals("Not enough power. Coordinate with Engineer and Shields.")
        compose.onNodeWithTag("engineValues").performScrollTo().assertTextContains("Accepted output: 40", substring = true)
    }

    @Test fun serverPauseAndTerminalStayOnGameplayWithoutResultsNavigation() {
        val repo = ControlsUiRepository(false); show(repo)
        compose.runOnIdle {
            val state = repo.session.value.roleState!!
            repo.session.value = repo.session.value.copy(roleState = state.copy(public = state.public.copy(stage="paused",paused_from="running")))
        }
        compose.onNodeWithTag("evade").performScrollTo().assertIsNotEnabled()
        compose.onNodeWithText("Paused while the crew reconnects. Controls and round time are paused.").performScrollTo().assertIsDisplayed()
        compose.runOnIdle {
            val state = repo.session.value.roleState!!
            repo.session.value = repo.session.value.copy(roleState = state.copy(public = state.public.copy(
                stage="finished",paused_from=null,result=RoundResult("victory","survived",90_000,100,0,0,emptyList()))))
        }
        compose.onNodeWithTag("terminalSummary").performScrollTo().assertTextEquals("Survived together")
        compose.onNodeWithTag("evade").assertDoesNotExist()
        compose.onNodeWithText("Results preview").assertDoesNotExist()
    }

    @Test fun pilotGetsPublicLabelAndOnlyPrivateImpactLaneWithServerDeadline() {
        val repo = ControlsUiRepository(false)
        val old = repo.session.value.roleState!!
        repo.session.value = repo.session.value.copy(roleState = old.copy(
            public = old.public.copy(warnings = listOf(PublicWarning(1,"asteroid","Asteroid approach"))),
            stations = old.stations.copy(pilot = old.stations.pilot!!.copy(
                hazards = listOf(PilotHazard(1,LaneValue.RIGHT,8000))))))
        show(repo)
        compose.onNodeWithTag("publicWarning-1").performScrollTo().assertTextEquals("Asteroid approach")
        compose.onNodeWithTag("privateWarning-1").performScrollTo().assertTextContains("Impact lane: right", substring = true)
        compose.onNodeWithTag("privateWarning-1").assertTextContains("8.0 s", substring = true)
        compose.onNodeWithTag("gameStation-ENGINEER").assertDoesNotExist()
        compose.onNodeWithTag("facing-RIGHT").assertDoesNotExist()
        compose.runOnIdle {
            repo.session.value = repo.session.value.copy(roleState = repo.session.value.roleState!!.let {
                it.copy(public=it.public.copy(stage="paused",paused_from="running"))
            })
        }
        compose.onNodeWithTag("privateWarning-1").assertTextContains("8.0 s", substring = true)
        compose.onNodeWithTag("evade").performScrollTo().assertIsNotEnabled()
    }

    @Test fun dualWarningsKeepInactiveBadgeAndOnlySelectedStationInstructions() {
        val repo = ControlsUiRepository(true)
        val old = repo.session.value.roleState!!
        repo.session.value = repo.session.value.copy(roleState = old.copy(
            public = old.public.copy(warnings = listOf(PublicWarning(1,"overheating","Engine overheating"),
                PublicWarning(2,"shield_overload","Shield overload"))),
            stations = old.stations.copy(
                engineer = old.stations.engineer!!.copy(instructions = listOf(EngineerInstruction(1,50,550,4000),EngineerInstruction(2,45,null,6000))),
                shields = old.stations.shields!!.copy(instructions = listOf(ShieldsInstruction(2,null,true,6000))))))
        show(repo)
        compose.onNodeWithTag("privateWarning-1").performScrollTo().assertTextContains("Cool to 550", substring = true)
        compose.onNodeWithTag("privateWarning-2").performScrollTo().assertTextContains("Hold output at 45", substring = true)
        compose.onNodeWithTag("gameStation-SHIELDS").performScrollTo().assertTextEquals("Shields · attention").performClick()
        compose.onNodeWithTag("privateWarning-1").assertDoesNotExist()
        compose.onNodeWithTag("privateWarning-2").performScrollTo().assertTextContains("Deactivate shields", substring = true)
        compose.onNodeWithTag("gameStation-ENGINEER").performScrollTo().assertTextEquals("Engineer · attention")
        compose.runOnIdle {
            val current = repo.session.value.roleState!!
            repo.session.value = repo.session.value.copy(roleState = current.copy(
                public=current.public.copy(warnings=emptyList()),
                stations=current.stations.copy(engineer=current.stations.engineer!!.copy(instructions=emptyList()),
                    shields=current.stations.shields!!.copy(instructions=emptyList()))))
        }
        compose.onNodeWithTag("privateWarning-2").assertDoesNotExist()
        compose.onNodeWithTag("publicWarning-1").assertDoesNotExist()
        compose.onNodeWithTag("gameStation-ENGINEER").assertTextEquals("Engineer")
    }

    @Test fun shieldFacingInstructionDoesNotRevealPilotLane() {
        val repo = ControlsUiRepository(true)
        val old = repo.session.value.roleState!!
        repo.session.value = repo.session.value.copy(roleState = old.copy(
            public=old.public.copy(warnings=listOf(PublicWarning(3,"asteroid","Asteroid approach"))),
            stations=old.stations.copy(engineer=old.stations.engineer!!.copy(instructions=emptyList()),
                shields=old.stations.shields!!.copy(instructions=listOf(ShieldsInstruction(3,Facing.REAR,false,7000))))))
        show(repo)
        compose.onNodeWithTag("gameStation-SHIELDS").performScrollTo().performClick()
        compose.onNodeWithTag("privateWarning-3").performScrollTo().assertTextContains("Cover rear", substring = true)
        compose.onNodeWithText("Impact lane:", substring=true).assertDoesNotExist()
        compose.onNodeWithTag("moveLeft").assertDoesNotExist()
    }

    @Test fun sharedLifecycleFeedbackDoesNotLocallyRemoveWarningOrChangeHull() {
        val repo = ControlsUiRepository(false)
        val old = repo.session.value.roleState!!
        repo.session.value = repo.session.value.copy(
            emergencyEvent=EmergencyEventPayload(GAME_ROUND,1,"asteroid","resolved"),
            roleState=old.copy(public=old.public.copy(warnings=listOf(PublicWarning(1,"asteroid","Asteroid approach")))))
        show(repo)
        compose.onNodeWithTag("emergencyEvent-1-resolved").performScrollTo().assertTextEquals("Asteroid approach: resolved")
        compose.onNodeWithTag("publicWarning-1").performScrollTo().assertIsDisplayed()
        compose.onNodeWithTag("serverHull").performScrollTo().assertTextContains("Hull: 100%",substring=true)
    }
}
