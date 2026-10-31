package com.agrivyaan.optix.server

import android.content.Context
import android.util.Log
import com.agrivyaan.optix.audio.SoundManager
import com.agrivyaan.optix.gps.GpsTelemetry
import com.agrivyaan.optix.gps.TrackDatabase
import com.agrivyaan.optix.map.FlightMissionManager
import com.agrivyaan.optix.map.MbTilesManager
import com.agrivyaan.optix.map.Waypoint
import com.agrivyaan.optix.network.NetworkHelper
import com.agrivyaan.optix.power.PowerManagerHelper
import com.agrivyaan.optix.recording.PhotoManager
import com.agrivyaan.optix.recording.RecordingManager
import fi.iki.elonen.NanoHTTPD
import fi.iki.elonen.NanoWSD
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import org.json.JSONArray
import org.json.JSONObject
import java.io.ByteArrayInputStream
import java.io.File
import java.io.FileInputStream
import java.io.InputStream
import java.util.UUID
import java.util.concurrent.ConcurrentHashMap

class ServerManager(
    private val context: Context,
    private val port: Int = 8080,
    private val powerManagerHelper: PowerManagerHelper,
    private val networkHelper: NetworkHelper,
    private val soundManager: SoundManager,
    private val recordingManager: RecordingManager,
    private val trackDatabase: TrackDatabase? = null,
    private val mbTilesManager: MbTilesManager? = null,
    private val flightMissionManager: FlightMissionManager? = null,
    private val photoManager: PhotoManager? = null,
    private val getGpsTelemetry: (() -> GpsTelemetry)? = null,
    private val onCommandReceived: (clientId: String, command: JSONObject, reply: (JSONObject) -> Unit) -> Unit,
    private val onClientDisconnected: ((clientId: String) -> Unit)? = null
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
        } else if (uri.startsWith("/leaflet/")) {
            val assetPath = "ground$uri"
            val mime = when {
                uri.endsWith(".js") -> "application/javascript"
                uri.endsWith(".css") -> "text/css"
                uri.endsWith(".png") -> "image/png"
                else -> "application/octet-stream"
            }
            return withCors(serveAsset(assetPath, mime))
        }

        // Offline MBTiles Tile Server (/tiles/{layer}/{z}/{x}/{y}.png)
        if (uri.startsWith("/tiles/")) {
            val parts = uri.removePrefix("/tiles/").split("/")
            val layer = if (parts.size >= 4) parts[0] else "default"
            val z = if (parts.size >= 4) parts[1].toIntOrNull() else parts.getOrNull(0)?.toIntOrNull()
            val x = if (parts.size >= 4) parts[2].toIntOrNull() else parts.getOrNull(1)?.toIntOrNull()
            val yStr = if (parts.size >= 4) parts[3] else parts.getOrNull(2)
            val y = yStr?.substringBefore(".")?.toIntOrNull()

            if (z != null && x != null && y != null && mbTilesManager != null) {
                val tileBytes = mbTilesManager.getTile(layer, z, x, y)
                if (tileBytes != null && tileBytes.isNotEmpty()) {
                    val mime = if (tileBytes.size > 2 && tileBytes[0] == 0xFF.toByte() && tileBytes[1] == 0xD8.toByte()) "image/jpeg" else "image/png"
                    val response = newFixedLengthResponse(Response.Status.OK, mime, ByteArrayInputStream(tileBytes), tileBytes.size.toLong())
                    response.addHeader("Cache-Control", "public, max-age=604800")
                    return withCors(response)
                }
            }
            return withCors(newFixedLengthResponse(Response.Status.NO_CONTENT, "image/png", ""))
        }

        // Available sounds list API
        if (uri == "/api/sounds" && method == Method.GET) {
            val jsonArray = soundManager.getSoundsJson()
            return withCors(newFixedLengthResponse(Response.Status.OK, "application/json", jsonArray.toString()))
        }

        // Recorded footages list API
        if (uri == "/api/recordings" && method == Method.GET) {
            val jsonArray = recordingManager.getRecordingsJson()
            return withCors(newFixedLengthResponse(Response.Status.OK, "application/json", jsonArray.toString()))
        }

        // Delete recording API
        if ((uri.startsWith("/api/recordings/") || uri == "/api/recordings/delete") && (method == Method.POST || method == Method.DELETE)) {
            val fileName = if (uri.startsWith("/api/recordings/")) {
                uri.removePrefix("/api/recordings/")
            } else {
                session.parameters["fileName"]?.firstOrNull() ?: ""
            }
            val deleted = recordingManager.deleteRecording(fileName)
            val resp = JSONObject().apply {
                put("success", deleted)
                put("fileName", fileName)
            }
            return withCors(newFixedLengthResponse(Response.Status.OK, "application/json", resp.toString()))
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

        // Recorded MP4 video footage download & stream
        if (uri.startsWith("/recordings/")) {
            val fileName = uri.removePrefix("/recordings/")
            val file = recordingManager.getRecordingFile(fileName)
            return if (file != null && file.exists()) {
                val stream = FileInputStream(file)
                val isDownload = session.parameters["download"]?.firstOrNull() == "1"
                val disposition = if (isDownload) "attachment; filename=\"$fileName\"" else "inline; filename=\"$fileName\""
                val response = newFixedLengthResponse(Response.Status.OK, "video/mp4", stream, file.length()).apply {
                    addHeader("Content-Disposition", disposition)
                    addHeader("Accept-Ranges", "bytes")
                }
                withCors(response)
            } else {
                withCors(newFixedLengthResponse(Response.Status.NOT_FOUND, MIME_PLAINTEXT, "Recording not found"))
            }
        }

        // Recorded photo snapshots download & stream
        if (uri.startsWith("/photos/")) {
            val fileName = uri.removePrefix("/photos/")
            val file = photoManager?.getPhotoFile(fileName)
            return if (file != null && file.exists()) {
                val stream = FileInputStream(file)
                val isDownload = session.parameters["download"]?.firstOrNull() == "1"
                val disposition = if (isDownload) "attachment; filename=\"$fileName\"" else "inline; filename=\"$fileName\""
                val response = newFixedLengthResponse(Response.Status.OK, "image/jpeg", stream, file.length()).apply {
                    addHeader("Content-Disposition", disposition)
                }
                withCors(response)
            } else {
                withCors(newFixedLengthResponse(Response.Status.NOT_FOUND, MIME_PLAINTEXT, "Photo not found"))
            }
        }

        // Map Layers API
        if (uri == "/api/maps" && method == Method.GET) {
            val jsonArray = mbTilesManager?.getLayersJson() ?: JSONArray()
            return withCors(newFixedLengthResponse(Response.Status.OK, "application/json", jsonArray.toString()))
        }

        if (uri == "/api/maps/estimate" && method == Method.GET) {
            val minLat = session.parameters["minLat"]?.firstOrNull()?.toDoubleOrNull() ?: 0.0
            val minLon = session.parameters["minLon"]?.firstOrNull()?.toDoubleOrNull() ?: 0.0
            val maxLat = session.parameters["maxLat"]?.firstOrNull()?.toDoubleOrNull() ?: 0.0
            val maxLon = session.parameters["maxLon"]?.firstOrNull()?.toDoubleOrNull() ?: 0.0
            val minZ = session.parameters["minZoom"]?.firstOrNull()?.toIntOrNull() ?: 10
            val maxZ = session.parameters["maxZoom"]?.firstOrNull()?.toIntOrNull() ?: 16
            val count = mbTilesManager?.estimateTileCount(minLat, minLon, maxLat, maxLon, minZ, maxZ) ?: 0L
            val estBytes = count * 20 * 1024L
            val resp = JSONObject().apply {
                put("totalTiles", count)
                put("estBytes", estBytes)
                put("estMb", (estBytes / (1024.0 * 1024.0) * 10.0).toInt() / 10.0)
            }
            return withCors(newFixedLengthResponse(Response.Status.OK, "application/json", resp.toString()))
        }

        if (uri == "/api/maps/download" && method == Method.POST) {
            val map = HashMap<String, String>()
            session.parseBody(map)
            val postData = map["postData"] ?: ""
            val json = if (postData.isNotEmpty()) JSONObject(postData) else JSONObject()
            val name = json.optString("name", "custom_map")
            val urlTemplate = json.optString("urlTemplate", "")
            val minLat = json.optDouble("minLat", 0.0)
            val minLon = json.optDouble("minLon", 0.0)
            val maxLat = json.optDouble("maxLat", 0.0)
            val maxLon = json.optDouble("maxLon", 0.0)
            val minZ = json.optInt("minZoom", 10)
            val maxZ = json.optInt("maxZoom", 16)

            val started = mbTilesManager?.startDownloadArea(name, urlTemplate, minLat, minLon, maxLat, maxLon, minZ, maxZ) ?: false
            val resp = JSONObject().apply {
                put("success", started)
            }
            return withCors(newFixedLengthResponse(Response.Status.OK, "application/json", resp.toString()))
        }

        if (uri == "/api/maps/download/progress" && method == Method.GET) {
            val progress = mbTilesManager?.getDownloadProgress() ?: JSONObject()
            return withCors(newFixedLengthResponse(Response.Status.OK, "application/json", progress.toString()))
        }

        if (uri == "/api/maps/download/pause" && method == Method.POST) {
            mbTilesManager?.pauseDownload()
            return withCors(newFixedLengthResponse(Response.Status.OK, "application/json", "{\"status\":\"paused\"}"))
        }

        if (uri == "/api/maps/download/resume" && method == Method.POST) {
            mbTilesManager?.resumeDownload()
            return withCors(newFixedLengthResponse(Response.Status.OK, "application/json", "{\"status\":\"running\"}"))
        }

        if (uri == "/api/maps/download/cancel" && method == Method.POST) {
            mbTilesManager?.cancelDownload()
            return withCors(newFixedLengthResponse(Response.Status.OK, "application/json", "{\"status\":\"cancelled\"}"))
        }

        if (uri == "/api/maps/delete" && (method == Method.POST || method == Method.DELETE)) {
            val layerId = session.parameters["id"]?.firstOrNull() ?: ""
            val deleted = mbTilesManager?.deleteLayer(layerId) ?: false
            val resp = JSONObject().apply {
                put("success", deleted)
                put("id", layerId)
            }
            return withCors(newFixedLengthResponse(Response.Status.OK, "application/json", resp.toString()))
        }

        // Tracks API
        if (uri == "/api/tracks" && method == Method.GET) {
            val sessions = trackDatabase?.getAllSessions() ?: emptyList()
            val array = JSONArray()
            for (s in sessions) array.put(s.toJson())
            return withCors(newFixedLengthResponse(Response.Status.OK, "application/json", array.toString()))
        }

        if (uri == "/api/tracks/points" && method == Method.GET) {
            val sessionId = session.parameters["sessionId"]?.firstOrNull() ?: ""
            val points = trackDatabase?.getSessionPoints(sessionId) ?: JSONArray()
            return withCors(newFixedLengthResponse(Response.Status.OK, "application/json", points.toString()))
        }

        if (uri == "/api/tracks/export" && method == Method.GET) {
            val sessionId = session.parameters["sessionId"]?.firstOrNull() ?: ""
            val format = session.parameters["format"]?.firstOrNull()?.lowercase() ?: "gpx"
            val file = when (format) {
                "kml" -> trackDatabase?.exportKml(sessionId)
                "csv" -> trackDatabase?.exportCsv(sessionId)
                else -> trackDatabase?.exportGpx(sessionId)
            }
            return if (file != null && file.exists()) {
                val stream = FileInputStream(file)
                val mime = when (format) {
                    "kml" -> "application/vnd.google-earth.kml+xml"
                    "csv" -> "text/csv"
                    else -> "application/gpx+xml"
                }
                val response = newFixedLengthResponse(Response.Status.OK, mime, stream, file.length()).apply {
                    addHeader("Content-Disposition", "attachment; filename=\"${file.name}\"")
                }
                withCors(response)
            } else {
                withCors(newFixedLengthResponse(Response.Status.NOT_FOUND, MIME_PLAINTEXT, "Track not found"))
            }
        }

        if (uri == "/api/tracks/delete" && (method == Method.POST || method == Method.DELETE)) {
            val sessionId = session.parameters["sessionId"]?.firstOrNull() ?: ""
            val deleted = trackDatabase?.deleteSession(sessionId) ?: false
            val resp = JSONObject().apply {
                put("success", deleted)
                put("sessionId", sessionId)
            }
            return withCors(newFixedLengthResponse(Response.Status.OK, "application/json", resp.toString()))
        }

        // Waypoints & Fields & Geofence
        if (uri == "/api/waypoints" && method == Method.GET) {
            val array = flightMissionManager?.getWaypointsJson() ?: JSONArray()
            return withCors(newFixedLengthResponse(Response.Status.OK, "application/json", array.toString()))
        }

        if (uri == "/api/waypoints" && method == Method.POST) {
            val map = HashMap<String, String>()
            session.parseBody(map)
            val json = JSONObject(map["postData"] ?: "{}")
            val wp = Waypoint(
                name = json.optString("name", "Waypoint"),
                lat = json.optDouble("lat", 0.0),
                lon = json.optDouble("lon", 0.0),
                category = json.optString("category", "Marker"),
                description = json.optString("description", "")
            )
            val added = flightMissionManager?.addWaypoint(wp) ?: false
            val resp = JSONObject().apply {
                put("success", added)
                put("waypoint", wp.toJson())
            }
            return withCors(newFixedLengthResponse(Response.Status.OK, "application/json", resp.toString()))
        }

        if (uri == "/api/waypoints/delete" && (method == Method.POST || method == Method.DELETE)) {
            val id = session.parameters["id"]?.firstOrNull() ?: ""
            val deleted = flightMissionManager?.deleteWaypoint(id) ?: false
            val resp = JSONObject().apply {
                put("success", deleted)
                put("id", id)
            }
            return withCors(newFixedLengthResponse(Response.Status.OK, "application/json", resp.toString()))
        }

        if (uri == "/api/fields" && method == Method.GET) {
            val array = flightMissionManager?.getFieldsJson() ?: JSONArray()
            return withCors(newFixedLengthResponse(Response.Status.OK, "application/json", array.toString()))
        }

        if (uri == "/api/fields" && method == Method.POST) {
            val map = HashMap<String, String>()
            session.parseBody(map)
            val json = JSONObject(map["postData"] ?: "{}")
            val name = json.optString("name", "Field")
            val ptsJson = json.optJSONArray("points") ?: JSONArray()
            val pts = mutableListOf<Pair<Double, Double>>()
            for (i in 0 until ptsJson.length()) {
                val p = ptsJson.getJSONArray(i)
                pts.add(Pair(p.getDouble(0), p.getDouble(1)))
            }
            val field = flightMissionManager?.saveField(name, pts)
            val resp = JSONObject().apply {
                put("success", field != null)
                if (field != null) put("field", field.toJson())
            }
            return withCors(newFixedLengthResponse(Response.Status.OK, "application/json", resp.toString()))
        }

        if (uri == "/api/fields/delete" && (method == Method.POST || method == Method.DELETE)) {
            val id = session.parameters["id"]?.firstOrNull() ?: ""
            val deleted = flightMissionManager?.deleteField(id) ?: false
            val resp = JSONObject().apply {
                put("success", deleted)
                put("id", id)
            }
            return withCors(newFixedLengthResponse(Response.Status.OK, "application/json", resp.toString()))
        }

        if (uri == "/api/geofence" && method == Method.GET) {
            val fm = flightMissionManager
            val resp = JSONObject().apply {
                put("active", fm?.isGeofenceActive ?: false)
                put("radiusMeters", fm?.geofenceRadiusMeters ?: 300.0)
                put("fieldId", fm?.geofenceFieldId ?: "")
            }
            return withCors(newFixedLengthResponse(Response.Status.OK, "application/json", resp.toString()))
        }

        if (uri == "/api/geofence" && method == Method.POST) {
            val map = HashMap<String, String>()
            session.parseBody(map)
            val json = JSONObject(map["postData"] ?: "{}")
            val fm = flightMissionManager
            if (fm != null) {
                if (json.has("active")) fm.isGeofenceActive = json.optBoolean("active", false)
                if (json.has("radiusMeters")) fm.geofenceRadiusMeters = json.optDouble("radiusMeters", 300.0)
                if (json.has("fieldId")) fm.geofenceFieldId = json.optString("fieldId", "")
            }
            val resp = JSONObject().apply {
                put("success", true)
                put("active", fm?.isGeofenceActive ?: false)
                put("radiusMeters", fm?.geofenceRadiusMeters ?: 300.0)
            }
            return withCors(newFixedLengthResponse(Response.Status.OK, "application/json", resp.toString()))
        }

        if (uri == "/api/photos" && method == Method.GET) {
            val array = photoManager?.getPhotosJson() ?: JSONArray()
            return withCors(newFixedLengthResponse(Response.Status.OK, "application/json", array.toString()))
        }

        if (uri == "/api/photos/delete" && (method == Method.POST || method == Method.DELETE)) {
            val fileName = session.parameters["fileName"]?.firstOrNull() ?: ""
            val deleted = photoManager?.deletePhoto(fileName) ?: false
            val resp = JSONObject().apply {
                put("success", deleted)
                put("fileName", fileName)
            }
            return withCors(newFixedLengthResponse(Response.Status.OK, "application/json", resp.toString()))
        }

        if (uri == "/api/telemetry" && method == Method.GET) {
            val t = getGpsTelemetry?.invoke()?.toJson() ?: JSONObject()
            return withCors(newFixedLengthResponse(Response.Status.OK, "application/json", t.toString()))
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
                put("isRecording", recordingManager.isRecording.value)
                put("recordingStartTime", recordingManager.recordingStartTime.value)
                put("recordingsCount", recordingManager.getRecordingsCount())
                put("deviceAdminActive", powerManagerHelper.isDeviceAdminActive())
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

    fun sendToClient(clientId: String, json: JSONObject) {
        val ws = activeWebSockets[clientId]
        if (ws != null && ws.isOpen) {
            try {
                ws.send(json.toString())
            } catch (e: Exception) {
                Log.e(TAG, "Failed to send message to client $clientId", e)
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
            onClientDisconnected?.invoke(id)
        }

        override fun onMessage(message: WebSocketFrame) {
            try {
                val text = message.textPayload
                val json = JSONObject(text)

                // Dispatch asynchronously so the WebSocket frame reader thread is never blocked
                serverScope.launch {
                    onCommandReceived(id, json) { responseJson ->
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
