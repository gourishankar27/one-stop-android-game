package com.onejob.game.app

import androidx.compose.material3.Button
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.res.stringResource
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.lifecycle.viewmodel.initializer
import androidx.lifecycle.viewmodel.viewModelFactory
import com.onejob.game.R
import com.onejob.game.data.GameRepository
import com.onejob.game.ui.connection.ConnectionCheckViewModel
import com.onejob.game.ui.connection.ConnectionFeedback

@Composable
fun DebugConnectionPanel(repository: GameRepository) {
    val model: ConnectionCheckViewModel = viewModel(factory = viewModelFactory {
        initializer { ConnectionCheckViewModel(repository) }
    })
    val state by model.connection.collectAsStateWithLifecycle()
    val result by model.result.collectAsStateWithLifecycle()
    val working by model.working.collectAsStateWithLifecycle()
    Text(stringResource(R.string.development_connection))
    Text(stringResource(R.string.development_connection_description))
    ConnectionFeedback(state, result)
    Button(onClick = model::connect, enabled = !working) { Text(stringResource(R.string.connect)) }
    Button(onClick = model::ping, enabled = !working) { Text(stringResource(R.string.ping)) }
    Button(onClick = model::createTestMembership, enabled = !working) { Text(stringResource(R.string.create_test_membership)) }
    Button(onClick = model::disconnect) { Text(stringResource(R.string.disconnect)) }
}
