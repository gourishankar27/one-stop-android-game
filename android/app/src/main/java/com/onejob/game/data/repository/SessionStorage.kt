package com.onejob.game.data.repository

import android.content.Context
import android.util.AtomicFile
import java.io.File
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.Json

/** Opaque outside this module. Never UI/saved-state/log data. */
class StoredSession internal constructor(
    internal val endpoint: String, internal val identity: SessionIdentity, internal val token: String,
) {
    internal fun valid(): Boolean = identity.roomCode.matches(Regex("[ABCDEFGHJKLMNPQRSTUVWXYZ23456789]{6}")) &&
        token.length in 1..256 && when (identity.kind) {
            "player" -> identity.playerId?.matches(Regex("[0-9a-fA-F]{8}(-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}")) == true
            "display" -> identity.playerId == null
            else -> false
        }
    override fun toString() = "StoredSession(redacted)"
}

/** Absence is distinct from unreadable storage. Implementations throw on I/O failure. */
interface SessionStorage {
    fun read(): StoredSession?
    fun write(value: StoredSession?)
}

/** UID-private atomic file, excluded from backup and device transfer. */
class AndroidSessionStorage(context: Context) : SessionStorage {
    private val file = AtomicFile(File(context.applicationContext.noBackupFilesDir, "membership_v1.json"))
    private val json = Json { ignoreUnknownKeys = false }
    @Serializable private data class Record(
        val version: Int, val endpoint: String, val room: String, val player: String?, val kind: String, val token: String,
    ) { override fun toString() = "Record(redacted)" }

    override fun read(): StoredSession? {
        if (!file.baseFile.exists() && !File(file.baseFile.path + ".bak").exists()) return null
        val bytes = file.openRead().use { input ->
            if (input.channel.size() > 4096) return invalidRecord()
            input.readBytes()
        }
        val record = try { json.decodeFromString<Record>(bytes.toString(Charsets.UTF_8)) }
            catch (_: IllegalArgumentException) { return invalidRecord() }
        val value = StoredSession(record.endpoint, SessionIdentity(record.room, record.player, record.kind), record.token)
        return if (record.version == 1 && value.valid()) value else invalidRecord()
    }
    private fun invalidRecord(): Nothing {
        write(null)
        error("Saved private session is unusable")
    }

    override fun write(value: StoredSession?) {
        if (value == null) {
            file.delete()
            check(!file.baseFile.exists() && !File(file.baseFile.path + ".bak").exists()) { "Private session removal failed" }
            return
        }
        require(value.valid()) { "Invalid private session" }
        val record = Record(1, value.endpoint, value.identity.roomCode, value.identity.playerId, value.identity.kind, value.token)
        val output = file.startWrite()
        try {
            output.write(json.encodeToString(Record.serializer(), record).toByteArray(Charsets.UTF_8))
            file.finishWrite(output)
        } catch (failure: Exception) { file.failWrite(output); throw failure }
    }
    override fun toString() = "AndroidSessionStorage(redacted)"
}
