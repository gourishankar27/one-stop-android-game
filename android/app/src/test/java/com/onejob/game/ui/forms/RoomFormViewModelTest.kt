package com.onejob.game.ui.forms

import androidx.lifecycle.SavedStateHandle
import androidx.lifecycle.ViewModelStore
import com.onejob.game.MainDispatcherRule
import com.onejob.game.data.ConnectionStatus
import com.onejob.game.data.GameRepository
import com.onejob.game.data.UnavailableGameRepository
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import kotlinx.coroutines.test.TestScope
import kotlinx.coroutines.test.UnconfinedTestDispatcher
import kotlinx.coroutines.test.runCurrent
import kotlinx.coroutines.test.runTest
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test

private class FakeGameRepository : GameRepository {
    val status = MutableStateFlow(ConnectionStatus.UNAVAILABLE)
    override val connectionStatus = status.asStateFlow()
}

@OptIn(ExperimentalCoroutinesApi::class)
class RoomFormViewModelTest {
    @get:Rule val mainDispatcher = MainDispatcherRule()
    private val store = ViewModelStore()
    private var count = 0

    @After
    fun clearModels() {
        store.clear()
    }

    private fun model(
        kind: FormKind = FormKind.JOIN,
        repository: GameRepository = FakeGameRepository(),
        handle: SavedStateHandle = SavedStateHandle(),
    ) = RoomFormViewModel(kind, repository, handle).also { store.put("form-${count++}", it) }

    private fun TestScope.observe(model: RoomFormViewModel) {
        backgroundScope.launch(UnconfinedTestDispatcher(testScheduler)) { model.uiState.collect {} }
        runCurrent()
    }

    @Test
    fun editsEmitImmutableStateAndCheckingShowsThenClearsHints() = runTest {
        val model = model()
        observe(model)
        val initial = model.uiState.value
        assertFalse(initial.checked)
        assertNull(initial.nameIssue)
        model.onCheckDraft()
        runCurrent()
        assertEquals(DraftIssue.NAME_REQUIRED, model.uiState.value.nameIssue)
        assertEquals(DraftIssue.ROOM_CODE_INVALID, model.uiState.value.codeIssue)
        model.onNameChanged(" Ada ")
        model.onRoomCodeChanged(" abcd23 ")
        runCurrent()
        assertTrue(model.uiState.value.draftValid)
        assertEquals(" Ada ", model.uiState.value.name)
        assertEquals(" abcd23 ", model.uiState.value.roomCode)
        assertEquals("", initial.name)
        assertFalse(initial.checked)
    }

    @Test
    fun createDraftNeedsNoRoomCodeAndNeverChangesRepositoryStatus() = runTest {
        val repository = FakeGameRepository()
        val model = model(FormKind.CREATE, repository)
        observe(model)
        model.onNameChanged("Crew")
        model.onCheckDraft()
        runCurrent()
        assertTrue(model.uiState.value.draftValid)
        assertEquals(ConnectionStatus.UNAVAILABLE, repository.connectionStatus.value)
        assertEquals(ConnectionStatus.UNAVAILABLE, UnavailableGameRepository().connectionStatus.value)
    }

    @Test
    fun repositoryStatusUpdatesFlowThroughWithoutOverwritingDraftOrValidation() = runTest {
        val repository = FakeGameRepository()
        val model = model(repository = repository)
        observe(model)
        model.onNameChanged("Crew")
        model.onRoomCodeChanged("ABCD23")
        model.onCheckDraft()
        runCurrent()
        for (status in listOf(ConnectionStatus.CONNECTING, ConnectionStatus.CONNECTED,
                              ConnectionStatus.RECONNECTING, ConnectionStatus.SESSION_EXPIRED)) {
            repository.status.value = status
            runCurrent()
            assertEquals(status, model.uiState.value.connectionStatus)
            assertEquals("Crew", model.uiState.value.name)
            assertTrue(model.uiState.value.draftValid)
        }
    }

    @Test
    fun freshModelRestoresOnlyNonsecretInputsAndUsesCurrentRepositoryState() = runTest {
        val repository = FakeGameRepository()
        val handle = SavedStateHandle()
        val first = model(repository = repository, handle = handle)
        observe(first)
        first.onNameChanged("Saved crew")
        first.onRoomCodeChanged("AbCD23")
        first.onCheckDraft()
        runCurrent()
        assertEquals(setOf("draft.name", "draft.code", "draft.checked"), handle.keys())
        val restoredHandle = SavedStateHandle(handle.keys().associateWith { handle.get<Any?>(it) })
        repository.status.value = ConnectionStatus.RECONNECTING
        val restored = model(repository = repository, handle = restoredHandle)
        observe(restored)
        assertEquals("Saved crew", restored.uiState.value.name)
        assertEquals("AbCD23", restored.uiState.value.roomCode)
        assertTrue(restored.uiState.value.draftValid)
        assertEquals(ConnectionStatus.RECONNECTING, restored.uiState.value.connectionStatus)
        assertFalse(handle.keys().any { it.contains("token") || it.contains("session") })
    }

    @Test
    fun separateBackStackModelsKeepCreateAndJoinDraftsIndependent() = runTest {
        val create = model(FormKind.CREATE)
        val join = model(FormKind.JOIN)
        observe(create)
        observe(join)
        create.onNameChanged("Captain")
        join.onNameChanged("Guest")
        join.onRoomCodeChanged("ABCD23")
        runCurrent()
        assertEquals("Captain", create.uiState.value.name)
        assertEquals("Guest", join.uiState.value.name)
        assertEquals("", create.uiState.value.roomCode)
        assertEquals("ABCD23", join.uiState.value.roomCode)
    }
}
