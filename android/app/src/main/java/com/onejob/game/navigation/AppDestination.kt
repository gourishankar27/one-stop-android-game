package com.onejob.game.navigation

/** Routes carry no credentials or room data. Navigation previews never grant membership. */
enum class AppDestination(val route: String) {
    HOME("home"),
    SETTINGS("settings"),
    CREATE("create"),
    JOIN("join"),
    DISPLAY_JOIN("display_join"),
    DISPLAY("display"),
    LOBBY("lobby"),
    ROLE("role"),
    COUNTDOWN("countdown"),
    GAMEPLAY("gameplay"),
    RESULTS("results"),
}
