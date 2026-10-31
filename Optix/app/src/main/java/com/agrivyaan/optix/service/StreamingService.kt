package com.agrivyaan.optix.service

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.os.Build
import android.os.IBinder
import android.util.Log
import androidx.core.app.NotificationCompat
import androidx.lifecycle.LifecycleService
import androidx.lifecycle.lifecycleScope
import com.agrivyaan.optix.MainActivity
import com.agrivyaan.optix.R
import com.agrivyaan.optix.audio.SoundManager
import com.agrivyaan.optix.network.MdnsHelper
import com.agrivyaan.optix.network.NetworkHelper
import com.agrivyaan.optix.power.BatteryInfo
import com.agrivyaan.optix.power.PowerManagerHelper
import com.agrivyaan.optix.gps.GpsManager
import com.agrivyaan.optix.gps.GpsTelemetry
import com.agrivyaan.optix.gps.TrackDatabase
import com.agrivyaan.optix.map.FlightMissionManager
import com.agrivyaan.optix.map.MbTilesManager
import com.agrivyaan.optix.recording.PhotoManager
import com.agrivyaan.optix.recording.RecordingManager
import com.agrivyaan.optix.server.ServerManager
import com.agrivyaan.optix.webrtc.QualityPreset
import com.agrivyaan.optix.webrtc.StreamMode
import com.agrivyaan.optix.webrtc.WebRtcManager
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.text.SimpleDateFormat
import java.util.*

enum class CameraMode {
    PHONE, USB, BOTH
}

data class ServiceUiState(
    val isRunning: Boolean = false,
    val statusText: String = "Idle",
    val ipAddress: String = "127.0.0.1",
    val port: Int = 8080,
    val pin: String = "123456",
    val clientsCount: Int = 0,
    val batteryInfo: BatteryInfo = BatteryInfo(),
    val cameraMode: CameraMode = CameraMode.PHONE,
    val isRecording: Boolean = false,
    val recordingStartTime: Long = 0L,
    val recordingsCount: Int = 0,
    val isDeviceAdminActive: Boolean = false,
    val telemetry: GpsTelemetry = GpsTelemetry(),
    val qualityPreset: String = "AUTO"
)

class StreamingService : LifecycleService() {

    private lateinit var powerManagerHelper: PowerManagerHelper
    private lateinit var networkHelper: NetworkHelper
    private lateinit var mdnsHelper: MdnsHelper
    private lateinit var soundManager: SoundManager
    lateinit var recordingManager: RecordingManager
        private set
    lateinit var photoManager: PhotoManager
        private set
    lateinit var trackDatabase: TrackDatabase
        private set
    lateinit var mbTilesManager: MbTilesManager
        private set
    lateinit var flightMissionManager: FlightMissionManager
        private set
    lateinit var gpsManager: GpsManager
        private set

    private var serverManager: ServerManager? = null
    private var webRtcManager: WebRtcManager? = null

    private var isAdaptiveQualityEnabled = true
    private var currentQualityPresetName = "AUTO"
    private var adaptiveQualityJob: Job? = null

