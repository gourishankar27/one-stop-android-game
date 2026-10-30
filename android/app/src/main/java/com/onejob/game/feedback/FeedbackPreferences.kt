package com.onejob.game.feedback

import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow

data class FeedbackPreferences(
    val audioEnabled: Boolean = false,
    val hapticsEnabled: Boolean = false,
    val reducedMotion: Boolean = true,
)

/** Exactly three local booleans; this interface cannot store a token or game state. */
interface FeedbackPreferenceStorage {
    fun read(key: String, default: Boolean): Boolean
    fun write(values: Map<String, Boolean>)
}

class MemoryFeedbackPreferenceStorage : FeedbackPreferenceStorage {
    private val values = mutableMapOf<String, Boolean>()
    override fun read(key: String, default: Boolean) = values[key] ?: default
    override fun write(values: Map<String, Boolean>) { this.values.putAll(values) }
}

class FeedbackPreferencesRepository(private val storage: FeedbackPreferenceStorage) {
    private val _preferences = MutableStateFlow(FeedbackPreferences(
        storage.read(AUDIO, false), storage.read(HAPTICS, false), storage.read(MOTION, true),
    ))
    val preferences = _preferences.asStateFlow()
    fun update(change: (FeedbackPreferences) -> FeedbackPreferences) {
        val value = change(_preferences.value)
        storage.write(mapOf(AUDIO to value.audioEnabled, HAPTICS to value.hapticsEnabled, MOTION to value.reducedMotion))
        _preferences.value = value
    }
    companion object {
        const val AUDIO = "audio_enabled"
        const val HAPTICS = "haptics_enabled"
        const val MOTION = "reduced_motion"
    }
}
