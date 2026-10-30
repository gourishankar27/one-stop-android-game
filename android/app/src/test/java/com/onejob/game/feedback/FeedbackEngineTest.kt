package com.onejob.game.feedback

import com.onejob.game.data.repository.ActionReceipt
import org.junit.Assert.*
import org.junit.Test

class FeedbackEngineTest {
    private fun frame(stage: String = "running", countdown: Long? = null, ids: List<Long> = emptyList(), round: String = "round") =
        FeedbackFrame(round, stage, countdown, ids)

    @Test fun countdownUsesOnlyNewDescendingServerStepsAndNeverReplaysAFullSnapshot() {
        val engine=FeedbackEngine()
        assertNull(engine.observe(frame("briefing"),true,0))
        assertEquals(FeedbackCue.COUNTDOWN,engine.observe(frame("countdown",3000),true,0))
        assertNull(engine.observe(frame("countdown",2800),true,200))
        assertEquals(FeedbackCue.COUNTDOWN,engine.observe(frame("countdown",2000),true,1000))
        assertNull(engine.observe(frame("countdown",3000),true,1500))
        assertEquals(FeedbackCue.COUNTDOWN,engine.observe(frame("countdown",1000),true,2000))
        assertNull(engine.observe(frame(),true,3000))
        assertNull(engine.observe(frame("countdown",1000),true,7000))
    }
    @Test fun firstResumePausedAndHiddenSnapshotsEstablishSilentBaselines() {
        val engine=FeedbackEngine()
        assertNull(engine.observe(frame(ids=listOf(3)),true,0))
        assertEquals(FeedbackCue.URGENT,engine.observe(frame(ids=listOf(3,4)),true,2000))
        assertNull(engine.observe(null,false,3000))
        assertNull(engine.observe(frame(ids=listOf(4,5)),true,4000))
        assertNull(engine.observe(frame(ids=listOf(5)),true,5000))
        assertNull(engine.observe(frame("paused",ids=listOf(5,6)),true,6000))
        assertNull(engine.observe(frame(ids=listOf(6)),true,7000))
        assertNull(engine.observe(frame(ids=listOf(7)),false,8000))
        assertNull(engine.observe(frame(ids=listOf(7)),true,9000))
        assertEquals(FeedbackCue.URGENT,engine.observe(frame(ids=listOf(8)),true,10000))
    }
    @Test fun simultaneousAndRepeatedUrgencyIsBoundedAndDroppedCuesNeverCatchUp() {
        val engine=FeedbackEngine();engine.observe(frame(),true,0)
        assertEquals(FeedbackCue.URGENT,engine.observe(frame(ids=listOf(1,2)),true,100))
        assertNull(engine.observe(frame(ids=listOf(2)),true,2000))
        assertEquals(FeedbackCue.URGENT,engine.observe(frame(ids=listOf(3)),true,2100))
        assertNull(engine.observe(frame(ids=listOf(4)),true,2500))
        assertNull(engine.observe(frame(ids=listOf(4)),true,5000))
        assertEquals(FeedbackCue.URGENT,engine.observe(frame(ids=listOf(5)),true,5100))
    }
    @Test fun onlyFreshCorrelatedActionSequencesInTheActiveRoundCanCue() {
        val engine=FeedbackEngine();val current=frame();engine.observe(current,true,0)
        assertEquals(FeedbackCue.ACCEPTED,engine.action(current,ActionReceipt("round",1,true),true,0))
        assertNull(engine.action(current,ActionReceipt("round",1,true),true,1000))
        assertEquals(FeedbackCue.REJECTED,engine.action(current,ActionReceipt("round",2,false),true,1000))
        assertNull(engine.action(current,ActionReceipt("other",10,true),true,2000))
        assertNull(engine.action(current,ActionReceipt("round",3,true),false,2000))
        assertNull(engine.action(current,ActionReceipt("round",3,true),true,3000))
    }
    @Test fun limiterAllowsAtMostThreeCuesPerFiveSecondsAndNoBurstQueue() {
        val engine=FeedbackEngine();val current=frame();engine.observe(current,true,0)
        assertEquals(FeedbackCue.ACCEPTED,engine.action(current,ActionReceipt("round",1,true),true,0))
        assertNull(engine.action(current,ActionReceipt("round",2,true),true,100))
        assertEquals(FeedbackCue.REJECTED,engine.action(current,ActionReceipt("round",3,false),true,400))
        assertEquals(FeedbackCue.ACCEPTED,engine.action(current,ActionReceipt("round",4,true),true,800))
        assertNull(engine.action(current,ActionReceipt("round",5,true),true,2000))
        assertNull(engine.action(current,ActionReceipt("round",5,true),true,6000))
        assertEquals(FeedbackCue.ACCEPTED,engine.action(current,ActionReceipt("round",6,true),true,6000))
    }
    @Test fun rematchesResetEventIdentityAndHistoryRemainsBounded() {
        val engine=FeedbackEngine()
        for(index in 1..100) {
            assertNull(engine.observe(frame(round="round-$index"),true,index*6000L))
            assertEquals(FeedbackCue.URGENT,engine.observe(frame(ids=listOf(1),round="round-$index"),true,index*6000L+500))
        }
        assertEquals(16,engine.rememberedRoundCount)
    }
    @Test fun joiningDuringCountdownDoesNotPlayTheCurrentNumber() {
        val engine=FeedbackEngine()
        assertNull(engine.observe(frame("countdown",1800),true,0))
        assertEquals(FeedbackCue.COUNTDOWN,engine.observe(frame("countdown",1000),true,1000))
        assertNull(engine.observe(frame("finished"),true,2000))
        assertNull(engine.action(frame("finished"),ActionReceipt("round",1,true),true,3000))
    }
}
