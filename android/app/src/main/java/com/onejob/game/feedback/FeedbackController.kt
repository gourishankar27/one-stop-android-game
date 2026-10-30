package com.onejob.game.feedback

import com.onejob.game.data.ConnectionStatus
import com.onejob.game.data.GameRepository
import com.onejob.game.data.repository.SessionState
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Job
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.launch

interface FeedbackSink {
    fun play(cue: FeedbackCue, audio: Boolean, haptics: Boolean)
    fun stop()
    fun close()
}

/** One app owner, called on Main. Device sinks exist only while a window is focused. */
class FeedbackController(
    private val repository: GameRepository,
    private val preferences: FeedbackPreferencesRepository,
    scope: CoroutineScope,
    private val now: () -> Long,
) {
    private val engine = FeedbackEngine()
    private var owner: Any? = null
    private var sink: FeedbackSink? = null
    private var screenEnabled = true
    private var previousPreferences = preferences.preferences.value
    private val jobs: List<Job> = listOf(
        scope.launch {
            combine(repository.connection, repository.session, preferences.preferences) { _, _, _ -> Unit }
                .collect { refresh() }
        },
        scope.launch {
            repository.actionReceipts.collect { receipt ->
                refresh()
                deliver(engine.action(frame(), receipt, active(), now()))
            }
        },
    )

    fun attach(owner: Any, sink: FeedbackSink) {
        this.sink?.close()
        this.owner = owner
        this.sink = sink
        // Never catch up an event received before this window became visible.
        engine.observe(frame(), false, now())
        refresh()
    }
    fun detach(owner: Any) {
        if (this.owner !== owner) return
        sink?.close(); sink = null; this.owner = null
        engine.observe(frame(), false, now())
    }
    fun setScreenEnabled(enabled: Boolean) { screenEnabled = enabled; refresh() }
    fun close() { jobs.forEach { it.cancel() }; sink?.close(); sink = null; owner = null }

    private fun active() = sink != null && screenEnabled && repository.connection.value.status == ConnectionStatus.CONNECTED
    private fun frame() = repository.session.value.feedbackFrame()
    private fun refresh() {
        val prefs = preferences.preferences.value
        if (!active() || prefs != previousPreferences || (!prefs.audioEnabled && !prefs.hapticsEnabled)) sink?.stop()
        previousPreferences = prefs
        deliver(engine.observe(frame(), active(), now()))
    }
    private fun deliver(cue: FeedbackCue?) {
        if (cue == null || !active()) return
        val prefs = preferences.preferences.value
        if (prefs.audioEnabled || prefs.hapticsEnabled) sink?.play(cue, prefs.audioEnabled, prefs.hapticsEnabled)
    }
}

internal fun SessionState.feedbackFrame(): FeedbackFrame? {
    val public = if (identity?.kind == "display") publicRound.takeIf { publicSnapshotReceived }
        else roleState?.takeIf { it.public.round_id == assigned?.round_id &&
            it.stations.roles().toSet() == assigned?.roles?.toSet() }?.public
    return public?.let { FeedbackFrame(it.round_id, it.stage, it.countdown_remaining_ms, it.warnings.map { warning -> warning.emergency_id }) }
}
