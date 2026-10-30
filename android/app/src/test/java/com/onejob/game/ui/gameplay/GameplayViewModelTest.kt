package com.onejob.game.ui.gameplay

import androidx.lifecycle.ViewModelStore
import com.onejob.game.MainDispatcherRule
import com.onejob.game.data.ConnectionStatus
import com.onejob.game.data.GameRepository
import com.onejob.game.data.UnavailableGameRepository
import com.onejob.game.data.protocol.*
import com.onejob.game.data.repository.*
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.test.*
import kotlinx.serialization.json.*
import org.junit.After
import org.junit.Assert.*
import org.junit.Rule
import org.junit.Test

private class ControlsRepository : GameRepository by UnavailableGameRepository() {
    override val connection = MutableStateFlow(ConnectionState(ConnectionStatus.CONNECTED))
    override val session = MutableStateFlow(SessionState())
    val calls = mutableListOf<PlayerAction>()
    val replies = mutableListOf<CompletableDeferred<CommandResult>>()
    override suspend fun performAction(roundId: String, action: PlayerAction): CommandResult {
        assertEquals(session.value.assigned!!.round_id, roundId)
        calls += action
        return CompletableDeferred<CommandResult>().also { replies += it }.await()
    }
}

@OptIn(ExperimentalCoroutinesApi::class)
class GameplayViewModelTest {
    @get:Rule val main = MainDispatcherRule()
    private val store = ViewModelStore()
    @After fun clear() = store.clear()

    private fun seed(repo: ControlsRepository, dual: Boolean = true) {
        val codec = ProtocolCodec()
        val cases = codec.json.parseToJsonElement(javaClass.classLoader!!.getResourceAsStream("phase09.json")!!.bufferedReader().use { it.readText() }).jsonArray
        val case = cases.first { entry ->
            entry.jsonObject["events"]?.jsonArray?.firstOrNull()?.jsonObject?.get("payload")
                ?.jsonObject?.get("roles")?.jsonArray?.let { (it.size == 2) == dual } == true
        }.jsonObject
        val assigned = ((codec.decode(case.getValue("events").jsonArray.first().toString()) as DecodedFrame.Message).message as ServerMessage.RoleAssigned).payload
        val state = ((codec.decode(case.getValue("response").toString()) as DecodedFrame.Message).message as ServerMessage.RoleState).payload
        repo.session.value = SessionState(SessionIdentity("ABCD23", "00000000-0000-0000-0000-000000000001"), assigned = assigned, roleState = state)
    }
    private fun model(repo: ControlsRepository, scope: TestScope) = GameplayViewModel(repo) { scope.testScheduler.currentTime }.also { store.put("game", it) }
    private fun accept(repo: ControlsRepository, index: Int) { repo.replies[index].complete(CommandResult.Accepted("action", Operation.ACTION)) }

    @Test fun ownedIntentsUseServerStateAndNeverComputeTimeResourcesOrOutcome() = runTest {
        val repo = ControlsRepository(); seed(repo)
        val model = model(repo, this); runCurrent()
        val original = model.uiState.value.snapshot!!
        model.select(StationRole.PILOT); assertEquals(StationRole.ENGINEER, model.uiState.value.selected)
        model.act(PlayerAction.Evade); runCurrent(); assertTrue(repo.calls.isEmpty())
        model.setOutput(80); runCurrent(); assertEquals(PlayerAction.SetEnginePower(80), repo.calls.single())
        accept(repo, 0); runCurrent()
        assertEquals(original, model.uiState.value.snapshot)
        advanceTimeBy(1_000); runCurrent()
        assertEquals(original.public.remaining_ms, model.uiState.value.snapshot!!.public.remaining_ms)
        val accepted = original.copy(stations = original.stations.copy(engineer = original.stations.engineer!!.copy(output = 80)))
        repo.session.value = repo.session.value.copy(roleState = accepted); runCurrent()
        assertEquals(80, model.uiState.value.snapshot!!.stations.engineer!!.output)
        assertNull(model.uiState.value.outputDraft)
    }

