package com.onejob.game

import androidx.test.platform.app.InstrumentationRegistry
import com.onejob.game.data.ConnectionStatus
import com.onejob.game.data.network.*
import com.onejob.game.data.repository.*
import kotlinx.coroutines.*
import kotlinx.coroutines.flow.first
import org.junit.Assert.*
import org.junit.Assume.assumeTrue
import org.junit.Test
import java.util.concurrent.atomic.AtomicInteger

class LiveServerDisplayTest {
    private class Droppable : SocketDataSource {
        private val delegate=OkHttpSocketDataSource()
        @Volatile var socket:SocketSession?=null
        val opens=AtomicInteger()
        override fun open(endpoint:Endpoint)=delegate.open(endpoint).also {socket=it;opens.incrementAndGet()}
        override fun close()=delegate.close()
    }
    @Test fun displayRecoveryNeverPausesPlayersAndRoomDeletionExpiresObservers() = runBlocking {
        assumeTrue(InstrumentationRegistry.getArguments().getString("oneJobLiveServer")=="true")
        val endpoint=Endpoint.parse(BuildConfig.WS_ENDPOINT,BuildConfig.DEBUG,BuildConfig.ALLOW_DEBUG_CLEARTEXT)
        assertTrue(endpoint is EndpointResult.Ready)
        val owner=CoroutineScope(SupervisorJob()+Dispatchers.Default)
        val source=Droppable()
        val host=SocketGameRepository(EndpointProvider {endpoint},OkHttpSocketDataSource(),owner)
        val guest=SocketGameRepository(EndpointProvider {endpoint},OkHttpSocketDataSource(),owner)
        val display=SocketGameRepository(EndpointProvider {endpoint},source,owner)
        val late=SocketGameRepository(EndpointProvider {endpoint},OkHttpSocketDataSource(),owner)
        val third=SocketGameRepository(EndpointProvider {endpoint},OkHttpSocketDataSource(),owner)
        try {
            withTimeout(30_000) {
                assertTrue(host.create("Display host") is CommandResult.Accepted)
                val code=host.session.first {it.lobby!=null}.identity!!.roomCode
                assertTrue(guest.join(code,"Display guest") is CommandResult.Accepted)
                assertTrue(display.joinDisplay(code) is CommandResult.Accepted)
                display.session.first {it.lobby!=null && it.publicSnapshotReceived}
                assertEquals("display",display.session.value.identity!!.kind)
                assertNull(display.session.value.identity!!.playerId)
                assertNull(display.session.value.assigned);assertNull(display.session.value.roleState)
                assertTrue(host.setReady(true) is CommandResult.Accepted)
                assertFalse(host.session.value.lobby!!.can_start)
                assertTrue(display.setReady(true) is CommandResult.Rejected)
                assertTrue(guest.setReady(true) is CommandResult.Accepted)
                host.session.first {it.lobby?.can_start==true}
                assertEquals(2,host.session.value.lobby!!.players.size)
                assertTrue(host.start() is CommandResult.Accepted)
                val round=host.session.first {it.roleState!=null}.assigned!!.round_id
                guest.session.first {it.roleState!=null}
                assertTrue(host.acknowledgeBriefing(round) is CommandResult.Accepted)
                assertTrue(guest.acknowledgeBriefing(round) is CommandResult.Accepted)
                display.session.first {it.publicRound?.stage=="running"}
                assertTrue(late.joinDisplay(code) is CommandResult.Accepted)
                late.session.first {it.publicRound?.stage=="running"}
                val full=third.joinDisplay(code)
                assertTrue(full is CommandResult.Rejected && full.code==RemoteCode.DISPLAY_FULL)
                val tick=host.session.value.roleState!!.public.tick_index
                source.socket!!.cancel()
                host.session.first {it.roleState!!.public.tick_index>tick+3 && it.roleState.public.stage=="running"}
                display.connection.first {it.status==ConnectionStatus.CONNECTED && source.opens.get()>1}
                assertEquals("display",display.session.value.identity!!.kind)
                assertEquals(round,display.session.value.publicRound!!.round_id)
                assertNull(display.session.value.assigned);assertNull(display.session.value.roleState)
                assertTrue(host.leave() is CommandResult.Accepted)
                display.session.first {it.publicRound?.result?.reason=="player_left"}
                assertTrue(guest.leave() is CommandResult.Accepted)
                display.connection.first {it.status==ConnectionStatus.SESSION_EXPIRED}
                late.connection.first {it.status==ConnectionStatus.SESSION_EXPIRED}
                assertNull(display.session.value.identity)
            }
        } finally {
            for(repo in listOf(host,guest,display,late,third)) repo.closeAndJoin()
            owner.cancel()
        }
    }
}
