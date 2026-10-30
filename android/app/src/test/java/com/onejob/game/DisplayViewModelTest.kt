package com.onejob.game

import androidx.lifecycle.SavedStateHandle
import androidx.lifecycle.ViewModelStore
import com.onejob.game.data.ConnectionStatus
import com.onejob.game.data.repository.*
import com.onejob.game.navigation.*
import com.onejob.game.ui.display.DisplayViewModel
import com.onejob.game.ui.forms.*
import com.onejob.game.ui.lobby.LobbyFeedback
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.*
import org.junit.Assert.*
import org.junit.Rule
import org.junit.Test

@OptIn(ExperimentalCoroutinesApi::class)
class DisplayViewModelTest {
    @get:Rule val main=MainDispatcherRule()
    @Test fun codeOnlyAdmissionNormalizesAndRetainsCapacityFeedback() = runTest {
        val repo=LobbyTestRepository();val store=ViewModelStore()
        val model=RoomFormViewModel(FormKind.DISPLAY,repo,SavedStateHandle());store.put("form",model)
        model.onSubmit();runCurrent();assertEquals(0,repo.admissionCalls)
        assertNull(model.uiState.value.nameIssue)
        model.onRoomCodeChanged(" abcd23 ");model.onSubmit();model.onSubmit();runCurrent()
        assertEquals(1,repo.admissionCalls);assertEquals("",repo.submittedName);assertEquals("ABCD23",repo.submittedCode)
        repo.admission.complete(CommandResult.Rejected("join",RemoteCode.DISPLAY_FULL));runCurrent()
        assertEquals(LobbyFeedback.DISPLAY_FULL,model.uiState.value.feedback)
        assertEquals(" abcd23 ",model.uiState.value.roomCode);store.clear()
    }
    @Test fun displayRouteAndModelRequireMembershipAndFreshPublicSnapshot() = runTest {
        val repo=LobbyTestRepository();repo.seed()
        val identity=SessionIdentity("ABCD23",null,"display")
        repo.session.value=repo.session.value.copy(identity=identity)
        val store=ViewModelStore();val model=DisplayViewModel(repo);store.put("display",model);runCurrent()
        assertFalse(model.uiState.value.restored)
        assertEquals(AppDestination.DISPLAY,sessionDestination(repo.session.value,AppDestination.LOBBY,false))
        repo.session.value=repo.session.value.copy(publicSnapshotReceived=true);runCurrent()
        assertTrue(model.uiState.value.restored);assertNull(model.uiState.value.public)
        repo.connection.value=ConnectionState(ConnectionStatus.RECONNECTING);repo.session.value=SessionState();runCurrent()
        assertFalse(model.uiState.value.restored);assertNull(model.uiState.value.lobby)
        assertEquals(AppDestination.DISPLAY,sessionDestination(SessionState(),AppDestination.DISPLAY,true));store.clear()
    }
}
