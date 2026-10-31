package com.agrivyaan.optix.map

import android.content.Context
import android.database.sqlite.SQLiteDatabase
import android.net.Uri
import android.util.Log
import kotlinx.coroutines.*
import org.json.JSONArray
import org.json.JSONObject
import java.io.*
import java.net.HttpURLConnection
import java.net.URL
import java.util.concurrent.ConcurrentHashMap
import java.util.concurrent.atomic.AtomicBoolean
import kotlin.math.*

data class MapLayerInfo(
    val id: String,
    val name: String,
    val format: String, // "png", "jpg", "pbf"
    val sizeBytes: Long,
    val minZoom: Int,
    val maxZoom: Int,
    val file: File
) {
    fun toJson(): JSONObject {
        return JSONObject().apply {
            put("id", id)
            put("name", name)
            put("format", format)
            put("sizeMb", (sizeBytes / (1024.0 * 1024.0) * 10.0).roundToInt() / 10.0)
            put("minZoom", minZoom)
            put("maxZoom", maxZoom)
        }
    }
}

class MbTilesManager(private val context: Context) {

    private val tag = "MbTilesManager"
    private val mapsDir: File = File(context.getExternalFilesDir("maps") ?: context.filesDir, "offline_maps").apply {
        if (!exists()) mkdirs()
    }

    private val activeDatabases = ConcurrentHashMap<String, SQLiteDatabase>()
    private val layersCache = ConcurrentHashMap<String, MapLayerInfo>()

    // Tile download task
    private var downloadJob: Job? = null
    private val isDownloading = AtomicBoolean(false)
    private val isPaused = AtomicBoolean(false)
    private var downloadProgress = JSONObject()

    init {
        refreshLayers()
    }

    @Synchronized
    fun refreshLayers(): List<MapLayerInfo> {
        val list = mutableListOf<MapLayerInfo>()
        val files = mapsDir.listFiles { _, name -> name.endsWith(".mbtiles", ignoreCase = true) } ?: emptyArray()

        for (file in files) {
            val id = file.nameWithoutExtension.lowercase()
            try {
                var db = activeDatabases[id]
                if (db == null || !db.isOpen) {
                    db = SQLiteDatabase.openDatabase(file.absolutePath, null, SQLiteDatabase.OPEN_READONLY)
                    activeDatabases[id] = db
                }

                var format = "png"
                var minZoom = 0
                var maxZoom = 18

                // Read metadata if available
                try {
                    val cursor = db.rawQuery("SELECT name, value FROM metadata", null)
                    cursor.use {
                        while (it.moveToNext()) {
                            val key = it.getString(0)
                            val value = it.getString(1)
                            when (key.lowercase()) {
                                "format" -> format = value
                                "minzoom" -> minZoom = value.toIntOrNull() ?: 0
                                "maxzoom" -> maxZoom = value.toIntOrNull() ?: 18
                            }
                        }
                    }
                } catch (_: Exception) {}

                val info = MapLayerInfo(
                    id = id,
                    name = file.nameWithoutExtension.replace("_", " ").replace("-", " ")
                        .replaceFirstChar { it.uppercase() },
                    format = format,
                    sizeBytes = file.length(),
                    minZoom = minZoom,
                    maxZoom = maxZoom,
                    file = file
                )
                list.add(info)
                layersCache[id] = info
            } catch (e: Exception) {
                Log.w(tag, "Failed to inspect mbtiles: ${file.name}", e)
            }
        }
        return list
    }

    fun getLayersJson(): JSONArray {
        val array = JSONArray()
        for (layer in refreshLayers()) {
            array.put(layer.toJson())
        }
        return array
    }

