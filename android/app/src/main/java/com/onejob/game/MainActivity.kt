package com.onejob.game

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import com.onejob.game.app.OneJobApp
import com.onejob.game.app.OneJobApplication
import com.onejob.game.ui.theme.OneJobTheme

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        val repository = (application as OneJobApplication).container.gameRepository
        setContent {
            OneJobTheme {
                OneJobApp(repository)
            }
        }
    }
}
