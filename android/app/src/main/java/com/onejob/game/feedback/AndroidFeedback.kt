package com.onejob.game.feedback

import android.content.Context
import android.content.SharedPreferences
import android.media.AudioAttributes
import android.media.AudioFocusRequest
import android.media.AudioManager
import android.media.SoundPool
import android.os.Build
import android.os.Handler
import android.os.Looper
import android.view.HapticFeedbackConstants
import android.view.View
import androidx.core.content.edit
import com.onejob.game.R

class AndroidFeedbackPreferenceStorage(private val preferences: SharedPreferences) : FeedbackPreferenceStorage {
    override fun read(key: String, default: Boolean) = preferences.getBoolean(key, default)
    override fun write(values: Map<String, Boolean>) {
        preferences.edit { values.forEach { (key, value) -> putBoolean(key, value) } }
    }
}

/** Short foreground-only effects; asynchronous sample loading never queues playback. */
class AndroidFeedbackSink(context: Context, private val view: View) : FeedbackSink {
    private val handler = Handler(Looper.getMainLooper())
    private val audio = context.applicationContext.getSystemService(AudioManager::class.java)
    private val attributes = AudioAttributes.Builder()
        .setUsage(AudioAttributes.USAGE_ASSISTANCE_SONIFICATION)
        .setContentType(AudioAttributes.CONTENT_TYPE_SONIFICATION).build()
    private val pool = SoundPool.Builder().setMaxStreams(1).setAudioAttributes(attributes).build()
    private var closed = false
    private var stream = 0
    private var focusHeld = false
    private val endSound = Runnable { stop() }
    private val ready = mutableSetOf<Int>()
    private val sounds: Map<FeedbackCue, Int>
    private val focus = AudioFocusRequest.Builder(AudioManager.AUDIOFOCUS_GAIN_TRANSIENT_MAY_DUCK)
        .setAudioAttributes(attributes).setAcceptsDelayedFocusGain(false)
        .setOnAudioFocusChangeListener({ change -> if (change != AudioManager.AUDIOFOCUS_GAIN) stop() }, handler)
        .build()

    init {
        pool.setOnLoadCompleteListener { _, sample, status ->
            handler.post { if (!closed && status == 0) ready.add(sample) }
        }
        sounds = mapOf(
            FeedbackCue.COUNTDOWN to pool.load(context.applicationContext, R.raw.feedback_countdown, 1),
            FeedbackCue.ACCEPTED to pool.load(context.applicationContext, R.raw.feedback_accepted, 1),
            FeedbackCue.REJECTED to pool.load(context.applicationContext, R.raw.feedback_rejected, 1),
            FeedbackCue.URGENT to pool.load(context.applicationContext, R.raw.feedback_urgent, 1),
        )
    }

    override fun play(cue: FeedbackCue, audio: Boolean, haptics: Boolean) {
        if (closed || !view.isAttachedToWindow || !view.hasWindowFocus()) return
        if (haptics) view.performHapticFeedback(when {
            cue == FeedbackCue.URGENT -> HapticFeedbackConstants.LONG_PRESS
            Build.VERSION.SDK_INT >= 30 && cue == FeedbackCue.REJECTED -> HapticFeedbackConstants.REJECT
            Build.VERSION.SDK_INT >= 30 && cue == FeedbackCue.ACCEPTED -> HapticFeedbackConstants.CONFIRM
            else -> HapticFeedbackConstants.VIRTUAL_KEY
        })
        val sample = sounds.getValue(cue)
        if (!audio || sample !in ready || this.audio?.ringerMode != AudioManager.RINGER_MODE_NORMAL) return
        stop()
        if (this.audio.requestAudioFocus(focus) != AudioManager.AUDIOFOCUS_REQUEST_GRANTED) return
        focusHeld = true
        stream = pool.play(sample, 0.18f, 0.18f, 1, 0, 1f)
        // Every asset is at most 120ms; release focus promptly even on a failed play.
        handler.postDelayed(endSound, 160)
    }

    override fun stop() {
        handler.removeCallbacks(endSound)
        if (stream != 0 && !closed) pool.stop(stream)
        stream = 0
        if (focusHeld) { focusHeld = false; audio?.abandonAudioFocusRequest(focus) }
    }
    override fun close() {
        if (closed) return
        stop(); closed = true; handler.removeCallbacksAndMessages(null); ready.clear(); pool.release()
    }
}
