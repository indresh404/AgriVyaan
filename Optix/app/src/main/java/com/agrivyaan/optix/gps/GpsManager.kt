package com.agrivyaan.optix.gps

import android.annotation.SuppressLint
import android.content.Context
import android.content.pm.PackageManager
import android.hardware.Sensor
import android.hardware.SensorEvent
import android.hardware.SensorEventListener
import android.hardware.SensorManager
import android.location.*
import android.os.Build
import android.os.Looper
import android.os.SystemClock
import android.util.Log
import androidx.core.content.ContextCompat
import kotlinx.coroutines.*
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import java.util.concurrent.atomic.AtomicBoolean
import kotlin.math.abs

class GpsManager(
    private val context: Context,
    private val onTelemetryUpdated: (GpsTelemetry) -> Unit
) : LocationListener, SensorEventListener {

    private val tag = "GpsManager"
    private val locationManager = context.getSystemService(Context.LOCATION_SERVICE) as LocationManager
    private val sensorManager = context.getSystemService(Context.SENSOR_SERVICE) as SensorManager

    private val gpsScope = CoroutineScope(Dispatchers.Default + SupervisorJob())
    private val filter = GpsFilter()

    private val _currentTelemetry = MutableStateFlow(GpsTelemetry())
    val currentTelemetry: StateFlow<GpsTelemetry> = _currentTelemetry.asStateFlow()

    private val isRunning = AtomicBoolean(false)

    // Sensor Hardware
    private var rotationSensor: Sensor? = null
    private var pressureSensor: Sensor? = null
    private var accelSensor: Sensor? = null
    private var magSensor: Sensor? = null

    // Sensor State
    private var compassHeading = 0f
    private val rotationMatrix = FloatArray(9)
    private val orientationAngles = FloatArray(3)
    private val accelReading = FloatArray(3)
    private val magReading = FloatArray(3)
    private var hasAccel = false
    private var hasMag = false

    // Barometer State
    private var takeoffPressure = 0f
    private var currentPressure = 0f
    private var relativeBaroAltitude = 0.0

    // GNSS Satellites
    private var satellitesVisible = 0
    private var satellitesUsed = 0
    private var gnssCallback: GnssStatus.Callback? = null

    // Home Point & Stats
    private var homeLat: Double? = null
    private var homeLon: Double? = null
    private var hasAutoSetHome = false
    private var totalDistanceTraveled = 0.0
    private var lastRecordedLat: Double? = null
    private var lastRecordedLon: Double? = null
    private var trackingStartTime = 0L

    // Config
    var updateIntervalMs = 1000L // Default 1 Hz
    var accuracyThresholdMeters = 15.0f

    // Watchdog
    private var lastFixTimeMs = 0L
    private var watchdogJob: Job? = null

    init {
        rotationSensor = sensorManager.getDefaultSensor(Sensor.TYPE_ROTATION_VECTOR)
        pressureSensor = sensorManager.getDefaultSensor(Sensor.TYPE_PRESSURE)
        if (rotationSensor == null) {
            accelSensor = sensorManager.getDefaultSensor(Sensor.TYPE_ACCELEROMETER)
            magSensor = sensorManager.getDefaultSensor(Sensor.TYPE_MAGNETIC_FIELD)
        }
    }

    @SuppressLint("MissingPermission")
    fun start() {
        if (isRunning.getAndSet(true)) return
        Log.i(tag, "Starting GPS & Sensor Telemetry subsystem at ${updateIntervalMs}ms interval...")

        trackingStartTime = System.currentTimeMillis()
        totalDistanceTraveled = 0.0
        lastRecordedLat = null
        lastRecordedLon = null
        filter.reset()

        // 1. Check permissions
        if (!hasLocationPermissions()) {
            Log.w(tag, "Location permissions not granted!")
            _currentTelemetry.value = _currentTelemetry.value.copy(
                status = "no_permission",
                alertMessage = "Location permissions not granted on phone"
            )
            onTelemetryUpdated(_currentTelemetry.value)
            return
        }

        // 2. Register Sensors
        rotationSensor?.let {
            sensorManager.registerListener(this, it, SensorManager.SENSOR_DELAY_UI)
        } ?: run {
            accelSensor?.let { sensorManager.registerListener(this, it, SensorManager.SENSOR_DELAY_UI) }
            magSensor?.let { sensorManager.registerListener(this, it, SensorManager.SENSOR_DELAY_UI) }
        }

        pressureSensor?.let {
            sensorManager.registerListener(this, it, SensorManager.SENSOR_DELAY_UI)
            Log.i(tag, "Hardware Barometer sensor registered")
        }

        // 3. Register GNSS Status (API 24+)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.N) {
            gnssCallback = object : GnssStatus.Callback() {
                override fun onSatelliteStatusChanged(status: GnssStatus) {
                    val count = status.satelliteCount
                    var used = 0
                    for (i in 0 until count) {
                        if (status.usedInFix(i)) used++
                    }
                    satellitesVisible = count
                    satellitesUsed = used
                }
            }
            try {
                locationManager.registerGnssStatusCallback(gnssCallback!!, null)
            } catch (e: Exception) {
                Log.w(tag, "Failed to register GnssStatusCallback: ${e.message}")
            }
        }

        // 4. Register GPS updates
        try {
            if (locationManager.isProviderEnabled(LocationManager.GPS_PROVIDER)) {
                locationManager.requestLocationUpdates(
                    LocationManager.GPS_PROVIDER,
                    updateIntervalMs,
                    0f,
                    this,
                    Looper.getMainLooper()
                )
                Log.i(tag, "GPS_PROVIDER updates requested successfully")
            } else {
                Log.w(tag, "GPS_PROVIDER is disabled in phone settings!")
                _currentTelemetry.value = _currentTelemetry.value.copy(
                    status = "disabled",
                    alertMessage = "GPS hardware disabled in phone settings"
                )
                onTelemetryUpdated(_currentTelemetry.value)
            }

            // Also register NETWORK_PROVIDER as immediate coarse fallback
            if (locationManager.isProviderEnabled(LocationManager.NETWORK_PROVIDER)) {
                locationManager.requestLocationUpdates(
                    LocationManager.NETWORK_PROVIDER,
                    updateIntervalMs * 2,
                    0f,
                    this,
                    Looper.getMainLooper()
                )
            }
        } catch (e: Exception) {
            Log.e(tag, "Error registering location updates", e)
        }

        // 5. Start Watchdog loop to detect lost fixes
        startWatchdog()
    }

    fun stop() {
        if (!isRunning.getAndSet(false)) return
        Log.i(tag, "Stopping GPS & Sensor Telemetry...")
        watchdogJob?.cancel()
        watchdogJob = null

        try {
            locationManager.removeUpdates(this)
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.N && gnssCallback != null) {
                locationManager.unregisterGnssStatusCallback(gnssCallback!!)
                gnssCallback = null
            }
            sensorManager.unregisterListener(this)
        } catch (e: Exception) {
            Log.w(tag, "Error stopping GPS listener: ${e.message}")
        }
    }

    fun setUpdateInterval(intervalMs: Long) {
        if (updateIntervalMs == intervalMs) return
        updateIntervalMs = intervalMs.coerceIn(200L, 10000L)
        if (isRunning.get()) {
            stop()
            start()
        }
    }

    fun setHomePoint(lat: Double, lon: Double) {
        homeLat = lat
        homeLon = lon
        hasAutoSetHome = true
        Log.i(tag, "Home point set to: $lat, $lon")
        recalculateAndEmit()
    }

    fun resetHomePoint() {
        val curr = _currentTelemetry.value
        if (curr.lat != 0.0 && curr.lon != 0.0) {
            setHomePoint(curr.lat, curr.lon)
        }
    }

    fun calibrateTakeoffAltitude() {
        if (currentPressure > 0f) {
            takeoffPressure = currentPressure
            relativeBaroAltitude = 0.0
            Log.i(tag, "Takeoff barometric pressure calibrated at ${takeoffPressure} hPa")
            recalculateAndEmit()
        }
    }

    override fun onLocationChanged(loc: Location) {
        lastFixTimeMs = SystemClock.elapsedRealtime()

        val rawLat = loc.latitude
        val rawLon = loc.longitude
        val altGps = loc.altitude
        val speed = loc.speed // m/s
        val speedKmh = speed * 3.6f
        val bearing = loc.bearing // GPS track (0-360)
        val accuracy = loc.accuracy

        val isMock = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
            loc.isMock
        } else {
            @Suppress("DEPRECATION")
            loc.isFromMockProvider
        }

        // Heading selection: Speed > 1.0 m/s uses GPS bearing; low speed uses compass
        val (finalHeading, headingSource) = if (speed >= 1.0f && loc.hasBearing()) {
            Pair(bearing, "gps")
        } else {
            Pair(compassHeading, "compass")
        }

        // Apply smooth Kalman filter for live display
        val filtered = filter.filter(rawLat, rawLon, altGps, finalHeading, accuracy)

        // Automatic Home Point assignment on first high-accuracy fix
        if (!hasAutoSetHome && accuracy <= 10.0f && accuracy > 0f) {
            homeLat = rawLat
            homeLon = rawLon
            hasAutoSetHome = true
            Log.i(tag, "★ Auto-set HOME point at ($rawLat, $rawLon) with accuracy ${accuracy}m")
            if (takeoffPressure == 0f && currentPressure > 0f) {
                takeoffPressure = currentPressure
            }
        }

        // Accumulate distance
        if (accuracy < 25.0f) {
            val lastLat = lastRecordedLat
            val lastLon = lastRecordedLon
            if (lastLat != null && lastLon != null) {
                val d = GpsTelemetry.calculateDistance(lastLat, lastLon, rawLat, rawLon)
                if (d in 0.5..150.0) {
                    totalDistanceTraveled += d
                    lastRecordedLat = rawLat
                    lastRecordedLon = rawLon
                }
            } else {
                lastRecordedLat = rawLat
                lastRecordedLon = rawLon
            }
        }

        // Fix Type Assessment
        val fixType = when {
            satellitesUsed >= 4 -> "3D Fix"
            satellitesUsed in 1..3 -> "2D Fix"
            loc.hasAltitude() -> "3D Fix"
            else -> "Searching"
        }

        // Distance & Bearing to Home
        val (homeDist, homeBearing) = if (homeLat != null && homeLon != null) {
            Pair(
                GpsTelemetry.calculateDistance(rawLat, rawLon, homeLat!!, homeLon!!),
                GpsTelemetry.calculateBearing(rawLat, rawLon, homeLat!!, homeLon!!)
            )
        } else {
            Pair(0.0, 0f)
        }

        // Accuracy Alert
        val alert = if (accuracy > accuracyThresholdMeters) {
            "GPS accuracy degraded (${accuracy.toInt()}m > ${accuracyThresholdMeters.toInt()}m)"
        } else if (isMock) {
            "Warning: Mock GPS location active"
        } else {
            null
        }

        val duration = if (trackingStartTime > 0L) (System.currentTimeMillis() - trackingStartTime) / 1000L else 0L

        val telemetry = GpsTelemetry(
            lat = filtered.lat,
            lon = filtered.lon,
            rawLat = rawLat,
            rawLon = rawLon,
            altitudeGps = altGps,
            altitudeBaro = relativeBaroAltitude,
            speed = speed,
            speedKmh = speedKmh,
            bearing = bearing,
            heading = filtered.heading,
            headingSource = headingSource,
            accuracy = accuracy,
            satellitesUsed = satellitesUsed,
            satellitesVisible = satellitesVisible,
            fixType = fixType,
            status = "locked",
            isMock = isMock,
            homeLat = homeLat ?: 0.0,
            homeLon = homeLon ?: 0.0,
            homeDistance = homeDist,
            homeBearing = homeBearing,
            totalFlightDistance = totalDistanceTraveled,
            flightDurationSeconds = duration,
            alertMessage = alert,
            timestamp = System.currentTimeMillis()
        )

        _currentTelemetry.value = telemetry
        onTelemetryUpdated(telemetry)
    }

    override fun onSensorChanged(event: SensorEvent) {
        when (event.sensor.type) {
            Sensor.TYPE_ROTATION_VECTOR -> {
                SensorManager.getRotationMatrixFromVector(rotationMatrix, event.values)
                SensorManager.getOrientation(rotationMatrix, orientationAngles)
                val azimuthRad = orientationAngles[0]
                val azimuthDeg = (Math.toDegrees(azimuthRad.toDouble()) + 360.0) % 360.0
                compassHeading = azimuthDeg.toFloat()
            }
            Sensor.TYPE_ACCELEROMETER -> {
                System.arraycopy(event.values, 0, accelReading, 0, 3)
                hasAccel = true
                computeCompassFromAccelMag()
            }
            Sensor.TYPE_MAGNETIC_FIELD -> {
                System.arraycopy(event.values, 0, magReading, 0, 3)
                hasMag = true
                computeCompassFromAccelMag()
            }
            Sensor.TYPE_PRESSURE -> {
                val pressure = event.values[0]
                currentPressure = pressure
                if (takeoffPressure <= 0f) {
                    takeoffPressure = pressure
                }
                // Altitude calculation relative to takeoff reference pressure
                val altCurrent = SensorManager.getAltitude(SensorManager.PRESSURE_STANDARD_ATMOSPHERE, pressure)
                val altTakeoff = SensorManager.getAltitude(SensorManager.PRESSURE_STANDARD_ATMOSPHERE, takeoffPressure)
                relativeBaroAltitude = (altCurrent - altTakeoff).toDouble()
            }
        }
    }

    private fun computeCompassFromAccelMag() {
        if (hasAccel && hasMag) {
            if (SensorManager.getRotationMatrix(rotationMatrix, null, accelReading, magReading)) {
                SensorManager.getOrientation(rotationMatrix, orientationAngles)
                val azimuthRad = orientationAngles[0]
                val azimuthDeg = (Math.toDegrees(azimuthRad.toDouble()) + 360.0) % 360.0
                compassHeading = azimuthDeg.toFloat()
            }
        }
    }

    override fun onAccuracyChanged(sensor: Sensor?, accuracy: Int) {}

    override fun onProviderEnabled(provider: String) {
        Log.i(tag, "Location provider enabled: $provider")
    }

    override fun onProviderDisabled(provider: String) {
        Log.w(tag, "Location provider disabled: $provider")
        if (provider == LocationManager.GPS_PROVIDER) {
            _currentTelemetry.value = _currentTelemetry.value.copy(
                status = "disabled",
                alertMessage = "GPS hardware disabled on phone"
            )
            onTelemetryUpdated(_currentTelemetry.value)
        }
    }

    @Deprecated("Deprecated in Java")
    override fun onStatusChanged(provider: String?, status: Int, extras: android.os.Bundle?) {}

    private fun startWatchdog() {
        watchdogJob?.cancel()
        watchdogJob = gpsScope.launch {
            while (isActive && isRunning.get()) {
                delay(2000)
                val now = SystemClock.elapsedRealtime()
                val delta = now - lastFixTimeMs
                if (lastFixTimeMs > 0 && delta > 10000) {
                    // Lost fix for more than 10 seconds
                    val lostTelemetry = _currentTelemetry.value.copy(
                        status = "lost",
                        fixType = "Searching",
                        alertMessage = "GPS signal lost (>10s)"
                    )
                    _currentTelemetry.value = lostTelemetry
                    onTelemetryUpdated(lostTelemetry)
                }
            }
        }
    }

    private fun recalculateAndEmit() {
        val curr = _currentTelemetry.value
        val (homeDist, homeBearing) = if (homeLat != null && homeLon != null) {
            Pair(
                GpsTelemetry.calculateDistance(curr.rawLat, curr.rawLon, homeLat!!, homeLon!!),
                GpsTelemetry.calculateBearing(curr.rawLat, curr.rawLon, homeLat!!, homeLon!!)
            )
        } else {
            Pair(0.0, 0f)
        }
        val updated = curr.copy(
            homeLat = homeLat ?: 0.0,
            homeLon = homeLon ?: 0.0,
            homeDistance = homeDist,
            homeBearing = homeBearing
        )
        _currentTelemetry.value = updated
        onTelemetryUpdated(updated)
    }

    fun hasLocationPermissions(): Boolean {
        return ContextCompat.checkSelfPermission(context, android.Manifest.permission.ACCESS_FINE_LOCATION) == PackageManager.PERMISSION_GRANTED ||
                ContextCompat.checkSelfPermission(context, android.Manifest.permission.ACCESS_COARSE_LOCATION) == PackageManager.PERMISSION_GRANTED
    }
}