    /**
     * Get image tile bytes for Slippy Map coordinates (z, x, y)
     * MBTiles uses TMS coordinates: tmsY = (1 << z) - 1 - y
     */
    fun getTile(layerId: String, z: Int, x: Int, y: Int): ByteArray? {
        val targetId = if (layerId.isEmpty() || layerId == "default") {
            layersCache.keys.firstOrNull() ?: return null
        } else {
            layerId.lowercase()
        }

        var db = activeDatabases[targetId]
        if (db == null || !db.isOpen) {
            val file = File(mapsDir, "$targetId.mbtiles")
            if (!file.exists()) return null
            try {
                db = SQLiteDatabase.openDatabase(file.absolutePath, null, SQLiteDatabase.OPEN_READONLY)
                activeDatabases[targetId] = db
            } catch (e: Exception) {
                Log.e(tag, "Cannot open mbtiles $targetId", e)
                return null
            }
        }

        val tmsY = (1 shl z) - 1 - y
        return try {
            val cursor = db.rawQuery(
                "SELECT tile_data FROM tiles WHERE zoom_level = ? AND tile_column = ? AND tile_row = ? LIMIT 1",
                arrayOf(z.toString(), x.toString(), tmsY.toString())
            )
            cursor.use {
                if (it.moveToFirst()) {
                    it.getBlob(0)
                } else {
                    null
                }
            }
        } catch (e: Exception) {
            Log.w(tag, "Error reading tile $z/$x/$y from $targetId: ${e.message}")
            null
        }
    }

    fun importMbTiles(sourceUri: Uri): Boolean {
        return try {
            val fileName = "imported_${System.currentTimeMillis()}.mbtiles"
            val destFile = File(mapsDir, fileName)
            context.contentResolver.openInputStream(sourceUri)?.use { input ->
                FileOutputStream(destFile).use { output ->
                    input.copyTo(output)
                }
            }
            refreshLayers()
            Log.i(tag, "Imported mbtiles: ${destFile.name} (${destFile.length()} bytes)")
            true
        } catch (e: Exception) {
            Log.e(tag, "Failed to import mbtiles", e)
            false
        }
    }

    fun deleteLayer(layerId: String): Boolean {
        return try {
            val id = layerId.lowercase()
            activeDatabases.remove(id)?.close()
            layersCache.remove(id)
            val file = File(mapsDir, "$id.mbtiles")
            if (file.exists()) file.delete() else false
        } catch (e: Exception) {
            Log.e(tag, "Failed to delete layer $layerId", e)
            false
        }
    }

    // Download Area Tool (Estimates count, downloads tiles into new MBTiles database)
    fun estimateTileCount(minLat: Double, minLon: Double, maxLat: Double, maxLon: Double, minZoom: Int, maxZoom: Int): Long {
        var total = 0L
        for (z in minZoom..maxZoom) {
            val (minX, maxY) = deg2tile(minLat, minLon, z)
            val (maxX, minY) = deg2tile(maxLat, maxLon, z)
            val countX = (abs(maxX - minX) + 1).toLong()
            val countY = (abs(maxY - minY) + 1).toLong()
            total += (countX * countY)
        }
        return total
    }

