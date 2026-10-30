package com.onejob.game.data

import com.onejob.game.data.protocol.*
import kotlinx.serialization.json.*
import org.junit.Assert.*
import org.junit.Test

class ProtocolCodecTest {
    private val codec = ProtocolCodec()

    @Test
    fun sharedPythonFixturesDecodeAndOutgoingMessagesMatchExactly() {
        for (file in listOf("phase03.json", "phase04.json", "phase06.json", "phase08.json", "phase09.json", "phase10.json", "phase11.json")) {
            val text = javaClass.classLoader!!.getResourceAsStream(file)!!.bufferedReader().use { it.readText() }
            for (element in codec.json.parseToJsonElement(text).jsonArray) {
                val request = element.jsonObject.getValue("request")
                val decodedClient = codec.json.decodeFromJsonElement<ClientMessage>(request)
                assertEquals(request, codec.json.parseToJsonElement(codec.encode(decodedClient)))
                val response = element.jsonObject.getValue("response")
                val decoded = codec.decode(response.toString())
                assertTrue(file, decoded is DecodedFrame.Message)
                val reencoder = Json(codec.json) { encodeDefaults = false }
                assertEquals(response, reencoder.encodeToJsonElement<ServerMessage>((decoded as DecodedFrame.Message).message))
                for (event in element.jsonObject["events"]?.jsonArray.orEmpty()) {
                    val decodedEvent = codec.decode(event.toString())
                    assertTrue(decodedEvent is DecodedFrame.Message)
                    assertEquals(event, reencoder.encodeToJsonElement<ServerMessage>((decodedEvent as DecodedFrame.Message).message))
                }
            }
        }
    }

    @Test fun emergencyEventsHaveOnlySharedLabelsAndStrictLifecycle() {
        val valid = """{"version":1,"type":"emergency_event","reply_to":null,"room_revision":10,"payload":{"round_id":"00000000-0000-0000-0000-000000000099","emergency_id":1,"kind":"asteroid","status":"started"}}"""
        val message = (codec.decode(valid) as DecodedFrame.Message).message as ServerMessage.EmergencyEvent
        assertEquals("started", message.payload.status)
        for (invalid in listOf(valid.replace("started","secret"), valid.replace("asteroid","other"),
            valid.replace("\"emergency_id\":1", "\"emergency_id\":0"), valid.replace("\"reply_to\":null","\"reply_to\":\"request\""))) {
            assertTrue(codec.decode(invalid) is DecodedFrame.Invalid)
        }
    }

    @Test
    fun incomingAdditiveFieldsAreIgnoredAtEnvelopeAndPayloadBoundaries() {
        val text = """{"version":1,"type":"pong","reply_to":"p","room_revision":null,"extra":{"future":true},"payload":{"nonce":"hello","future":7}}"""
        assertEquals("hello", ((codec.decode(text) as DecodedFrame.Message).message as ServerMessage.Pong).payload.nonce)
    }

    @Test
    fun unknownKindAndVersionHaveDistinctSafeFailures() {
        assertEquals(DecodedFrame.Invalid(ProtocolIssue.UNKNOWN_TYPE), codec.decode("""{"version":1,"type":"SECRET_SENTINEL","payload":{}}"""))
        assertEquals(DecodedFrame.Invalid(ProtocolIssue.UNSUPPORTED_VERSION), codec.decode("""{"version":2,"type":"pong"}"""))
        assertFalse(codec.decode("{SECRET_SENTINEL").toString().contains("SECRET_SENTINEL"))
    }

    @Test
    fun missingAndCoercedPrimitiveFieldsAreRejected() {
        val base = """{"version":1,"type":"pong","reply_to":"p","room_revision":null,"payload":{"nonce":"hello"}}"""
        for (invalid in listOf(
            base.replace("\"version\":1", "\"version\":\"1\""),
            base.replace("\"version\":1", "\"version\":true"),
            base.replace("\"nonce\":\"hello\"", "\"nonce\":12"),
            base.replace("\"room_revision\":null", "\"room_revision\":\"2\""),
            base.replace("\"room_revision\":null,", ""),
            base.replace("\"reply_to\":\"p\"", "\"reply_to\":12"),
            base.replace("\"room_revision\":null", "\"room_revision\":-1"),
        )) assertEquals(invalid, DecodedFrame.Invalid(ProtocolIssue.MALFORMED), codec.decode(invalid))
    }

    @Test
    fun malformedAndOversizedFramesNeverReturnInputInErrors() {
        assertEquals(DecodedFrame.Invalid(ProtocolIssue.MALFORMED), codec.decode("{SECRET_SENTINEL"))
        assertEquals(DecodedFrame.Invalid(ProtocolIssue.OVERSIZE), codec.decode("é".repeat(8193)))
        assertEquals(DecodedFrame.Invalid(ProtocolIssue.MALFORMED), codec.decode("[]"))
        assertEquals(DecodedFrame.Invalid(ProtocolIssue.MALFORMED), codec.decode("""{"version":1,"version":2}"""))
        assertEquals(DecodedFrame.Invalid(ProtocolIssue.MALFORMED), codec.decode("""{"version":1,"type":"pong","reply_to":"p","room_revision":null,"payload":{"nonce":"hello","\u006eonce":"other"}}"""))
        assertEquals(DecodedFrame.Invalid(ProtocolIssue.MALFORMED), codec.decode("[".repeat(1000) + "]".repeat(1000)))
    }

    @Test
    fun credentialAndErrorDtoStringsAreRedactedAndActionEncodingIsTyped() {
        val token = "TOKEN_SENTINEL"
        assertFalse(ClientMessage.Resume("resume", ResumePayload(token)).toString().contains(token))
        assertFalse(SessionPayload("ABCD23", "player", PLAYER, token).toString().contains(token))
        assertFalse(ErrorPayload(token, token, false).toString().contains(token))
        val action = ClientMessage.Action("action", ActionPayload(ROUND, 1, PlayerAction.Coolant))
        assertEquals("coolant", codec.json.parseToJsonElement(codec.encode(action)).jsonObject["payload"]!!.jsonObject["action"]!!.jsonObject["type"]!!.jsonPrimitive.content)
        assertThrows(IllegalArgumentException::class.java) {
            codec.encode(ClientMessage.Action("action", ActionPayload(ROUND, 0, PlayerAction.Coolant)))
        }
        assertThrows(IllegalArgumentException::class.java) {
            codec.encode(ClientMessage.Action("action", ActionPayload(ROUND, 1, PlayerAction.SetEnginePower(101))))
        }
    }

    companion object {
        const val PLAYER = "00000000-0000-0000-0000-000000000001"
        const val ROUND = "00000000-0000-0000-0000-000000000010"
    }
}
