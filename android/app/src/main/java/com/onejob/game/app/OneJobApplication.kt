package com.onejob.game.app

import android.app.Application
import android.content.Context
import android.os.SystemClock
import com.onejob.game.feedback.*
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

class AppContainer(context: Context, repository: GameRepository? = null) {
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.Default)
    val gameRepository: GameRepository = repository ?: SocketGameRepository(
        EndpointProvider { Endpoint.parse(BuildConfig.WS_ENDPOINT, BuildConfig.DEBUG, BuildConfig.ALLOW_DEBUG_CLEARTEXT) },
        OkHttpSocketDataSource(), scope,
    )
    private val feedbackScope = CoroutineScope(SupervisorJob() + Dispatchers.Main.immediate)
    val feedbackPreferences = FeedbackPreferencesRepository(AndroidFeedbackPreferenceStorage(
        context.applicationContext.getSharedPreferences("one_job_feedback_v1", Context.MODE_PRIVATE),
    ))
    val feedback = FeedbackController(gameRepository, feedbackPreferences, feedbackScope, SystemClock::elapsedRealtime)
    fun close() { feedback.close(); feedbackScope.cancel(); gameRepository.close(); scope.cancel() }
}

class OneJobApplication : Application() {
    private val owner = lazy { AppContainer(this) }
    val container: AppContainer get() = owner.value
    override fun onTerminate() {
        if (owner.isInitialized()) owner.value.close()
        super.onTerminate()
    }
}
