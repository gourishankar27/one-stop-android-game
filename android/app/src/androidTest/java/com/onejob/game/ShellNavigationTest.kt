package com.onejob.game

import android.Manifest
import android.content.pm.PackageManager
import com.onejob.game.app.OneJobApplication
import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.assertTextContains
import androidx.compose.ui.test.junit4.createAndroidComposeRule
import androidx.compose.ui.test.onNodeWithTag
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.onAllNodesWithText
import androidx.compose.ui.test.onFirst
import androidx.compose.ui.test.performClick
import androidx.compose.ui.test.performScrollTo
import androidx.compose.ui.test.performTextInput
import androidx.test.espresso.Espresso
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test

class ShellNavigationTest {
    @get:Rule val compose = createAndroidComposeRule<MainActivity>()

    private fun open(label: String) {
        compose.onNodeWithText(label).performScrollTo().performClick()
    }

    @Test
    fun homeHasRealAdmissionAndResultsRequireAServerRound() {
        compose.onNodeWithText("Preview results").assertDoesNotExist()
        open("Create room")
        Espresso.pressBack()
        compose.onNodeWithText("ONE JOB").performScrollTo().assertIsDisplayed()
    }

    @Test
    fun joinDraftAndDestinationSurviveActivityRecreationThenBackReturnsHome() {
        open("Join room")
        compose.onNodeWithTag("nameInput").performTextInput("Saved crew")
        compose.onNodeWithTag("codeInput").performScrollTo().performTextInput("aBcD23")
        compose.activityRule.scenario.recreate()
        compose.onAllNodesWithText("Join room").onFirst().performScrollTo().assertIsDisplayed()
        compose.onNodeWithTag("nameInput").assertTextContains("Saved crew")
        compose.onNodeWithTag("codeInput").assertTextContains("aBcD23")
        open("Back")
        compose.onNodeWithText("ONE JOB").performScrollTo().assertIsDisplayed()
    }

    @Test
    fun activityRecreationRetainsTheApplicationRepositoryOwner() {
        val before = (compose.activity.application as OneJobApplication).container.gameRepository
        compose.activityRule.scenario.recreate()
        val after = (compose.activity.application as OneJobApplication).container.gameRepository
        org.junit.Assert.assertSame(before, after)
    }

    @Test
    fun createValidationStaysLocalAndJoinStartsWithItsOwnDraft() {
        open("Create room")
        compose.onNodeWithTag("submitAdmission").performScrollTo().performClick()
        compose.onNodeWithText("Enter a player name.").performScrollTo().assertIsDisplayed()
        compose.onNodeWithTag("nameInput").performScrollTo().performTextInput("Captain")
        open("Back")
        open("Join room")
        compose.onNodeWithTag("nameInput").assertTextContains("")
        compose.onNodeWithText("Choose your name. Join the same room code as your friends.").assertIsDisplayed()
        Espresso.pressBack()
        compose.onNodeWithText("ONE JOB").performScrollTo().assertIsDisplayed()
    }

    @Test
    fun installedNetworkingShellHasNetworkPermission() {
        val activity = compose.activity
        val info = activity.packageManager.getPackageInfo(activity.packageName, PackageManager.GET_PERMISSIONS)
        assertTrue(info.requestedPermissions.orEmpty().contains(Manifest.permission.INTERNET))
    }
}
