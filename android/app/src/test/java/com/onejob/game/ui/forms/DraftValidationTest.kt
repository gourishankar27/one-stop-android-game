package com.onejob.game.ui.forms

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class DraftValidationTest {
    @Test
    fun nameHintsIgnoreOuterSpacesAndCountUnicodeCharacters() {
        assertNull(DraftValidation.name("  Ada  "))
        assertNull(DraftValidation.name("🚀".repeat(20)))
        assertEquals(DraftIssue.NAME_TOO_LONG, DraftValidation.name("🚀".repeat(21)))
    }

    @Test
    fun emptyControlAndInvalidUnicodeNamesHaveUsefulHints() {
        assertEquals(DraftIssue.NAME_REQUIRED, DraftValidation.name("   "))
        assertEquals(DraftIssue.NAME_CONTROL_CHARACTER, DraftValidation.name("A\nB"))
        assertEquals(DraftIssue.NAME_INVALID_UNICODE, DraftValidation.name("\uD800"))
        assertEquals(DraftIssue.NAME_INVALID_UNICODE, DraftValidation.name("\uDC00"))
    }

    @Test
    fun codesAcceptCaseAndOuterSpacesButRejectAmbiguousAndNonAsciiSymbols() {
        assertNull(DraftValidation.roomCode(" abcd23 "))
        for (code in listOf("ABCDE", "ABCDEFG", "ABCDI2", "ABCDO2", "ABCD01", "AB C23", "ſBCD23")) {
            assertEquals(code, DraftIssue.ROOM_CODE_INVALID, DraftValidation.roomCode(code))
        }
    }
}
