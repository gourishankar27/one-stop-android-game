package com.onejob.game.data

import com.onejob.game.data.protocol.*
import kotlinx.serialization.json.*
import org.junit.Assert.*
import org.junit.Test

class RoleCodecTest {
    private val codec = ProtocolCodec()
    private val fixtures = codec.json.parseToJsonElement(javaClass.classLoader!!.getResourceAsStream("phase08.json")!!.bufferedReader().use { it.readText() }).jsonArray

    @Test fun privateViewsAndInstructionsAreRedactedInDiagnostics() {
        for (case in fixtures) {
            val value = case.jsonObject.getValue("response")
            val message = (codec.decode(value.toString()) as DecodedFrame.Message).message
            if (message is ServerMessage.RoleState) {
                assertFalse(message.toString().contains("temperature"))
                assertFalse(message.toString().contains("available_power"))
            }
            for (event in case.jsonObject["events"]?.jsonArray.orEmpty()) {
                val assigned = (codec.decode(event.toString()) as DecodedFrame.Message).message as ServerMessage.RoleAssigned
                assertFalse(assigned.toString().contains("steps"))
                assertFalse(assigned.toString().contains("enough output"))
            }
        }
    }

    @Test fun malformedOrUnownedStationShapesAndCoercedBriefingFieldsAreRejected() {
        val original = fixtures.first().jsonObject.getValue("response").jsonObject
        val payload = original.getValue("payload").jsonObject
        fun changedPayload(value: JsonObject) = JsonObject(original + ("payload" to value)).toString()
        val stations = payload.getValue("stations").jsonObject
        val unknown = JsonObject(stations + ("foreign" to JsonObject(emptyMap())))
        assertEquals(DecodedFrame.Invalid(ProtocolIssue.MALFORMED), codec.decode(changedPayload(JsonObject(payload + ("stations" to unknown)))))
        val status = payload.getValue("briefing").jsonObject
        for ((key, value) in listOf("acknowledged" to JsonPrimitive("false"), "remaining_ms" to JsonPrimitive(-1))) {
            val modified = JsonObject(status + (key to value))
            assertEquals(DecodedFrame.Invalid(ProtocolIssue.MALFORMED), codec.decode(changedPayload(JsonObject(payload + ("briefing" to modified)))))
        }
        val event = fixtures.first().jsonObject.getValue("events").jsonArray.first().jsonObject
        val instructions = event.getValue("payload").jsonObject
        val modified = JsonObject(instructions + ("roles" to JsonArray(listOf(JsonPrimitive("pilot"), JsonPrimitive("engineer")))))
        assertEquals(DecodedFrame.Invalid(ProtocolIssue.MALFORMED), codec.decode(JsonObject(event + ("payload" to modified)).toString()))
    }
}
