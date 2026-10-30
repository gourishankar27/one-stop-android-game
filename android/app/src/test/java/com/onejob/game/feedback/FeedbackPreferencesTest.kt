package com.onejob.game.feedback

import org.junit.Assert.*
import org.junit.Test

class FeedbackPreferencesTest {
    private class Storage: FeedbackPreferenceStorage {
        val values=mutableMapOf<String,Boolean>()
        override fun read(key:String,default:Boolean)=values[key]?:default
        override fun write(values:Map<String,Boolean>) {this.values.putAll(values)}
    }
    @Test fun defaultsAreQuietAndMotionReduced() {
        assertEquals(FeedbackPreferences(false,false,true),FeedbackPreferencesRepository(Storage()).preferences.value)
    }
    @Test fun exactlyThreeLocalBooleansSurviveRepositoryRecreation() {
        val storage=Storage();val first=FeedbackPreferencesRepository(storage)
        first.update {it.copy(audioEnabled=true)}
        first.update {it.copy(hapticsEnabled=true,reducedMotion=false)}
        assertEquals(setOf("audio_enabled","haptics_enabled","reduced_motion"),storage.values.keys)
        assertEquals(FeedbackPreferences(true,true,false),FeedbackPreferencesRepository(storage).preferences.value)
        val second=FeedbackPreferencesRepository(storage)
        second.update {it.copy(audioEnabled=false)}
        assertEquals(FeedbackPreferences(false,true,false),FeedbackPreferencesRepository(storage).preferences.value)
    }
}
