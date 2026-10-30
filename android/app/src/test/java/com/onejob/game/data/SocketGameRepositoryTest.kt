package com.onejob.game.data

import com.onejob.game.data.network.*
import com.onejob.game.data.protocol.*
import com.onejob.game.data.repository.*
import kotlinx.coroutines.*
import kotlinx.coroutines.channels.Channel
import kotlinx.coroutines.test.*
import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.decodeFromJsonElement
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.Json
import org.junit.Assert.*
import org.junit.Test

private const val PLAYER = "00000000-0000-0000-0000-000000000001"
private const val ROUND = "00000000-0000-0000-0000-000000000010"
private const val TOKEN = "SYNTHETIC_TOKEN_SENTINEL"

private class FakeSocket : SocketSession {
    override val events = Channel<SocketEvent>(64)
    val sent = mutableListOf<ClientMessage>()
    var cancelled = false
    var acceptsSends = true
    private val codec = ProtocolCodec()
    private val serverJson = Json(codec.json) { encodeDefaults = false }
    override fun send(text: String): Boolean {
        if (!acceptsSends) return false
        sent += codec.json.decodeFromString<ClientMessage>(text)
        return true
    }
    override fun close(code: Int) { cancelled = true }
    override fun cancel() { cancelled = true }
    fun open() { check(events.trySend(SocketEvent.Open).isSuccess) }
    fun reply(message: ServerMessage) { raw(serverJson.encodeToString<ServerMessage>(message)) }
    fun raw(text: String) { check(events.trySend(SocketEvent.Text(text)).isSuccess) }
    fun fail() { events.close(TransportFailure(TransportProblem.NETWORK)) }
}

private class FakeSource(private val clock: () -> Long) : SocketDataSource {
    val sockets = mutableListOf<FakeSocket>()
    val times = mutableListOf<Long>()
    var closed = false
    override fun open(endpoint: Endpoint): SocketSession = FakeSocket().also { sockets += it; times += clock() }
    override fun close() { closed = true; sockets.forEach { it.cancel() } }
}

@OptIn(ExperimentalCoroutinesApi::class)
class SocketGameRepositoryTest {
    private class Rig(val scope: TestScope) {
        val source = FakeSource { scope.testScheduler.currentTime }
        private var ids = 0
        var endpoint = Endpoint.parse("ws://127.0.0.1:8000/ws", true, true)
        val repo = SocketGameRepository(EndpointProvider { endpoint }, source, scope,
            now = { scope.testScheduler.currentTime }, newId = { "request-${++ids}" })
        val socket get() = source.sockets.last()

        suspend fun admit() {
            val command = scope.async { repo.create(" Crew ") }
            scope.runCurrent()
            socket.open(); scope.runCurrent()
            val request = socket.sent.single() as ClientMessage.Create
            assertEquals("Crew", request.payload.name)
            socket.reply(ServerMessage.SessionAccepted(1, request.request_id, 1, SessionPayload("ABCD23", "player", PLAYER, TOKEN)))
            socket.reply(lobby())
            scope.runCurrent()
            assertTrue(command.await() is CommandResult.Accepted)
            assertNotNull(repo.session.value.lobby)
        }

        fun lobby(revision: Long = 1, reply: String? = null, ready: Boolean = false) = ServerMessage.Lobby(
            1, reply, revision, LobbyPayload("ABCD23", "lobby", PLAYER, listOf(LobbyPlayer(PLAYER, "Crew", true, ready)), false),
        )
    }

    private fun privateFixture(role: StationRole): Pair<ServerMessage.RoleAssigned, ServerMessage.RoleState> {
        val codec = ProtocolCodec()
        val data = javaClass.classLoader!!.getResourceAsStream("phase08.json")!!.bufferedReader().use { it.readText() }
        for (item in codec.json.parseToJsonElement(data).jsonArray) {
            val event = item.jsonObject["events"]?.jsonArray?.firstOrNull() ?: continue
            val assigned = (codec.decode(event.toString()) as DecodedFrame.Message).message as ServerMessage.RoleAssigned
            if (assigned.payload.roles == listOf(role)) {
                val state = (codec.decode(item.jsonObject.getValue("response").toString()) as DecodedFrame.Message).message as ServerMessage.RoleState
                return assigned.copy(room_revision = 7) to state.copy(reply_to = null, room_revision = 7)
            }
        }
        error("Missing synthetic role fixture")
    }

