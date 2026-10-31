package com.agrivyaan.optix.map

import android.content.ContentValues
import android.content.Context
import android.database.sqlite.SQLiteDatabase
import android.database.sqlite.SQLiteOpenHelper
import android.util.Log
import org.json.JSONArray
import org.json.JSONObject
import java.util.*
import kotlin.math.*

data class Waypoint(
    val id: String = UUID.randomUUID().toString(),
    val name: String,
    val lat: Double,
    val lon: Double,
    val category: String = "Marker",
    val description: String = "",
    val timestamp: Long = System.currentTimeMillis()
) {
    fun toJson(): JSONObject {
        return JSONObject().apply {
            put("id", id)
            put("name", name)
            put("lat", lat)
            put("lon", lon)
            put("category", category)
            put("description", description)
            put("timestamp", timestamp)
        }
    }
}

data class FieldBoundary(
    val id: String = UUID.randomUUID().toString(),
    val name: String,
    val points: List<Pair<Double, Double>>, // lat, lon
    val areaM2: Double,
    val areaHectares: Double,
    val areaAcres: Double,
    val perimeterMeters: Double,
    val timestamp: Long = System.currentTimeMillis()
) {
    fun toJson(): JSONObject {
        val ptsArray = JSONArray()
        for (pt in points) {
            ptsArray.put(JSONArray().put(pt.first).put(pt.second))
        }
        return JSONObject().apply {
            put("id", id)
            put("name", name)
            put("points", ptsArray)
            put("areaM2", (areaM2 * 10.0).roundToInt() / 10.0)
            put("areaHectares", (areaHectares * 100.0).roundToInt() / 100.0)
            put("areaAcres", (areaAcres * 100.0).roundToInt() / 100.0)
            put("perimeterMeters", (perimeterMeters * 10.0).roundToInt() / 10.0)
            put("timestamp", timestamp)
        }
    }
}

class FlightMissionManager(context: Context) : SQLiteOpenHelper(context, "optix_mission.db", null, 1) {

    private val tag = "FlightMissionManager"

    // Geofence configuration
    var isGeofenceActive = false
    var geofenceRadiusMeters = 300.0 // Default 300m radius around Home
    var geofenceFieldId: String? = null // Or polygon boundary geofence

    override fun onCreate(db: SQLiteDatabase) {
        db.execSQL(
            """
            CREATE TABLE IF NOT EXISTS waypoints (
                id TEXT PRIMARY KEY,
                name TEXT,
                lat REAL,
                lon REAL,
                category TEXT,
                description TEXT,
                timestamp INTEGER
            )
            """.trimIndent()
        )

        db.execSQL(
            """
            CREATE TABLE IF NOT EXISTS fields (
                id TEXT PRIMARY KEY,
                name TEXT,
                points_json TEXT,
                area_m2 REAL,
                area_hectares REAL,
                area_acres REAL,
                perimeter_m REAL,
                timestamp INTEGER
            )
            """.trimIndent()
        )
    }

    override fun onUpgrade(db: SQLiteDatabase, oldVersion: Int, newVersion: Int) {}

    // Waypoints
    fun addWaypoint(waypoint: Waypoint): Boolean {
        return try {
            val db = writableDatabase
            val values = ContentValues().apply {
                put("id", waypoint.id)
                put("name", waypoint.name)
                put("lat", waypoint.lat)
                put("lon", waypoint.lon)
                put("category", waypoint.category)
                put("description", waypoint.description)
                put("timestamp", waypoint.timestamp)
            }
            db.insertWithOnConflict("waypoints", null, values, SQLiteDatabase.CONFLICT_REPLACE)
            true
        } catch (e: Exception) {
            Log.e(tag, "Failed to add waypoint", e)
            false
        }
    }

