package com.onejob.game.app

import android.app.Application
import com.onejob.game.data.GameRepository
import com.onejob.game.BuildConfig
import com.onejob.game.data.network.Endpoint
import com.onejob.game.data.network.EndpointProvider
import com.onejob.game.data.network.OkHttpSocketDataSource
import com.onejob.game.data.repository.SocketGameRepository
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel

class AppContainer(repository: GameRepository? = null) {
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.Default)
    val gameRepository: GameRepository = repository ?: SocketGameRepository(
        EndpointProvider { Endpoint.parse(BuildConfig.WS_ENDPOINT, BuildConfig.DEBUG, BuildConfig.ALLOW_DEBUG_CLEARTEXT) },
        OkHttpSocketDataSource(), scope,
    )
    fun close() { gameRepository.close(); scope.cancel() }
}

class OneJobApplication : Application() {
    private val owner = lazy { AppContainer() }
    val container: AppContainer get() = owner.value
    override fun onTerminate() {
        if (owner.isInitialized()) owner.value.close()
        super.onTerminate()
    }
}
