package com.onejob.game.ui.connection

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.onejob.game.data.GameRepository
import com.onejob.game.data.repository.CommandResult
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

enum class ProbeResult { NONE, SUCCEEDED, REJECTED, UNCERTAIN, NOT_SENT, DISCONNECTED }

class ConnectionCheckViewModel(private val repository: GameRepository) : ViewModel() {
    val connection = repository.connection
    private val _result = MutableStateFlow(ProbeResult.NONE)
    val result = _result.asStateFlow()
    private val _working = MutableStateFlow(false)
    val working = _working.asStateFlow()
    fun connect() = run { repository.connect() }
    fun ping() = run { repository.ping() }
    fun createTestMembership() = run { repository.create("Connection check") }
    fun disconnect() = run { repository.disconnect() }
    private fun run(command: suspend () -> CommandResult) {
        if (_working.value) return
        _working.value = true
        viewModelScope.launch {
            try {
                _result.value = when (command()) {
                    is CommandResult.Accepted -> ProbeResult.SUCCEEDED
                    is CommandResult.Rejected -> ProbeResult.REJECTED
                    is CommandResult.Uncertain -> ProbeResult.UNCERTAIN
                    is CommandResult.NotSent -> ProbeResult.NOT_SENT
                    CommandResult.LeftLocally -> ProbeResult.DISCONNECTED
                }
            } finally { _working.value = false }
        }
    }
}