    @Test fun sliderHasOneInFlightAndConflatesLatestAtNoMoreThanTenHertz() = runTest {
        val repo = ControlsRepository(); seed(repo)
        val model = model(repo, this); runCurrent()
        model.setOutput(1); runCurrent()
        for (value in 2..100) model.setOutput(value)
        runCurrent(); assertEquals(1, repo.calls.size)
        accept(repo, 0); runCurrent()
        advanceTimeBy(99); runCurrent(); assertEquals(1, repo.calls.size)
        advanceTimeBy(1); runCurrent(); assertEquals(2, repo.calls.size)
        assertEquals(PlayerAction.SetEnginePower(100), repo.calls.last())
        accept(repo, 1); runCurrent()
        advanceTimeBy(10_000); runCurrent(); assertEquals(2, repo.calls.size)
    }

    @Test fun shutdownDiscardsOutputQueuedBeforeItAndNeverTurnsEngineBackOnLocally() = runTest {
        val repo = ControlsRepository(); seed(repo)
        val model = model(repo, this); runCurrent()
        model.setOutput(10); runCurrent(); model.setOutput(90)
        model.act(PlayerAction.EmergencyShutdown); runCurrent()
        assertEquals(listOf(PlayerAction.SetEnginePower(10), PlayerAction.EmergencyShutdown), repo.calls)
        model.setOutput(80); runCurrent(); assertEquals(2, repo.calls.size)
        accept(repo, 0); accept(repo, 1); runCurrent()
        advanceTimeBy(1_000); runCurrent(); assertEquals(2, repo.calls.size)
        assertNull(model.uiState.value.outputDraft)
        assertEquals(60, model.uiState.value.snapshot!!.stations.engineer!!.output)
    }

    @Test fun duplicateButtonsAreGuardedAndPowerRejectionLeavesAcceptedSnapshotUntouched() = runTest {
        val repo = ControlsRepository(); seed(repo)
        val model = model(repo, this); runCurrent()
        val original = model.uiState.value.snapshot
        model.act(PlayerAction.EngineBoost); model.act(PlayerAction.EngineBoost); runCurrent()
        assertEquals(1, repo.calls.size)
        repo.replies.single().complete(CommandResult.Rejected("boost", RemoteCode.INSUFFICIENT_POWER)); runCurrent()
        assertEquals(ActionFeedback.POWER, model.uiState.value.feedback)
        assertEquals(original, model.uiState.value.snapshot)
    }

    @Test fun recoveryDiscardsPrivatePresentationAndQueuedActionsWithoutAutomaticResend() = runTest {
        val repo = ControlsRepository(); seed(repo)
        val model = model(repo, this); runCurrent()
        model.setOutput(20); runCurrent(); model.setOutput(90)
        repo.connection.value = ConnectionState(ConnectionStatus.RECONNECTING); runCurrent()
        assertNull(model.uiState.value.snapshot); assertTrue(model.uiState.value.instructions.isEmpty())
        assertFalse(model.uiState.value.canControl)
        accept(repo, 0); runCurrent()
        repo.connection.value = ConnectionState(ConnectionStatus.CONNECTED); runCurrent()
        advanceTimeBy(1_000); runCurrent(); assertEquals(1, repo.calls.size)
        assertNull(model.uiState.value.outputDraft)
    }

    @Test fun pauseAndTerminalDisableAllControlsAndDoNotRunAClientClock() = runTest {
        val repo = ControlsRepository(); seed(repo)
        val model = model(repo, this); runCurrent()
        val original = repo.session.value.roleState!!
        repo.session.value = repo.session.value.copy(roleState = original.copy(public = original.public.copy(stage = "paused", paused_from = "running")))
        runCurrent(); model.act(PlayerAction.Coolant); model.setOutput(100); runCurrent()
        assertTrue(repo.calls.isEmpty()); assertFalse(model.uiState.value.canControl)
        val terminal = original.public.copy(stage = "finished", result = RoundResult("defeat", "hull_destroyed", 20_000, 0, 0, 0, emptyList()))
        repo.session.value = repo.session.value.copy(roleState = original.copy(public = terminal)); runCurrent()
        assertEquals("defeat", model.uiState.value.snapshot!!.public.result!!.outcome)
        assertFalse(model.uiState.value.canControl)
    }

    @Test fun foreignMetadataOrStationMismatchNeverReachesPanels() = runTest {
        val repo = ControlsRepository(); seed(repo)
        val assigned = repo.session.value.assigned!!
        repo.session.value = repo.session.value.copy(assigned = assigned.copy(roles = listOf(StationRole.PILOT)))
        val model = model(repo, this); runCurrent()
        assertNull(model.uiState.value.snapshot)
        model.act(PlayerAction.Coolant); runCurrent(); assertTrue(repo.calls.isEmpty())
    }
}
