package com.agrivyaan.optix.server

import android.content.Context
import android.util.Log
import com.agrivyaan.optix.audio.SoundManager
import com.agrivyaan.optix.network.NetworkHelper
import com.agrivyaan.optix.power.PowerManagerHelper
import fi.iki.elonen.NanoHTTPD
import fi.iki.elonen.NanoWSD
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import org.json.JSONObject
import java.io.InputStream
import java.util.UUID
import java.util.concurrent.ConcurrentHashMap

class ServerManager(
    private val context: Context,
    private val port: Int = 8080,
    private val powerManagerHelper: PowerManagerHelper,
    private val networkHelper: NetworkHelper,
    private val soundManager: SoundManager,
    private val onCommandReceived: (command: JSONObject, reply: (JSONObject) -> Unit) -> Unit
) : NanoWSD(port) {

    private val _connectedClientsCount = MutableStateFlow(0)
    val connectedClientsCount: StateFlow<Int> = _connectedClientsCount.asStateFlow()

    private val activeWebSockets = ConcurrentHashMap<String, OptixWebSocket>()
    private val serverScope = CoroutineScope(Dispatchers.Default)

    override fun openWebSocket(handshake: IHTTPSession): WebSocket {
        val socketId = UUID.randomUUID().toString()
        return OptixWebSocket(handshake, socketId)
    }

    override fun serveHttp(session: IHTTPSession): Response {
        val uri = session.uri
        val method = session.method

        fun withCors(response: Response): Response {
            response.addHeader("Access-Control-Allow-Origin", "*")
            response.addHeader("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            response.addHeader("Access-Control-Allow-Headers", "Content-Type, Authorization")
            return response
        }

        if (method == Method.OPTIONS) {
            return withCors(newFixedLengthResponse(Response.Status.OK, MIME_PLAINTEXT, ""))
        }

        // Static ground control assets
        if (uri == "/" || uri == "/index.html") {
            return withCors(serveAsset("ground/index.html", "text/html"))
        } else if (uri == "/app.js") {
            return withCors(serveAsset("ground/app.js", "application/javascript"))
        } else if (uri == "/style.css") {
            return withCors(serveAsset("ground/style.css", "text/css"))
        }

        // Available sounds list API
        if (uri == "/api/sounds" && method == Method.GET) {
            val jsonArray = soundManager.getSoundsJson()
            return withCors(newFixedLengthResponse(Response.Status.OK, "application/json", jsonArray.toString()))
        }

        // Audio file stream
        if (uri.startsWith("/sounds/")) {
            val fileName = uri.removePrefix("/sounds/")
            val stream = soundManager.openSoundAssetStream(fileName)
            return if (stream != null) {
                withCors(newChunkedResponse(Response.Status.OK, "audio/mpeg", stream))
            } else {
                withCors(newFixedLengthResponse(Response.Status.NOT_FOUND, MIME_PLAINTEXT, "Sound not found"))
            }
        }

        // Telemetry & Status API
        if (uri == "/api/status" && method == Method.GET) {
            val battery = powerManagerHelper.batteryInfo.value
            val signal = networkHelper.signalInfo.value
            val json = JSONObject().apply {
                put("app", "Optix")
                put("status", "running")
                put("screenOn", powerManagerHelper.isScreenOn())
                put("batteryLevel", battery.level)
                put("isCharging", battery.isCharging)
                put("temperatureCelsius", battery.temperatureCelsius)
                put("isOverheating", battery.isOverheating)
                put("wifiRssi", signal.rssiDbm)
                put("wifiPercent", signal.signalPercent)
                put("ipAddress", signal.ip)
                put("connectedClients", _connectedClientsCount.value)
            }
            return withCors(newFixedLengthResponse(Response.Status.OK, "application/json", json.toString()))
        }

        if (uri == "/api/auth") {
            val resp = JSONObject().apply {
                put("success", true)
                put("token", "optix_open_session")
            }
            return withCors(newFixedLengthResponse(Response.Status.OK, "application/json", resp.toString()))
        }

        return withCors(newFixedLengthResponse(Response.Status.NOT_FOUND, MIME_PLAINTEXT, "Not Found"))
    }

    private fun serveAsset(assetPath: String, mimeType: String): Response {
        return try {
            val inputStream: InputStream = context.assets.open(assetPath)
            newChunkedResponse(Response.Status.OK, mimeType, inputStream)
        } catch (e: Exception) {
            Log.e(TAG, "Error opening asset $assetPath", e)
            newFixedLengthResponse(Response.Status.NOT_FOUND, MIME_PLAINTEXT, "Asset not found: $assetPath")
        }
    }

    fun broadcastJson(json: JSONObject) {
        val text = json.toString()
        for (ws in activeWebSockets.values) {
            try {
                if (ws.isOpen) {
                    ws.send(text)
                }
            } catch (e: Exception) {
                Log.e(TAG, "Failed to broadcast message", e)
            }
        }
    }

    inner class OptixWebSocket(handshake: IHTTPSession, val id: String) : WebSocket(handshake) {

        override fun onOpen() {
            activeWebSockets[id] = this
            _connectedClientsCount.value = activeWebSockets.size
            Log.d(TAG, "Client connected: $id (Total: ${activeWebSockets.size})")
        }

        override fun onClose(code: WebSocketFrame.CloseCode?, reason: String?, initiatedByRemote: Boolean) {
            activeWebSockets.remove(id)
            _connectedClientsCount.value = activeWebSockets.size
            Log.d(TAG, "Client disconnected: $id (Total: ${activeWebSockets.size})")
        }

        override fun onMessage(message: WebSocketFrame) {
            try {
                val text = message.textPayload
                val json = JSONObject(text)

                // Dispatch asynchronously so the WebSocket frame reader thread is never blocked
                serverScope.launch {
                    onCommandReceived(json) { responseJson ->
                        try {
                            if (isOpen) {
                                send(responseJson.toString())
                            }
                        } catch (e: Exception) {
                            Log.e(TAG, "Failed to send command reply", e)
                        }
                    }
                }
            } catch (e: Exception) {
                Log.e(TAG, "WebSocket onMessage error", e)
            }
        }

        override fun onPong(pong: WebSocketFrame?) {}

        override fun onException(exception: java.io.IOException?) {
            Log.e(TAG, "WebSocket exception: $id", exception)
        }
    }

    companion object {
        private const val TAG = "ServerManager"
    }
}