    fun getWaypointsJson(): JSONArray {
        val array = JSONArray()
        try {
            val db = readableDatabase
            val cursor = db.rawQuery("SELECT id, name, lat, lon, category, description, timestamp FROM waypoints ORDER BY timestamp DESC", null)
            cursor.use {
                while (it.moveToNext()) {
                    array.put(
                        Waypoint(
                            id = it.getString(0),
                            name = it.getString(1),
                            lat = it.getDouble(2),
                            lon = it.getDouble(3),
                            category = it.getString(4),
                            description = it.getString(5),
                            timestamp = it.getLong(6)
                        ).toJson()
                    )
                }
            }
        } catch (e: Exception) {
            Log.e(tag, "Failed to get waypoints", e)
        }
        return array
    }

    fun deleteWaypoint(id: String): Boolean {
        return try {
            writableDatabase.delete("waypoints", "id = ?", arrayOf(id)) > 0
        } catch (_: Exception) { false }
    }

    // Fields & Polygons
    fun saveField(name: String, points: List<Pair<Double, Double>>): FieldBoundary? {
        if (points.size < 3) return null
        val (areaM2, perimeterM) = calculatePolygonAreaAndPerimeter(points)
        val hectares = areaM2 / 10000.0
        val acres = areaM2 * 0.000247105

        val field = FieldBoundary(
            name = name,
            points = points,
            areaM2 = areaM2,
            areaHectares = hectares,
            areaAcres = acres,
            perimeterMeters = perimeterM
        )

        try {
            val ptsArray = JSONArray()
            for (p in points) {
                ptsArray.put(JSONArray().put(p.first).put(p.second))
            }
            val db = writableDatabase
            val values = ContentValues().apply {
                put("id", field.id)
                put("name", field.name)
                put("points_json", ptsArray.toString())
                put("area_m2", field.areaM2)
                put("area_hectares", field.areaHectares)
                put("area_acres", field.areaAcres)
                put("perimeter_m", field.perimeterMeters)
                put("timestamp", field.timestamp)
            }
            db.insertWithOnConflict("fields", null, values, SQLiteDatabase.CONFLICT_REPLACE)
            return field
        } catch (e: Exception) {
            Log.e(tag, "Failed to save field", e)
            return null
        }
    }

    fun getFieldsJson(): JSONArray {
        val array = JSONArray()
        try {
            val db = readableDatabase
            val cursor = db.rawQuery("SELECT id, name, points_json, area_m2, area_hectares, area_acres, perimeter_m, timestamp FROM fields ORDER BY timestamp DESC", null)
            cursor.use {
                while (it.moveToNext()) {
                    val ptsJson = JSONArray(it.getString(2))
                    val pts = mutableListOf<Pair<Double, Double>>()
                    for (i in 0 until ptsJson.length()) {
                        val p = ptsJson.getJSONArray(i)
                        pts.add(Pair(p.getDouble(0), p.getDouble(1)))
                    }
                    array.put(
                        FieldBoundary(
                            id = it.getString(0),
                            name = it.getString(1),
                            points = pts,
                            areaM2 = it.getDouble(3),
                            areaHectares = it.getDouble(4),
                            areaAcres = it.getDouble(5),
                            perimeterMeters = it.getDouble(6),
                            timestamp = it.getLong(7)
                        ).toJson()
                    )
                }
            }
        } catch (e: Exception) {
            Log.e(tag, "Failed to get fields", e)
        }
        return array
    }

    fun deleteField(id: String): Boolean {
        return try {
            writableDatabase.delete("fields", "id = ?", arrayOf(id)) > 0
        } catch (_: Exception) { false }
    }

