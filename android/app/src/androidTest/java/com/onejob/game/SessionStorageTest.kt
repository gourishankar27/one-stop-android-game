package com.onejob.game

import android.content.Context
import android.content.ContextWrapper
import androidx.test.platform.app.InstrumentationRegistry
import com.onejob.game.data.repository.*
import java.io.File
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.jsonObject
import org.junit.Assert.*
import org.junit.Test

class SessionStorageTest {
    private fun isolated(check: (AndroidSessionStorage, File) -> Unit) {
        val app = InstrumentationRegistry.getInstrumentation().targetContext
        val directory = File(app.noBackupFilesDir, "resilience-storage-test").apply { mkdirs() }
        val context = object : ContextWrapper(app) {
            override fun getApplicationContext(): Context = this
            override fun getNoBackupFilesDir(): File = directory
        }
        try { check(AndroidSessionStorage(context), File(directory,"membership_v1.json")) }
        finally { directory.deleteRecursively() }
    }
    private fun value(kind: String = "player") = StoredSession("wss://synthetic.invalid/ws",
        SessionIdentity("ABCD23", if(kind=="player") "00000000-0000-0000-0000-000000000001" else null,kind),
        "SYNTHETIC_STORAGE_TOKEN")

    @Test fun atomicPrivateRecordContainsOnlyMinimalCredentialAndClearsAcrossNewOwners() = isolated { storage, file ->
        assertNull(storage.read())
        for(kind in listOf("player","display")) {
            storage.write(value(kind))
            assertEquals(setOf("version","endpoint","room","player","kind","token"),Json.parseToJsonElement(file.readText()).jsonObject.keys)
            val restored=storage.read()!!
            assertEquals(kind,restored.identity.kind)
            assertEquals("SYNTHETIC_STORAGE_TOKEN",restored.token)
            assertFalse(restored.toString().contains("SYNTHETIC"))
            storage.write(null); assertFalse(file.exists()); assertNull(storage.read())
        }
    }
    @Test fun corruptOversizeWrongVersionAndInterruptedWriteCannotRestoreUntrustedData() = isolated { storage, file ->
        for(data in listOf("{", "x".repeat(5000), "{}", "null")) {
            file.writeText(data); assertThrows(IllegalStateException::class.java) { storage.read() }
            assertFalse(file.exists()); assertNull(storage.read())
        }
        storage.write(value()); val valid=file.readText()
        file.writeText(valid.replace("\"version\":1","\"version\":2"))
        assertThrows(IllegalStateException::class.java) { storage.read() }
        file.writeText(valid.replace("ABCD23","invalid"))
        assertThrows(IllegalStateException::class.java) { storage.read() }
        // AtomicFile recovers a previous completed backup, never a partial replacement.
        File(file.path+".bak").writeText(valid); file.writeText("{")
        assertEquals("SYNTHETIC_STORAGE_TOKEN",storage.read()!!.token)
        storage.write(null)
        assertFalse(File(file.path+".bak").exists())
    }
    @Test fun explicitBackupAndDeviceTransferRulesExcludeAllPrivateData() {
        val resources=InstrumentationRegistry.getInstrumentation().targetContext.resources
        for(resource in listOf(R.xml.backup_rules,R.xml.data_extraction_rules)) {
            val parser=resources.getXml(resource)
            val excluded=mutableListOf<String>()
            parser.use {
                while(parser.next()!=org.xmlpull.v1.XmlPullParser.END_DOCUMENT) {
                    if(parser.eventType==org.xmlpull.v1.XmlPullParser.START_TAG && parser.name=="exclude") {
                        assertEquals(".",parser.getAttributeValue(null,"path"))
                        excluded+=parser.getAttributeValue(null,"domain")
                    }
                }
            }
            val copies=if(resource==R.xml.data_extraction_rules) 2 else 1
            for(domain in listOf("root","file","database","sharedpref","external")) assertEquals(copies,excluded.count {it==domain})
        }
    }
}
