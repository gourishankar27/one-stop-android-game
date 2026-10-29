package com.onejob.game.ui.forms

import androidx.lifecycle.SavedStateHandle
import androidx.lifecycle.ViewModelStore
import com.onejob.game.LobbyTestRepository
import com.onejob.game.MainDispatcherRule
import com.onejob.game.data.repository.*
import com.onejob.game.ui.lobby.LobbyFeedback
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.runCurrent
import kotlinx.coroutines.test.runTest
import org.junit.After
import org.junit.Assert.*
import org.junit.Rule
import org.junit.Test

@OptIn(ExperimentalCoroutinesApi::class)
class AdmissionViewModelTest {
    @get:Rule val main = MainDispatcherRule()
    private val store = ViewModelStore()
    private fun model(repo: LobbyTestRepository, kind: FormKind = FormKind.JOIN) =
        RoomFormViewModel(kind, repo, SavedStateHandle()).also { store.put("form", it) }
    @After fun clear() = store.clear()

    @Test fun invalidInputsNeverSendAndNormalizationPreservesRawRejectedInputs() = runTest {
        val repo = LobbyTestRepository(); val model = model(repo)
        model.onSubmit(); runCurrent(); assertEquals(0, repo.admissionCalls)
        assertEquals(DraftIssue.NAME_REQUIRED, model.uiState.value.nameIssue)
        model.onNameChanged(" Crew 🚀 "); model.onRoomCodeChanged(" abcd23 ")
        model.onSubmit(); runCurrent()
        assertEquals("Crew 🚀", repo.submittedName); assertEquals("ABCD23", repo.submittedCode)
        repo.admission.complete(CommandResult.Rejected("join", RemoteCode.ROOM_NOT_FOUND)); runCurrent()
        assertEquals(" Crew 🚀 ", model.uiState.value.name)
        assertEquals(" abcd23 ", model.uiState.value.roomCode)
        assertEquals(LobbyFeedback.ROOM_NOT_FOUND, model.uiState.value.feedback)
        assertFalse(model.uiState.value.admitted)
    }
    @Test fun duplicateSubmitAndEditsAreBlockedWhileAdmissionIsPending() = runTest {
        val repo = LobbyTestRepository(); val model = model(repo, FormKind.CREATE)
        model.onNameChanged("Captain"); model.onSubmit(); model.onSubmit(); model.onNameChanged("Other")
        runCurrent(); assertEquals(1, repo.admissionCalls); assertEquals("Captain", model.uiState.value.name)
        assertTrue(model.uiState.value.pending)
        repo.seed(); repo.admission.complete(CommandResult.Accepted("create", Operation.CREATE)); runCurrent()
        assertTrue(model.uiState.value.admitted); assertFalse(model.uiState.value.canSubmit)
        model.onSubmit(); runCurrent(); assertEquals(1, repo.admissionCalls)
    }
    @Test fun acceptedResultAloneDoesNotInventAdmission() = runTest {
        val repo = LobbyTestRepository(); val model = model(repo, FormKind.CREATE)
        model.onNameChanged("Crew"); model.onSubmit(); runCurrent()
        repo.admission.complete(CommandResult.Accepted("create", Operation.CREATE)); runCurrent()
        assertFalse(model.uiState.value.admitted)
        repo.seed(); runCurrent(); assertTrue(model.uiState.value.admitted)
    }
    @Test fun uncertainAdmissionRequiresExplicitResetAndNeverRetriesItself() = runTest {
        val repo = LobbyTestRepository(); val model = model(repo, FormKind.CREATE)
        model.onNameChanged("Crew"); model.onSubmit(); runCurrent()
        repo.admission.complete(CommandResult.Uncertain("create", Operation.CREATE)); runCurrent()
        model.onSubmit(); runCurrent(); assertEquals(1, repo.admissionCalls)
        assertFalse(model.uiState.value.canSubmit)
        model.resetAttempt(); runCurrent(); assertEquals(1, repo.disconnects)
        repo.admission = CompletableDeferred()
        model.onSubmit(); runCurrent(); assertEquals(2, repo.admissionCalls)
    }
    @Test fun cancelPendingAdmissionClosesConnectionAndReturnsWithoutReplay() = runTest {
        val repo = LobbyTestRepository(); val model = model(repo, FormKind.CREATE)
        model.onNameChanged("Crew"); model.onSubmit(); runCurrent()
        model.cancel(); model.cancel(); runCurrent()
        assertEquals(1, repo.disconnects); assertEquals(1, repo.admissionCalls)
        assertTrue(model.uiState.value.exited); assertFalse(model.uiState.value.admitted)
    }
    @Test fun fullStartedAndCapacityRejectionsRemainTypedAndRetainInputs() = runTest {
        for ((code, feedback) in listOf(RemoteCode.ROOM_FULL to LobbyFeedback.ROOM_FULL, RemoteCode.ROOM_STARTED to LobbyFeedback.ROOM_STARTED, RemoteCode.CAPACITY to LobbyFeedback.CAPACITY)) {
            val repo = LobbyTestRepository(); val model = model(repo)
            model.onNameChanged("Crew"); model.onRoomCodeChanged("ABCD23"); model.onSubmit(); runCurrent()
            repo.admission.complete(CommandResult.Rejected("join", code)); runCurrent()
            assertEquals(feedback, model.uiState.value.feedback); assertEquals("Crew", model.uiState.value.name)
        }
    }
}
