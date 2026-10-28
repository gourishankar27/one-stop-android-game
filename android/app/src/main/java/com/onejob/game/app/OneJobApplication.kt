package com.onejob.game.app

import android.app.Application
import com.onejob.game.data.GameRepository
import com.onejob.game.data.UnavailableGameRepository

class AppContainer(val gameRepository: GameRepository = UnavailableGameRepository())

class OneJobApplication : Application() {
    val container: AppContainer by lazy { AppContainer() }
}