    @Test fun emergencyLifecycleDoesNotInventStateOrSuppressEqualRevisionSnapshot() = runTest {
        val rig = Rig(this)
        try {
            rig.admit()
            val (assigned, original) = privateFixture(StationRole.PILOT)
            val state = original.copy(payload=original.payload.copy(
                public=original.payload.public.copy(stage="running",tick_index=80),
                briefing=BriefingStatus(true,emptyList(),0,true,false)))
            rig.socket.reply(assigned); rig.socket.reply(state); runCurrent()
            val event=ServerMessage.EmergencyEvent(1,null,8,
                EmergencyEventPayload(assigned.payload.round_id,1,"asteroid","started"))
            rig.socket.reply(event); runCurrent()
            assertEquals(state.payload,rig.repo.session.value.roleState)
            assertEquals(event.payload,rig.repo.session.value.emergencyEvent)
            val updated=state.copy(room_revision=8,payload=state.payload.copy(
                public=state.payload.public.copy(warnings=listOf(PublicWarning(1,"asteroid","Asteroid approach"))),
                stations=state.payload.stations.copy(pilot=state.payload.stations.pilot!!.copy(
                    hazards=listOf(PilotHazard(1,LaneValue.LEFT,8000))))))
            rig.socket.reply(updated); rig.socket.reply(event); runCurrent()
            assertEquals(updated.payload,rig.repo.session.value.roleState)
            val resolved=event.copy(room_revision=9,payload=event.payload.copy(status="resolved"))
            rig.socket.reply(resolved)
            rig.socket.reply(event.copy(room_revision=9,payload=event.payload.copy(emergency_id=2)))
            runCurrent()
            assertEquals(resolved.payload,rig.repo.session.value.emergencyEvent)
            rig.socket.reply(event.copy(payload=event.payload.copy(round_id="00000000-0000-0000-0000-000000000098")))
            runCurrent()
            assertEquals(ConnectionStatus.CONNECTED,rig.repo.connectionStatus.value)
            assertEquals(updated.payload,rig.repo.session.value.roleState)
        } finally { rig.repo.closeAndJoin() }
    }

    @Test fun actionSequenceIsAllocatedByRepositoryAndRejectedActionsAreCorrelated() = runTest {
        val rig = Rig(this)
        try {
            rig.admit()
            val (assigned, state) = privateFixture(StationRole.PILOT)
            val roundId = assigned.payload.round_id
            val running = state.copy(payload = state.payload.copy(
                public = state.payload.public.copy(stage = "running"),
                briefing = BriefingStatus(true, emptyList(), 0, true, false)))
            rig.socket.reply(assigned); rig.socket.reply(running); runCurrent()
            val first = async { rig.repo.performAction(roundId, PlayerAction.Evade) }; runCurrent()
            val request = rig.socket.sent.last() as ClientMessage.Action
            assertEquals(1L, request.payload.client_action_seq)
            rig.socket.reply(ServerMessage.ActionRejected(1, request.request_id, 7,
                ActionRejectedPayload("insufficient_power", "SECRET_SENTINEL", 1, roundId)))
            runCurrent(); assertEquals(RemoteCode.INSUFFICIENT_POWER, (first.await() as CommandResult.Rejected).code)
            val second = async { rig.repo.performAction(roundId, PlayerAction.Evade) }; runCurrent()
            val next = rig.socket.sent.last() as ClientMessage.Action
            assertEquals(2L, next.payload.client_action_seq)
            rig.socket.reply(ServerMessage.Ack(1, next.request_id, 8, AckPayload("player_action", 2, 12)))
            runCurrent()
            val accepted = second.await() as CommandResult.Accepted
            assertEquals(2L, accepted.sequence); assertEquals(12L, accepted.appliedTick)
            assertEquals(state.payload.stations, rig.repo.session.value.roleState!!.stations)
            assertFalse(first.toString().contains("SECRET_SENTINEL"))
        } finally { rig.repo.closeAndJoin() }
    }

