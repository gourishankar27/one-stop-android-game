package com.onejob.game

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import com.onejob.game.app.OneJobApp
import com.onejob.game.app.OneJobApplication
import com.onejob.game.app.AppContainer
import com.onejob.game.feedback.AndroidFeedbackSink
import com.onejob.game.ui.theme.OneJobTheme

class MainActivity : ComponentActivity() {
    private lateinit var container: AppContainer
    private var resumed = false
    private var feedbackBound = false
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        container = (application as OneJobApplication).container
        val repository = container.gameRepository
        setContent {
            OneJobTheme {
                OneJobApp(repository, container.feedbackPreferences, container.feedback)
            }
        }
    }
    override fun onStart() { super.onStart(); container.gameRepository.setForeground(true) }
    override fun onStop() {
        if (!isChangingConfigurations) container.gameRepository.setForeground(false)
        super.onStop()
    }
    override fun onResume() { super.onResume(); resumed = true; bindFeedback() }
    override fun onPause() { resumed = false; bindFeedback(); super.onPause() }
    override fun onWindowFocusChanged(hasFocus: Boolean) { super.onWindowFocusChanged(hasFocus); bindFeedback() }
    private fun bindFeedback() {
        if (!::container.isInitialized) return
        if (resumed && window.decorView.hasWindowFocus()) {
            if (!feedbackBound) {
                container.feedback.attach(this, AndroidFeedbackSink(this, window.decorView)); feedbackBound = true
            }
        } else if (feedbackBound) { container.feedback.detach(this); feedbackBound = false }
    }
}
