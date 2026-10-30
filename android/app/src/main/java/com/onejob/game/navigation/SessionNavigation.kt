package com.onejob.game.navigation

import com.onejob.game.data.repository.SessionState

/** Presentation routing from authoritative stages; no clock or one-shot event dependency. */
fun sessionDestination(session: SessionState, previous: AppDestination?, recovering: Boolean): AppDestination {
    if (session.identity?.kind == "display") return AppDestination.DISPLAY
    val lobbyStage = session.lobby?.stage
    if (lobbyStage == "lobby") return AppDestination.LOBBY
    // A fresh briefing invalidates the preceding result before its assignment arrives.
    if (lobbyStage == "briefing") return AppDestination.ROLE
    val assigned = session.assigned
    val public = session.roleState?.takeIf {
        assigned != null && it.public.round_id == assigned.round_id &&
            it.stations.roles().toSet() == assigned.roles.toSet()
    }?.public
    if (public?.result != null) return AppDestination.RESULTS
    val stage = public?.stage ?: lobbyStage
    return when {
        stage in setOf("finished", "aborted") -> AppDestination.RESULTS
        stage == "countdown" || public?.paused_from == "countdown" -> AppDestination.COUNTDOWN
        stage == "running" || public?.paused_from == "running" -> AppDestination.GAMEPLAY
        stage == "briefing" || public?.paused_from == "briefing" -> AppDestination.ROLE
        recovering && previous in sessionDestinations -> previous!!
        else -> AppDestination.LOBBY
    }
}

val sessionDestinations = setOf(AppDestination.LOBBY, AppDestination.ROLE,
    AppDestination.COUNTDOWN, AppDestination.GAMEPLAY, AppDestination.RESULTS, AppDestination.DISPLAY)
