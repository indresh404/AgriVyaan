package com.agrivyaan.optix.gps

import android.content.ContentValues
import android.content.Context
import android.database.sqlite.SQLiteDatabase
import android.database.sqlite.SQLiteOpenHelper
import android.os.Build
import android.os.Environment
import android.util.Log
import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.io.FileOutputStream
import java.io.OutputStreamWriter
import java.text.SimpleDateFormat
import java.util.*
import java.util.concurrent.ConcurrentLinkedDeque

data class TrackSession(
    val id: String,
    val name: String,
    val startTime: Long,
    var endTime: Long = 0L,
    var pointsCount: Int = 0,
    var distanceMeters: Double = 0.0,
    var maxSpeed: Float = 0f,
    var maxAltitude: Double = 0.0
) {
    fun toJson(): JSONObject {
        return JSONObject().apply {
            put("id", id)
            put("name", name)
            put("startTime", startTime)
            put("endTime", endTime)
            put("pointsCount", pointsCount)
            put("distanceMeters", distanceMeters)
            put("maxSpeed", maxSpeed)
            put("maxAltitude", maxAltitude)
        }
    }
}

class TrackDatabase(private val context: Context) : SQLiteOpenHelper(context, "optix_tracks.db", null, 1) {

    private val tag = "TrackDatabase"
    private val memoryRingBuffer = ConcurrentLinkedDeque<GpsTelemetry>()
    private val maxRingBufferItems = 1200 // 10 minutes at 2 Hz

    private var activeSession: TrackSession? = null

    override fun onCreate(db: SQLiteDatabase) {
        db.execSQL(
            """
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                name TEXT,
                start_time INTEGER,
                end_time INTEGER,
                points_count INTEGER,
                distance_meters REAL,
                max_speed REAL,
                max_altitude REAL
            )
            """.trimIndent()
        )

        db.execSQL(
            """
            CREATE TABLE IF NOT EXISTS points (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT,
                timestamp INTEGER,
                lat REAL,
                lon REAL,
                altitude_gps REAL,
                altitude_baro REAL,
                speed REAL,
                bearing REAL,
                heading REAL,
                accuracy REAL,
                sats INTEGER
            )
            """.trimIndent()
        )
        db.execSQL("CREATE INDEX IF NOT EXISTS idx_session_time ON points (session_id, timestamp)")
    }

    override fun onUpgrade(db: SQLiteDatabase, oldVersion: Int, newVersion: Int) {}

    @Synchronized
    fun startSession(): TrackSession {
        // End any open session first
        endSession()

        val sdf = SimpleDateFormat("yyyyMMdd_HHmmss", Locale.US)
        val timestamp = System.currentTimeMillis()
        val name = "Track_${sdf.format(Date(timestamp))}"
        val id = UUID.randomUUID().toString()

        val session = TrackSession(
            id = id,
            name = name,
            startTime = timestamp
        )

        try {
            val db = writableDatabase
            val values = ContentValues().apply {
                put("id", session.id)
                put("name", session.name)
                put("start_time", session.startTime)
                put("end_time", 0L)
                put("points_count", 0)
                put("distance_meters", 0.0)
                put("max_speed", 0f)
                put("max_altitude", 0.0)
            }
            db.insert("sessions", null, values)
            activeSession = session
            memoryRingBuffer.clear()
            Log.i(tag, "Started new track recording session: ${session.name} ($id)")
        } catch (e: Exception) {
            Log.e(tag, "Failed to start track session", e)
        }
        return session
    }

    @Synchronized
    fun endSession(): TrackSession? {
        val session = activeSession ?: return null
        session.endTime = System.currentTimeMillis()
        try {
            val db = writableDatabase
            val values = ContentValues().apply {
                put("end_time", session.endTime)
                put("points_count", session.pointsCount)
                put("distance_meters", session.distanceMeters)
                put("max_speed", session.maxSpeed)
                put("max_altitude", session.maxAltitude)
            }
            db.update("sessions", values, "id = ?", arrayOf(session.id))
            Log.i(tag, "Ended track session: ${session.name} with ${session.pointsCount} points")
        } catch (e: Exception) {
            Log.e(tag, "Failed to end track session", e)
        }
        activeSession = null
        return session
    }

    fun getActiveSession(): TrackSession? = activeSession

