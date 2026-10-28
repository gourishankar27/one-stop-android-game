package com.onejob.game

import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.junit4.createAndroidComposeRule
import androidx.compose.ui.test.onNodeWithText
import org.junit.Rule
import org.junit.Test

class FoundationHomeTest {
    @get:Rule
    val composeRule = createAndroidComposeRule<MainActivity>()

    @Test
    fun homeExplainsFoundationStatus() {
        composeRule.onNodeWithText("ONE JOB").assertIsDisplayed()
        composeRule.onNodeWithText("Android foundation").assertIsDisplayed()
    }
}