    @Test fun mismatchedActionRejectionCannotCompleteAnotherAction() = runTest {
        val rig = Rig(this)
        try {
            rig.admit()
            val (assigned, state) = privateFixture(StationRole.PILOT)
            rig.socket.reply(assigned); rig.socket.reply(state); runCurrent()
            val roundId = assigned.payload.round_id
            val command = async { rig.repo.performAction(roundId, PlayerAction.Evade) }; runCurrent()
            val request = rig.socket.sent.last() as ClientMessage.Action
            rig.socket.reply(ServerMessage.ActionRejected(1, request.request_id, 8,
                ActionRejectedPayload("cooldown", "safe", 99, roundId)))
            runCurrent(); assertEquals(ConnectionStatus.PROTOCOL_ERROR, rig.repo.connectionStatus.value)
            assertTrue(command.await() is CommandResult.Uncertain)
            assertNull(rig.repo.session.value.roleState)
        } finally { rig.repo.closeAndJoin() }
    }

    @Test fun terminalEventRequiresSnapshotAndReturnToLobbyRetiresPrivateRound()=runTest {
        val rig=Rig(this)
        try {
            rig.admit()
            val (assigned,old)=privateFixture(StationRole.PILOT)
            val running=old.copy(payload=old.payload.copy(public=old.payload.public.copy(stage="running"),
                briefing=BriefingStatus(true,emptyList(),0,true,false)))
            rig.socket.reply(assigned);rig.socket.reply(running);runCurrent()
            val result=RoundResult("victory","survived",60000,0,2,1,listOf(ResultPlayer(PLAYER,"Crew"),
                ResultPlayer("00000000-0000-0000-0000-000000000002","Crew")))
            rig.socket.reply(ServerMessage.GameOver(1,null,8,GameOverPayload(assigned.payload.round_id,result)));runCurrent()
            assertNull(rig.repo.session.value.roleState!!.public.result)
            val terminal=running.copy(room_revision=8,payload=running.payload.copy(public=running.payload.public.copy(
                stage="finished",tick_index=600,remaining_ms=0,result=result)))
            rig.socket.reply(terminal);runCurrent()
            assertEquals(result,rig.repo.session.value.roleState!!.public.result)
            val command=async { rig.repo.returnToLobby() };runCurrent()
            val request=rig.socket.sent.last() as ClientMessage.ReturnToLobby
            rig.socket.reply(ServerMessage.Ack(1,request.request_id,9,AckPayload("return_to_lobby")))
            rig.socket.reply(rig.lobby(9));runCurrent()
            assertTrue(command.await() is CommandResult.Accepted)
            assertNull(rig.repo.session.value.roleState);assertNull(rig.repo.session.value.assigned)
            assertNull(rig.repo.session.value.publicRound);assertNull(rig.repo.session.value.emergencyEvent)
            rig.socket.reply(assigned.copy(room_revision=9));rig.socket.reply(terminal.copy(room_revision=9));runCurrent()
            assertNull(rig.repo.session.value.roleState);assertNull(rig.repo.session.value.assigned)
        } finally { rig.repo.closeAndJoin() }
    }

    @Test fun rematchClearsOldResultBeforeAssignmentAndStartsFreshActionSequence()=runTest {
        val rig=Rig(this)
        try {
            rig.admit()
            val (assigned,old)=privateFixture(StationRole.PILOT)
            val running=old.copy(payload=old.payload.copy(public=old.payload.public.copy(stage="running"),
                briefing=BriefingStatus(true,emptyList(),0,true,false)))
            rig.socket.reply(assigned);rig.socket.reply(running);runCurrent()
            val action=async { rig.repo.performAction(assigned.payload.round_id,PlayerAction.Evade) };runCurrent()
            val first=rig.socket.sent.last() as ClientMessage.Action
            rig.socket.reply(ServerMessage.Ack(1,first.request_id,8,AckPayload("player_action",1,0)));runCurrent();action.await()
            rig.socket.reply(rig.lobby(8).copy(payload=rig.lobby().payload.copy(stage="finished")));runCurrent()
            val again=async { rig.repo.playAgain() };runCurrent()
            val request=rig.socket.sent.last() as ClientMessage.PlayAgain
            rig.socket.reply(ServerMessage.Ack(1,request.request_id,9,AckPayload("play_again")))
            rig.socket.reply(rig.lobby(9).copy(payload=rig.lobby().payload.copy(stage="briefing")));runCurrent()
            assertTrue(again.await() is CommandResult.Accepted)
            assertNull(rig.repo.session.value.roleState);assertNull(rig.repo.session.value.assigned)
            val newId="00000000-0000-0000-0000-000000000100"
            rig.socket.reply(assigned.copy(room_revision=9,payload=assigned.payload.copy(round_id=newId)))
            rig.socket.reply(running.copy(room_revision=9,payload=running.payload.copy(public=running.payload.public.copy(round_id=newId))))
            runCurrent()
            val nextAction=async { rig.repo.performAction(newId,PlayerAction.Evade) };runCurrent()
            val second=rig.socket.sent.last() as ClientMessage.Action
            assertEquals(1L,second.payload.client_action_seq)
            rig.socket.reply(ServerMessage.Ack(1,second.request_id,10,AckPayload("player_action",1,0)));runCurrent()
            assertTrue(nextAction.await() is CommandResult.Accepted)
        } finally { rig.repo.closeAndJoin() }
    }

