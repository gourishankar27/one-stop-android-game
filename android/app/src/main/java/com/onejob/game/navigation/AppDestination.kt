package com.onejob.game.navigation

/** Routes carry no credentials or room data. Navigation previews never grant membership. */
enum class AppDestination(val route: String) {
    HOME("home"),
    CREATE("create"),
    JOIN("join"),
    LOBBY("lobby"),
    ROLE("role"),
    COUNTDOWN("countdown"),
    GAMEPLAY("gameplay"),
    RESULTS("results"),
}
