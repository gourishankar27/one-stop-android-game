package com.onejob.game.data.network

import com.onejob.game.data.protocol.ProtocolCodec
import kotlinx.coroutines.channels.Channel
import kotlinx.coroutines.channels.ReceiveChannel
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.Response
import okhttp3.WebSocket
import okhttp3.WebSocketListener
import okio.ByteString
import java.io.Closeable
import java.util.concurrent.TimeUnit

sealed interface SocketEvent {
    data object Open : SocketEvent
    class Text(val text: String) : SocketEvent { override fun toString() = "Text(redacted)" }
    data object Binary : SocketEvent
    data class Closed(val code: Int) : SocketEvent
}

enum class TransportProblem { NETWORK, BACKPRESSURE, OVERSIZE }
class TransportFailure(val problem: TransportProblem) : Exception(problem.name)

interface SocketSession {
    val events: ReceiveChannel<SocketEvent>
    fun send(text: String): Boolean
    fun close(code: Int = 1000)
    fun cancel()
}

interface SocketDataSource : Closeable {
    fun open(endpoint: Endpoint): SocketSession
}

class OkHttpSocketDataSource(
    private val client: OkHttpClient = OkHttpClient.Builder()
        .connectTimeout(5, TimeUnit.SECONDS)
        .readTimeout(0, TimeUnit.SECONDS)
        .retryOnConnectionFailure(false)
        .build(),
) : SocketDataSource {
    private var current: SocketSession? = null

    override fun open(endpoint: Endpoint): SocketSession {
        current?.cancel()
        val inbound = Channel<SocketEvent>(64)
        val session = object : SocketSession {
            lateinit var socket: WebSocket
            override val events = inbound
            override fun send(text: String): Boolean {
                val size = text.toByteArray(Charsets.UTF_8).size
                return size <= ProtocolCodec.MAX_FRAME_BYTES && socket.queueSize() + size <= 64 * 1024 && socket.send(text)
            }
            override fun close(code: Int) { socket.close(code, null) }
            override fun cancel() { socket.cancel(); inbound.close() }
        }
        val listener = object : WebSocketListener() {
            private fun offer(socket: WebSocket, event: SocketEvent) {
                if (!inbound.trySend(event).isSuccess) {
                    inbound.close(TransportFailure(TransportProblem.BACKPRESSURE))
                    socket.cancel()
                }
            }
            override fun onOpen(webSocket: WebSocket, response: Response) { offer(webSocket, SocketEvent.Open) }
            override fun onMessage(webSocket: WebSocket, text: String) {
                if (text.toByteArray(Charsets.UTF_8).size > ProtocolCodec.MAX_FRAME_BYTES) {
                    inbound.close(TransportFailure(TransportProblem.OVERSIZE))
                    webSocket.cancel()
                } else offer(webSocket, SocketEvent.Text(text))
            }
            override fun onMessage(webSocket: WebSocket, bytes: ByteString) { offer(webSocket, SocketEvent.Binary) }
            override fun onClosing(webSocket: WebSocket, code: Int, reason: String) { webSocket.close(code, null) }
            override fun onClosed(webSocket: WebSocket, code: Int, reason: String) {
                offer(webSocket, SocketEvent.Closed(code))
                inbound.close()
            }
            override fun onFailure(webSocket: WebSocket, t: Throwable, response: Response?) {
                // Throwable/HTTP content may contain endpoint/frame data; expose only a safe category.
                inbound.close(TransportFailure(TransportProblem.NETWORK))
            }
        }
        session.socket = client.newWebSocket(Request.Builder().url(endpoint.address).build(), listener)
        current = session
        return session
    }

    override fun close() {
        current?.cancel()
        current = null
        client.connectionPool.evictAll()
        client.dispatcher.executorService.shutdown()
    }
}
