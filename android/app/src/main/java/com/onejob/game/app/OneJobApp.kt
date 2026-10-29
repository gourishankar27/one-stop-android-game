package com.onejob.game.app

import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.LaunchedEffect
import androidx.lifecycle.createSavedStateHandle
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.lifecycle.viewmodel.initializer
import androidx.lifecycle.viewmodel.viewModelFactory
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import androidx.navigation.compose.currentBackStackEntryAsState
import com.onejob.game.data.GameRepository
import com.onejob.game.navigation.AppDestination
import com.onejob.game.ui.ShellHome
import com.onejob.game.ui.PlaceholderScreen
import com.onejob.game.ui.forms.FormKind
import com.onejob.game.ui.forms.RoomFormScreen
import com.onejob.game.ui.forms.RoomFormViewModel
import com.onejob.game.ui.lobby.LobbyViewModel
import com.onejob.game.ui.lobby.LobbyScreen
import com.onejob.game.ui.lobby.LobbyFeedbackText
import com.onejob.game.ui.roles.RoleViewModel
import com.onejob.game.ui.roles.RoleScreen
import com.onejob.game.data.ConnectionStatus
import com.onejob.game.ui.lobby.LobbyOperation

@Composable
fun OneJobApp(repository: GameRepository) {
    val navController = rememberNavController()
    val lobbyModel: LobbyViewModel = viewModel(factory = viewModelFactory {
        initializer { LobbyViewModel(repository) }
    })
    val lobby by lobbyModel.uiState.collectAsStateWithLifecycle()
    val roleModel: RoleViewModel = viewModel(factory = viewModelFactory { initializer { RoleViewModel(repository) } })
    val role by roleModel.uiState.collectAsStateWithLifecycle()
    val session by repository.session.collectAsStateWithLifecycle()
    val entry by navController.currentBackStackEntryAsState()
    val route = entry?.destination?.route
    val roleRequired = session.lobby?.stage in setOf("briefing", "paused", "aborted") || session.roleState != null ||
        (route == AppDestination.ROLE.route && (lobby.connection.status != ConnectionStatus.CONNECTED || lobby.pending == LobbyOperation.LEAVE))
    val sessionDestination = if (roleRequired) AppDestination.ROLE else AppDestination.LOBBY
    val openLobby = {
        navController.navigate(sessionDestination.route) {
            popUpTo(AppDestination.HOME.route)
            launchSingleTop = true
        }
    }
    LaunchedEffect(lobby.keepLobby, route, sessionDestination) {
        if (lobby.keepLobby && route !in listOf(AppDestination.CREATE.route, AppDestination.JOIN.route, sessionDestination.route)) {
            openLobby()
        } else if (!lobby.keepLobby && route in listOf(AppDestination.LOBBY.route, AppDestination.ROLE.route)) {
            navController.navigate(AppDestination.HOME.route) {
                popUpTo(AppDestination.HOME.route) { inclusive = true }
                launchSingleTop = true
            }
        }
    }
    NavHost(navController, startDestination = AppDestination.HOME.route) {
        composable(AppDestination.HOME.route) {
            ShellHome(feedbackContent = { LobbyFeedbackText(lobby.feedback) }) { destination ->
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
                LaunchedEffect(state.admitted, state.exited) {
                    if (state.exited) navController.popBackStack()
                    else if (state.admitted) openLobby()
                }
                RoomFormScreen(
                    kind = kind,
                    state = state,
                    onNameChanged = model::onNameChanged,
                    onCodeChanged = model::onRoomCodeChanged,
                    onSubmit = model::onSubmit,
                    onResetAttempt = model::resetAttempt,
                    onBack = model::cancel,
                )
            }
        }
        composable(AppDestination.LOBBY.route) {
            LobbyScreen(lobby, lobbyModel::toggleReady, lobbyModel::start, lobbyModel::askLeave,
                lobbyModel::dismissLeave, lobbyModel::confirmLeave, lobbyModel::retry)
        }
        composable(AppDestination.ROLE.route) {
            RoleScreen(role, lobby.confirmLeave, roleModel::select, roleModel::confirmRead,
                roleModel::acknowledge, lobbyModel::askLeave, lobbyModel::dismissLeave, lobbyModel::confirmLeave)
        }
        for (destination in listOf(
            AppDestination.GAMEPLAY, AppDestination.RESULTS,
        )) {
            composable(destination.route) {
                PlaceholderScreen(destination) { navController.popBackStack() }
            }
        }
    }
}
