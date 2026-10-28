package com.onejob.game.ui.forms

enum class DraftIssue {
    NAME_REQUIRED,
    NAME_TOO_LONG,
    NAME_CONTROL_CHARACTER,
    NAME_INVALID_UNICODE,
    ROOM_CODE_INVALID,
}

/** Presentation hints for local drafts. The server validates every actual admission. */
object DraftValidation {
    fun name(value: String): DraftIssue? {
        if (value.any { Character.isISOControl(it) }) return DraftIssue.NAME_CONTROL_CHARACTER
        var index = 0
        while (index < value.length) {
            val character = value[index]
            if (Character.isHighSurrogate(character)) {
                if (index + 1 >= value.length || !Character.isLowSurrogate(value[index + 1])) {
                    return DraftIssue.NAME_INVALID_UNICODE
                }
                index += 2
            } else {
                if (Character.isLowSurrogate(character)) return DraftIssue.NAME_INVALID_UNICODE
                index++
            }
        }
        val trimmed = value.trim()
        if (trimmed.isEmpty()) return DraftIssue.NAME_REQUIRED
        if (trimmed.codePointCount(0, trimmed.length) > 20) return DraftIssue.NAME_TOO_LONG
        return null
    }

    fun roomCode(value: String): DraftIssue? {
        val trimmed = value.trim()
        val alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
        return if (trimmed.length == 6 && trimmed.all { it.code < 128 && it.uppercaseChar() in alphabet }) {
            null
        } else {
            DraftIssue.ROOM_CODE_INVALID
        }
    }
}
