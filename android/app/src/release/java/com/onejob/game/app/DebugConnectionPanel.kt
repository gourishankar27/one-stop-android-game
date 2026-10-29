package com.onejob.game.app

import androidx.compose.runtime.Composable
import com.onejob.game.data.GameRepository

/** No development controls in release. */
@Composable
fun DebugConnectionPanel(repository: GameRepository) = Unit