    @Synchronized
    fun recordPoint(telemetry: GpsTelemetry) {
        // Keep in in-memory ring buffer (black box)
        memoryRingBuffer.addLast(telemetry)
        while (memoryRingBuffer.size > maxRingBufferItems) {
            memoryRingBuffer.removeFirst()
        }

        val session = activeSession ?: return
        if (telemetry.rawLat == 0.0 && telemetry.rawLon == 0.0) return

        try {
            val db = writableDatabase
            val values = ContentValues().apply {
                put("session_id", session.id)
                put("timestamp", telemetry.timestamp)
                put("lat", telemetry.rawLat)
                put("lon", telemetry.rawLon)
                put("altitude_gps", telemetry.altitudeGps)
                put("altitude_baro", telemetry.altitudeBaro)
                put("speed", telemetry.speed)
                put("bearing", telemetry.bearing)
                put("heading", telemetry.heading)
                put("accuracy", telemetry.accuracy)
                put("sats", telemetry.satellitesUsed)
            }
            db.insert("points", null, values)

            session.pointsCount++
            session.distanceMeters = telemetry.totalFlightDistance
            if (telemetry.speed > session.maxSpeed) session.maxSpeed = telemetry.speed
            if (telemetry.altitudeGps > session.maxAltitude) session.maxAltitude = telemetry.altitudeGps
        } catch (e: Exception) {
            Log.e(tag, "Failed to record track point", e)
        }
    }

    fun getMissedPoints(sinceTimestamp: Long): List<GpsTelemetry> {
        val result = mutableListOf<GpsTelemetry>()
        for (item in memoryRingBuffer) {
            if (item.timestamp > sinceTimestamp) {
                result.add(item)
            }
        }
        return result
    }

    fun getAllSessions(): List<TrackSession> {
        val list = mutableListOf<TrackSession>()
        try {
            val db = readableDatabase
            val cursor = db.rawQuery("SELECT id, name, start_time, end_time, points_count, distance_meters, max_speed, max_altitude FROM sessions ORDER BY start_time DESC", null)
            cursor.use {
                while (it.moveToNext()) {
                    list.add(
                        TrackSession(
                            id = it.getString(0),
                            name = it.getString(1),
                            startTime = it.getLong(2),
                            endTime = it.getLong(3),
                            pointsCount = it.getInt(4),
                            distanceMeters = it.getDouble(5),
                            maxSpeed = it.getFloat(6),
                            maxAltitude = it.getDouble(7)
                        )
                    )
                }
            }
        } catch (e: Exception) {
            Log.e(tag, "Failed to get sessions", e)
        }
        return list
    }

    fun getSessionPoints(sessionId: String): JSONArray {
        val array = JSONArray()
        try {
            val db = readableDatabase
            val cursor = db.rawQuery(
                "SELECT timestamp, lat, lon, altitude_gps, altitude_baro, speed, bearing, heading, accuracy, sats FROM points WHERE session_id = ? ORDER BY timestamp ASC",
                arrayOf(sessionId)
            )
            cursor.use {
                while (it.moveToNext()) {
                    array.put(JSONObject().apply {
                        put("t", it.getLong(0))
                        put("lat", it.getDouble(1))
                        put("lon", it.getDouble(2))
                        put("altGps", it.getDouble(3))
                        put("altBaro", it.getDouble(4))
                        put("speed", it.getFloat(5))
                        put("bearing", it.getFloat(6))
                        put("heading", it.getFloat(7))
                        put("acc", it.getFloat(8))
                        put("sats", it.getInt(9))
                    })
                }
            }
        } catch (e: Exception) {
            Log.e(tag, "Failed to get session points", e)
        }
        return array
    }

    fun deleteSession(sessionId: String): Boolean {
        return try {
            val db = writableDatabase
            db.delete("points", "session_id = ?", arrayOf(sessionId))
            db.delete("sessions", "id = ?", arrayOf(sessionId))
            true
        } catch (e: Exception) {
            Log.e(tag, "Failed to delete session $sessionId", e)
            false
        }
    }

