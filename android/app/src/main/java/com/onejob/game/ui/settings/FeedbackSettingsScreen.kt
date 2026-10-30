package com.onejob.game.ui.settings

import androidx.activity.compose.BackHandler
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.selection.toggleable
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.runtime.staticCompositionLocalOf
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.unit.dp
import androidx.lifecycle.ViewModel
import com.onejob.game.R
import com.onejob.game.feedback.FeedbackPreferences
import com.onejob.game.feedback.FeedbackPreferencesRepository
import com.onejob.game.ui.ShellPage

val LocalOpenFeedbackSettings = staticCompositionLocalOf<(() -> Unit)?> { null }

class FeedbackSettingsViewModel(private val repository: FeedbackPreferencesRepository) : ViewModel() {
    val preferences = repository.preferences
    fun audio(value: Boolean) = repository.update { it.copy(audioEnabled = value) }
    fun haptics(value: Boolean) = repository.update { it.copy(hapticsEnabled = value) }
    fun motion(value: Boolean) = repository.update { it.copy(reducedMotion = value) }
}

@Composable
fun FeedbackSettingsScreen(value: FeedbackPreferences, audio: (Boolean) -> Unit,
                           haptics: (Boolean) -> Unit, motion: (Boolean) -> Unit, onBack: () -> Unit) {
    BackHandler(onBack = onBack)
    ShellPage(R.string.feedback_settings_title, onBack) {
        Text(stringResource(R.string.feedback_settings_hint))
        PreferenceToggle(stringResource(R.string.feedback_audio), stringResource(R.string.feedback_audio_hint),
            "audioEnabled", value.audioEnabled, audio)
        PreferenceToggle(stringResource(R.string.feedback_haptics), stringResource(R.string.feedback_haptics_hint),
            "hapticsEnabled", value.hapticsEnabled, haptics)
        PreferenceToggle(stringResource(R.string.feedback_motion), stringResource(R.string.feedback_motion_hint),
            "reducedMotion", value.reducedMotion, motion)
        Text(stringResource(R.string.feedback_text_always_visible))
    }
}

@Composable
private fun PreferenceToggle(label: String, hint: String, tag: String, checked: Boolean, change: (Boolean) -> Unit) {
    Column(Modifier.fillMaxWidth()) {
        Row(Modifier.fillMaxWidth().heightIn(min = 56.dp).testTag(tag)
            .toggleable(checked, role = Role.Switch, onValueChange = change),
            horizontalArrangement = Arrangement.SpaceBetween) {
            Text(label, modifier = Modifier.weight(1f).padding(8.dp), style = MaterialTheme.typography.titleMedium)
            Switch(checked = checked, onCheckedChange = null)
        }
        Text(hint, style = MaterialTheme.typography.bodyMedium)
    }
}
