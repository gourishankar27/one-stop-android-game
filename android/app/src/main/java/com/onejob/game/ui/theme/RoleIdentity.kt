package com.onejob.game.ui.theme

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.semantics.clearAndSetSemantics
import androidx.compose.ui.unit.dp
import com.onejob.game.R
import com.onejob.game.data.protocol.StationRole

/** Monogram + text are redundant; tint is never the only role identifier. */
@Composable
fun RoleIdentity(role: StationRole) {
    val (light, dark, label) = when (role) {
        StationRole.PILOT -> Triple(Color(0xFFD1F4EE), Color(0xFF00382F), R.string.identity_pilot)
        StationRole.ENGINEER -> Triple(Color(0xFFFFF0C2), Color(0xFF4E3700), R.string.identity_engineer)
        StationRole.SHIELDS -> Triple(Color(0xFFDFE9FF), Color(0xFF102A56), R.string.identity_shields)
    }
    val night = isSystemInDarkTheme()
    Surface(color = if (night) dark else light, contentColor = if (night) light else dark,
        shape = RoundedCornerShape(12.dp), modifier = Modifier.fillMaxWidth().testTag("roleIdentity-${role.name}")
            .semantics(mergeDescendants = true) { heading() }) {
        Row(Modifier.padding(12.dp), horizontalArrangement = Arrangement.spacedBy(12.dp)) {
            Text(role.name.take(1), style = MaterialTheme.typography.titleLarge, modifier = Modifier.clearAndSetSemantics { })
            Text(stringResource(label), style = MaterialTheme.typography.titleLarge)
        }
    }
}