    // Export Formats: GPX, KML, CSV
    fun exportGpx(sessionId: String): File? {
        val session = getSession(sessionId) ?: return null
        val exportDir = getExportDir()
        val file = File(exportDir, "${session.name}.gpx")

        try {
            val db = readableDatabase
            val cursor = db.rawQuery(
                "SELECT timestamp, lat, lon, altitude_gps, speed FROM points WHERE session_id = ? ORDER BY timestamp ASC",
                arrayOf(sessionId)
            )
            cursor.use {
                val isoFormat = SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss'Z'", Locale.US).apply {
                    timeZone = TimeZone.getTimeZone("UTC")
                }
                FileOutputStream(file).use { fos ->
                    OutputStreamWriter(fos, Charsets.UTF_8).use { w ->
                        w.write("<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n")
                        w.write("<gpx version=\"1.1\" creator=\"Optix DroneCam\" xmlns=\"http://www.topografix.com/GPX/1/1\">\n")
                        w.write("  <metadata>\n    <name>${session.name}</name>\n  </metadata>\n")
                        w.write("  <trk>\n    <name>${session.name}</name>\n    <trkseg>\n")
                        while (it.moveToNext()) {
                            val time = it.getLong(0)
                            val lat = it.getDouble(1)
                            val lon = it.getDouble(2)
                            val alt = it.getDouble(3)
                            val speed = it.getFloat(4)
                            w.write("      <trkpt lat=\"$lat\" lon=\"$lon\">\n")
                            w.write("        <ele>$alt</ele>\n")
                            w.write("        <time>${isoFormat.format(Date(time))}</time>\n")
                            w.write("        <speed>$speed</speed>\n")
                            w.write("      </trkpt>\n")
                        }
                        w.write("    </trkseg>\n  </trk>\n</gpx>\n")
                    }
                }
            }
            return file
        } catch (e: Exception) {
            Log.e(tag, "Failed to export GPX for $sessionId", e)
            return null
        }
    }

    fun exportKml(sessionId: String): File? {
        val session = getSession(sessionId) ?: return null
        val exportDir = getExportDir()
        val file = File(exportDir, "${session.name}.kml")

        try {
            val db = readableDatabase
            val cursor = db.rawQuery(
                "SELECT lat, lon, altitude_gps FROM points WHERE session_id = ? ORDER BY timestamp ASC",
                arrayOf(sessionId)
            )
            cursor.use {
                FileOutputStream(file).use { fos ->
                    OutputStreamWriter(fos, Charsets.UTF_8).use { w ->
                        w.write("<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n")
                        w.write("<kml xmlns=\"http://www.opengis.net/kml/2.2\">\n")
                        w.write("  <Document>\n    <name>${session.name}</name>\n")
                        w.write("    <Placemark>\n      <name>${session.name}</name>\n")
                        w.write("      <LineString>\n        <extrude>1</extrude>\n        <altitudeMode>absolute</altitudeMode>\n")
                        w.write("        <coordinates>\n")
                        while (it.moveToNext()) {
                            val lat = it.getDouble(0)
                            val lon = it.getDouble(1)
                            val alt = it.getDouble(2)
                            w.write("          $lon,$lat,$alt\n")
                        }
                        w.write("        </coordinates>\n      </LineString>\n    </Placemark>\n  </Document>\n</kml>\n")
                    }
                }
            }
            return file
        } catch (e: Exception) {
            Log.e(tag, "Failed to export KML for $sessionId", e)
            return null
        }
    }

    fun exportCsv(sessionId: String): File? {
        val session = getSession(sessionId) ?: return null
        val exportDir = getExportDir()
        val file = File(exportDir, "${session.name}.csv")

        try {
            val db = readableDatabase
            val cursor = db.rawQuery(
                "SELECT timestamp, lat, lon, altitude_gps, altitude_baro, speed, bearing, heading, accuracy, sats FROM points WHERE session_id = ? ORDER BY timestamp ASC",
                arrayOf(sessionId)
            )
            cursor.use {
                FileOutputStream(file).use { fos ->
                    OutputStreamWriter(fos, Charsets.UTF_8).use { w ->
                        w.write("Timestamp,Lat,Lon,AltitudeGPS,AltitudeBaro,Speed_mps,Speed_kmh,Bearing,Heading,Accuracy_m,Satellites\n")
                        while (it.moveToNext()) {
                            val t = it.getLong(0)
                            val lat = it.getDouble(1)
                            val lon = it.getDouble(2)
                            val altG = it.getDouble(3)
                            val altB = it.getDouble(4)
                            val spd = it.getFloat(5)
                            val brg = it.getFloat(6)
                            val hdg = it.getFloat(7)
                            val acc = it.getFloat(8)
                            val sat = it.getInt(9)
                            w.write("$t,$lat,$lon,$altG,$altB,$spd,${spd * 3.6f},$brg,$hdg,$acc,$sat\n")
                        }
                    }
                }
            }
            return file
        } catch (e: Exception) {
            Log.e(tag, "Failed to export CSV for $sessionId", e)
            return null
        }
    }

    private fun getSession(sessionId: String): TrackSession? {
        var session: TrackSession? = null
        try {
            val db = readableDatabase
            val cursor = db.rawQuery("SELECT id, name, start_time, end_time, points_count, distance_meters, max_speed, max_altitude FROM sessions WHERE id = ?", arrayOf(sessionId))
            cursor.use {
                if (it.moveToFirst()) {
                    session = TrackSession(
                        id = it.getString(0),
                        name = it.getString(1),
                        startTime = it.getLong(2),
                        endTime = it.getLong(3),
                        pointsCount = it.getInt(4),
                        distanceMeters = it.getDouble(5),
                        maxSpeed = it.getFloat(6),
                        maxAltitude = it.getDouble(7)
                    )
                }
            }
        } catch (_: Exception) {}
        return session
    }

    private fun getExportDir(): File {
        val baseDir = context.getExternalFilesDir("DroneCam/Tracks")
            ?: File(context.filesDir, "DroneCam/Tracks")
        if (!baseDir.exists()) baseDir.mkdirs()
        return baseDir
    }
}
