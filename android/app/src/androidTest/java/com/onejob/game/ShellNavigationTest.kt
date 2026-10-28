package com.onejob.game

import android.Manifest
import android.content.pm.PackageManager
import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.assertTextContains
import androidx.compose.ui.test.junit4.createAndroidComposeRule
import androidx.compose.ui.test.onNodeWithTag
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
import androidx.compose.ui.test.performScrollTo
import androidx.compose.ui.test.performTextInput
import androidx.test.espresso.Espresso
import org.junit.Assert.assertFalse
import org.junit.Rule
import org.junit.Test

class ShellNavigationTest {
    @get:Rule val compose = createAndroidComposeRule<MainActivity>()

    private fun open(label: String) {
        compose.onNodeWithText(label).performScrollTo().performClick()
    }

    @Test
    fun everyFutureDestinationIsTruthfulAndSystemBackReturnsHome() {
        for ((button, title) in listOf(
            "Preview lobby" to "Lobby preview",
            "Preview role briefing" to "Role briefing preview",
            "Preview gameplay" to "Gameplay preview",
            "Preview results" to "Results preview",
        )) {
            open(button)
            compose.onNodeWithText(title).assertIsDisplayed()
            compose.onNodeWithText("Preview — not implemented").assertIsDisplayed()
            compose.onNodeWithText("No room or game session is open.").assertIsDisplayed()
            Espresso.pressBack()
            compose.onNodeWithText("ONE JOB").performScrollTo().assertIsDisplayed()
        }
    }

    @Test
    fun joinDraftAndDestinationSurviveActivityRecreationThenBackReturnsHome() {
        open("Join room setup")
        compose.onNodeWithTag("nameInput").performTextInput("Saved crew")
        compose.onNodeWithTag("codeInput").performScrollTo().performTextInput("aBcD23")
        open("Check draft")
        compose.onNodeWithText("Draft looks good. Online play is not connected yet.")
            .performScrollTo().assertIsDisplayed()
        compose.activityRule.scenario.recreate()
        compose.onNodeWithText("Join room draft").performScrollTo().assertIsDisplayed()
        compose.onNodeWithTag("nameInput").assertTextContains("Saved crew")
        compose.onNodeWithTag("codeInput").assertTextContains("aBcD23")
        compose.onNodeWithText("Draft looks good. Online play is not connected yet.")
            .performScrollTo().assertIsDisplayed()
        open("Back")
        compose.onNodeWithText("ONE JOB").performScrollTo().assertIsDisplayed()
    }

    @Test
    fun createValidationStaysLocalAndJoinStartsWithItsOwnDraft() {
        open("Create room setup")
        open("Check draft")
        compose.onNodeWithText("Enter a player name.").performScrollTo().assertIsDisplayed()
        compose.onNodeWithTag("nameInput").performScrollTo().performTextInput("Captain")
        open("Check draft")
        compose.onNodeWithText("Draft looks good. Online play is not connected yet.")
            .performScrollTo().assertIsDisplayed()
        open("Back")
        open("Join room setup")
        compose.onNodeWithTag("nameInput").assertTextContains("")
        compose.onNodeWithText("Local draft only").assertIsDisplayed()
        Espresso.pressBack()
        compose.onNodeWithText("ONE JOB").performScrollTo().assertIsDisplayed()
    }

    @Test
    fun installedShellHasNoNetworkPermission() {
        val activity = compose.activity
        val info = activity.packageManager.getPackageInfo(activity.packageName, PackageManager.GET_PERMISSIONS)
        assertFalse(info.requestedPermissions.orEmpty().contains(Manifest.permission.INTERNET))
    }
}
