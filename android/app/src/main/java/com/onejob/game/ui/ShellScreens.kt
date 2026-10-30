package com.onejob.game.ui

import androidx.annotation.StringRes
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.heightIn
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
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.semantics.testTagsAsResourceId
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.platform.testTag
import com.onejob.game.ui.settings.LocalOpenFeedbackSettings
import com.onejob.game.R
import com.onejob.game.navigation.AppDestination

@OptIn(androidx.compose.ui.ExperimentalComposeUiApi::class)
@Composable
fun ShellPage(
    @StringRes title: Int,
    onBack: (() -> Unit)? = null,
    maxContentWidth: Dp = 600.dp,
    content: @Composable ColumnScope.() -> Unit,
) {
    Scaffold { insets ->
        Column(
            modifier = Modifier.fillMaxSize().semantics { testTagsAsResourceId = true }.padding(insets).imePadding()
                .verticalScroll(rememberScrollState()).padding(24.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
        ) {
            Column(
                modifier = Modifier.widthIn(max = maxContentWidth).fillMaxWidth(),
                verticalArrangement = Arrangement.spacedBy(16.dp),
            ) {
                val openSettings = LocalOpenFeedbackSettings.current
                if (onBack != null || openSettings != null) Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                    if (onBack != null) TextButton(onClick = onBack) { Text(stringResource(R.string.back)) }
                    if (openSettings != null) TextButton(onClick = openSettings,
                        modifier = Modifier.heightIn(min = 48.dp).testTag("feedbackSettings")) { Text(stringResource(R.string.feedback_settings_title)) }
                }
                Text(stringResource(title), style = MaterialTheme.typography.headlineLarge, modifier = Modifier.semantics { heading() })
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
        OutlinedButton(onClick = { onNavigate(AppDestination.DISPLAY_JOIN) }, modifier = Modifier.fillMaxWidth()) {
            Text(stringResource(R.string.display_join_title))
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
