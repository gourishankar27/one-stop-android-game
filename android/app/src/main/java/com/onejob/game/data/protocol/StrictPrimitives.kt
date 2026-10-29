package com.onejob.game.data.protocol

import kotlinx.serialization.KSerializer
import kotlinx.serialization.SerializationException
import kotlinx.serialization.descriptors.PrimitiveKind
import kotlinx.serialization.descriptors.PrimitiveSerialDescriptor
import kotlinx.serialization.encoding.Decoder
import kotlinx.serialization.encoding.Encoder
import kotlinx.serialization.json.JsonDecoder
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.booleanOrNull
import kotlinx.serialization.json.intOrNull
import kotlinx.serialization.json.longOrNull

private fun primitive(decoder: Decoder): JsonPrimitive =
    (decoder as? JsonDecoder)?.decodeJsonElement() as? JsonPrimitive
        ?: throw SerializationException("Invalid primitive")

object StrictStringSerializer : KSerializer<String> {
    override val descriptor = PrimitiveSerialDescriptor("StrictString", PrimitiveKind.STRING)
    override fun serialize(encoder: Encoder, value: String) = encoder.encodeString(value)
    override fun deserialize(decoder: Decoder): String {
        val value = primitive(decoder)
        if (!value.isString) throw SerializationException("Expected string")
        return value.content
    }
}

object StrictIntSerializer : KSerializer<Int> {
    override val descriptor = PrimitiveSerialDescriptor("StrictInt", PrimitiveKind.INT)
    override fun serialize(encoder: Encoder, value: Int) = encoder.encodeInt(value)
    override fun deserialize(decoder: Decoder): Int {
        val value = primitive(decoder)
        return value.intOrNull?.takeIf { !value.isString }
            ?: throw SerializationException("Expected integer")
    }
}

object StrictLongSerializer : KSerializer<Long> {
    override val descriptor = PrimitiveSerialDescriptor("StrictLong", PrimitiveKind.LONG)
    override fun serialize(encoder: Encoder, value: Long) = encoder.encodeLong(value)
    override fun deserialize(decoder: Decoder): Long {
        val value = primitive(decoder)
        return value.longOrNull?.takeIf { !value.isString }
            ?: throw SerializationException("Expected integer")
    }
}

object StrictBooleanSerializer : KSerializer<Boolean> {
    override val descriptor = PrimitiveSerialDescriptor("StrictBoolean", PrimitiveKind.BOOLEAN)
    override fun serialize(encoder: Encoder, value: Boolean) = encoder.encodeBoolean(value)
    override fun deserialize(decoder: Decoder): Boolean {
        val value = primitive(decoder)
        return value.booleanOrNull?.takeIf { !value.isString }
            ?: throw SerializationException("Expected boolean")
    }
}
