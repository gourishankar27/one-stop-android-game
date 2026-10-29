package com.onejob.game.ui.roles

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
import kotlinx.coroutines.test.runCurrent
import kotlinx.coroutines.test.runTest
import kotlinx.serialization.json.*
import org.junit.After
import org.junit.Assert.*
import org.junit.Rule
import org.junit.Test

private class BriefingRepository : GameRepository by UnavailableGameRepository() {
    override val connection = MutableStateFlow(ConnectionState(ConnectionStatus.CONNECTED))
    override val session = MutableStateFlow(SessionState())
    var reply = CompletableDeferred<CommandResult>()
    val acknowledgements = mutableListOf<String>()
    override suspend fun acknowledgeBriefing(roundId: String): CommandResult { acknowledgements += roundId; return reply.await() }
}

@OptIn(ExperimentalCoroutinesApi::class)
class RoleViewModelTest {
    @get:Rule val main = MainDispatcherRule()
    private val store = ViewModelStore()
    @After fun clear() = store.clear()
    private fun seed(repo: BriefingRepository, dual: Boolean = true) {
        val codec = ProtocolCodec()
        val cases = codec.json.parseToJsonElement(javaClass.classLoader!!.getResourceAsStream("phase08.json")!!.bufferedReader().use { it.readText() }).jsonArray
        for (case in cases) {
            val event = case.jsonObject["events"]?.jsonArray?.firstOrNull() ?: continue
            val assigned = ((codec.decode(event.toString()) as DecodedFrame.Message).message as ServerMessage.RoleAssigned).payload
            if ((assigned.roles.size == 2) == dual) {
                val state = ((codec.decode(case.jsonObject.getValue("response").toString()) as DecodedFrame.Message).message as ServerMessage.RoleState).payload
                repo.session.value = SessionState(SessionIdentity("ABCD23", "00000000-0000-0000-0000-000000000001"), assigned = assigned, roleState = state)
                return
            }
        }
        error("Missing synthetic fixture")
    }
    private fun model(repo: BriefingRepository) = RoleViewModel(repo).also { store.put("role", it) }

    @Test fun dualStationAcknowledgementRequiresExplicitReadOfBothOwnedInstructions() = runTest {
        val repo = BriefingRepository(); seed(repo)
        val model = model(repo); runCurrent()
        assertEquals(listOf(StationRole.ENGINEER, StationRole.SHIELDS), model.uiState.value.instructions.map { it.role })
        model.acknowledge(); runCurrent(); assertTrue(repo.acknowledgements.isEmpty())
        model.confirmRead(); runCurrent(); assertFalse(model.uiState.value.canAcknowledge)
        model.select(StationRole.PILOT); runCurrent(); assertEquals(StationRole.ENGINEER, model.uiState.value.selected)
        model.select(StationRole.SHIELDS); model.confirmRead(); runCurrent()
        assertTrue(model.uiState.value.canAcknowledge)
        model.acknowledge(); model.acknowledge(); runCurrent()
        assertEquals(1, repo.acknowledgements.size); assertTrue(model.uiState.value.pending)
        repo.reply.complete(CommandResult.Accepted("read", Operation.BRIEFING)); runCurrent()
        assertFalse(model.uiState.value.acknowledged)
    }
    @Test fun oneStationReaderSeesOnlyOwnMetadataAndServerHoldCannotStartSimulation() = runTest {
        val repo = BriefingRepository(); seed(repo, dual = false)
        val model = model(repo); runCurrent()
        assertEquals(1, model.uiState.value.instructions.size)
        model.confirmRead(); assertTrue(model.uiState.value.canAcknowledge)
        val snapshot = repo.session.value.roleState!!
        repo.session.value = repo.session.value.copy(roleState = snapshot.copy(briefing = BriefingStatus(true, emptyList(), 0, true, true)))
        runCurrent()
        assertTrue(model.uiState.value.acknowledged && model.uiState.value.held)
        assertFalse(model.uiState.value.canAcknowledge)
        assertEquals(0L, repo.session.value.roleState!!.public.tick_index)
    }
    @Test fun reconnectClearsPrivatePresentationAndReadHistoryUntilFreshSnapshot() = runTest {
        val repo = BriefingRepository(); seed(repo)
        val model = model(repo); runCurrent(); model.confirmRead()
        repo.connection.value = ConnectionState(ConnectionStatus.RECONNECTING)
        repo.session.value = SessionState(); runCurrent()
        assertTrue(model.uiState.value.instructions.isEmpty() && model.uiState.value.read.isEmpty())
        assertFalse(model.uiState.value.canAcknowledge)
        seed(repo); repo.connection.value = ConnectionState(ConnectionStatus.CONNECTED); runCurrent()
        assertTrue(model.uiState.value.read.isEmpty()); assertFalse(model.uiState.value.canAcknowledge)
    }
    @Test fun pausedAndAbortedBriefingsNeverPermitAcknowledgement() = runTest {
        val repo = BriefingRepository(); seed(repo)
        val model = model(repo); runCurrent()
        model.confirmRead(); model.select(StationRole.SHIELDS); model.confirmRead()
        val snapshot = repo.session.value.roleState!!
        repo.session.value = repo.session.value.copy(roleState = snapshot.copy(public = snapshot.public.copy(stage = "paused", paused_from = "briefing")))
        runCurrent(); assertTrue(model.uiState.value.paused); assertFalse(model.uiState.value.canAcknowledge)
        val result = RoundResult("aborted", "briefing_timeout", 0, 100, 0, 0, emptyList())
        repo.session.value = repo.session.value.copy(roleState = snapshot.copy(public = snapshot.public.copy(stage = "aborted", result = result)))
        runCurrent(); assertEquals("briefing_timeout", model.uiState.value.abortReason)
        assertFalse(model.uiState.value.canRead || model.uiState.value.canAcknowledge)
    }
    @Test fun mismatchedMetadataNeverRendersForeignInstructions() = runTest {
        val repo = BriefingRepository(); seed(repo)
        val assigned = repo.session.value.assigned!!
        repo.session.value = repo.session.value.copy(assigned = assigned.copy(instructions = assigned.instructions + RoleInstruction(StationRole.PILOT, "FOREIGN", listOf("SECRET_SENTINEL"))))
        val model = model(repo); runCurrent()
        assertTrue(model.uiState.value.instructions.isEmpty()); assertFalse(model.uiState.value.canAcknowledge)
    }
}
