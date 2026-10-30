package com.onejob.game

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
import org.junit.Assert.assertEquals
import org.junit.Rule
import org.junit.Test

private const val ROLE_ROUND = "00000000-0000-0000-0000-000000000099"
private const val ROLE_PLAYER = "00000000-0000-0000-0000-000000000001"

private class RoleUiRepository(dual: Boolean) : GameRepository by UnavailableGameRepository() {
    override val connection = MutableStateFlow(ConnectionState(ConnectionStatus.CONNECTED))
    override val session = MutableStateFlow(SessionState())
    var acknowledgements = 0
    init {
        val roles = if (dual) listOf(StationRole.ENGINEER, StationRole.SHIELDS) else listOf(StationRole.PILOT)
        val metadata = roles.map { RoleInstruction(it, it.name.lowercase().replaceFirstChar(Char::uppercase), listOf(it.name + " own instruction")) }
        val view = PublicRound(ROLE_ROUND, "briefing", 0, 90_000, null, null, 100, 60, emptyList(), null)
        val stations = if (dual) OwnedStations(
            engineer = EngineerView(50, 100, 50, EngineerCooldowns(0, 0), 0, emptyList()),
            shields = ShieldsView(600, false, Facing.FRONT, ShieldsCooldowns(0, 0), 0, 0, emptyList()),
        ) else OwnedStations(pilot = PilotView(LaneValue.CENTER, true, 0, PilotCooldowns(0, 0), emptyList()))
        val briefing = BriefingStatus(false, listOf(ROLE_PLAYER), 60_000, false, false)
        session.value = SessionState(
            identity = SessionIdentity("ABCD23", ROLE_PLAYER),
            assigned = RoleAssignedPayload(ROLE_ROUND, roles, metadata),
            roleState = RoleStatePayload(view, stations, briefing),
        )
    }
    override suspend fun acknowledgeBriefing(roundId: String): CommandResult {
        assertEquals(ROLE_ROUND, roundId); acknowledgements++
        return CommandResult.Accepted("read", Operation.BRIEFING)
    }
}

class RoleUiTest {
    @get:Rule val compose = createComposeRule()
    private fun show(repo: RoleUiRepository) { compose.setContent { OneJobTheme { OneJobApp(repo) } } }

    @Test fun twoStationInstructionsMustBothBeReadBeforeAcknowledgement() {
        val repo = RoleUiRepository(true); show(repo)
        compose.onNodeWithTag("station-PILOT").assertDoesNotExist()
        compose.onNodeWithText("PILOT own instruction").assertDoesNotExist()
        compose.onNodeWithText("ENGINEER own instruction").performScrollTo().assertIsDisplayed()
        compose.onNodeWithText("SHIELDS own instruction").assertDoesNotExist()
        compose.onNodeWithTag("acknowledgeBriefing").performScrollTo().assertIsNotEnabled()
        compose.onNodeWithTag("readStation").performScrollTo().performClick()
        compose.onNodeWithTag("acknowledgeBriefing").assertIsNotEnabled()
        compose.onNodeWithTag("station-SHIELDS").performScrollTo().performClick()
        compose.onNodeWithText("SHIELDS own instruction").performScrollTo().assertIsDisplayed()
        compose.onNodeWithText("ENGINEER own instruction").assertDoesNotExist()
        compose.onNodeWithTag("readStation").performScrollTo().performClick()
        compose.onNodeWithTag("acknowledgeBriefing").performScrollTo().assertIsEnabled().performClick()
        compose.runOnIdle { assertEquals(1, repo.acknowledgements) }
    }

    @Test fun ownStationOnlyAndServerHoldNeverNavigateToGameplay() {
        val repo = RoleUiRepository(false); show(repo)
        compose.onNodeWithTag("station-ENGINEER").assertDoesNotExist()
        compose.onNodeWithTag("station-SHIELDS").assertDoesNotExist()
        compose.onNodeWithTag("readStation").performScrollTo().performClick()
        compose.onNodeWithTag("acknowledgeBriefing").performScrollTo().performClick()
        compose.runOnIdle {
            val state = repo.session.value.roleState!!
            repo.session.value = repo.session.value.copy(roleState = state.copy(briefing = BriefingStatus(true, emptyList(), 0, true, true)))
        }
        compose.onNodeWithText("Briefings complete. Gameplay is not available in this build.").performScrollTo().assertIsDisplayed()
        compose.onNodeWithTag("acknowledgeBriefing").assertIsNotEnabled()
        compose.onNodeWithText("Gameplay preview").assertDoesNotExist()
    }

    @Test fun serverTimeoutOpensAuthoritativeResultsWithoutControls() {
        val repo = RoleUiRepository(false); show(repo)
        compose.runOnIdle {
            val state = repo.session.value.roleState!!
            val result = RoundResult("aborted", "briefing_timeout", 0, 100, 0, 0, emptyList())
            repo.session.value = repo.session.value.copy(roleState = state.copy(public = state.public.copy(stage = "aborted", result = result)))
        }
        compose.onNodeWithText("Briefing timed out before everyone acknowledged.").performScrollTo().assertIsDisplayed()
        compose.onNodeWithTag("terminalSummary").performScrollTo().assertTextEquals("Round aborted")
        compose.onNodeWithTag("acknowledgeBriefing").assertDoesNotExist()
        compose.onNodeWithText("Results preview").assertDoesNotExist()
    }
}
