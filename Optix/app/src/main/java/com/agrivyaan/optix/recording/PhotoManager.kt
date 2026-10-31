package com.agrivyaan.optix.recording

import android.content.Context
import android.media.ExifInterface
import android.media.MediaScannerConnection
import android.util.Log
import com.agrivyaan.optix.gps.GpsTelemetry
import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.io.FileOutputStream
import java.text.SimpleDateFormat
import java.util.*
import kotlin.math.abs

data class PhotoItem(
    val fileName: String,
    val fileSize: Long,
    val timestamp: Long,
    val lat: Double,
    val lon: Double,
    val altitude: Double,
    val downloadUrl: String
) {
    fun toJson(): JSONObject = JSONObject().apply {
        put("fileName", fileName)
        put("fileSize", fileSize)
        put("timestamp", timestamp)
        put("lat", lat)
        put("lon", lon)
        put("altitude", altitude)
        put("downloadUrl", downloadUrl)
    }
}

class PhotoManager(private val context: Context) {

    private val tag = "PhotoManager"
    val photosDir: File by lazy {
        val dir = context.getExternalFilesDir("photos") ?: File(context.filesDir, "photos")
        if (!dir.exists()) dir.mkdirs()
        dir
    }

    fun saveSnapshot(jpegBytes: ByteArray, telemetry: GpsTelemetry?): File? {
        return try {
            val sdf = SimpleDateFormat("yyyyMMdd_HHmmss", Locale.US)
            val time = System.currentTimeMillis()
            val fileName = "OPTIX_SNAP_${sdf.format(Date(time))}.jpg"
            val file = File(photosDir, fileName)

            FileOutputStream(file).use { it.write(jpegBytes) }

            // Write EXIF Geotagging
            if (telemetry != null && telemetry.rawLat != 0.0) {
                try {
                    val exif = ExifInterface(file.absolutePath)
                    writeGpsExif(exif, telemetry.rawLat, telemetry.rawLon, telemetry.altitudeGps, time)
                    exif.saveAttributes()
                    Log.i(tag, "Embedded EXIF GPS metadata: lat=${telemetry.rawLat}, lon=${telemetry.rawLon}")
                } catch (e: Exception) {
                    Log.w(tag, "Failed to write EXIF GPS metadata: ${e.message}")
                }
            }

            try {
                MediaScannerConnection.scanFile(context, arrayOf(file.absolutePath), arrayOf("image/jpeg"), null)
            } catch (_: Exception) {}

            Log.i(tag, "Snapshot saved: ${file.name} (${file.length()} bytes)")
            file
        } catch (e: Exception) {
            Log.e(tag, "Failed to save snapshot", e)
            null
        }
    }

    fun getPhotosJson(): JSONArray {
        val array = JSONArray()
        val files = photosDir.listFiles { _, name -> name.endsWith(".jpg", ignoreCase = true) } ?: emptyArray()
        files.sortByDescending { it.lastModified() }

        for (file in files) {
            var lat = 0.0
            var lon = 0.0
            var alt = 0.0
            try {
                val exif = ExifInterface(file.absolutePath)
                val latLong = FloatArray(2)
                if (exif.getLatLong(latLong)) {
                    lat = latLong[0].toDouble()
                    lon = latLong[1].toDouble()
                }
                alt = exif.getAltitude(0.0)
            } catch (_: Exception) {}

            array.put(
                PhotoItem(
                    fileName = file.name,
                    fileSize = file.length(),
                    timestamp = file.lastModified(),
                    lat = lat,
                    lon = lon,
                    altitude = alt,
                    downloadUrl = "/photos/${file.name}"
                ).toJson()
            )
        }
        return array
    }

    fun getPhotoFile(fileName: String): File? {
        val file = File(photosDir, fileName)
        return if (file.exists() && file.isFile) file else null
    }

    fun deletePhoto(fileName: String): Boolean {
        val file = File(photosDir, fileName)
        return if (file.exists()) file.delete() else false
    }

    private fun writeGpsExif(exif: ExifInterface, lat: Double, lon: Double, alt: Double, timestamp: Long) {
        exif.setAttribute(ExifInterface.TAG_GPS_LATITUDE, decimalToDms(lat))
        exif.setAttribute(ExifInterface.TAG_GPS_LATITUDE_REF, if (lat >= 0) "N" else "S")
        exif.setAttribute(ExifInterface.TAG_GPS_LONGITUDE, decimalToDms(lon))
        exif.setAttribute(ExifInterface.TAG_GPS_LONGITUDE_REF, if (lon >= 0) "E" else "W")

        if (alt != 0.0) {
            val altAbs = abs(alt)
            exif.setAttribute(ExifInterface.TAG_GPS_ALTITUDE, "${(altAbs * 1000).toInt()}/1000")
            exif.setAttribute(ExifInterface.TAG_GPS_ALTITUDE_REF, if (alt >= 0) "0" else "1")
        }

        val sdfDate = SimpleDateFormat("yyyy:MM:dd", Locale.US).apply { timeZone = TimeZone.getTimeZone("UTC") }
        val sdfTime = SimpleDateFormat("HH:mm:ss", Locale.US).apply { timeZone = TimeZone.getTimeZone("UTC") }
        exif.setAttribute(ExifInterface.TAG_GPS_DATESTAMP, sdfDate.format(Date(timestamp)))
        exif.setAttribute(ExifInterface.TAG_GPS_TIMESTAMP, sdfTime.format(Date(timestamp)))
    }

    private fun decimalToDms(coord: Double): String {
        val absCoord = abs(coord)
        val degrees = absCoord.toInt()
        val minutesDouble = (absCoord - degrees) * 60.0
        val minutes = minutesDouble.toInt()
        val seconds = ((minutesDouble - minutes) * 60.0 * 1000).toInt()
        return "$degrees/1,$minutes/1,$seconds/1000"
    }
}
