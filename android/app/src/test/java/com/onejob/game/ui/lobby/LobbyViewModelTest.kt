package com.onejob.game.ui.lobby

import androidx.lifecycle.ViewModelStore
import com.onejob.game.LobbyTestRepository
import com.onejob.game.MainDispatcherRule
import com.onejob.game.data.ConnectionStatus
import com.onejob.game.data.repository.*
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.runCurrent
import kotlinx.coroutines.test.runTest
import org.junit.After
import org.junit.Assert.*
import org.junit.Rule
import org.junit.Test

@OptIn(ExperimentalCoroutinesApi::class)
class LobbyViewModelTest {
    @get:Rule val main = MainDispatcherRule()
    private val store = ViewModelStore()
    private fun model(repo: LobbyTestRepository) = LobbyViewModel(repo).also { store.put("lobby", it) }
    @After fun clear() = store.clear()

    @Test fun onlyEligibleHostCanSendStartAndUnavailableNeverInventsRound() = runTest {
        val repo = LobbyTestRepository(); repo.seed(host = false, allReady = true)
        val model = model(repo); runCurrent()
        model.start(); runCurrent(); assertEquals(0, repo.starts)
        assertEquals(StartBlock.HOST_ONLY, model.uiState.value.startBlock)
        repo.seed(allReady = true, canStart = false); runCurrent()
        model.start(); runCurrent(); assertEquals(0, repo.starts)
        repo.seed(allReady = true); runCurrent(); assertTrue(model.uiState.value.canStart)
        model.start(); model.start(); runCurrent(); assertEquals(1, repo.starts)
        assertEquals(LobbyFeedback.FEATURE_UNAVAILABLE, model.uiState.value.feedback)
        assertTrue(model.uiState.value.keepLobby); assertNull(repo.session.value.publicRound)
    }
    @Test fun duplicateNamesHaveDistinctIdsAndReadyIsNeverOptimistic() = runTest {
        val repo = LobbyTestRepository(); repo.seed(); repo.readyResult = CompletableDeferred()
        val model = model(repo); runCurrent()
        assertEquals(2, model.uiState.value.members.map { it.id }.distinct().size)
        assertEquals(1, model.uiState.value.members.map { it.name }.distinct().size)
        model.toggleReady(); model.toggleReady(); runCurrent()
        assertEquals(listOf(true), repo.ready); assertFalse(model.uiState.value.localReady)
        assertFalse(model.uiState.value.canReady)
        repo.readyResult.complete(CommandResult.Accepted("ready", Operation.READY)); runCurrent()
        assertFalse(model.uiState.value.localReady)
        repo.seed(allReady = true); runCurrent(); assertTrue(model.uiState.value.localReady)
    }
    @Test fun disabledStartReasonsFollowRosterAndServerHints() = runTest {
        val repo = LobbyTestRepository(); repo.seed(count = 1)
        val model = model(repo); runCurrent(); assertEquals(StartBlock.TWO_PLAYERS, model.uiState.value.startBlock)
        repo.seed(); runCurrent(); assertEquals(StartBlock.READY, model.uiState.value.startBlock)
        repo.session.value = repo.session.value.copy(lobby = repo.session.value.lobby!!.let { it.copy(players = it.players.mapIndexed { index, player -> player.copy(connected = index == 0) }) })
        runCurrent(); assertEquals(StartBlock.CONNECTED, model.uiState.value.startBlock)
    }
    @Test fun reconnectClearsRosterAndDisablesControlsUntilFreshSession() = runTest {
        val repo = LobbyTestRepository(); repo.seed(allReady = true)
        val model = model(repo); runCurrent()
        repo.connection.value = ConnectionState(ConnectionStatus.RECONNECTING)
        repo.session.value = SessionState(); runCurrent()
        assertTrue(model.uiState.value.keepLobby); assertTrue(model.uiState.value.members.isEmpty())
        assertFalse(model.uiState.value.canReady); assertFalse(model.uiState.value.canStart)
        repo.seed(); runCurrent(); assertEquals(2, model.uiState.value.members.size)
        assertFalse(model.uiState.value.localReady)
    }
    @Test fun leaveRequiresConfirmationAndLaterAdmissionWorks() = runTest {
        val repo = LobbyTestRepository(); repo.seed()
        val model = model(repo); runCurrent()
        model.confirmLeave(); runCurrent(); assertEquals(0, repo.leaves)
        model.askLeave(); model.dismissLeave(); runCurrent(); assertTrue(model.uiState.value.keepLobby)
        model.askLeave(); model.confirmLeave(); model.confirmLeave(); runCurrent()
        assertEquals(1, repo.leaves); assertFalse(model.uiState.value.keepLobby)
        assertEquals(LobbyFeedback.LEFT, model.uiState.value.feedback)
        repo.seed(); runCurrent(); assertTrue(model.uiState.value.keepLobby)
        assertTrue(model.uiState.value.canReady); assertNull(model.uiState.value.feedback)
    }
    @Test fun expiryOrRoomRemovalEndsLobbyAndDoesNotStartAdmission() = runTest {
        val repo = LobbyTestRepository(); repo.seed()
        val model = model(repo); runCurrent()
        repo.connection.value = ConnectionState(ConnectionStatus.SESSION_EXPIRED)
        repo.session.value = SessionState(); runCurrent()
        assertFalse(model.uiState.value.keepLobby)
        assertEquals(LobbyFeedback.EXPIRED, model.uiState.value.feedback)
        assertEquals(0, repo.admissionCalls)
    }
    @Test fun localOnlyLeaveExplainsReservedSeatAndLateReplyCannotReplaceLeave() = runTest {
        val repo = LobbyTestRepository(); repo.seed()
        repo.leaveResult = CommandResult.LeftLocally
        repo.readyResult = CompletableDeferred()
        val model = model(repo); runCurrent()
        model.toggleReady(); runCurrent()
        model.askLeave(); model.confirmLeave(); runCurrent()
        assertEquals(LobbyFeedback.LEFT_UNCERTAIN, model.uiState.value.feedback)
        repo.readyResult.complete(CommandResult.Rejected("old-ready", RemoteCode.NOT_HOST)); runCurrent()
        assertEquals(LobbyFeedback.LEFT_UNCERTAIN, model.uiState.value.feedback)
        assertNull(model.uiState.value.pending); assertFalse(model.uiState.value.keepLobby)
    }
}
