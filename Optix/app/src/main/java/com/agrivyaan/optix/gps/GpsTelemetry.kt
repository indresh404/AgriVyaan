package com.agrivyaan.optix.gps

import org.json.JSONObject
import kotlin.math.*

/**
 * Real-time GPS & flight dynamics telemetry packet
 */
data class GpsTelemetry(
    val lat: Double = 0.0,
    val lon: Double = 0.0,
    val rawLat: Double = 0.0,
    val rawLon: Double = 0.0,
    val altitudeGps: Double = 0.0,
    val altitudeBaro: Double = 0.0,
    val speed: Float = 0f,            // m/s
    val speedKmh: Float = 0f,         // km/h
    val bearing: Float = 0f,          // GPS track (0-360)
    val heading: Float = 0f,          // Compass or fused (0-360)
    val headingSource: String = "compass", // "gps" or "compass"
    val accuracy: Float = 0f,         // meters
    val satellitesUsed: Int = 0,
    val satellitesVisible: Int = 0,
    val fixType: String = "No Fix",   // "No Fix", "Searching", "2D Fix", "3D Fix"
    val status: String = "idle",       // "locked", "searching", "lost", "disabled", "no_permission"
    val isMock: Boolean = false,
    val homeLat: Double = 0.0,
    val homeLon: Double = 0.0,
    val homeDistance: Double = 0.0,   // meters
    val homeBearing: Float = 0f,      // degrees to home
    val totalFlightDistance: Double = 0.0, // meters
    val flightDurationSeconds: Long = 0,
    val alertMessage: String? = null,
    val timestamp: Long = System.currentTimeMillis()
) {
    fun toJson(): JSONObject {
        return JSONObject().apply {
            put("type", "telemetry")
            put("lat", lat)
            put("lon", lon)
            put("rawLat", rawLat)
            put("rawLon", rawLon)
            put("altitudeGps", (altitudeGps * 10.0).roundToInt() / 10.0)
            put("altitudeBaro", (altitudeBaro * 10.0).roundToInt() / 10.0)
            put("speed", (speed * 10.0).roundToInt() / 10.0)
            put("speedKmh", (speedKmh * 10.0).roundToInt() / 10.0)
            put("bearing", (bearing * 10.0).roundToInt() / 10.0)
            put("heading", (heading * 10.0).roundToInt() / 10.0)
            put("headingSource", headingSource)
            put("accuracy", (accuracy * 10.0).roundToInt() / 10.0)
            put("satellitesUsed", satellitesUsed)
            put("satellitesVisible", satellitesVisible)
            put("fixType", fixType)
            put("status", status)
            put("isMock", isMock)
            put("homeLat", homeLat)
            put("homeLon", homeLon)
            put("homeDistance", (homeDistance * 10.0).roundToInt() / 10.0)
            put("homeBearing", (homeBearing * 10.0).roundToInt() / 10.0)
            put("totalDistance", (totalFlightDistance * 10.0).roundToInt() / 10.0)
            put("flightTime", flightDurationSeconds)
            if (alertMessage != null) {
                put("alert", alertMessage)
            }
            put("timestamp", timestamp)
        }
    }

    companion object {
        fun calculateDistance(lat1: Double, lon1: Double, lat2: Double, lon2: Double): Double {
            val r = 6371000.0 // Earth radius in meters
            val dLat = Math.toRadians(lat2 - lat1)
            val dLon = Math.toRadians(lon2 - lon1)
            val a = sin(dLat / 2) * sin(dLat / 2) +
                    cos(Math.toRadians(lat1)) * cos(Math.toRadians(lat2)) *
                    sin(dLon / 2) * sin(dLon / 2)
            val c = 2 * atan2(sqrt(a), sqrt(1 - a))
            return r * c
        }

        fun calculateBearing(lat1: Double, lon1: Double, lat2: Double, lon2: Double): Float {
            val dLon = Math.toRadians(lon2 - lon1)
            val y = sin(dLon) * cos(Math.toRadians(lat2))
            val x = cos(Math.toRadians(lat1)) * sin(Math.toRadians(lat2)) -
                    sin(Math.toRadians(lat1)) * cos(Math.toRadians(lat2)) * cos(dLon)
            val b = Math.toDegrees(atan2(y, x))
            return ((b + 360.0) % 360.0).toFloat()
        }
    }
}
