package com.onejob.game

import com.onejob.game.data.protocol.*
import com.onejob.game.data.repository.*
import com.onejob.game.navigation.*
import kotlinx.serialization.json.*
import org.junit.Assert.*
import org.junit.Test

class SessionNavigationTest {
    private fun session(label: String): SessionState {
        val codec=ProtocolCodec()
        val text=javaClass.classLoader!!.getResourceAsStream("phase11.json")!!.bufferedReader().use { it.readText() }
        val case=codec.json.parseToJsonElement(text).jsonArray.first {
            it.jsonObject["request"]!!.jsonObject["request_id"]!!.jsonPrimitive.content=="$label-2-1"
        }.jsonObject
        val assigned=((codec.decode(case["events"]!!.jsonArray[0].toString()) as DecodedFrame.Message).message as ServerMessage.RoleAssigned).payload
        val state=((codec.decode(case["response"].toString()) as DecodedFrame.Message).message as ServerMessage.RoleState).payload
        return SessionState(identity=SessionIdentity("ABCD23","00000000-0000-0000-0000-000000000001"),assigned=assigned,roleState=state)
    }

    @Test fun countdownAndItsPauseUseOnlyServerStage() {
        assertEquals(AppDestination.COUNTDOWN,sessionDestination(session("countdown"),null,false))
        assertEquals(AppDestination.COUNTDOWN,sessionDestination(session("paused-countdown"),AppDestination.GAMEPLAY,false))
    }
    @Test fun eachTerminalSnapshotShowsResultsWithoutGameOverEvent() {
        for (kind in listOf("victory","defeat","briefing-abort"))
            assertEquals(AppDestination.RESULTS,sessionDestination(session(kind),AppDestination.GAMEPLAY,false))
    }
    @Test fun newBriefingAndLobbyOverrideOldResultAndRecoveryRetainsOnlyRoute() {
        val old=session("victory")
        val lobby=LobbyPayload("ABCD23","lobby",old.identity!!.playerId,
            listOf(LobbyPlayer(old.identity.playerId!!,"Crew",true,false)),false)
        assertEquals(AppDestination.LOBBY,sessionDestination(old.copy(lobby=lobby),AppDestination.RESULTS,false))
        assertEquals(AppDestination.ROLE,sessionDestination(old.copy(lobby=lobby.copy(stage="briefing")),AppDestination.RESULTS,false))
        assertEquals(AppDestination.RESULTS,sessionDestination(SessionState(),AppDestination.RESULTS,true))
        assertEquals(AppDestination.LOBBY,sessionDestination(SessionState(),AppDestination.RESULTS,false))
        val changed=old.copy(assigned=old.assigned!!.copy(round_id="00000000-0000-0000-0000-000000000100"),
            lobby=lobby.copy(stage="running"))
        assertEquals(AppDestination.GAMEPLAY,sessionDestination(changed,null,false))
    }
}
