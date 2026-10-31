package com.agrivyaan.optix.recording

import android.content.Context
import android.media.MediaScannerConnection
import android.util.Log
import com.agrivyaan.optix.webrtc.WebRtcManager
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

data class RecordingItem(
    val fileName: String,
    val fileSize: Long,
    val sizeFormatted: String,
    val timestamp: Long,
    val dateFormatted: String,
    val downloadUrl: String
) {
    fun toJson(): JSONObject = JSONObject().apply {
        put("fileName", fileName)
        put("fileSize", fileSize)
        put("sizeFormatted", sizeFormatted)
        put("timestamp", timestamp)
        put("dateFormatted", dateFormatted)
        put("downloadUrl", downloadUrl)
    }
}

class RecordingManager(
    private val context: Context,
    private val getWebRtcManager: () -> WebRtcManager?
) {
    private val tag = "RecordingManager"

    val recordingsDir: File by lazy {
        val dir = context.getExternalFilesDir("recordings") ?: File(context.filesDir, "recordings")
        if (!dir.exists()) dir.mkdirs()
        dir
    }

    private val _isRecording = MutableStateFlow(false)
    val isRecording: StateFlow<Boolean> = _isRecording.asStateFlow()

    private val _recordingStartTime = MutableStateFlow(0L)
    val recordingStartTime: StateFlow<Long> = _recordingStartTime.asStateFlow()

    private val _currentFileName = MutableStateFlow("")
    val currentFileName: StateFlow<String> = _currentFileName.asStateFlow()

    private var activeRecorder: VideoRecorder? = null
    private var activeOutputFile: File? = null

    @Synchronized
    fun startRecording(
        width: Int = 1280,
        height: Int = 720,
        fps: Int = 30,
        bitRate: Int = 6_000_000
    ): Boolean {
        if (_isRecording.value) {
            Log.w(tag, "Recording is already active")
            return true
        }

        val rtc = getWebRtcManager()
        if (rtc == null) {
            Log.e(tag, "WebRtcManager not available to start recording")
            return false
        }

        rtc.ensureCameraRunning()

        val timeStamp = SimpleDateFormat("yyyyMMdd_HHmmss", Locale.US).format(Date())
        val fileName = "OPTIX_REC_${timeStamp}.mp4"
        val outputFile = File(recordingsDir, fileName)

        val recorder = VideoRecorder(
            context = context,
            outputFile = outputFile,
            width = width,
            height = height,
            fps = fps,
            bitRate = bitRate,
            sharedEglContext = rtc.eglContext
        )

        val started = recorder.start()
        if (!started) {
            Log.e(tag, "Failed to initialize and start VideoRecorder")
            return false
        }

        activeRecorder = recorder
        activeOutputFile = outputFile
        rtc.setRecordingSink(recorder)

        _isRecording.value = true
        _recordingStartTime.value = System.currentTimeMillis()
        _currentFileName.value = fileName

        Log.i(tag, "Continuous local recording started: $fileName")
        return true
    }

    @Synchronized
    fun stopRecording(): File? {
        if (!_isRecording.value && activeRecorder == null) {
            return null
        }

        Log.i(tag, "Stopping local recording...")
        val rtc = getWebRtcManager()
        rtc?.setRecordingSink(null)

        val recorder = activeRecorder
        activeRecorder = null
        val recordedFile = recorder?.stop()

        _isRecording.value = false
        _recordingStartTime.value = 0L
        val savedName = _currentFileName.value
        _currentFileName.value = ""

        if (recordedFile != null && recordedFile.exists()) {
            Log.i(tag, "Recording saved successfully: ${recordedFile.absolutePath} (${recordedFile.length()} bytes)")
            // Notify system media scanner so file is discoverable
            try {
                MediaScannerConnection.scanFile(
                    context,
                    arrayOf(recordedFile.absolutePath),
                    arrayOf("video/mp4"),
                    null
                )
            } catch (e: Exception) {
                Log.w(tag, "MediaScanner error", e)
            }
            return recordedFile
        } else {
            Log.w(tag, "Recorded file was empty or not generated for $savedName")
            return null
        }
    }

    fun getRecordingsList(): List<RecordingItem> {
        val files = recordingsDir.listFiles { file ->
            file.isFile && file.name.endsWith(".mp4", ignoreCase = true)
        } ?: return emptyList()

        val dateFormat = SimpleDateFormat("yyyy-MM-dd HH:mm:ss", Locale.US)

        return files.sortedByDescending { it.lastModified() }.map { file ->
            val size = file.length()
            val formattedSize = formatFileSize(size)
            val dateStr = dateFormat.format(Date(file.lastModified()))
            RecordingItem(
                fileName = file.name,
                fileSize = size,
                sizeFormatted = formattedSize,
                timestamp = file.lastModified(),
                dateFormatted = dateStr,
                downloadUrl = "/recordings/${file.name}"
            )
        }
    }

    fun getRecordingsJson(): JSONArray {
        val list = getRecordingsList()
        val array = JSONArray()
        for (item in list) {
            array.put(item.toJson())
        }
        return array
    }

    fun getRecordingFile(fileName: String): File? {
        // Sanitize to prevent directory traversal
        val sanitized = File(fileName).name
        val target = File(recordingsDir, sanitized)
        return if (target.exists() && target.isFile) target else null
    }

    fun deleteRecording(fileName: String): Boolean {
        val file = getRecordingFile(fileName) ?: return false
        val deleted = file.delete()
        Log.i(tag, "Delete recording '$fileName' result: $deleted")
        return deleted
    }

    fun getRecordingsCount(): Int {
        return recordingsDir.listFiles { f -> f.isFile && f.name.endsWith(".mp4", ignoreCase = true) }?.size ?: 0
    }

    private fun formatFileSize(bytes: Long): String {
        return when {
            bytes >= 1024 * 1024 * 1024 -> String.format(Locale.US, "%.2f GB", bytes / (1024.0 * 1024.0 * 1024.0))
            bytes >= 1024 * 1024 -> String.format(Locale.US, "%.1f MB", bytes / (1024.0 * 1024.0))
            bytes >= 1024 -> String.format(Locale.US, "%.1f KB", bytes / 1024.0)
            else -> "$bytes B"
        }
    }
}