    @Test fun privateSnapshotMismatchIsFatalAndNeverPublishedToSession() = runTest {
        val rig = Rig(this)
        try {
            rig.admit()
            val (assigned, state) = privateFixture(StationRole.PILOT)
            rig.socket.reply(assigned); rig.socket.reply(state); runCurrent()
            assertEquals(setOf(StationRole.PILOT), rig.repo.session.value.roleState!!.stations.roles().toSet())
            val foreign = privateFixture(StationRole.ENGINEER).second
            rig.socket.reply(foreign.copy(room_revision = 8)); runCurrent()
            assertEquals(ConnectionStatus.PROTOCOL_ERROR, rig.repo.connectionStatus.value)
            assertNull(rig.repo.session.value.roleState); assertNull(rig.repo.session.value.assigned)
            assertFalse(rig.repo.session.value.toString().contains("temperature"))
        } finally { rig.repo.closeAndJoin() }
    }

    @Test fun briefingRecoveryRequiresFreshCorrelatedPrivateViewAndDoesNotResendAck() = runTest {
        val rig = Rig(this)
        try {
            rig.admit()
            val (assigned, state) = privateFixture(StationRole.PILOT)
            rig.socket.reply(assigned); rig.socket.reply(state); runCurrent()
            val request = async { rig.repo.acknowledgeBriefing(assigned.payload.round_id) }; runCurrent()
            assertTrue(rig.socket.sent.last() is ClientMessage.Briefing)
            rig.socket.fail(); runCurrent()
            assertTrue(request.await() is CommandResult.Uncertain)
            assertNull(rig.repo.session.value.assigned); assertNull(rig.repo.session.value.roleState)
            advanceTimeBy(1_000); runCurrent(); rig.socket.open(); runCurrent()
            val resume = rig.socket.sent.single() as ClientMessage.Resume
            rig.socket.reply(ServerMessage.SessionAccepted(1, resume.request_id, 8, SessionPayload("ABCD23", "player", PLAYER, TOKEN)))
            runCurrent()
            val fresh = rig.socket.sent.last() as ClientMessage.State
            rig.socket.reply(rig.lobby(8).copy(payload = rig.lobby().payload.copy(stage = "briefing")))
            rig.socket.reply(assigned.copy(room_revision = 8)); rig.socket.reply(state.copy(room_revision = 8)); runCurrent()
            assertEquals(ConnectionStatus.RECONNECTING, rig.repo.connectionStatus.value)
            rig.socket.reply(state.copy(reply_to = fresh.request_id, room_revision = 8)); runCurrent()
            assertEquals(ConnectionStatus.CONNECTED, rig.repo.connectionStatus.value)
            assertNotNull(rig.repo.session.value.roleState)
            assertTrue(rig.socket.sent.none { it is ClientMessage.Briefing })
        } finally { rig.repo.closeAndJoin() }
    }

    @Test
    fun correlationAndEqualRevisionDistinctMessagesPreserveSessionAndLobby() = runTest {
        val rig = Rig(this)
        try {
            rig.admit()
            assertEquals(SessionIdentity("ABCD23", PLAYER), rig.repo.session.value.identity)
            val ready = async { rig.repo.setReady(true) }; runCurrent()
            val request = rig.socket.sent.last() as ClientMessage.Ready
            rig.socket.reply(ServerMessage.Ack(1, "unrelated", 2, AckPayload("player_ready")))
            runCurrent(); assertFalse(ready.isCompleted)
            rig.socket.reply(ServerMessage.Ack(1, request.request_id, 2, AckPayload("player_ready")))
            rig.socket.reply(rig.lobby(2, ready = true)); runCurrent()
            assertTrue(ready.await() is CommandResult.Accepted)
            assertTrue(rig.repo.session.value.lobby!!.players.single().ready)
            rig.socket.reply(rig.lobby(1)); runCurrent()
            assertTrue(rig.repo.session.value.lobby!!.players.single().ready)
            assertFalse(rig.repo.session.value.toString().contains(TOKEN))
        } finally { rig.repo.closeAndJoin() }
    }

