package com.onejob.game

import android.content.Context
import android.media.SoundPool
import androidx.compose.foundation.layout.Column
import androidx.compose.ui.semantics.SemanticsProperties
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.unit.dp
import androidx.test.platform.app.InstrumentationRegistry
import com.onejob.game.app.OneJobApp
import com.onejob.game.data.*
import com.onejob.game.data.protocol.*
import com.onejob.game.data.repository.*
import com.onejob.game.feedback.*
import com.onejob.game.ui.theme.OneJobTheme
import com.onejob.game.ui.theme.RoleIdentity
import kotlinx.coroutines.flow.MutableStateFlow
import org.junit.After
import org.junit.Assert.*
import org.junit.Rule
import org.junit.Test
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicInteger

class FeedbackSettingsTest {
    @get:Rule val compose=createComposeRule()
    private val context get()=InstrumentationRegistry.getInstrumentation().targetContext
    private val disk get()=context.getSharedPreferences("phase13_preferences_test",Context.MODE_PRIVATE)
    @After fun cleanPreferences() {disk.edit().clear().commit()}

    @Test fun accessibleTogglesPersistOnlyLocalBooleansAndQuietDefaults() {
        disk.edit().clear().commit()
        val preferences=FeedbackPreferencesRepository(AndroidFeedbackPreferenceStorage(disk))
        compose.setContent {OneJobTheme {OneJobApp(UnavailableGameRepository(),preferences)}}
        compose.onNodeWithTag("feedbackSettings").performClick()
        compose.onNodeWithTag("audioEnabled").performScrollTo().assertIsOff().assertHeightIsAtLeast(48.dp)
            .assert(hasText("Sound effects")).performClick()
        compose.onNodeWithTag("hapticsEnabled").performScrollTo().assertIsOff().assertHeightIsAtLeast(48.dp).performClick()
        compose.onNodeWithTag("reducedMotion").assertIsOn().assertHeightIsAtLeast(48.dp).performScrollTo().performClick()
        compose.onNodeWithText("Back").performScrollTo().performClick()
        compose.onNodeWithTag("feedbackSettings").performClick()
        compose.onNodeWithTag("audioEnabled").performScrollTo().assertIsOn()
        compose.onNodeWithTag("hapticsEnabled").performScrollTo().assertIsOn()
        compose.onNodeWithTag("reducedMotion").performScrollTo().assertIsOff()
        disk.edit().commit()
        assertEquals(FeedbackPreferences(true,true,false),FeedbackPreferencesRepository(AndroidFeedbackPreferenceStorage(disk)).preferences.value)
        assertEquals(setOf("audio_enabled","haptics_enabled","reduced_motion"),disk.all.keys)
        assertTrue(disk.all.values.all {it is Boolean})
    }

    private class DisplayRepo:GameRepository by UnavailableGameRepository() {
        override val connection=MutableStateFlow(ConnectionState(ConnectionStatus.CONNECTED))
        override val session=MutableStateFlow(SessionState())
        var calls=0
        override suspend fun setReady(ready:Boolean):CommandResult {calls++;return CommandResult.NotSent(ConnectionProblem.CONFIGURATION)}
        fun show(ids:List<Long>) {
            val players=(1..2).map {LobbyPlayer("00000000-0000-0000-0000-00000000000$it","Crew",true,false)}
            session.value=SessionState(SessionIdentity("ABCD23",null,"display"),LobbyPayload("ABCD23","running",players[0].player_id,players,false),
                PublicRound("00000000-0000-0000-0000-000000000099","running",10,89000,null,null,90,50,
                    ids.map {PublicWarning(it,"asteroid","Asteroid approach")},null),publicSnapshotReceived=true)
        }
    }
    @Test fun settingsStayOpenDuringServerUpdatesAndWarningsRemainVisibleWhenEffectsOff() {
        val repo=DisplayRepo();repo.show(emptyList())
        val preferences=FeedbackPreferencesRepository(MemoryFeedbackPreferenceStorage())
        compose.setContent {OneJobTheme {OneJobApp(repo,preferences)}}
        compose.onNodeWithTag("feedbackSettings").performScrollTo().performClick()
        compose.onNodeWithTag("audioEnabled").assertIsOff();compose.onNodeWithTag("hapticsEnabled").assertIsOff()
        compose.runOnIdle {repo.show(listOf(8))}
        compose.onNodeWithTag("audioEnabled").assertIsDisplayed()
        compose.onNodeWithText("Back").performScrollTo().performClick()
        compose.onNodeWithTag("displayWarning-8").performScrollTo().assertTextEquals("Asteroid approach")
            .assert(SemanticsMatcher.keyIsDefined(SemanticsProperties.LiveRegion))
        assertEquals(0,repo.calls);assertEquals("display",repo.session.value.identity!!.kind)
    }

    @Test fun roleIdentityHasTextRedundancyAndHeadingSemantics() {
        compose.setContent {OneJobTheme {Column {StationRole.entries.forEach {RoleIdentity(it)}}}}
        for((role,label) in listOf(StationRole.PILOT to "Pilot · navigation",StationRole.ENGINEER to "Engineer · power",StationRole.SHIELDS to "Shields · protection"))
            compose.onNodeWithTag("roleIdentity-${role.name}").assert(hasText(label))
                .assert(SemanticsMatcher.keyIsDefined(SemanticsProperties.Heading))
    }

    @Test fun packagedToneAssetsDecodeWithoutStartingPlayback() {
        val loaded=CountDownLatch(4);val errors=AtomicInteger()
        val pool=SoundPool.Builder().setMaxStreams(1).build()
        try {
            pool.setOnLoadCompleteListener {_,_,status->if(status!=0) errors.incrementAndGet();loaded.countDown()}
            for(id in listOf(R.raw.feedback_countdown,R.raw.feedback_accepted,R.raw.feedback_rejected,R.raw.feedback_urgent))
                assertTrue(pool.load(context,id,1)>0)
            assertTrue("Generated WAVs must decode on Android",loaded.await(10,TimeUnit.SECONDS))
            assertEquals(0,errors.get())
        } finally {pool.release()}
    }
}
