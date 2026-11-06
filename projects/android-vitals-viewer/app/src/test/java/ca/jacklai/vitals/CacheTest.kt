package ca.jacklai.vitals

import androidx.room.Room
import androidx.test.core.app.ApplicationProvider
import kotlinx.coroutines.test.runTest
import org.junit.*
import org.junit.Assert.*
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import java.io.IOException

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [35])
class CacheTest {
    private lateinit var db: VitalsDatabase
    private val source = "http://localhost:8000"
    @Before fun open() { db = Room.inMemoryDatabaseBuilder(ApplicationProvider.getApplicationContext(), VitalsDatabase::class.java).build() }
    @After fun close() { db.close() }
    private fun repo(body: String = fixture(), error: Exception? = null) = VisitRepository(db.snapshots(), object : BridgeApi() {
        override suspend fun visits(source: String, patient: String, session: String): String {
            error?.let { throw it }; return body
        }
    }) { 123L }
    @Test fun refreshSavesValidatedSnapshotAndTime() = runTest {
        repo().refresh(source, PATIENT, "session")
        val saved = db.snapshots().get(source, PATIENT)!!
        assertEquals(123L, saved.savedAt); assertEquals(18, ReportParser.parse(saved.json, PATIENT).visits.sumOf { it.readings.size })
    }
    @Test fun networkFailureKeepsLastGoodSnapshot() = runTest {
        repo().refresh(source, PATIENT, "session")
        try { repo(error = IOException()).refresh(source, PATIENT, "session"); fail() } catch (_: IOException) { }
        assertEquals(fixture(), db.snapshots().get(source, PATIENT)!!.json)
    }
    @Test fun expiredSessionKeepsCacheForLabelledOfflineView() = runTest {
        repo().refresh(source, PATIENT, "session")
        try { repo(error = SessionExpired()).refresh(source, PATIENT, "session"); fail() } catch (_: SessionExpired) { }
        assertNotNull(repo().cached(source, PATIENT))
    }
    @Test fun malformedResponseCannotReplaceGoodData() = runTest {
        repo().refresh(source, PATIENT, "session")
        try { repo(body = "{}").refresh(source, PATIENT, "session"); fail() } catch (_: Exception) { }
        assertEquals(fixture(), repo().cached(source, PATIENT)!!.json)
    }
    @Test fun isolatesServerAndPatient() = runTest {
        repo().refresh(source, PATIENT, "session")
        assertNull(repo().cached("https://other.example", PATIENT))
        assertNull(repo().cached(source, "other-patient"))
    }
    @Test fun replacementRemovesDeletedReadingsRatherThanAppending() = runTest {
        repo().refresh(source, PATIENT, "session")
        val changed = org.json.JSONObject(fixture())
        changed.getJSONArray("visits").remove(0)
        repo(changed.toString()).refresh(source, PATIENT, "session")
        assertEquals(1, ReportParser.parse(repo().cached(source, PATIENT)!!.json, PATIENT).visits.size)
    }
    @Test fun logoutCanClearAllSavedPatients() = runTest {
        repo().refresh(source, PATIENT, "session"); db.snapshots().clear()
        assertNull(repo().cached(source, PATIENT))
    }
    @Test fun diskSnapshotSurvivesDatabaseReopen() = runTest {
        val context = ApplicationProvider.getApplicationContext<android.content.Context>()
        val name = "cache-reopen-test.db"
        context.deleteDatabase(name)
        try {
            Room.databaseBuilder(context, VitalsDatabase::class.java, name).build().let {
                try { it.snapshots().put(Snapshot(source, PATIENT, fixture(), 123)) } finally { it.close() }
            }
            Room.databaseBuilder(context, VitalsDatabase::class.java, name).build().let {
                try { assertEquals(123L, it.snapshots().get(source, PATIENT)!!.savedAt) } finally { it.close() }
            }
        } finally { context.deleteDatabase(name) }
    }
}
