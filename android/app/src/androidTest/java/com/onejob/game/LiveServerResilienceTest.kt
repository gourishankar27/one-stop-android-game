package com.onejob.game

import android.content.Context
import android.content.ContextWrapper
import androidx.test.platform.app.InstrumentationRegistry
import com.onejob.game.data.ConnectionStatus
import com.onejob.game.data.network.*
import com.onejob.game.data.protocol.*
import com.onejob.game.data.repository.*
import java.io.File
import kotlinx.coroutines.*
import kotlinx.coroutines.flow.first
import org.junit.Assert.*
import org.junit.Assume.assumeTrue
import org.junit.Test

class LiveServerResilienceTest {
    @Test fun privateProcessRecoveryAndBackgroundPreserveIdentitySequenceAndTerminalForTwoAndThreePlayers() = runBlocking {
        assumeTrue(InstrumentationRegistry.getArguments().getString("oneJobLiveServer")=="true")
        val endpoint=Endpoint.parse(BuildConfig.WS_ENDPOINT,BuildConfig.DEBUG,BuildConfig.ALLOW_DEBUG_CLEARTEXT)
        assertTrue(endpoint is EndpointResult.Ready)
        val app=InstrumentationRegistry.getInstrumentation().targetContext
        val owner=CoroutineScope(SupervisorJob()+Dispatchers.Default)
        val repositories=mutableListOf<SocketGameRepository>()
        val directories=mutableListOf<File>()
        fun store(name:String):AndroidSessionStorage {
            val directory=File(app.noBackupFilesDir,"resilience-live-$name").apply {mkdirs()}
            directories+=directory
            val context=object:ContextWrapper(app) {
                override fun getApplicationContext():Context=this
                override fun getNoBackupFilesDir():File=directory
            }
            return AndroidSessionStorage(context)
        }
        fun repo(storage:SessionStorage?=null)=SocketGameRepository(EndpointProvider {endpoint},OkHttpSocketDataSource(),owner,
            now=android.os.SystemClock::elapsedRealtime,sessionStorage=storage).also {repositories+=it}
        try { withTimeout(60_000) {
            for(count in listOf(2,3)) {
                val disk=store("host-$count")
                var host=repo(disk)
                assertTrue(host.create("Host") is CommandResult.Accepted)
                val identity=host.session.value.identity!!
                val guests=(1 until count).map { repo().also {assertTrue(it.join(identity.roomCode,"Guest") is CommandResult.Accepted)} }
                val all=listOf(host)+guests
                all.forEach {assertTrue(it.setReady(true) is CommandResult.Accepted)}
                host.session.first {it.lobby?.can_start==true}
                assertTrue(host.start() is CommandResult.Accepted)
                val briefing=host.session.first {it.assigned!=null && it.roleState!=null}
                val round=briefing.assigned!!.round_id
                all.forEach {assertTrue(it.acknowledgeBriefing(round) is CommandResult.Accepted)}
                host.session.first {it.roleState?.public?.stage=="running"}
                val action=when {
                    StationRole.PILOT in briefing.assigned.roles -> PlayerAction.MoveLane(Direction.LEFT)
                    StationRole.ENGINEER in briefing.assigned.roles -> PlayerAction.SetEnginePower(60)
                    else -> PlayerAction.SetShield(true,Facing.LEFT)
                }
                assertTrue(host.performAction(round,action) is CommandResult.Accepted)
                host.requestState()
                val high=host.session.value.roleState!!.last_client_action_seq
                assertTrue(high>0)
                host.setForeground(false)
                guests.first().session.first {it.roleState?.public?.stage=="paused"}
                assertEquals(identity.playerId,guests.first().session.value.lobby!!.host_player_id)
                assertNull(host.session.value.roleState)
                assertTrue(host.performAction(round,action) is CommandResult.NotSent)
                host.closeAndJoin() // New repository/storage owner models a fresh process; no cached views/counter.
                host=repo(disk)
                host.connection.first {it.status==ConnectionStatus.CONNECTED}
                val recovered=host.session.first {it.roleState?.public?.stage=="running"}
                assertEquals(identity,recovered.identity)
                assertEquals(briefing.assigned.roles,recovered.assigned!!.roles)
                assertEquals(high,recovered.roleState!!.last_client_action_seq)
                val next=host.performAction(round,action)
                assertFalse(next is CommandResult.Rejected && next.code==RemoteCode.STALE_ACTION)
                assertTrue(next is CommandResult.Accepted || next is CommandResult.Rejected)
                host.requestState()
                assertEquals(high+1,host.session.value.roleState!!.last_client_action_seq)

                val displayDisk=store("display-$count")
                var display=repo(displayDisk)
                assertTrue(display.joinDisplay(identity.roomCode) is CommandResult.Accepted)
                display.session.first {it.publicSnapshotReceived}
                display.setForeground(false); display.closeAndJoin()
                host.requestState(); assertEquals("running",host.session.value.roleState!!.public.stage)
                display=repo(displayDisk); display.connection.first {it.status==ConnectionStatus.CONNECTED}
                assertEquals("display",display.session.value.identity!!.kind)
                assertNull(display.session.value.assigned); assertNull(display.session.value.roleState)
                assertEquals(round,display.session.value.publicRound!!.round_id)
                assertTrue(guests.last().leave() is CommandResult.Accepted)
                val terminal=host.session.first {it.roleState?.public?.result!=null}.roleState!!.public.result!!
                host.setForeground(false); host.closeAndJoin(); host=repo(disk)
                host.connection.first {it.status==ConnectionStatus.CONNECTED}
                assertEquals(terminal,host.session.value.roleState!!.public.result)
                assertTrue(host.returnToLobby() is CommandResult.Accepted)
                host.session.first {it.lobby?.stage=="lobby" && it.roleState==null}
                assertTrue(display.leave() is CommandResult.Accepted); assertNull(displayDisk.read())
                guests.dropLast(1).forEach {it.leave()}
                assertTrue(host.leave() is CommandResult.Accepted); assertNull(disk.read())
            }
        } } finally {
            repositories.forEach {it.closeAndJoin()}; owner.cancel()
            directories.forEach {it.deleteRecursively()}
        }
    }
}
