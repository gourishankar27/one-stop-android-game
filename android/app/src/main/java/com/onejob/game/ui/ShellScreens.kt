package com.onejob.game.ui

import androidx.annotation.StringRes
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.semantics.testTagsAsResourceId
import com.onejob.game.R
import com.onejob.game.navigation.AppDestination

@OptIn(androidx.compose.ui.ExperimentalComposeUiApi::class)
@Composable
fun ShellPage(
    @StringRes title: Int,
    onBack: (() -> Unit)? = null,
    content: @Composable ColumnScope.() -> Unit,
) {
    Scaffold { insets ->
        Column(
            modifier = Modifier.fillMaxSize().semantics { testTagsAsResourceId = true }.padding(insets).imePadding()
                .verticalScroll(rememberScrollState()).padding(24.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
        ) {
            Column(
                modifier = Modifier.widthIn(max = 600.dp).fillMaxWidth(),
                verticalArrangement = Arrangement.spacedBy(16.dp),
            ) {
                if (onBack != null) {
                    TextButton(onClick = onBack) { Text(stringResource(R.string.back)) }
                }
                Text(stringResource(title), style = MaterialTheme.typography.headlineLarge)
                content()
            }
        }
    }
}

@Composable
fun ShellHome(
    feedbackContent: @Composable () -> Unit = {},
    onNavigate: (AppDestination) -> Unit,
) {
    ShellPage(R.string.home_title) {
        Text(stringResource(R.string.home_tagline), style = MaterialTheme.typography.titleMedium)
        Text(stringResource(R.string.foundation_status), style = MaterialTheme.typography.titleLarge)
        Text(stringResource(R.string.foundation_description))
        feedbackContent()
        Button(onClick = { onNavigate(AppDestination.CREATE) }, modifier = Modifier.fillMaxWidth()) {
            Text(stringResource(R.string.create_setup))
        }
        Button(onClick = { onNavigate(AppDestination.JOIN) }, modifier = Modifier.fillMaxWidth()) {
            Text(stringResource(R.string.join_setup))
        }
        Text(stringResource(R.string.explore_previews), style = MaterialTheme.typography.titleMedium)
        for ((destination, label) in listOf(
            AppDestination.GAMEPLAY to R.string.preview_gameplay,
            AppDestination.RESULTS to R.string.preview_results,
        )) {
            OutlinedButton(onClick = { onNavigate(destination) }, modifier = Modifier.fillMaxWidth()) {
                Text(stringResource(label))
            }
        }
    }
}

@Composable
fun PlaceholderScreen(destination: AppDestination, onBack: () -> Unit) {
    val (title, description) = when (destination) {
        AppDestination.LOBBY -> R.string.lobby_title to R.string.lobby_description
        AppDestination.ROLE -> R.string.role_title to R.string.role_description
        AppDestination.GAMEPLAY -> R.string.gameplay_title to R.string.gameplay_description
        AppDestination.RESULTS -> R.string.results_title to R.string.results_description
        else -> error("Not a preview destination")
    }
    ShellPage(title, onBack) {
        Text(stringResource(R.string.preview_status), style = MaterialTheme.typography.titleMedium)
        Text(stringResource(description))
        Text(stringResource(R.string.no_session))
    }
}