    override fun onCreate() {
        super.onCreate()
        instance = this
        powerManagerHelper = PowerManagerHelper(this)
        networkHelper = NetworkHelper(this)
        mdnsHelper = MdnsHelper(this)
        soundManager = SoundManager(this)
        recordingManager = RecordingManager(this) { webRtcManager }
        photoManager = PhotoManager(this)
        trackDatabase = TrackDatabase(this)
        mbTilesManager = MbTilesManager(this)
        flightMissionManager = FlightMissionManager(this)

        gpsManager = GpsManager(this) { telemetry ->
            trackDatabase.recordPoint(telemetry)
            val breachAlert = flightMissionManager.checkGeofence(
                telemetry.rawLat,
                telemetry.rawLon,
                telemetry.homeLat,
                telemetry.homeLon
            )
            val finalTelemetry = if (breachAlert != null) {
                telemetry.copy(alertMessage = breachAlert)
            } else {
                telemetry
            }

            val json = finalTelemetry.toJson()
            val sentOverDc = webRtcManager?.broadcastDataChannel(json.toString()) ?: false
            if (!sentOverDc) {
                serverManager?.broadcastJson(json)
            }

            _uiState.value = _uiState.value.copy(telemetry = finalTelemetry)
        }

        recordingManager.getTelemetry = { gpsManager.currentTelemetry.value }

        webRtcManager = WebRtcManager(this) { clientId, signalingJson ->
            if (clientId.isEmpty() || clientId == "*") {
                serverManager?.broadcastJson(signalingJson)
            } else {
                serverManager?.sendToClient(clientId, signalingJson)
            }
        }

        createNotificationChannel()

        // Check Device Admin status
        _uiState.value = _uiState.value.copy(
            isDeviceAdminActive = powerManagerHelper.isDeviceAdminActive(),
            recordingsCount = recordingManager.getRecordingsCount()
        )

        // Observe network IP
        lifecycleScope.launch {
            networkHelper.ipAddress.collect { ip ->
                _uiState.value = _uiState.value.copy(ipAddress = ip)
                updateNotification("Listening at http://$ip:8080")
            }
        }

        // Observe battery
        lifecycleScope.launch {
            powerManagerHelper.batteryInfo.collect { batt ->
                _uiState.value = _uiState.value.copy(batteryInfo = batt)
            }
        }

        // Observe streaming state
        lifecycleScope.launch {
            webRtcManager?.isStreaming?.collect { streaming ->
                _uiState.value = _uiState.value.copy(
                    statusText = if (_uiState.value.isRecording) "Recording & Streaming" else if (streaming) "Live Streaming" else if (_uiState.value.clientsCount > 0) "Viewer Connected" else "Server Running"
                )
            }
        }

        // Observe recording state
        lifecycleScope.launch {
            recordingManager.isRecording.collect { recording ->
                _uiState.value = _uiState.value.copy(
                    isRecording = recording,
                    recordingsCount = recordingManager.getRecordingsCount(),
                    statusText = if (recording) "Recording in Progress" else if (webRtcManager?.isStreaming?.value == true) "Live Streaming" else if (_uiState.value.clientsCount > 0) "Viewer Connected" else "Server Running"
                )
                if (recording) {
                    updateNotification("🔴 RECORDING ACTIVE • http://${_uiState.value.ipAddress}:8080")
                }
            }
        }

        lifecycleScope.launch {
            recordingManager.recordingStartTime.collect { startTime ->
                _uiState.value = _uiState.value.copy(recordingStartTime = startTime)
            }
        }
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        super.onStartCommand(intent, flags, startId)
        val action = intent?.action ?: ACTION_START_STREAMING

        when (action) {
            ACTION_START_STREAMING, ACTION_START_SERVER_ONLY -> {
                startServiceForeground()
                startServer()
            }
            ACTION_USB_PERMISSION_GRANTED -> {
                Log.i(TAG, "ACTION_USB_PERMISSION_GRANTED received. Restarting USB capture pipeline...")
                webRtcManager?.requestUsbPermission()
            }
            ACTION_STOP_STREAMING -> {
                stopServer()
                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.N) {
                    stopForeground(STOP_FOREGROUND_REMOVE)
                } else {
                    @Suppress("DEPRECATION")
                    stopForeground(true)
                }
                stopSelf()
            }
        }

