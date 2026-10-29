package com.onejob.game.data.network

import java.net.URI

sealed interface EndpointResult {
    data class Ready(val endpoint: Endpoint) : EndpointResult
    data object Missing : EndpointResult
    data object Invalid : EndpointResult
}

fun interface EndpointProvider {
    fun current(): EndpointResult
}

class Endpoint private constructor(internal val address: String) {
    override fun toString() = "Endpoint(redacted)"

    internal fun sameAs(other: Endpoint) = address == other.address

    companion object {
        fun parse(address: String, debug: Boolean = false, allowCleartext: Boolean = false): EndpointResult {
            if (address.isBlank()) return EndpointResult.Missing
            val uri = try { URI(address) } catch (_: Exception) { return EndpointResult.Invalid }
            val host = uri.host ?: return EndpointResult.Invalid
            if (uri.rawUserInfo != null || uri.rawQuery != null || uri.rawFragment != null ||
                uri.rawPath != "/ws" || uri.port !in -1..65535 || uri.port == 0) return EndpointResult.Invalid
            val scheme = uri.scheme?.lowercase()
            if (scheme != "wss" && !(scheme == "ws" && debug && allowCleartext && privateHost(host))) {
                return EndpointResult.Invalid
            }
            return EndpointResult.Ready(Endpoint(uri.toASCIIString()))
        }

        private fun privateHost(host: String): Boolean {
            if (host == "localhost" || host == "::1" || host == "[::1]") return true
            val parts = host.split('.')
            if (parts.size != 4 || parts.any { it.isEmpty() || it.any { c -> c !in '0'..'9' } }) return false
            val bytes = parts.map { it.toIntOrNull() ?: return false }
            if (parts.zip(bytes).any { (text, number) -> text != number.toString() }) return false
            if (bytes.any { it !in 0..255 }) return false
            return bytes[0] == 10 || bytes[0] == 127 ||
                (bytes[0] == 192 && bytes[1] == 168) ||
                (bytes[0] == 172 && bytes[1] in 16..31)
        }
    }
}
