package com.onejob.game.data.repository

import com.onejob.game.data.ConnectionStatus
import com.onejob.game.data.GameRepository
import com.onejob.game.data.network.Endpoint
import com.onejob.game.data.network.EndpointProvider
import com.onejob.game.data.network.EndpointResult
import com.onejob.game.data.network.SocketDataSource
import com.onejob.game.data.network.SocketEvent
import com.onejob.game.data.network.SocketSession
import com.onejob.game.data.network.TransportFailure
import com.onejob.game.data.network.TransportProblem
import com.onejob.game.data.protocol.*
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.channels.Channel
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.asSharedFlow
import kotlinx.coroutines.channels.BufferOverflow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import java.util.Locale
import java.util.UUID

/** All mutable session/request state belongs to this coroutine owner, never a socket callback. */
class SocketGameRepository(
    private val endpointProvider: EndpointProvider,
    private val source: SocketDataSource,
    parentScope: CoroutineScope,
    private val now: () -> Long = { System.nanoTime() / 1_000_000 },
    private val newId: () -> String = { UUID.randomUUID().toString() },
    sessionStorage: SessionStorage? = null,
) : GameRepository {
    private enum class Purpose { PUBLIC, HEARTBEAT, RESUME, SYNC, LEAVE }
    private sealed interface Event {
        class Connect(val result: CompletableDeferred<CommandResult>) : Event
        class Request(val message: ClientMessage, val result: CompletableDeferred<CommandResult>, val automaticSequence: Boolean = false) : Event
        class Leave(val result: CompletableDeferred<CommandResult>) : Event
        class Disconnect(val result: CompletableDeferred<CommandResult>) : Event
        data class Incoming(val generation: Long, val event: SocketEvent) : Event
        data class Lost(val generation: Long, val problem: TransportProblem) : Event
        data class OpenTimeout(val generation: Long) : Event
        data class Timeout(val generation: Long, val id: String) : Event
        data class Heartbeat(val generation: Long) : Event
        data class Retry(val epoch: Long) : Event
        data class RecoveryExpired(val epoch: Long) : Event
        data class CancelRequest(val id: String) : Event
        data class Foreground(val value: Boolean) : Event
    }
    private class Pending(
        val operation: Operation, val purpose: Purpose, val timer: Job,
        val result: CompletableDeferred<CommandResult>?, val nonce: String? = null,
        val actionSequence: Long? = null,
        val actionRound: String? = null,
    )

    private val owner = SupervisorJob(parentScope.coroutineContext[Job])
    private val scope = CoroutineScope(parentScope.coroutineContext + owner)
    private val events = Channel<Event>(64)
    private val codec = ProtocolCodec()
    private val credentials = MemoryCredentialStore(sessionStorage)
    private val restored = credentials.restore((endpointProvider.current() as? EndpointResult.Ready)?.endpoint)
    private val revisions = RevisionGate()
    private val pending = mutableMapOf<String, Pending>()
    private val _connection = MutableStateFlow(ConnectionState(
        if (!restored) ConnectionStatus.UNAVAILABLE else if (credentials.value != null) ConnectionStatus.RECONNECTING else ConnectionStatus.DISCONNECTED,
        if (!restored) ConnectionProblem.STORAGE else null,
    ))
    private val _status = MutableStateFlow(_connection.value.status)
    private val _session = MutableStateFlow(SessionState())
    private val _actionReceipts = MutableSharedFlow<ActionReceipt>(extraBufferCapacity = 16, onBufferOverflow = BufferOverflow.DROP_OLDEST)
    override val actionReceipts = _actionReceipts.asSharedFlow()
    override val connection = _connection.asStateFlow()
    override val connectionStatus = _status.asStateFlow()
    override val session = _session.asStateFlow()
    private var generation = 0L
    private var endpoint: Endpoint? = null
    private var socket: SocketSession? = null
    private var opened = false
    private var reader: Job? = null
    private var openTimer: Job? = null
    private var heartbeat: Job? = null
    private var retry: Job? = null
    private var recoveryTimer: Job? = null
    private var recoveryDeadline: Long? = null
    private var recoveryEpoch = 0L
    private var retryAttempt = 0
    private var syncId: String? = null
    private var connectReply: CompletableDeferred<CommandResult>? = null
    private var actionRound: String? = null
    private var actionSequence = 0L
    private var storageFailed = !restored
    private val visibility = MutableStateFlow(true)
    private var foreground = false

    private val worker = scope.launch {
        scope.launch { visibility.collect { events.send(Event.Foreground(it)) } }
        try {
            for (event in events) {
                when (event) {
                    is Event.Connect -> onConnect(event.result)
                    is Event.Request -> onRequest(event.message, event.result, event.automaticSequence)
                    is Event.Leave -> onLeave(event.result)
                    is Event.Disconnect -> {
                        val cleared = resetMembership()
                        stopTransport()
                        failPending()
                        state(ConnectionStatus.DISCONNECTED)
                        event.result.complete(if (cleared) CommandResult.LeftLocally else CommandResult.NotSent(ConnectionProblem.STORAGE))
                    }
                    is Event.Incoming -> if (event.generation == generation) incoming(event.event)
                    is Event.Lost -> if (event.generation == generation) {
                        if (event.problem == TransportProblem.OVERSIZE) protocolFailure(ProtocolIssue.OVERSIZE)
                        else lost(if (event.problem == TransportProblem.BACKPRESSURE) ConnectionProblem.BACKPRESSURE else ConnectionProblem.NETWORK)
                    }
                    is Event.OpenTimeout -> if (event.generation == generation && !opened) lost(ConnectionProblem.NETWORK)
                    is Event.Timeout -> if (event.generation == generation) timedOut(event.id)
                    is Event.Heartbeat -> if (event.generation == generation && opened && visibility.value) {
                        send(ClientMessage.Ping(newId(), NoncePayload(newId())), Purpose.HEARTBEAT)
                    }
                    is Event.Retry -> if (event.epoch == recoveryEpoch && recoveryDeadline != null && visibility.value && socket == null) {
                        if (now() >= recoveryDeadline!!) expire() else openSocket()
                    }
                    is Event.RecoveryExpired -> if (event.epoch == recoveryEpoch && recoveryDeadline != null) expire()
                    is Event.CancelRequest -> pending.remove(event.id)?.timer?.cancel()
                    is Event.Foreground -> onForeground(event.value)
                }
            }
        } finally {
            stopTransport()
            failPending()
            resetMembership(preserveDisk = true)
            state(ConnectionStatus.DISCONNECTED)
            source.close()
            events.close()
            while (true) {
                val abandoned = events.tryReceive().getOrNull() ?: break
                val result = when (abandoned) {
                    is Event.Connect -> abandoned.result
                    is Event.Request -> abandoned.result
                    is Event.Leave -> abandoned.result
                    is Event.Disconnect -> abandoned.result
                    else -> null
                }
                result?.complete(CommandResult.NotSent(ConnectionProblem.NETWORK))
            }
            owner.cancel()
        }
    }

    override suspend fun connect(): CommandResult = ask { Event.Connect(it) }
    override fun setForeground(foreground: Boolean) { visibility.value = foreground }
    override suspend fun ping(): CommandResult = connectedRequest { ClientMessage.Ping(it, NoncePayload(newId())) }
    override suspend fun create(name: String): CommandResult = connectedRequest { ClientMessage.Create(it, NamePayload(name.trim())) }
    override suspend fun join(roomCode: String, name: String): CommandResult = connectedRequest {
        ClientMessage.Join(it, JoinPayload(roomCode.trim().uppercase(Locale.ROOT), name.trim()))
    }
    override suspend fun joinDisplay(roomCode: String): CommandResult = connectedRequest {
        ClientMessage.JoinDisplay(it, DisplayJoinPayload(roomCode.trim().uppercase(Locale.ROOT)))
    }
    override suspend fun setReady(ready: Boolean): CommandResult = request { ClientMessage.Ready(it, ReadyPayload(ready)) }
    override suspend fun start(): CommandResult = request { ClientMessage.Start(it) }
    override suspend fun playAgain(): CommandResult = request { ClientMessage.PlayAgain(it) }
    override suspend fun returnToLobby(): CommandResult = request { ClientMessage.ReturnToLobby(it) }
    override suspend fun requestState(): CommandResult = request { ClientMessage.State(it) }
    override suspend fun acknowledgeBriefing(roundId: String): CommandResult = request {
        ClientMessage.Briefing(it, RoundPayload(roundId))
    }
    override suspend fun submitAction(roundId: String, sequence: Long, action: PlayerAction): CommandResult = request {
        ClientMessage.Action(it, ActionPayload(roundId, sequence, action))
    }
    override suspend fun performAction(roundId: String, action: PlayerAction): CommandResult = request(automaticSequence = true) {
        ClientMessage.Action(it, ActionPayload(roundId, 1, action))
    }
    override suspend fun leave(): CommandResult = ask { Event.Leave(it) }
    override suspend fun disconnect(): CommandResult = ask { Event.Disconnect(it) }
    override fun close() { owner.cancel() }
    suspend fun closeAndJoin() { close(); worker.join() }

    private suspend fun connectedRequest(factory: (String) -> ClientMessage): CommandResult {
        val connected = connect()
        return if (connected is CommandResult.Accepted) request(factory = factory) else connected
    }
    private suspend fun request(automaticSequence: Boolean = false, factory: (String) -> ClientMessage): CommandResult {
        val message = factory(newId())
        return try {
            ask { Event.Request(message, it, automaticSequence) }
        } catch (cancelled: CancellationException) {
            events.trySend(Event.CancelRequest(message.request_id))
            throw cancelled
        }
    }
    private suspend fun ask(factory: (CompletableDeferred<CommandResult>) -> Event): CommandResult {
        if (!owner.isActive) return CommandResult.NotSent(ConnectionProblem.NETWORK)
        val result = CompletableDeferred<CommandResult>()
        if (!events.trySend(factory(result)).isSuccess) return CommandResult.NotSent(ConnectionProblem.BACKPRESSURE)
        return try { result.await() } catch (cancelled: CancellationException) { result.cancel(); throw cancelled }
    }

    private fun state(status: ConnectionStatus, problem: ConnectionProblem? = null) {
        _connection.value = ConnectionState(status, if (storageFailed) ConnectionProblem.STORAGE else problem, retryAttempt)
        _status.value = status
    }
    private fun onConnect(result: CompletableDeferred<CommandResult>) {
        if (result.isCancelled) return
        if (!visibility.value) { result.complete(CommandResult.NotSent(ConnectionProblem.BACKGROUNDED)); return }
        if (opened && syncId == null && recoveryDeadline == null) {
            result.complete(CommandResult.Accepted("connect", Operation.CONNECT))
            return
        }
        if (socket != null || retry?.isActive == true || connectReply != null) {
            result.complete(CommandResult.NotSent(ConnectionProblem.BACKPRESSURE))
            return
        }
        if (recoveryDeadline != null && now() >= recoveryDeadline!!) {
            expire()
            result.complete(CommandResult.NotSent(ConnectionProblem.NETWORK))
            return
        }
        connectReply = result
        openSocket()
    }

    private fun openSocket() {
        val configuration = endpointProvider.current()
        if (configuration !is EndpointResult.Ready) {
            connectReply?.complete(CommandResult.NotSent(ConnectionProblem.CONFIGURATION))
            connectReply = null
            resetMembership()
            state(ConnectionStatus.UNAVAILABLE, ConnectionProblem.CONFIGURATION)
            return
        }
        val credential = credentials.value
        if (credential != null && !credential.endpoint.sameAs(configuration.endpoint)) resetMembership()
        stopTransport()
        endpoint = configuration.endpoint
        val current = generation
        state(if (credentials.value == null) ConnectionStatus.CONNECTING else ConnectionStatus.RECONNECTING)
        val session = try { source.open(configuration.endpoint) } catch (_: Exception) {
            lost(ConnectionProblem.NETWORK)
            return
        }
        socket = session
        reader = scope.launch {
            try {
                for (event in session.events) events.send(Event.Incoming(current, event))
                events.send(Event.Lost(current, TransportProblem.NETWORK))
            } catch (cancelled: CancellationException) {
                throw cancelled
            } catch (failure: TransportFailure) {
                events.send(Event.Lost(current, failure.problem))
            } catch (_: Exception) {
                events.send(Event.Lost(current, TransportProblem.NETWORK))
            }
        }
        openTimer = scope.launch { delay(5_000); events.send(Event.OpenTimeout(current)) }
    }

    private fun incoming(event: SocketEvent) {
        when (event) {
            SocketEvent.Open -> {
                opened = true
                openTimer?.cancel()
                val current = generation
                heartbeat = scope.launch {
                    while (true) { delay(10_000); events.send(Event.Heartbeat(current)) }
                }
                val credential = credentials.value
                if (credential == null) {
                    state(ConnectionStatus.CONNECTED)
                    connectReply?.complete(CommandResult.Accepted("connect", Operation.CONNECT))
                    connectReply = null
                } else send(ClientMessage.Resume(newId(), ResumePayload(credential.token)), Purpose.RESUME)
            }
            is SocketEvent.Text -> when (val decoded = codec.decode(event.text)) {
                is DecodedFrame.Message -> message(decoded.message)
                is DecodedFrame.Invalid -> protocolFailure(decoded.issue)
            }
            SocketEvent.Binary -> protocolFailure(ProtocolIssue.MALFORMED)
            is SocketEvent.Closed -> when (event.code) {
                1008 -> expire()
                1002 -> protocolFailure(ProtocolIssue.UNSUPPORTED_VERSION)
                1007, 1009 -> protocolFailure(ProtocolIssue.MALFORMED)
                else -> lost(ConnectionProblem.NETWORK)
            }
        }
    }

    private fun onRequest(message: ClientMessage, result: CompletableDeferred<CommandResult>, automaticSequence: Boolean) {
        if (result.isCancelled) return
        if (!visibility.value || !opened || syncId != null || recoveryDeadline != null) {
            result.complete(CommandResult.NotSent(ConnectionProblem.NETWORK))
            return
        }
        if (credentials.value == null && message !is ClientMessage.Ping && message !is ClientMessage.Create && message !is ClientMessage.Join && message !is ClientMessage.JoinDisplay) {
            result.complete(CommandResult.NotSent(ConnectionProblem.ADMISSION_REQUIRED))
            return
        }
        if (credentials.value?.identity?.kind == "display" && message !is ClientMessage.Ping && message !is ClientMessage.State) {
            result.complete(CommandResult.Rejected(message.request_id, RemoteCode.NOT_CONTROLLER)); return
        }
        var outgoing = message
        if (message is ClientMessage.Action && message.payload.round_id == _session.value.roleState?.public?.round_id) {
            if (actionRound != message.payload.round_id) { actionRound = message.payload.round_id; actionSequence = 0 }
            if (automaticSequence) {
                if (actionSequence == Long.MAX_VALUE) {
                    result.complete(CommandResult.Rejected(message.request_id, RemoteCode.STALE_ACTION)); return
                }
                outgoing = message.copy(payload = message.payload.copy(client_action_seq = ++actionSequence))
            } else actionSequence = maxOf(actionSequence, message.payload.client_action_seq)
        } else if (automaticSequence) {
            result.complete(CommandResult.Rejected(message.request_id, RemoteCode.STALE_ROUND)); return
        }
        send(outgoing, Purpose.PUBLIC, result)
    }

    private fun send(message: ClientMessage, purpose: Purpose, result: CompletableDeferred<CommandResult>? = null) {
        if (pending.size >= 32 || message.request_id in pending) {
            result?.complete(CommandResult.NotSent(ConnectionProblem.BACKPRESSURE))
            if (purpose != Purpose.PUBLIC) lost(ConnectionProblem.BACKPRESSURE)
            return
        }
        val text = try { codec.encode(message) } catch (_: Exception) {
            result?.complete(CommandResult.Rejected(message.request_id, RemoteCode.INVALID_MESSAGE))
            return
        }
        val sent = try { socket?.send(text) == true } catch (_: Exception) { false }
        if (!sent) {
            result?.complete(CommandResult.NotSent(ConnectionProblem.BACKPRESSURE))
            lost(ConnectionProblem.BACKPRESSURE)
            return
        }
        val current = generation
        val timer = scope.launch { delay(5_000); events.send(Event.Timeout(current, message.request_id)) }
        pending[message.request_id] = Pending(
            operation(message), purpose, timer, result,
            (message as? ClientMessage.Ping)?.payload?.nonce,
            (message as? ClientMessage.Action)?.payload?.client_action_seq,
            (message as? ClientMessage.Action)?.payload?.round_id,
        )
        if (purpose == Purpose.SYNC) syncId = message.request_id
    }

    private fun message(message: ServerMessage) {
        val request = message.reply_to?.let { pending[it] }
        if (credentials.value?.identity?.kind == "display" &&
            (message is ServerMessage.RoleAssigned || message is ServerMessage.RoleState ||
                message is ServerMessage.EmergencyEvent || message is ServerMessage.GameOver || message is ServerMessage.ActionRejected)) {
            protocolFailure(ProtocolIssue.MALFORMED); return
        }
        when (message) {
            is ServerMessage.SessionAccepted -> {
                if (request == null || request.operation !in setOf(Operation.CREATE, Operation.JOIN, Operation.JOIN_DISPLAY, Operation.RESUME)) return
                val identity = SessionIdentity(message.payload.room_code, message.payload.player_id, message.payload.kind)
                if (request.operation != Operation.RESUME &&
                    ((request.operation == Operation.JOIN_DISPLAY) != (identity.kind == "display"))) {
                    protocolFailure(ProtocolIssue.MALFORMED); return
                }
                if (request.operation == Operation.RESUME && credentials.value?.identity != identity) {
                    protocolFailure(ProtocolIssue.MALFORMED); return
                }
                if (!revisions.accept("session_accepted", identity.roomCode, null, message.room_revision!!)) {
                    protocolFailure(ProtocolIssue.MALFORMED); return
                }
                if (!credentials.save(Credential(endpoint!!, identity, message.payload.resume_token))) {
                    stopTransport(); failPending(); resetMembership()
                    state(ConnectionStatus.UNAVAILABLE, ConnectionProblem.STORAGE); return
                }
                storageFailed = false
                _session.value = SessionState(identity)
                complete(message, request)
                if (request.purpose == Purpose.RESUME) synchronize()
            }
            is ServerMessage.Lobby -> {
                val identity = credentials.value?.identity ?: return
                if (identity.roomCode != message.payload.room_code || (identity.kind == "player" && message.payload.players.none { it.player_id == identity.playerId })) {
                    protocolFailure(ProtocolIssue.MALFORMED); return
                }
                if (request != null && request.operation != Operation.STATE) { protocolFailure(ProtocolIssue.MALFORMED); return }
                if (request != null && message.payload.stage != "lobby") { protocolFailure(ProtocolIssue.MALFORMED); return }
                if (revisions.accept("lobby_state", identity.roomCode, null, message.room_revision!!)) {
                    val previous = _session.value
                    val resetsRound = message.payload.stage == "lobby" ||
                        (message.payload.stage == "briefing" && previous.lobby?.stage in setOf("lobby", "finished", "aborted"))
                    if (resetsRound) {
                        revisions.retireRound()
                        actionRound = null; actionSequence = 0
                        _session.value = previous.copy(lobby = message.payload, publicRound = null,
                            assigned = null, roleState = null, emergencyEvent = null, publicSnapshotReceived = false)
                    } else _session.value = previous.copy(lobby = message.payload)
                }
                if (request != null) {
                    if (request.purpose == Purpose.SYNC && _session.value.lobby == null) {
                        protocolFailure(ProtocolIssue.MALFORMED); return
                    }
                    complete(message, request)
                    if (request.purpose == Purpose.SYNC) recovered()
                }
            }
            is ServerMessage.PublicState -> {
                val identity = credentials.value?.identity ?: return
                if (identity.kind != "display" || (request != null && request.operation != Operation.STATE)) {
                    protocolFailure(ProtocolIssue.MALFORMED); return
                }
                val round = message.payload.public
                if (revisions.accept("public_state", identity.roomCode, round?.round_id, message.room_revision!!)) {
                    if ((_session.value.lobby?.stage == "lobby") != (round == null)) {
                        protocolFailure(ProtocolIssue.MALFORMED); return
                    }
                    _session.value = _session.value.copy(publicRound = round, publicSnapshotReceived = true)
                }
                if (request != null) {
                    if (!_session.value.publicSnapshotReceived || _session.value.lobby == null) {
                        protocolFailure(ProtocolIssue.MALFORMED); return
                    }
                    complete(message, request)
                    if (request.purpose == Purpose.SYNC) recovered()
                }
            }
            is ServerMessage.RoleAssigned -> {
                val identity = credentials.value?.identity ?: return
                val assigned = message.payload
                if (revisions.accept("role_assigned", identity.roomCode, assigned.round_id, message.room_revision!!)) {
                    _session.value = _session.value.copy(assigned = assigned,
                        roleState = _session.value.roleState?.takeIf { it.public.round_id == assigned.round_id },
                        publicRound = _session.value.publicRound?.takeIf { it.round_id == assigned.round_id },
                        emergencyEvent = _session.value.emergencyEvent?.takeIf { it.round_id == assigned.round_id })
                }
            }
            is ServerMessage.RoleState -> {
                val identity = credentials.value?.identity ?: return
                val assigned = _session.value.assigned
                val payload = message.payload
                if (assigned == null || assigned.round_id != payload.public.round_id) {
                    if (request != null) protocolFailure(ProtocolIssue.MALFORMED)
                    return
                }
                if (payload.stations.roles().toSet() != assigned.roles.toSet() ||
                    payload.briefing.acknowledged == (identity.playerId in payload.briefing.waiting_player_ids) ||
                    (request != null && request.operation != Operation.STATE)) {
                    protocolFailure(ProtocolIssue.MALFORMED); return
                }
                if (revisions.accept("role_state", identity.roomCode, payload.public.round_id, message.room_revision!!,
                    allowEqual = request?.operation == Operation.STATE)) {
                    if (actionRound != payload.public.round_id) { actionRound = payload.public.round_id; actionSequence = 0 }
                    actionSequence = maxOf(actionSequence, payload.last_client_action_seq)
                    _session.value = _session.value.copy(roleState = payload, publicRound = payload.public)
                }
                if (request != null) {
                    if (_session.value.roleState == null) { protocolFailure(ProtocolIssue.MALFORMED); return }
                    complete(message, request)
                    if (request.purpose == Purpose.SYNC) recovered()
                }
            }
            is ServerMessage.Pong -> {
                if (request == null) return
                if (request.operation != Operation.PING || request.nonce != message.payload.nonce) { protocolFailure(ProtocolIssue.MALFORMED); return }
                complete(message, request)
            }
            is ServerMessage.EmergencyEvent -> {
                // Keep only the latest shared event. The full server snapshot owns
                // active warnings; an event never infers a local ship or round outcome.
                if (request != null) { protocolFailure(ProtocolIssue.MALFORMED); return }
                val identity = credentials.value?.identity ?: return
                if (_session.value.assigned?.round_id != message.payload.round_id) return
                if (revisions.accept("emergency_event-${message.payload.emergency_id}-${message.payload.status}",
                    identity.roomCode, message.payload.round_id, message.room_revision!!)) {
                    val previous = _session.value.emergencyEvent
                    if (message.payload.status != "started" || previous == null || previous.status == "started") {
                        _session.value = _session.value.copy(emergencyEvent = message.payload)
                    }
                }
            }
            is ServerMessage.GameOver -> {
                // Result navigation requires the complete authoritative role snapshot.
                // This one-shot event cannot populate or alter ship/result state.
                val identity = credentials.value?.identity ?: return
                if (_session.value.assigned?.round_id != message.payload.round_id) return
                revisions.accept("game_over", identity.roomCode, message.payload.round_id, message.room_revision!!)
            }
            is ServerMessage.Ack -> {
                if (request == null) return
                if (message.payload.operation != wireOperation(request.operation) ||
                    (request.operation == Operation.ACTION && (message.payload.client_action_seq != request.actionSequence || message.payload.applied_tick == null))) {
                    protocolFailure(ProtocolIssue.MALFORMED); return
                }
                if (request.operation == Operation.ACTION) {
                    _actionReceipts.tryEmit(ActionReceipt(request.actionRound!!, request.actionSequence!!, true))
                }
                if (request.purpose == Purpose.LEAVE) { stopTransport(); state(ConnectionStatus.DISCONNECTED) }
                complete(message, request)
            }
            is ServerMessage.ActionRejected -> {
                if (request == null) return
                if (request.operation != Operation.ACTION ||
                    request.actionSequence != message.payload.client_action_seq ||
                    request.actionRound != message.payload.round_id) {
                    protocolFailure(ProtocolIssue.MALFORMED); return
                }
                pending.remove(message.reply_to)?.timer?.cancel()
                _actionReceipts.tryEmit(ActionReceipt(request.actionRound!!, request.actionSequence!!, false))
                request.result?.complete(CommandResult.Rejected(message.reply_to!!,
                    RemoteCode.fromWire(message.payload.code)))
            }
            is ServerMessage.Error -> {
                val code = RemoteCode.fromWire(message.payload.code)
                if (request != null) {
                    pending.remove(message.reply_to)?.timer?.cancel()
                }
                when {
                    code == RemoteCode.SESSION_EXPIRED -> expire()
                    code == RemoteCode.NOT_AUTHENTICATED -> {
                        resetMembership(); stopTransport(); failPending()
                        state(ConnectionStatus.UNAVAILABLE, ConnectionProblem.ADMISSION_REQUIRED)
                    }
                    request?.purpose == Purpose.RESUME -> lost(ConnectionProblem.NETWORK)
                    request?.purpose == Purpose.SYNC -> protocolFailure(ProtocolIssue.MALFORMED)
                    request?.purpose == Purpose.LEAVE -> { stopTransport(); state(ConnectionStatus.DISCONNECTED) }
                }
                request?.result?.complete(CommandResult.Rejected(message.reply_to!!, code))
            }
        }
    }

    private fun complete(message: ServerMessage, request: Pending) {
        pending.remove(message.reply_to)?.timer?.cancel()
        val action = (message as? ServerMessage.Ack)?.payload
        request.result?.complete(CommandResult.Accepted(message.reply_to!!, request.operation,
            message.room_revision, action?.client_action_seq, action?.applied_tick))
    }
    private fun synchronize() {
        if (syncId == null && opened) send(ClientMessage.State(newId()), Purpose.SYNC)
    }
    private fun recovered() {
        syncId = null
        recoveryDeadline = null
        recoveryTimer?.cancel()
        retry?.cancel()
        retryAttempt = 0
        state(ConnectionStatus.CONNECTED)
        connectReply?.complete(CommandResult.Accepted("connect", Operation.CONNECT))
        connectReply = null
    }

    private fun timedOut(id: String) {
        val request = pending.remove(id) ?: return
        when {
            request.purpose == Purpose.LEAVE -> { stopTransport(); state(ConnectionStatus.DISCONNECTED, ConnectionProblem.COMMAND_UNCERTAIN) }
            request.purpose == Purpose.HEARTBEAT || request.operation == Operation.PING -> lost(ConnectionProblem.HEARTBEAT_TIMEOUT)
            request.purpose == Purpose.RESUME -> lost(ConnectionProblem.NETWORK)
            request.purpose == Purpose.SYNC -> lost(ConnectionProblem.SNAPSHOT_TIMEOUT)
            request.operation in setOf(Operation.CREATE, Operation.JOIN, Operation.JOIN_DISPLAY) -> {
                stopTransport(); failPending(); state(ConnectionStatus.UNAVAILABLE, ConnectionProblem.COMMAND_UNCERTAIN)
            }
            else -> { state(ConnectionStatus.CONNECTED, ConnectionProblem.COMMAND_UNCERTAIN); synchronize() }
        }
        request.result?.complete(CommandResult.Uncertain(id, request.operation))
    }

    private fun protocolFailure(issue: ProtocolIssue) {
        _session.value = _session.value.copy(lobby = null, publicRound = null, assigned = null, roleState = null, emergencyEvent = null)
        revisions.clear()
        state(ConnectionStatus.PROTOCOL_ERROR, if (issue == ProtocolIssue.UNSUPPORTED_VERSION) ConnectionProblem.UNSUPPORTED_VERSION else ConnectionProblem.PROTOCOL)
        if (issue == ProtocolIssue.UNKNOWN_TYPE && credentials.value != null && syncId == null && opened) {
            synchronize()
        } else {
            stopTransport()
            failPending()
            if (!resetMembership()) state(ConnectionStatus.PROTOCOL_ERROR, ConnectionProblem.STORAGE)
        }
    }
    private fun onLeave(result: CompletableDeferred<CommandResult>) {
        if (result.isCancelled) return
        val cleared = resetMembership()
        failPending()
        if (!cleared) {
            stopTransport(); state(ConnectionStatus.UNAVAILABLE, ConnectionProblem.STORAGE)
            result.complete(CommandResult.NotSent(ConnectionProblem.STORAGE)); return
        }
        if (opened) send(ClientMessage.Leave(newId()), Purpose.LEAVE, result)
        else { stopTransport(); state(ConnectionStatus.DISCONNECTED); result.complete(CommandResult.LeftLocally) }
    }
    private fun lost(problem: ConnectionProblem) {
        stopTransport()
        failPending()
        _session.value = SessionState()
        revisions.clear()
        if (credentials.value == null) { state(ConnectionStatus.UNAVAILABLE, problem); return }
        beginRecovery()
        if (!visibility.value) { state(ConnectionStatus.RECONNECTING, ConnectionProblem.BACKGROUNDED); return }
        scheduleRetry(problem)
    }
    private fun beginRecovery() {
        if (recoveryDeadline == null) {
            recoveryDeadline = now() + 30_000
            recoveryEpoch++
            val epoch = recoveryEpoch
            recoveryTimer = scope.launch { delay(30_000); events.send(Event.RecoveryExpired(epoch)) }
        }
    }
    private fun onForeground(value: Boolean) {
        if (foreground == value) return
        foreground = value
        if (credentials.value == null) {
            if (!value) { stopTransport(); failPending(); state(ConnectionStatus.DISCONNECTED) }
            return
        }
        if (!value) {
            stopTransport(); failPending(); retry?.cancel()
            _session.value = SessionState(); revisions.clear()
            beginRecovery()
            state(ConnectionStatus.RECONNECTING, ConnectionProblem.BACKGROUNDED)
        } else {
            if (recoveryDeadline != null && now() >= recoveryDeadline!!) { expire(); return }
            beginRecovery()
            retry?.cancel()
            if (socket == null) openSocket()
        }
    }
    private fun scheduleRetry(problem: ConnectionProblem) {
        val delays = longArrayOf(1_000, 2_000, 4_000, 8_000)
        if (retryAttempt >= delays.size || now() + delays[retryAttempt] >= recoveryDeadline!!) {
            state(ConnectionStatus.UNAVAILABLE, ConnectionProblem.RECONNECT_EXHAUSTED)
            return
        }
        val wait = delays[retryAttempt++]
        val epoch = recoveryEpoch
        state(ConnectionStatus.RECONNECTING, problem)
        retry = scope.launch { delay(wait); events.send(Event.Retry(epoch)) }
    }
    private fun expire() {
        stopTransport()
        failPending()
        resetMembership()
        state(ConnectionStatus.SESSION_EXPIRED)
    }
    private fun resetMembership(preserveDisk: Boolean = false): Boolean {
        actionRound = null; actionSequence = 0
        val cleared = credentials.clear(preserveDisk)
        if (!preserveDisk) storageFailed = !cleared
        _session.value = SessionState()
        revisions.clear()
        recoveryDeadline = null
        recoveryTimer?.cancel()
        retry?.cancel()
        retryAttempt = 0
        syncId = null
        return cleared
    }
    private fun stopTransport() {
        generation++
        opened = false
        socket?.cancel()
        socket = null
        reader?.cancel(); reader = null
        openTimer?.cancel(); openTimer = null
        heartbeat?.cancel(); heartbeat = null
        syncId = null
    }
    private fun failPending() {
        pending.forEach { (id, request) ->
            request.timer.cancel()
            request.result?.complete(CommandResult.Uncertain(id, request.operation))
        }
        pending.clear()
        connectReply?.complete(CommandResult.NotSent(ConnectionProblem.NETWORK))
        connectReply = null
    }
    private fun operation(message: ClientMessage) = when (message) {
        is ClientMessage.Briefing -> Operation.BRIEFING
        is ClientMessage.Ping -> Operation.PING
        is ClientMessage.Create -> Operation.CREATE
        is ClientMessage.Join -> Operation.JOIN
        is ClientMessage.JoinDisplay -> Operation.JOIN_DISPLAY
        is ClientMessage.Resume -> Operation.RESUME
        is ClientMessage.Ready -> Operation.READY
        is ClientMessage.Start -> Operation.START
        is ClientMessage.PlayAgain -> Operation.PLAY_AGAIN
        is ClientMessage.ReturnToLobby -> Operation.RETURN_TO_LOBBY
        is ClientMessage.State -> Operation.STATE
        is ClientMessage.Leave -> Operation.LEAVE
        is ClientMessage.Action -> Operation.ACTION
    }
    private fun wireOperation(operation: Operation): String = when (operation) {
        Operation.BRIEFING -> "briefing_ready"
        Operation.READY -> "player_ready"
        Operation.LEAVE -> "leave_room"
        Operation.ACTION -> "player_action"
        Operation.START -> "start_game"
        Operation.PLAY_AGAIN -> "play_again"
        Operation.RETURN_TO_LOBBY -> "return_to_lobby"
        else -> ""
    }
}
