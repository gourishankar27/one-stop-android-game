package com.onejob.game.feedback

import com.onejob.game.data.repository.ActionReceipt

enum class FeedbackCue { COUNTDOWN, ACCEPTED, REJECTED, URGENT }

/** Presentation input only; no private target, resource rule or device reference. */
data class FeedbackFrame(
    val roundId: String,
    val stage: String,
    val countdownMs: Long?,
    val emergencyIds: List<Long>,
)

/** Bounded history survives navigation/activity recreation, never process death. */
class FeedbackEngine {
    private data class Seen(var emergency: Long = 0, var countdown: Long? = null, var action: Long = 0)
    private val rounds = linkedMapOf<String, Seen>()
    private var activeRound: String? = null
    private var armed = false
    private val recent = ArrayDeque<Long>()
    private var lastCue: Long? = null
    private var lastUrgent: Long? = null
    internal val rememberedRoundCount: Int get() = rounds.size

    fun observe(frame: FeedbackFrame?, active: Boolean, now: Long): FeedbackCue? {
        if (frame == null) { armed = false; return null }
        val changedRound = activeRound != frame.roundId
        activeRound = frame.roundId
        val seen = rounds.getOrPut(frame.roundId) { Seen() }
        if (rounds.size > 16) rounds.remove(rounds.keys.first())
        val emergency = frame.emergencyIds.maxOrNull() ?: 0
        val countdown = frame.countdownMs?.let { (it + 999) / 1000 }
        val baseline = !active || !armed || changedRound || frame.stage !in setOf("briefing", "countdown", "running")
        val urgent = !baseline && frame.stage == "running" && emergency > seen.emergency
        val count = !baseline && frame.stage == "countdown" && countdown != null && countdown in 1L..3L &&
            (seen.countdown == null || countdown < seen.countdown!!)
        seen.emergency = maxOf(seen.emergency, emergency)
        if (countdown != null && countdown in 1L..3L) seen.countdown = minOf(seen.countdown ?: countdown, countdown)
        armed = active && frame.stage in setOf("briefing", "countdown", "running")
        return when {
            urgent -> offer(FeedbackCue.URGENT, now)
            count -> offer(FeedbackCue.COUNTDOWN, now)
            else -> null
        }
    }

    fun action(frame: FeedbackFrame?, receipt: ActionReceipt, active: Boolean, now: Long): FeedbackCue? {
        val seen = rounds[receipt.roundId] ?: return null
        if (receipt.sequence <= seen.action) return null
        seen.action = receipt.sequence
        if (!active || !armed || frame?.roundId != receipt.roundId || frame.stage != "running") return null
        return offer(if (receipt.accepted) FeedbackCue.ACCEPTED else FeedbackCue.REJECTED, now)
    }

    private fun offer(cue: FeedbackCue, now: Long): FeedbackCue? {
        while (recent.firstOrNull()?.let { now - it >= 5000 } == true) recent.removeFirst()
        if (lastCue?.let { now - it < 350 } == true || recent.size >= 3) return null
        if (cue == FeedbackCue.URGENT && lastUrgent?.let { now - it < 1200 } == true) return null
        recent.addLast(now)
        lastCue = now
        if (cue == FeedbackCue.URGENT) lastUrgent = now
        return cue
    }
}
