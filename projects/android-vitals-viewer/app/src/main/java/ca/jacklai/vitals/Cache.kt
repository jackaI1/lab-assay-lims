package ca.jacklai.vitals

import android.content.Context
import androidx.room.*

@Entity(tableName = "snapshots", primaryKeys = ["source", "patient"])
data class Snapshot(val source: String, val patient: String, val json: String, val savedAt: Long)
@Dao
interface SnapshotDao {
    @Query("SELECT * FROM snapshots WHERE source = :source AND patient = :patient")
    suspend fun get(source: String, patient: String): Snapshot?
    @Insert(onConflict = OnConflictStrategy.REPLACE) suspend fun put(snapshot: Snapshot)
    @Query("DELETE FROM snapshots") suspend fun clear()
}
@Database(entities = [Snapshot::class], version = 1, exportSchema = true)
abstract class VitalsDatabase : RoomDatabase() {
    abstract fun snapshots(): SnapshotDao
    companion object {
        fun open(context: Context) = Room.databaseBuilder(context, VitalsDatabase::class.java, "fictional-vitals.db").build()
    }
}

class VisitRepository(private val dao: SnapshotDao, private val api: BridgeApi,
                      private val now: () -> Long = System::currentTimeMillis) {
    suspend fun cached(source: String, patient: String) = dao.get(source, patient)
    suspend fun refresh(source: String, patient: String, session: String): Snapshot {
        val raw = api.visits(source, patient, session)
        ReportParser.parse(raw, patient) // Reject invalid or mixed-patient responses before replacing anything.
        return Snapshot(source, patient, raw, now()).also { dao.put(it) }
    }
}
