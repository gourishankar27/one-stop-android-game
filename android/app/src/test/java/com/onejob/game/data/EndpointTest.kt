package com.onejob.game.data

import com.onejob.game.data.network.Endpoint
import com.onejob.game.data.network.EndpointResult
import org.junit.Assert.*
import org.junit.Test

class EndpointTest {
    @Test
    fun releaseAllowsOnlyCredentialFreeWssAndHasNoDefault() {
        assertEquals(EndpointResult.Missing, Endpoint.parse(""))
        assertTrue(Endpoint.parse("wss://example.test/ws") is EndpointResult.Ready)
        for (address in listOf("ws://10.0.2.2:8000/ws", "wss://user:SECRET@example.test/ws", "wss://example.test/ws?token=SECRET", "wss://example.test/ws#SECRET", "https://example.test/ws", "wss://example.test/other")) {
            assertEquals(EndpointResult.Invalid, Endpoint.parse(address))
        }
    }

    @Test
    fun debugCleartextRequiresExplicitOptInAndPrivateOrLoopbackAddress() {
        for (host in listOf("10.0.2.2", "192.168.1.20", "172.16.0.1", "127.0.0.1", "localhost", "[::1]")) {
            val url = "ws://$host:8000/ws"
            assertEquals(EndpointResult.Invalid, Endpoint.parse(url, debug = true))
            assertTrue(host, Endpoint.parse(url, debug = true, allowCleartext = true) is EndpointResult.Ready)
        }
        for (host in listOf("8.8.8.8", "172.32.0.1", "192.169.0.1", "10.example.test", "999.1.2.3")) {
            assertEquals(EndpointResult.Invalid, Endpoint.parse("ws://$host/ws", true, true))
        }
    }
}