    // Geofence Checking
    fun checkGeofence(currentLat: Double, currentLon: Double, homeLat: Double, homeLon: Double): String? {
        if (!isGeofenceActive) return null
        if (currentLat == 0.0 && currentLon == 0.0) return null

        val fid = geofenceFieldId
        if (fid != null && fid.isNotEmpty()) {
            val field = getFieldById(fid)
            if (field != null && field.points.size >= 3) {
                val isInside = isPointInPolygon(currentLat, currentLon, field.points)
                if (!isInside) {
                    return "GEOFENCE ALERT: Drone is outside '${field.name}' boundary!"
                }
                return null
            }
        }

        // Circular radius around home
        if (homeLat != 0.0 && homeLon != 0.0) {
            val dist = calculateDistance(currentLat, currentLon, homeLat, homeLon)
            if (dist > geofenceRadiusMeters) {
                val outside = (dist - geofenceRadiusMeters).roundToInt()
                return "GEOFENCE BREACH: Drone is ${outside}m outside allowed radius (${geofenceRadiusMeters.toInt()}m)!"
            }
        }
        return null
    }

    private fun getFieldById(id: String): FieldBoundary? {
        var field: FieldBoundary? = null
        try {
            val cursor = readableDatabase.rawQuery("SELECT id, name, points_json, area_m2, area_hectares, area_acres, perimeter_m, timestamp FROM fields WHERE id = ?", arrayOf(id))
            cursor.use {
                if (it.moveToFirst()) {
                    val ptsJson = JSONArray(it.getString(2))
                    val pts = mutableListOf<Pair<Double, Double>>()
                    for (i in 0 until ptsJson.length()) {
                        val p = ptsJson.getJSONArray(i)
                        pts.add(Pair(p.getDouble(0), p.getDouble(1)))
                    }
                    field = FieldBoundary(
                        id = it.getString(0),
                        name = it.getString(1),
                        points = pts,
                        areaM2 = it.getDouble(3),
                        areaHectares = it.getDouble(4),
                        areaAcres = it.getDouble(5),
                        perimeterMeters = it.getDouble(6),
                        timestamp = it.getLong(7)
                    )
                }
            }
        } catch (_: Exception) {}
        return field
    }

    companion object {
        fun calculateDistance(lat1: Double, lon1: Double, lat2: Double, lon2: Double): Double {
            val r = 6371000.0
            val dLat = Math.toRadians(lat2 - lat1)
            val dLon = Math.toRadians(lon2 - lon1)
            val a = sin(dLat / 2) * sin(dLat / 2) +
                    cos(Math.toRadians(lat1)) * cos(Math.toRadians(lat2)) *
                    sin(dLon / 2) * sin(dLon / 2)
            val c = 2 * atan2(sqrt(a), sqrt(1 - a))
            return r * c
        }

        /**
         * Spherical polygon area (in m²) using Girard's theorem / planar projection for agricultural parcels
         */
        fun calculatePolygonAreaAndPerimeter(points: List<Pair<Double, Double>>): Pair<Double, Double> {
            if (points.size < 3) return Pair(0.0, 0.0)
            val r = 6378137.0 // Earth radius in meters
            var totalArea = 0.0
            var perimeter = 0.0

            for (i in points.indices) {
                val p1 = points[i]
                val p2 = points[(i + 1) % points.size]
                perimeter += calculateDistance(p1.first, p1.second, p2.first, p2.second)

                val lat1 = Math.toRadians(p1.first)
                val lat2 = Math.toRadians(p2.first)
                val dLon = Math.toRadians(p2.second - p1.second)
                totalArea += dLon * (2.0 + sin(lat1) + sin(lat2))
            }
            totalArea = abs(totalArea * (r * r) / 4.0)
            return Pair(totalArea, perimeter)
        }

        /**
         * Ray casting algorithm for point-in-polygon
         */
        fun isPointInPolygon(lat: Double, lon: Double, polygon: List<Pair<Double, Double>>): Boolean {
            var inside = false
            var j = polygon.size - 1
            for (i in polygon.indices) {
                val pi = polygon[i]
                val pj = polygon[j]
                if ((pi.second > lon) != (pj.second > lon) &&
                    (lat < (pj.first - pi.first) * (lon - pi.second) / (pj.second - pi.second) + pi.first)
                ) {
                    inside = !inside
                }
                j = i
            }
            return inside
        }
    }
}
