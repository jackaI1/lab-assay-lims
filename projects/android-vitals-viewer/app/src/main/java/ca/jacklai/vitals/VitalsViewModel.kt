package ca.jacklai.vitals

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import java.io.IOException

data class ScreenState(val source: String = "http://localhost:8000",
    val patient: String = "11111111-1111-4111-8111-111111111111", val report: VisitReport? = null,
    val savedAt: Long? = null, val message: String = "Sign in to load fictional visits.",
    val busy: Boolean = false, val signedIn: Boolean = false, val login: Boolean = false)

class VitalsViewModel(app: Application) : AndroidViewModel(app) {
    private val database = VitalsDatabase.open(app)
    private val api = BridgeApi()
    private val repository = VisitRepository(database.snapshots(), api)
    private val preferences = app.getSharedPreferences("connection", 0)
    private var session = "" // Process memory only. SMART tokens never leave the bridge.
    private val mutable = MutableStateFlow(ScreenState(
        source = preferences.getString("source", "http://localhost:8000")!!,
        patient = preferences.getString("patient", "11111111-1111-4111-8111-111111111111")!!, busy = true))
    val state = mutable.asStateFlow()
    init { viewModelScope.launch { loadCache(); mutable.value = mutable.value.copy(busy = false) } }

    private suspend fun loadCache() {
        val s = mutable.value
        val cached = repository.cached(s.source, s.patient)
        mutable.value = s.copy(report = cached?.let { runCatching { ReportParser.parse(it.json, s.patient) }.getOrNull() },
            savedAt = cached?.savedAt, message = if (cached != null) "Saved snapshot. Sign in to check for updates." else "Sign in to load fictional visits.")
    }
    fun connect(source: String, patient: String) {
        if (mutable.value.busy || mutable.value.login) return
        val pair = runCatching { validateSource(source) to validatePatient(patient) }.getOrElse {
            mutable.value = mutable.value.copy(message = "Enter a bridge URL and a valid fictional patient UUID."); return
        }
        val previousSession = session
        val previousSource = mutable.value.source
        session = ""
        mutable.value = ScreenState(pair.first, pair.second, busy = true)
        preferences.edit().putString("source", pair.first).putString("patient", pair.second).apply()
        viewModelScope.launch {
            if (previousSession.isNotEmpty()) runCatching { api.logout(previousSource, previousSession) }
            loadCache()
            mutable.value = mutable.value.copy(busy = false, login = true)
        }
    }
    fun cancelLogin() { mutable.value = mutable.value.copy(login = false, message = "Sign-in cancelled. Saved snapshot is still available.") }
    fun authorized(cookie: String) {
        session = cookie
        mutable.value = mutable.value.copy(login = false)
        refresh()
    }
    fun refresh() {
        val s = mutable.value
        if (s.busy) return
        if (session.isEmpty()) { mutable.value = s.copy(message = "Sign in to check for updates."); return }
        mutable.value = s.copy(busy = true, message = "Checking the bridge…")
        viewModelScope.launch {
            try {
                val snapshot = repository.refresh(s.source, s.patient, session)
                mutable.value = mutable.value.copy(report = ReportParser.parse(snapshot.json, s.patient), savedAt = snapshot.savedAt,
                    signedIn = true, message = "Up to date. Fictional records only.")
            } catch (_: SessionExpired) {
                session = ""
                mutable.value = mutable.value.copy(signedIn = false, message = "Session expired. Sign in again. Showing saved snapshot.")
            } catch (e: IOException) {
                mutable.value = mutable.value.copy(message = if (e is BridgeFailure)
                    "Bridge unavailable (${e.status}). Retry or sign in again. Showing saved snapshot."
                    else "Offline or bridge unreachable. Showing saved snapshot.")
            } catch (_: Exception) {
                mutable.value = mutable.value.copy(message = "The report could not be read. Saved snapshot was kept.")
            } finally { mutable.value = mutable.value.copy(busy = false) }
        }
    }
    fun logout() {
        if (mutable.value.busy) return
        val old = session
        val source = mutable.value.source
        session = ""
        mutable.value = mutable.value.copy(signedIn = false, busy = true)
        viewModelScope.launch {
            val revoked = runCatching { if (old.isNotEmpty()) api.logout(source, old) }.isSuccess
            database.snapshots().clear()
            mutable.value = mutable.value.copy(report = null, savedAt = null, busy = false,
                message = if (revoked) "Signed out. Saved snapshots cleared." else "Local sign-out complete. Bridge unreachable; its session will expire automatically.")
        }
    }
    override fun onCleared() { database.close(); super.onCleared() }
}