        return START_STICKY
    }

    private fun startServiceForeground() {
        val notification = buildNotification("Optix Server starting...")
        startForeground(NOTIFICATION_ID, notification)
        powerManagerHelper.acquireLocks()
        networkHelper.startMonitoring()
        mdnsHelper.registerService(8080, "dronecam")
    }

    private fun startServer() {
        if (serverManager != null) return

        try {
            gpsManager.start()
            trackDatabase.startSession()
            startAdaptiveQualityLoop()

            serverManager = ServerManager(
                context = this,
                port = 8080,
                powerManagerHelper = powerManagerHelper,
                networkHelper = networkHelper,
                soundManager = soundManager,
                recordingManager = recordingManager,
                trackDatabase = trackDatabase,
                mbTilesManager = mbTilesManager,
                flightMissionManager = flightMissionManager,
                photoManager = photoManager,
                getGpsTelemetry = { gpsManager.currentTelemetry.value },
                onCommandReceived = { clientId, cmdJson, reply ->
                    handleRemoteCommand(clientId, cmdJson, reply)
                },
                onClientDisconnected = { clientId ->
                    Log.i(TAG, "Client disconnected: $clientId, releasing its WebRTC stream")
                    webRtcManager?.closeClientConnection(clientId)
                }
            ).apply {
                start()
            }

            lifecycleScope.launch {
                serverManager?.connectedClientsCount?.collect { count ->
                    _uiState.value = _uiState.value.copy(
                        clientsCount = count,
                        statusText = if (count > 0) "Viewer Connected" else "Server Running"
                    )
                    updateNotification("Clients: $count | IP: ${_uiState.value.ipAddress}")
                }
            }

            _uiState.value = _uiState.value.copy(
                isRunning = true,
                statusText = "Server Running",
                port = 8080
            )

            Log.i(TAG, "ServerManager started on port 8080 (Free access, no PIN)")
        } catch (e: Exception) {
            Log.e(TAG, "Failed to start ServerManager", e)
            _uiState.value = _uiState.value.copy(
                isRunning = false,
                statusText = "Server Error: ${e.message}"
            )
        }
    }

    private fun handleRemoteCommand(clientId: String, command: JSONObject, reply: (JSONObject) -> Unit) {
        val cmd = command.optString("cmd", "")
        val type = command.optString("type", "")
        Log.d(TAG, "Remote message received from [$clientId]: cmd='$cmd', type='$type'")

        // WebRTC Signaling messages
        if (type == "answer") {
            val sdp = command.optString("sdp", "")
            if (sdp.isNotEmpty()) {
                webRtcManager?.handleRemoteAnswer(clientId, sdp)
            }
            return
        }

        if (type == "candidate") {
            val candidate = command.optString("candidate", "")
            val sdpMid = command.optString("sdpMid", "0")
            val sdpMLineIndex = command.optInt("sdpMLineIndex", 0)
            if (candidate.isNotEmpty()) {
                webRtcManager?.handleRemoteIceCandidate(clientId, candidate, sdpMid, sdpMLineIndex)
            }
            return
        }

        when (cmd) {
            "ping" -> {
                reply(JSONObject().apply {
                    put("type", "ack")
                    put("cmd", "ping")
                    put("timestamp", System.currentTimeMillis())
                })
            }
            "start_stream", "request_stream" -> {
                Log.i(TAG, "Ground station [$clientId] requested Start Stream. (Current active mode: ${_uiState.value.cameraMode})")
                val modeStr = command.optString("mode", "")
                val activeViewers = webRtcManager?.clientPeerConnectionsCount ?: 0
                // Only adapt mode if there are no existing active viewers; otherwise preserve running stream mode
                if (modeStr.isNotEmpty() && activeViewers == 0) {
                    val requestedMode = try {
                        CameraMode.valueOf(modeStr.uppercase())
                    } catch (_: Exception) {
                        CameraMode.PHONE
                    }
                    if (requestedMode != _uiState.value.cameraMode) {
                        _uiState.value = _uiState.value.copy(cameraMode = requestedMode)
                        val streamMode = when (requestedMode) {
                            CameraMode.PHONE -> StreamMode.PHONE
                            CameraMode.USB -> StreamMode.USB
                            CameraMode.BOTH -> StreamMode.BOTH
                        }
                        webRtcManager?.setStreamMode(streamMode)
                    }
                }
                webRtcManager?.ensureCameraRunning()
                webRtcManager?.startStreamingToClient(clientId)
                reply(JSONObject().apply {
                    put("type", "ack")
                    put("cmd", "start_stream")
                    put("status", "started")
                    put("mode", _uiState.value.cameraMode.name)
                })
            }
            "stop_stream" -> {
                Log.i(TAG, "Ground station [$clientId] requested Stop Stream.")
                webRtcManager?.closeClientConnection(clientId)
                reply(JSONObject().apply {
                    put("type", "ack")
                    put("cmd", "stop_stream")
                    put("status", "stopped")
                })
            }
            "toggle_torch" -> {
                val isOn = webRtcManager?.toggleTorch() ?: false
                reply(JSONObject().apply {
                    put("type", "ack")
                    put("cmd", "toggle_torch")
                    put("torchOn", isOn)
                })
            }
            "toggle_strobe" -> {
                val isStrobe = webRtcManager?.toggleStrobe() ?: false
                reply(JSONObject().apply {
                    put("type", "ack")
                    put("cmd", "toggle_strobe")
                    put("strobeOn", isStrobe)
                })
            }
            "play_sound" -> {
                val file = command.optString("file", "sound_effect_1.mp3")
                val success = soundManager.playSound(file)
                reply(JSONObject().apply {
                    put("type", "ack")
                    put("cmd", "play_sound")
                    put("file", file)
                    put("success", success)
                })
            }
            "stop_sound" -> {
                soundManager.stopSound()
                reply(JSONObject().apply {
                    put("type", "ack")
                    put("cmd", "stop_sound")
                })
            }
            "torch" -> {
                val isOn = webRtcManager?.toggleTorch() ?: false
                reply(JSONObject().apply {
                    put("type", "ack")
                    put("cmd", "torch")
                    put("torchOn", isOn)
                })
            }
            "switch_camera" -> {
                webRtcManager?.switchCamera()
                reply(JSONObject().apply {
                    put("type", "ack")
                    put("cmd", "switch_camera")
                })
            }
            "set_quality" -> {
                val width = command.optInt("width", 1280)
                val height = command.optInt("height", 720)
                val fps = command.optInt("fps", 30)
                webRtcManager?.setQualityPreset(width, height, fps)
                reply(JSONObject().apply {
                    put("type", "ack")
                    put("cmd", "set_quality")
                    put("width", width)
                    put("height", height)
                    put("fps", fps)
                })
            }
            "wake_screen" -> {
                powerManagerHelper.wakeScreen()
                reply(JSONObject().apply {
                    put("type", "ack")
                    put("cmd", "wake_screen")
                    put("screenOn", powerManagerHelper.isScreenOn())
                })
            }
            "lock_screen" -> {
                val isAdmin = powerManagerHelper.isDeviceAdminActive()
                val locked = if (isAdmin) powerManagerHelper.lockScreenNow() else false
                reply(JSONObject().apply {
                    put("type", "ack")
                    put("cmd", "lock_screen")
                    put("success", locked)
                    put("deviceAdminActive", isAdmin)
                    if (!isAdmin) {
                        put("error", "Device Administrator is not enabled on the drone phone. Please open Optix app Pre-Flight settings to enable.")
                    }
                })
            }
            "start_recording" -> {
                val success = recordingManager.startRecording()
                val fileName = recordingManager.currentFileName.value
                val startTime = recordingManager.recordingStartTime.value
                reply(JSONObject().apply {
                    put("type", "ack")
                    put("cmd", "start_recording")
                    put("success", success)
                    put("fileName", fileName)
                    put("startTime", startTime)
                })
                if (success) {
                    serverManager?.broadcastJson(JSONObject().apply {
                        put("type", "recording_state")
                        put("isRecording", true)
                        put("fileName", fileName)
                        put("startTime", startTime)
                    })
                }
            }
            "stop_recording" -> {
                val savedFile = recordingManager.stopRecording()
                val success = savedFile != null
                val fileName = savedFile?.name ?: ""
                reply(JSONObject().apply {
                    put("type", "ack")
                    put("cmd", "stop_recording")
                    put("success", success)
                    put("fileName", fileName)
                    put("fileSize", savedFile?.length() ?: 0L)
                })
                serverManager?.broadcastJson(JSONObject().apply {
                    put("type", "recording_state")
                    put("isRecording", false)
                    put("fileName", fileName)
                })
            }
            "get_recordings" -> {
                reply(JSONObject().apply {
                    put("type", "ack")
                    put("cmd", "get_recordings")
                    put("recordings", recordingManager.getRecordingsJson())
                })
            }
            "delete_recording" -> {
                val fileName = command.optString("fileName", "")
                val deleted = recordingManager.deleteRecording(fileName)
                reply(JSONObject().apply {
                    put("type", "ack")
                    put("cmd", "delete_recording")
                    put("fileName", fileName)
                    put("success", deleted)
                })
            }
            "request_usb_permission" -> {
                Log.i(TAG, "Requesting USB camera permission...")
                powerManagerHelper.wakeScreen()
                val launchIntent = Intent(this, MainActivity::class.java).apply {
                    addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_SINGLE_TOP)
                }
                startActivity(launchIntent)
                webRtcManager?.requestUsbPermission()
                reply(JSONObject().apply {
                    put("type", "ack")
                    put("cmd", "request_usb_permission")
                })
            }
            "get_status" -> {
                val batt = powerManagerHelper.batteryInfo.value
                val sig = networkHelper.signalInfo.value
                reply(JSONObject().apply {
                    put("type", "state")
                    put("screenOn", powerManagerHelper.isScreenOn())
                    put("batteryLevel", batt.level)
                    put("temperatureCelsius", batt.temperatureCelsius)
                    put("wifiRssi", sig.rssiDbm)
                    put("wifiPercent", sig.signalPercent)
                    put("isStreaming", webRtcManager?.isStreaming?.value ?: false)
                    put("mode", _uiState.value.cameraMode.name)
                    put("isRecording", recordingManager.isRecording.value)
                    put("recordingStartTime", recordingManager.recordingStartTime.value)
                    put("recordingsCount", recordingManager.getRecordingsCount())
                    put("deviceAdminActive", powerManagerHelper.isDeviceAdminActive())
                    put("telemetry", gpsManager.currentTelemetry.value.toJson())
                    put("qualityPreset", currentQualityPresetName)
                })
            }
            "sync_track" -> {
                val since = command.optLong("since", 0L)
                val missed = trackDatabase.getMissedPoints(since)
                val ptsArray = JSONArray()
                for (p in missed) ptsArray.put(p.toJson())
                reply(JSONObject().apply {
                    put("type", "track_sync")
                    put("points", ptsArray)
                })
            }
            "set_home" -> {
                val lat = command.optDouble("lat", 0.0)
                val lon = command.optDouble("lon", 0.0)
                if (lat != 0.0 && lon != 0.0) {
                    gpsManager.setHomePoint(lat, lon)
                } else {
                    gpsManager.resetHomePoint()
                }
                reply(JSONObject().apply {
                    put("type", "ack")
                    put("cmd", "set_home")
                    put("success", true)
                })
            }
            "calibrate_baro" -> {
                gpsManager.calibrateTakeoffAltitude()
                reply(JSONObject().apply {
                    put("type", "ack")
                    put("cmd", "calibrate_baro")
                    put("success", true)
                })
            }
            "set_gps_rate" -> {
                val rateMs = command.optLong("intervalMs", 1000L)
                gpsManager.setUpdateInterval(rateMs)
                reply(JSONObject().apply {
                    put("type", "ack")
                    put("cmd", "set_gps_rate")
                    put("intervalMs", rateMs)
                })
            }
            "set_camera_quality" -> {
                val presetStr = command.optString("preset", "AUTO").uppercase()
                currentQualityPresetName = presetStr
                if (presetStr == "AUTO") {
                    isAdaptiveQualityEnabled = true
                    startAdaptiveQualityLoop()
                } else {
                    isAdaptiveQualityEnabled = false
                    val preset = when (presetStr) {
                        "FAST" -> QualityPreset.FAST_LOW_LATENCY
                        "HIGH" -> QualityPreset.HIGH_FIDELITY
                        else -> QualityPreset.BALANCED
                    }
                    webRtcManager?.applyQualityPreset(preset)
                }
                _uiState.value = _uiState.value.copy(qualityPreset = currentQualityPresetName)
                reply(JSONObject().apply {
                    put("type", "ack")
                    put("cmd", "set_camera_quality")
                    put("preset", currentQualityPresetName)
                })
            }
            "take_snapshot" -> {
                val tel = gpsManager.currentTelemetry.value
                val width = 1280
                val height = 720
                val bitmap = android.graphics.Bitmap.createBitmap(width, height, android.graphics.Bitmap.Config.ARGB_8888)
                val canvas = android.graphics.Canvas(bitmap)
                canvas.drawColor(android.graphics.Color.BLACK)
                val paint = android.graphics.Paint().apply {
                    color = android.graphics.Color.WHITE
                    textSize = 40f
                    isAntiAlias = true
                }
                val tsText = SimpleDateFormat("yyyy-MM-dd HH:mm:ss", Locale.US).format(Date())
                canvas.drawText("OPTIX DRONECAM FPV SNAPSHOT", 60f, 90f, paint)
                paint.textSize = 28f
                canvas.drawText("UTC: $tsText", 60f, 140f, paint)
                canvas.drawText("LAT: ${tel.rawLat} | LON: ${tel.rawLon}", 60f, 190f, paint)
                canvas.drawText("ALT (GPS): ${tel.altitudeGps}m | REL (BARO): ${tel.altitudeBaro}m", 60f, 240f, paint)
                canvas.drawText("SPEED: ${tel.speedKmh} km/h | HDG: ${tel.heading.toInt()}°", 60f, 290f, paint)

                val bos = java.io.ByteArrayOutputStream()
                bitmap.compress(android.graphics.Bitmap.CompressFormat.JPEG, 92, bos)
                val photoFile = photoManager.saveSnapshot(bos.toByteArray(), tel)

                reply(JSONObject().apply {
                    put("type", "ack")
                    put("cmd", "take_snapshot")
                    put("success", photoFile != null)
                    if (photoFile != null) {
                        put("fileName", photoFile.name)
                        put("lat", tel.rawLat)
                        put("lon", tel.rawLon)
                        put("altitude", tel.altitudeGps)
                        put("downloadUrl", "/photos/${photoFile.name}")
                    }
                })

                if (photoFile != null) {
                    serverManager?.broadcastJson(JSONObject().apply {
                        put("type", "new_snapshot")
                        put("fileName", photoFile.name)
                        put("lat", tel.rawLat)
                        put("lon", tel.rawLon)
                        put("altitude", tel.altitudeGps)
                        put("downloadUrl", "/photos/${photoFile.name}")
                    })
                }
            }
            "set_mode" -> {
                val modeStr = command.optString("mode", "PHONE")
                val newMode = try {
                    CameraMode.valueOf(modeStr.uppercase())
                } catch (_: Exception) {
                    CameraMode.PHONE
                }
                if (newMode != _uiState.value.cameraMode) {
                    _uiState.value = _uiState.value.copy(cameraMode = newMode)
                    val streamMode = when (newMode) {
                        CameraMode.PHONE -> StreamMode.PHONE
                        CameraMode.USB -> StreamMode.USB
                        CameraMode.BOTH -> StreamMode.BOTH
                    }
                    webRtcManager?.setStreamMode(streamMode)
                    serverManager?.broadcastJson(JSONObject().apply {
                        put("type", "mode_changed")
                        put("mode", newMode.name)
                    })
                }
                reply(JSONObject().apply {
                    put("type", "ack")
                    put("cmd", "set_mode")
                    put("mode", newMode.name)
                })
            }
            else -> {
                reply(JSONObject().apply {
                    put("type", "ack")
                    put("cmd", cmd)
                })
            }
        }
    }

    private fun startAdaptiveQualityLoop() {
        adaptiveQualityJob?.cancel()
        adaptiveQualityJob = lifecycleScope.launch {
            while (isActive) {
                delay(3000)
                if (!isAdaptiveQualityEnabled) continue

                val rssi = networkHelper.signalInfo.value.rssiDbm
                if (rssi == 0) continue

                val targetPreset = when {
                    rssi < -78 -> QualityPreset.FAST_LOW_LATENCY
                    rssi in -78..-65 -> QualityPreset.BALANCED
                    else -> QualityPreset.HIGH_FIDELITY
                }
                webRtcManager?.applyQualityPreset(targetPreset)
            }
        }
    }

    private fun stopServer() {
        adaptiveQualityJob?.cancel()
        adaptiveQualityJob = null
        try {
            gpsManager.stop()
            trackDatabase.endSession()
        } catch (_: Exception) {}

        try {
            webRtcManager?.closeAllPeerConnections()
            webRtcManager?.stopCameraCapture()
        } catch (e: Exception) {
            Log.e(TAG, "Error stopping WebRTC", e)
        }

        try {
            serverManager?.stop()
            serverManager = null
        } catch (e: Exception) {
            Log.e(TAG, "Error stopping server", e)
        }

        mdnsHelper.unregisterService()
        networkHelper.stopMonitoring()
        powerManagerHelper.releaseLocks()

        _uiState.value = _uiState.value.copy(
            isRunning = false,
            statusText = "Idle",
            clientsCount = 0
        )
    }

    override fun onDestroy() {
        try {
            recordingManager.stopRecording()
        } catch (_: Exception) {}
        stopServer()
        webRtcManager?.release()
        webRtcManager = null
        instance = null
        super.onDestroy()
    }

    private fun createNotificationChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val channel = NotificationChannel(
                CHANNEL_ID,
                getString(R.string.channel_name),
                NotificationManager.IMPORTANCE_LOW
            ).apply {
                description = getString(R.string.channel_description)
                setShowBadge(false)
            }
            val manager = getSystemService(NotificationManager::class.java)
            manager?.createNotificationChannel(channel)
        }
    }

    private fun buildNotification(contentText: String): Notification {
        val launchIntent = Intent(this, MainActivity::class.java).apply {
            flags = Intent.FLAG_ACTIVITY_SINGLE_TOP
        }
        val pendingIntent = PendingIntent.getActivity(
            this,
            0,
            launchIntent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )

        return NotificationCompat.Builder(this, CHANNEL_ID)
            .setContentTitle("Optix Streaming Service")
            .setContentText(contentText)
            .setSmallIcon(R.mipmap.ic_launcher)
            .setContentIntent(pendingIntent)
            .setOngoing(true)
            .build()
    }

    private fun updateNotification(text: String) {
        val manager = getSystemService(NotificationManager::class.java)
        manager?.notify(NOTIFICATION_ID, buildNotification(text))
    }

    companion object {
        private const val TAG = "StreamingService"
        const val CHANNEL_ID = "optix_streaming_channel"
        const val NOTIFICATION_ID = 1001

        const val ACTION_START_STREAMING = "com.agrivyaan.optix.action.START_STREAMING"
        const val ACTION_STOP_STREAMING = "com.agrivyaan.optix.action.STOP_STREAMING"
        const val ACTION_START_SERVER_ONLY = "com.agrivyaan.optix.action.START_SERVER_ONLY"
        const val ACTION_USB_PERMISSION_GRANTED = "com.agrivyaan.optix.USB_PERMISSION_GRANTED"

        private val _uiState = MutableStateFlow(ServiceUiState())
        val uiState: StateFlow<ServiceUiState> = _uiState.asStateFlow()

        var instance: StreamingService? = null
            private set

        fun startRecording(): Boolean {
            return instance?.recordingManager?.startRecording() ?: false
        }

        fun stopRecording(): File? {
            return instance?.recordingManager?.stopRecording()
        }

        fun refreshDeviceAdminStatus() {
            instance?.let {
                _uiState.value = _uiState.value.copy(
                    isDeviceAdminActive = it.powerManagerHelper.isDeviceAdminActive(),
                    recordingsCount = it.recordingManager.getRecordingsCount()
                )
            }
        }

        fun setCameraMode(mode: CameraMode) {
            _uiState.value = _uiState.value.copy(cameraMode = mode)
        }
    }
}