    fun startDownloadArea(
        name: String,
        urlTemplate: String,
        minLat: Double,
        minLon: Double,
        maxLat: Double,
        maxLon: Double,
        minZoom: Int,
        maxZoom: Int
    ): Boolean {
        if (isDownloading.get()) {
            Log.w(tag, "Download area is already active")
            return false
        }

        val totalTiles = estimateTileCount(minLat, minLon, maxLat, maxLon, minZoom, maxZoom)
        val sanitizedName = name.replace(Regex("[^a-zA-Z0-9_]"), "_").lowercase()
        val outputFile = File(mapsDir, "$sanitizedName.mbtiles")

        isDownloading.set(true)
        isPaused.set(false)

        downloadProgress = JSONObject().apply {
            put("status", "running")
            put("name", sanitizedName)
            put("total", totalTiles)
            put("completed", 0)
            put("percent", 0)
        }

        downloadJob = CoroutineScope(Dispatchers.IO).launch {
            Log.i(tag, "Starting offline map area download: $totalTiles tiles into $outputFile")
            var db: SQLiteDatabase? = null
            try {
                if (outputFile.exists()) outputFile.delete()
                db = SQLiteDatabase.openOrCreateDatabase(outputFile, null)
                db.execSQL("CREATE TABLE metadata (name text, value text);")
                db.execSQL("CREATE TABLE tiles (zoom_level integer, tile_column integer, tile_row integer, tile_data blob);")
                db.execSQL("CREATE UNIQUE INDEX tile_index on tiles (zoom_level, tile_column, tile_row);")

                db.execSQL("INSERT INTO metadata VALUES ('name', '$sanitizedName');")
                db.execSQL("INSERT INTO metadata VALUES ('format', 'png');")
                db.execSQL("INSERT INTO metadata VALUES ('minzoom', '$minZoom');")
                db.execSQL("INSERT INTO metadata VALUES ('maxzoom', '$maxZoom');")

                var completed = 0L

                for (z in minZoom..maxZoom) {
                    if (!isDownloading.get()) break
                    val (minX, maxY) = deg2tile(minLat, minLon, z)
                    val (maxX, minY) = deg2tile(maxLat, maxLon, z)

                    for (x in minX..maxX) {
                        for (y in minY..maxY) {
                            while (isPaused.get() && isDownloading.get()) {
                                delay(500)
                            }
                            if (!isDownloading.get()) break

                            val tmsY = (1 shl z) - 1 - y
                            val tileUrl = urlTemplate
                                .replace("{z}", z.toString())
                                .replace("{x}", x.toString())
                                .replace("{y}", y.toString())

                            val tileBytes = fetchTileFromUrl(tileUrl)
                            if (tileBytes != null && tileBytes.isNotEmpty()) {
                                try {
                                    val stmt = db.compileStatement("INSERT OR REPLACE INTO tiles VALUES (?, ?, ?, ?)")
                                    stmt.bindLong(1, z.toLong())
                                    stmt.bindLong(2, x.toLong())
                                    stmt.bindLong(3, tmsY.toLong())
                                    stmt.bindBlob(4, tileBytes)
                                    stmt.executeInsert()
                                } catch (e: Exception) {
                                    Log.w(tag, "Tile write error: ${e.message}")
                                }
                            }

                            completed++
                            if (completed % 10 == 0L || completed == totalTiles) {
                                val pct = ((completed.toDouble() / totalTiles) * 100).toInt()
                                downloadProgress.put("completed", completed)
                                downloadProgress.put("percent", pct)
                            }

                            // Mild delay to prevent saturating bandwidth
                            delay(20)
                        }
                    }
                }

                downloadProgress.put("status", if (isDownloading.get()) "completed" else "cancelled")
                Log.i(tag, "Finished offline map download: $completed / $totalTiles")
            } catch (e: Exception) {
                Log.e(tag, "Download area failed", e)
                downloadProgress.put("status", "error")
                downloadProgress.put("error", e.message ?: "Unknown error")
            } finally {
                db?.close()
                isDownloading.set(false)
                refreshLayers()
            }
        }
        return true
    }

    fun pauseDownload() {
        isPaused.set(true)
        downloadProgress.put("status", "paused")
    }

    fun resumeDownload() {
        isPaused.set(false)
        downloadProgress.put("status", "running")
    }

    fun cancelDownload() {
        isDownloading.set(false)
        downloadJob?.cancel()
        downloadProgress.put("status", "cancelled")
    }

    fun getDownloadProgress(): JSONObject = downloadProgress

    private fun fetchTileFromUrl(urlString: String): ByteArray? {
        return try {
            val url = URL(urlString)
            val conn = url.openConnection() as HttpURLConnection
            conn.connectTimeout = 4000
            conn.readTimeout = 4000
            conn.setRequestProperty("User-Agent", "Optix-DroneCam/1.0")
            if (conn.responseCode == 200) {
                conn.inputStream.use { it.readBytes() }
            } else {
                null
            }
        } catch (_: Exception) {
            null
        }
    }

    companion object {
        fun deg2tile(latDeg: Double, lonDeg: Double, zoom: Int): Pair<Int, Int> {
            val n = 1 shl zoom
            val x = ((lonDeg + 180.0) / 360.0 * n).toInt().coerceIn(0, n - 1)
            val latRad = Math.toRadians(latDeg)
            val y = ((1.0 - asinh(tan(latRad)) / Math.PI) / 2.0 * n).toInt().coerceIn(0, n - 1)
            return Pair(x, y)
        }
    }
}