    @Test
    fun fiveSecondAdmissionTimeoutIsUncertainAndNeverRetriesCreate() = runTest {
        val rig = Rig(this)
        try {
            val result = async { rig.repo.create("Crew") }; runCurrent()
            rig.socket.open(); runCurrent()
            advanceTimeBy(4_999); runCurrent(); assertFalse(result.isCompleted)
            advanceTimeBy(1); runCurrent()
            assertTrue(result.await() is CommandResult.Uncertain)
            assertEquals(ConnectionProblem.COMMAND_UNCERTAIN, rig.repo.connection.value.problem)
            advanceTimeBy(30_000); runCurrent()
            assertEquals(1, rig.source.sockets.size)
            assertEquals(1, rig.socket.sent.count { it is ClientMessage.Create })
        } finally { rig.repo.closeAndJoin() }
    }

    @Test
    fun lossClearsViewsResumesWithCredentialAndRequiresFreshCorrelatedSnapshotWithoutActionReplay() = runTest {
        val rig = Rig(this)
        try {
            rig.admit()
            val action = async { rig.repo.submitAction(ROUND, 1, PlayerAction.Coolant) }; runCurrent()
            val old = rig.socket
            old.fail(); runCurrent()
            assertTrue(action.await() is CommandResult.Uncertain)
            assertNull(rig.repo.session.value.lobby)
            assertEquals(ConnectionStatus.RECONNECTING, rig.repo.connectionStatus.value)
            advanceTimeBy(1_000); runCurrent()
            rig.socket.open(); runCurrent()
            val resume = rig.socket.sent.single() as ClientMessage.Resume
            assertEquals(TOKEN, resume.payload.resume_token)
            rig.socket.reply(ServerMessage.SessionAccepted(1, resume.request_id, 2, SessionPayload("ABCD23", "player", PLAYER, TOKEN)))
            rig.socket.reply(rig.lobby(2)); runCurrent()
            assertEquals(ConnectionStatus.RECONNECTING, rig.repo.connectionStatus.value)
            val fresh = rig.socket.sent.last() as ClientMessage.State
            rig.socket.reply(rig.lobby(2, fresh.request_id)); runCurrent()
            assertEquals(ConnectionStatus.CONNECTED, rig.repo.connectionStatus.value)
            assertNotNull(rig.repo.session.value.lobby)
            assertEquals(1, rig.source.sockets.flatMap { it.sent }.count { it is ClientMessage.Action })
            assertEquals(1, rig.source.sockets.flatMap { it.sent }.count { it is ClientMessage.Create })
            assertTrue(old.cancelled)
        } finally { rig.repo.closeAndJoin() }
    }

    @Test
    fun retryDelaysAreOneTwoFourEightThenStopAndExpireWithinGrace() = runTest {
        val rig = Rig(this)
        try {
            rig.admit(); rig.socket.fail(); runCurrent()
            for ((index, wait) in listOf(1_000L, 2_000L, 4_000L, 8_000L).withIndex()) {
                advanceTimeBy(wait - 1); runCurrent(); assertEquals(index + 1, rig.source.sockets.size)
                advanceTimeBy(1); runCurrent(); assertEquals(index + 2, rig.source.sockets.size)
                rig.socket.fail(); runCurrent()
            }
            assertEquals(listOf(0L, 1_000L, 3_000L, 7_000L, 15_000L), rig.source.times)
            assertEquals(ConnectionProblem.RECONNECT_EXHAUSTED, rig.repo.connection.value.problem)
            advanceTimeBy(15_000); runCurrent()
            assertEquals(ConnectionStatus.SESSION_EXPIRED, rig.repo.connectionStatus.value)
            assertEquals(5, rig.source.sockets.size)
        } finally { rig.repo.closeAndJoin() }
    }

