package com.onejob.game

import androidx.test.platform.app.InstrumentationRegistry
import com.onejob.game.data.ConnectionStatus
import com.onejob.game.data.network.Endpoint
import com.onejob.game.data.network.EndpointProvider
import com.onejob.game.data.network.EndpointResult
import com.onejob.game.data.network.OkHttpSocketDataSource
import com.onejob.game.data.network.SocketDataSource
import com.onejob.game.data.network.SocketSession
import com.onejob.game.data.repository.CommandResult
import com.onejob.game.data.repository.RemoteCode
import com.onejob.game.data.repository.SocketGameRepository
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.withTimeout
import org.junit.Assert.*
import org.junit.Assume.assumeTrue
import org.junit.Test
import java.util.concurrent.atomic.AtomicInteger

/** Explicitly opt in against a disposable local server; regular connected tests skip it. */
class LiveServerNetworkingTest {
    private class DroppableSource : SocketDataSource {
        private val delegate = OkHttpSocketDataSource()
        @Volatile var latest: SocketSession? = null
        val opens = AtomicInteger()
        override fun open(endpoint: Endpoint): SocketSession = delegate.open(endpoint).also {
            latest = it
            opens.incrementAndGet()
        }
        override fun close() = delegate.close()
    }

    @Test
    fun realServerPingCreateJoinAndCredentialResumeReplaceFullSnapshot() = runBlocking {
        assumeTrue(InstrumentationRegistry.getArguments().getString("oneJobLiveServer") == "true")
        val endpoint = Endpoint.parse(BuildConfig.WS_ENDPOINT, BuildConfig.DEBUG, BuildConfig.ALLOW_DEBUG_CLEARTEXT)
        assertTrue("Configure an explicit debug endpoint before this check", endpoint is EndpointResult.Ready)
        val owner = CoroutineScope(SupervisorJob() + Dispatchers.Default)
        val source = DroppableSource()
        val host = SocketGameRepository(EndpointProvider { endpoint }, source, owner)
        val guest = SocketGameRepository(EndpointProvider { endpoint }, OkHttpSocketDataSource(), owner)
        try {
            withTimeout(30_000) {
                assertTrue("Connect failed; check the LAN endpoint", host.connect() is CommandResult.Accepted)
                assertTrue("Ping failed", host.ping() is CommandResult.Accepted)
                assertTrue("Create failed", host.create("Network host") is CommandResult.Accepted)
                val identity = host.session.first { it.identity != null && it.lobby != null }.identity!!
                assertTrue("Join failed", guest.join(identity.roomCode, "Network guest") is CommandResult.Accepted)
                host.session.first { it.lobby?.players?.size == 2 }
                assertTrue(host.setReady(true) is CommandResult.Accepted)
                assertTrue(guest.setReady(true) is CommandResult.Accepted)
                host.session.first { it.lobby?.can_start == true }
                val craftedNonHostStart = guest.start()
                assertTrue("The server must reject non-host Start even without the UI guard", craftedNonHostStart is CommandResult.Rejected && craftedNonHostStart.code == RemoteCode.NOT_HOST)
                val start = host.start()
                assertTrue("Eligible Start must enter briefing", start is CommandResult.Accepted)
                val hostBriefing = host.session.first { it.assigned != null && it.roleState != null }
                val guestBriefing = guest.session.first { it.assigned != null && it.roleState != null }
                val roundId = hostBriefing.assigned!!.round_id
                assertEquals(roundId, guestBriefing.assigned!!.round_id)
                assertEquals(hostBriefing.assigned.roles.toSet(), hostBriefing.roleState!!.stations.roles().toSet())
                assertEquals(guestBriefing.assigned.roles.toSet(), guestBriefing.roleState!!.stations.roles().toSet())
                assertEquals(3, (hostBriefing.assigned.roles + guestBriefing.assigned.roles).distinct().size)
                val guestOwnsPilot = com.onejob.game.data.protocol.StationRole.PILOT in guestBriefing.assigned.roles
                val wrongAction = if (guestOwnsPilot) com.onejob.game.data.protocol.PlayerAction.Coolant else com.onejob.game.data.protocol.PlayerAction.MoveLane(com.onejob.game.data.protocol.Direction.LEFT)
                val wrong = guest.submitAction(roundId, 1, wrongAction)
                assertTrue("A crafted wrong-role action must be rejected by the server", wrong is CommandResult.Rejected && wrong.code == RemoteCode.NOT_ROLE_OWNER)
                val stale = guest.acknowledgeBriefing("00000000-0000-0000-0000-000000000098")
                assertTrue(stale is CommandResult.Rejected && stale.code == RemoteCode.STALE_ROUND)
                assertTrue(host.acknowledgeBriefing(roundId) is CommandResult.Accepted)
                assertTrue(guest.acknowledgeBriefing(roundId) is CommandResult.Accepted)
                host.session.first { it.roleState?.public?.stage == "running" }
                val engineer = if (com.onejob.game.data.protocol.StationRole.ENGINEER in hostBriefing.assigned.roles) host else guest
                val pilot = if (engineer === host) guest else host
                fun actionAccepted(result: CommandResult) {
                    assertTrue(result is CommandResult.Accepted && result.sequence != null && result.appliedTick != null)
                }
                actionAccepted(engineer.performAction(roundId, com.onejob.game.data.protocol.PlayerAction.SetShield(true, com.onejob.game.data.protocol.Facing.LEFT)))
                actionAccepted(engineer.performAction(roundId, com.onejob.game.data.protocol.PlayerAction.RechargeShield))
                val pressure = engineer.performAction(roundId, com.onejob.game.data.protocol.PlayerAction.EngineBoost)
                assertTrue(pressure is CommandResult.Rejected && pressure.code == RemoteCode.INSUFFICIENT_POWER)
                actionAccepted(engineer.performAction(roundId, com.onejob.game.data.protocol.PlayerAction.SetEnginePower(100)))
                actionAccepted(engineer.performAction(roundId, com.onejob.game.data.protocol.PlayerAction.EngineBoost))
                actionAccepted(engineer.performAction(roundId, com.onejob.game.data.protocol.PlayerAction.ShieldBoost))
                actionAccepted(pilot.performAction(roundId, com.onejob.game.data.protocol.PlayerAction.MoveLane(com.onejob.game.data.protocol.Direction.LEFT)))
                actionAccepted(pilot.performAction(roundId, com.onejob.game.data.protocol.PlayerAction.Evade))
                actionAccepted(engineer.performAction(roundId, com.onejob.game.data.protocol.PlayerAction.Coolant))
                engineer.session.first { it.roleState?.stations?.engineer?.output == 100 }
                pilot.session.first { it.roleState?.stations?.pilot?.lane == com.onejob.game.data.protocol.LaneValue.LEFT }
                actionAccepted(engineer.performAction(roundId, com.onejob.game.data.protocol.PlayerAction.EmergencyShutdown))
                engineer.session.first { it.roleState?.stations?.engineer?.output == 0 && it.roleState.stations.shields?.active == false }

                source.latest!!.cancel()
                host.connection.first { it.status == ConnectionStatus.RECONNECTING }
                assertNull("A broken connection must discard cached lobby state", host.session.value.lobby)
                assertNull("A broken connection must discard private station views", host.session.value.roleState)
                val recovered = combine(host.connection, host.session) { connection, session -> connection to session }
                    .first { (connection, session) -> connection.status == ConnectionStatus.CONNECTED && session.lobby != null }
                    .second
                assertEquals(identity, recovered.identity)
                assertEquals(roundId, recovered.assigned!!.round_id)
                assertTrue(recovered.roleState!!.briefing.acknowledged && !recovered.roleState.briefing.held_for_gameplay)
                assertEquals("running", recovered.roleState.public.stage)
                assertEquals(2, recovered.lobby!!.players.size)
                assertTrue("Readiness must come from the resumed server snapshot", recovered.lobby.players.none { it.ready })
                assertEquals("Only one replacement socket is expected", 2, source.opens.get())
                val resumedAction = if (com.onejob.game.data.protocol.StationRole.PILOT in recovered.assigned.roles)
                    com.onejob.game.data.protocol.PlayerAction.MoveLane(com.onejob.game.data.protocol.Direction.RIGHT)
                else com.onejob.game.data.protocol.PlayerAction.EmergencyShutdown
                actionAccepted(host.performAction(roundId, resumedAction))
                assertTrue(host.requestState() is CommandResult.Accepted)
                assertTrue(guest.leave() is CommandResult.Accepted)
                host.session.first { it.lobby?.players?.size == 1 }
                host.session.first { it.roleState?.public?.result?.reason == "player_left" }
                assertTrue(host.leave() is CommandResult.Accepted)
                assertNull(host.session.value.identity)
                assertEquals(ConnectionStatus.DISCONNECTED, host.connectionStatus.value)
            }
        } finally {
            host.closeAndJoin()
            guest.closeAndJoin()
            owner.cancel()
        }
    }
}
