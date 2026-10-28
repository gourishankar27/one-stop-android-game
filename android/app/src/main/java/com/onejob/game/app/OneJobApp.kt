package com.onejob.game.app

import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.lifecycle.createSavedStateHandle
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.lifecycle.viewmodel.initializer
import androidx.lifecycle.viewmodel.viewModelFactory
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import com.onejob.game.data.GameRepository
import com.onejob.game.navigation.AppDestination
import com.onejob.game.ui.ShellHome
import com.onejob.game.ui.PlaceholderScreen
import com.onejob.game.ui.forms.FormKind
import com.onejob.game.ui.forms.RoomFormScreen
import com.onejob.game.ui.forms.RoomFormViewModel

@Composable
fun OneJobApp(repository: GameRepository) {
    val navController = rememberNavController()
    NavHost(navController, startDestination = AppDestination.HOME.route) {
        composable(AppDestination.HOME.route) {
            ShellHome { destination ->
                navController.navigate(destination.route) { launchSingleTop = true }
            }
        }
        for ((destination, kind) in listOf(
            AppDestination.CREATE to FormKind.CREATE,
            AppDestination.JOIN to FormKind.JOIN,
        )) {
            composable(destination.route) {
                val model: RoomFormViewModel = viewModel(factory = viewModelFactory {
                    initializer { RoomFormViewModel(kind, repository, createSavedStateHandle()) }
                })
                val state by model.uiState.collectAsStateWithLifecycle()
                RoomFormScreen(
                    kind = kind,
                    state = state,
                    onNameChanged = model::onNameChanged,
                    onCodeChanged = model::onRoomCodeChanged,
                    onCheckDraft = model::onCheckDraft,
                    onBack = { navController.popBackStack() },
                )
            }
        }
        for (destination in listOf(
            AppDestination.LOBBY, AppDestination.ROLE,
            AppDestination.GAMEPLAY, AppDestination.RESULTS,
        )) {
            composable(destination.route) {
                PlaceholderScreen(destination) { navController.popBackStack() }
            }
        }
    }
}
