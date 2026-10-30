package com.onejob.game.feedback

import com.onejob.game.MainDispatcherRule
import com.onejob.game.data.*
import com.onejob.game.data.protocol.*
import com.onejob.game.data.repository.*
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.test.*
import kotlinx.coroutines.ExperimentalCoroutinesApi
import org.junit.Assert.*
import org.junit.Rule
import org.junit.Test

@OptIn(ExperimentalCoroutinesApi::class)
class FeedbackControllerTest {
    @get:Rule val main=MainDispatcherRule()
    private class Repo:GameRepository by UnavailableGameRepository() {
        override val connection=MutableStateFlow(ConnectionState(ConnectionStatus.CONNECTED))
        override val session=MutableStateFlow(SessionState())
        override val actionReceipts=MutableSharedFlow<ActionReceipt>(extraBufferCapacity=16)
        fun show(stage:String="running",count:Long?=null,ids:List<Long> =emptyList()) {
            session.value=SessionState(identity=SessionIdentity("ABCD23",null,"display"),
                publicRound=PublicRound("round",stage,0,90000,count,null,100,50,ids.map {PublicWarning(it,"asteroid","Asteroid approach")},null),
                publicSnapshotReceived=true)
        }
    }
    private class Sink:FeedbackSink {
        val cues=mutableListOf<Triple<FeedbackCue,Boolean,Boolean>>()
        var stops=0;var closed=false
        override fun play(cue:FeedbackCue,audio:Boolean,haptics:Boolean) {cues+=Triple(cue,audio,haptics)}
        override fun stop() {stops++}
        override fun close() {closed=true}
    }
    @Test fun foregroundRecreationSettingsAndRecoveryNeverReplayOldWarnings() = runTest {
        val repo=Repo();val prefs=FeedbackPreferencesRepository(MemoryFeedbackPreferenceStorage())
        prefs.update {it.copy(audioEnabled=true,hapticsEnabled=true)}
        val controller=FeedbackController(repo,prefs,backgroundScope) {testScheduler.currentTime}
        val owner=Any();val first=Sink();controller.attach(owner,first);runCurrent()
        repo.show("briefing");runCurrent();repo.show("countdown",3000);runCurrent()
        assertEquals(FeedbackCue.COUNTDOWN,first.cues.single().first)
        controller.setScreenEnabled(false);repo.show(ids=listOf(1));runCurrent()
        advanceTimeBy(6000);controller.setScreenEnabled(true);runCurrent()
        assertEquals(1,first.cues.size)
        repo.show(ids=listOf(2));runCurrent();assertEquals(2,first.cues.size)
        controller.detach(owner)
        val replacement=Sink();val nextOwner=Any();controller.attach(nextOwner,replacement)
        controller.detach(owner);runCurrent();assertFalse(replacement.closed);assertTrue(first.closed)
        repo.connection.value=ConnectionState(ConnectionStatus.RECONNECTING);repo.show(ids=listOf(3));runCurrent()
        repo.connection.value=ConnectionState(ConnectionStatus.CONNECTED);runCurrent()
        assertTrue(replacement.cues.isEmpty())
        advanceTimeBy(6000);repo.show(ids=listOf(4));runCurrent()
        assertEquals(FeedbackCue.URGENT,replacement.cues.single().first)
        controller.close();assertTrue(replacement.closed)
    }
    @Test fun mutingConsumesHistoryAndPreferenceChangesStopOutputImmediately() = runTest {
        val repo=Repo();val prefs=FeedbackPreferencesRepository(MemoryFeedbackPreferenceStorage())
        val controller=FeedbackController(repo,prefs,backgroundScope) {testScheduler.currentTime}
        val sink=Sink();controller.attach(Any(),sink);repo.show();runCurrent()
        repo.show(ids=listOf(1));runCurrent();assertTrue(sink.cues.isEmpty())
        prefs.update {it.copy(audioEnabled=true)};runCurrent();assertTrue(sink.cues.isEmpty())
        advanceTimeBy(6000);repo.show(ids=listOf(2));runCurrent()
        assertEquals(Triple(FeedbackCue.URGENT,true,false),sink.cues.single())
        val stops=sink.stops;prefs.update {it.copy(audioEnabled=false,hapticsEnabled=true)};runCurrent()
        assertTrue(sink.stops>stops)
        advanceTimeBy(6000);repo.show(ids=listOf(3));runCurrent()
        assertEquals(Triple(FeedbackCue.URGENT,false,true),sink.cues.last())
        prefs.update {it.copy(hapticsEnabled=false)};runCurrent()
        repo.show(ids=listOf(4));runCurrent();prefs.update {it.copy(audioEnabled=true)};runCurrent()
        assertEquals(2,sink.cues.size);controller.close()
    }
    @Test fun actionReceiptsAreConsumedWhileHiddenAndDoNotReplayOnAttach() = runTest {
        val repo=Repo();val prefs=FeedbackPreferencesRepository(MemoryFeedbackPreferenceStorage())
        prefs.update {it.copy(hapticsEnabled=true)}
        val controller=FeedbackController(repo,prefs,backgroundScope) {testScheduler.currentTime}
        repo.show();runCurrent();repo.actionReceipts.emit(ActionReceipt("round",1,true));runCurrent()
        val sink=Sink();controller.attach(Any(),sink);runCurrent()
        repo.actionReceipts.emit(ActionReceipt("round",1,true));runCurrent();assertTrue(sink.cues.isEmpty())
        repo.actionReceipts.emit(ActionReceipt("round",2,false));runCurrent()
        assertEquals(FeedbackCue.REJECTED,sink.cues.single().first);controller.close()
    }
}