    @Test
    fun hangingHandshakesCannotExtendAbsoluteRecoveryDeadline() = runTest {
        val rig = Rig(this)
        try {
            rig.admit(); rig.socket.fail(); runCurrent()
            advanceTimeBy(30_000); runCurrent()
            assertEquals(listOf(0L, 1_000L, 8_000L, 17_000L), rig.source.times)
            assertEquals(ConnectionStatus.SESSION_EXPIRED, rig.repo.connectionStatus.value)
            assertTrue(rig.source.sockets.all { it.cancelled })
        } finally { rig.repo.closeAndJoin() }
    }

    @Test
    fun explicitLeaveClearsCredentialEvenIfAckIsLostAndDoesNotResume() = runTest {
        val rig = Rig(this)
        try {
            rig.admit()
            val leaving = async { rig.repo.leave() }; runCurrent()
            assertTrue(rig.socket.sent.last() is ClientMessage.Leave)
            assertNull(rig.repo.session.value.identity)
            rig.socket.fail(); runCurrent()
            assertTrue(leaving.await() is CommandResult.Uncertain)
            advanceTimeBy(30_000); runCurrent(); assertEquals(1, rig.source.sockets.size)
            val reconnect = async { rig.repo.connect() }; runCurrent()
            rig.socket.open(); runCurrent(); assertTrue(reconnect.await() is CommandResult.Accepted)
            assertTrue(rig.socket.sent.none { it is ClientMessage.Resume })
        } finally { rig.repo.closeAndJoin() }
    }

    @Test
    fun sessionExpiredClearsIdentityAndCredentialWithoutRetry() = runTest {
        val rig = Rig(this)
        try {
            rig.admit()
            rig.socket.reply(ServerMessage.Error(1, null, null, ErrorPayload("session_expired", TOKEN, false)))
            runCurrent()
            assertEquals(ConnectionStatus.SESSION_EXPIRED, rig.repo.connectionStatus.value)
            assertNull(rig.repo.session.value.identity)
            assertFalse(rig.repo.connection.value.toString().contains(TOKEN))
            advanceTimeBy(30_000); runCurrent(); assertEquals(1, rig.source.sockets.size)
            val reconnect = async { rig.repo.connect() }; runCurrent(); rig.socket.open(); runCurrent()
            assertTrue(reconnect.await() is CommandResult.Accepted)
            assertTrue(rig.socket.sent.isEmpty())
        } finally { rig.repo.closeAndJoin() }
    }

    @Test
    fun unknownKindRequestsFullStateWhileMalformedVersionIsDistinctFatalProtocolFeedback() = runTest {
        val rig = Rig(this)
        try {
            rig.admit()
            rig.socket.raw("""{"version":1,"type":"UNKNOWN_SECRET_SENTINEL","reply_to":null,"room_revision":1,"payload":{}}""")
            runCurrent()
            assertEquals(ConnectionStatus.PROTOCOL_ERROR, rig.repo.connectionStatus.value)
            assertNull(rig.repo.session.value.lobby)
            val request = rig.socket.sent.last() as ClientMessage.State
            rig.socket.reply(rig.lobby(1, request.request_id)); runCurrent()
            assertEquals(ConnectionStatus.CONNECTED, rig.repo.connectionStatus.value)
            rig.socket.raw("""{"version":2,"type":"pong"}"""); runCurrent()
            assertEquals(ConnectionProblem.UNSUPPORTED_VERSION, rig.repo.connection.value.problem)
            assertTrue(rig.socket.cancelled)
            assertFalse(rig.repo.connection.value.toString().contains("SENTINEL"))
        } finally { rig.repo.closeAndJoin() }
    }

    @Test
    fun pendingRequestsAreBoundedAndNeverQueueWhileDisconnected() = runTest {
        val rig = Rig(this)
        try {
            assertTrue(rig.repo.setReady(true) is CommandResult.NotSent)
            rig.admit()
            val requests = (1..33).map { async { rig.repo.setReady(true) } }
            runCurrent()
            assertEquals(32, rig.socket.sent.count { it is ClientMessage.Ready })
            assertTrue(requests.last().await() is CommandResult.NotSent)
            rig.repo.disconnect(); runCurrent()
            assertTrue(requests.take(32).all { it.await() is CommandResult.Uncertain })
        } finally { rig.repo.closeAndJoin() }
    }

