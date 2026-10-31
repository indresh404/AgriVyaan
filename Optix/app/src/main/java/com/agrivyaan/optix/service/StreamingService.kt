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
import com.agrivyaan.optix.server.ServerManager
import com.agrivyaan.optix.webrtc.StreamMode
import com.agrivyaan.optix.webrtc.WebRtcManager
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import org.json.JSONObject

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
    val cameraMode: CameraMode = CameraMode.PHONE
)

class StreamingService : LifecycleService() {

    private lateinit var powerManagerHelper: PowerManagerHelper
    private lateinit var networkHelper: NetworkHelper
    private lateinit var mdnsHelper: MdnsHelper
    private lateinit var soundManager: SoundManager
    private var serverManager: ServerManager? = null
    private var webRtcManager: WebRtcManager? = null

    override fun onCreate() {
        super.onCreate()
        powerManagerHelper = PowerManagerHelper(this)
        networkHelper = NetworkHelper(this)
        mdnsHelper = MdnsHelper(this)
        soundManager = SoundManager(this)

        webRtcManager = WebRtcManager(this) { signalingJson ->
            serverManager?.broadcastJson(signalingJson)
        }

        createNotificationChannel()

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
                    statusText = if (streaming) "Live Streaming" else if (_uiState.value.clientsCount > 0) "Viewer Connected" else "Server Running"
                )
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
            serverManager = ServerManager(
                context = this,
                port = 8080,
                powerManagerHelper = powerManagerHelper,
                networkHelper = networkHelper,
                soundManager = soundManager,
                onCommandReceived = { cmdJson, reply ->
                    handleRemoteCommand(cmdJson, reply)
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

    private fun handleRemoteCommand(command: JSONObject, reply: (JSONObject) -> Unit) {
        val cmd = command.optString("cmd", "")
        val type = command.optString("type", "")
        Log.d(TAG, "Remote message received: cmd='$cmd', type='$type'")

        // WebRTC Signaling messages
        if (type == "answer") {
            val sdp = command.optString("sdp", "")
            if (sdp.isNotEmpty()) {
                webRtcManager?.handleRemoteAnswer(sdp)
            }
            return
        }

        if (type == "candidate") {
            val candidate = command.optString("candidate", "")
            val sdpMid = command.optString("sdpMid", "0")
            val sdpMLineIndex = command.optInt("sdpMLineIndex", 0)
            if (candidate.isNotEmpty()) {
                webRtcManager?.handleRemoteIceCandidate(candidate, sdpMid, sdpMLineIndex)
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
                Log.i(TAG, "Ground station requested Start Stream. Initializing WebRTC Offer...")
                val modeStr = command.optString("mode", "")
                if (modeStr.isNotEmpty()) {
                    val newMode = try {
                        CameraMode.valueOf(modeStr.uppercase())
                    } catch (_: Exception) {
                        CameraMode.PHONE
                    }
                    _uiState.value = _uiState.value.copy(cameraMode = newMode)
                    val streamMode = when (newMode) {
                        CameraMode.PHONE -> StreamMode.PHONE
                        CameraMode.USB -> StreamMode.USB
                        CameraMode.BOTH -> StreamMode.BOTH
                    }
                    webRtcManager?.setStreamMode(streamMode)
                } else {
                    webRtcManager?.ensureCameraRunning()
                    webRtcManager?.startStreamingToClient()
                }
                reply(JSONObject().apply {
                    put("type", "ack")
                    put("cmd", "start_stream")
                    put("status", "started")
                })
            }
            "stop_stream" -> {
                Log.i(TAG, "Ground station requested Stop Stream.")
                webRtcManager?.closePeerConnection()
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
                val locked = powerManagerHelper.lockScreenNow()
                reply(JSONObject().apply {
                    put("type", "ack")
                    put("cmd", "lock_screen")
                    put("success", locked)
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
                })
            }
            "set_mode" -> {
                val modeStr = command.optString("mode", "PHONE")
                val newMode = try {
                    CameraMode.valueOf(modeStr.uppercase())
                } catch (_: Exception) {
                    CameraMode.PHONE
                }
                _uiState.value = _uiState.value.copy(cameraMode = newMode)
                val streamMode = when (newMode) {
                    CameraMode.PHONE -> StreamMode.PHONE
                    CameraMode.USB -> StreamMode.USB
                    CameraMode.BOTH -> StreamMode.BOTH
                }
                webRtcManager?.setStreamMode(streamMode)
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

    private fun stopServer() {
        try {
            webRtcManager?.closePeerConnection()
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
        stopServer()
        webRtcManager?.release()
        webRtcManager = null
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

        fun setCameraMode(mode: CameraMode) {
            _uiState.value = _uiState.value.copy(cameraMode = mode)
        }
    }
}
