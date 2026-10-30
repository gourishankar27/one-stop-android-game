package com.onejob.game.ui.lobby

import com.onejob.game.LobbyTestRepository
import com.onejob.game.MainDispatcherRule
import com.onejob.game.data.repository.*
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.*
import org.junit.Assert.*
import org.junit.Rule
import org.junit.Test

@OptIn(ExperimentalCoroutinesApi::class)
class LifecycleCommandsTest {
    @get:Rule val main=MainDispatcherRule()
    private fun terminal(host: Boolean,ready: Boolean=true): LobbyTestRepository {
        val repo=LobbyTestRepository();repo.seed(host=host,allReady=ready)
        repo.session.value=repo.session.value.copy(lobby=repo.session.value.lobby!!.copy(stage="finished"))
        return repo
    }
    @Test fun hostCommandsGuardPendingAndWaitForAuthoritativeStage()=runTest {
        val repo=terminal(true);repo.lifecycleResult=CompletableDeferred()
        val model=LobbyViewModel(repo);runCurrent()
        assertTrue(model.uiState.value.canPlayAgain && model.uiState.value.canReturnToLobby)
        assertFalse(model.uiState.value.canStart)
        model.playAgain();model.playAgain();model.returnToLobby();model.toggleReady();runCurrent()
        assertEquals(1,repo.playAgains);assertEquals(0,repo.returns);assertTrue(repo.ready.isEmpty())
        assertEquals("finished",repo.session.value.lobby!!.stage)
        repo.lifecycleResult.complete(CommandResult.Accepted("again",Operation.PLAY_AGAIN));runCurrent()
        assertEquals("finished",repo.session.value.lobby!!.stage)
        repo.session.value=repo.session.value.copy(lobby=repo.session.value.lobby!!.copy(stage="briefing",can_start=false));runCurrent()
        assertFalse(model.uiState.value.canPlayAgain || model.uiState.value.canReturnToLobby || model.uiState.value.canReady)
    }
    @Test fun nonHostAndNotReadyCannotPlayAgainButReadyIsNotOptimistic()=runTest {
        val repo=terminal(false,false);val model=LobbyViewModel(repo);runCurrent()
        model.playAgain();model.returnToLobby();runCurrent()
        assertEquals(0,repo.playAgains+repo.returns)
        assertTrue(model.uiState.value.canReady)
        model.toggleReady();runCurrent()
        assertEquals(listOf(true),repo.ready);assertFalse(model.uiState.value.localReady)
    }
}