    @Test
    fun changingEndpointNeverSendsCredentialElsewhere() = runTest {
        val rig = Rig(this)
        try {
            rig.admit()
            val old = rig.socket
            old.fail(); runCurrent(); advanceTimeBy(1_000); runCurrent()
            rig.endpoint = Endpoint.parse("wss://other.example/ws")
            rig.socket.fail(); runCurrent(); advanceTimeBy(2_000); runCurrent()
            rig.socket.open(); runCurrent()
            assertTrue(rig.socket.sent.none { it is ClientMessage.Resume })
            assertNull(rig.repo.session.value.identity)
            assertTrue(old.cancelled)
        } finally { rig.repo.closeAndJoin() }
    }

    @Test
    fun queuedObsoleteGenerationCannotExpireReplacementOrOverwriteSnapshot() = runTest {
        val rig = Rig(this)
        try {
            rig.admit()
            val old = rig.socket
            old.events.trySend(SocketEvent.Closed(1001))
            old.reply(ServerMessage.Error(1, null, null, ErrorPayload("session_expired", TOKEN, false)))
            old.reply(rig.lobby(999, ready = true))
            runCurrent()
            assertEquals(ConnectionStatus.RECONNECTING, rig.repo.connectionStatus.value)
            assertNull(rig.repo.session.value.lobby)
            advanceTimeBy(1_000); runCurrent(); rig.socket.open(); runCurrent()
            val resume = rig.socket.sent.single() as ClientMessage.Resume
            rig.socket.reply(ServerMessage.SessionAccepted(1, resume.request_id, 2, SessionPayload("ABCD23", "player", PLAYER, TOKEN)))
            runCurrent()
            val state = rig.socket.sent.last() as ClientMessage.State
            rig.socket.reply(rig.lobby(2, state.request_id)); runCurrent()
            assertEquals(ConnectionStatus.CONNECTED, rig.repo.connectionStatus.value)
            assertFalse(rig.repo.session.value.lobby!!.players.single().ready)
            assertTrue(old.cancelled)
        } finally { rig.repo.closeAndJoin() }
    }

    @Test
    fun blockedTransportDoesNotSendOrReplayAndDuplicateConnectDoesNotOpenAnotherSocket() = runTest {
        val rig = Rig(this)
        try {
            rig.admit()
            assertTrue(rig.repo.connect() is CommandResult.Accepted)
            assertEquals(1, rig.source.sockets.size)
            rig.socket.acceptsSends = false
            val result = rig.repo.setReady(true)
            assertEquals(CommandResult.NotSent(ConnectionProblem.BACKPRESSURE), result)
            runCurrent()
            assertEquals(ConnectionStatus.RECONNECTING, rig.repo.connectionStatus.value)
            assertTrue(rig.socket.sent.none { it is ClientMessage.Ready })
        } finally { rig.repo.closeAndJoin() }
    }

    @Test
    fun heartbeatTimeoutClearsViewsAndOwnerCancellationClosesEverySocket() = runTest {
        val rig = Rig(this)
        rig.admit()
        advanceTimeBy(10_000); runCurrent()
        assertTrue(rig.socket.sent.last() is ClientMessage.Ping)
        advanceTimeBy(5_000); runCurrent()
        assertEquals(ConnectionProblem.HEARTBEAT_TIMEOUT, rig.repo.connection.value.problem)
        assertNull(rig.repo.session.value.lobby)
        rig.repo.closeAndJoin()
        assertTrue(rig.source.closed)
        assertTrue(rig.source.sockets.all { it.cancelled })
        assertTrue(rig.repo.ping() is CommandResult.NotSent)
    }

    @Test
    fun revisionGateKeepsKindsSeparateAndRejectsRetiredRoundEvenWithHigherRevision() {
        val gate = RevisionGate()
        assertTrue(gate.accept("lobby_state", "ABCD23", null, 2))
        assertTrue(gate.accept("public_state", "ABCD23", ROUND, 2))
        assertFalse(gate.accept("lobby_state", "ABCD23", null, 1))
        assertTrue(gate.accept("public_state", "ABCD23", "new-round", 3))
        assertFalse(gate.accept("public_state", "ABCD23", ROUND, 99))
        assertFalse(gate.accept("public_state", "ABCD23", "unseen-stale-round", 2))
        assertFalse(gate.accept("another-kind", "ABCD23", null, 2))
        assertTrue(gate.accept("lobby_state", "ABCD23", null, 3))
    }
}
