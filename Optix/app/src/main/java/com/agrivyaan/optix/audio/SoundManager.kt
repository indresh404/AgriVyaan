package com.agrivyaan.optix.audio

import android.content.Context
import android.content.res.AssetFileDescriptor
import android.media.AudioAttributes
import android.media.MediaPlayer
import android.util.Log
import org.json.JSONArray
import org.json.JSONObject
import java.io.InputStream

data class SoundEffect(
    val id: String,
    val fileName: String,
    val label: String,
    val assetPath: String
)

class SoundManager(private val context: Context) {

    private val tag = "SoundManager"
    private var mediaPlayer: MediaPlayer? = null

    fun getAvailableSounds(): List<SoundEffect> {
        val soundList = mutableListOf<SoundEffect>()
        val audioExtensions = listOf(".mp3", ".wav", ".ogg", ".m4a")

        try {
            // Check assets/sounds/
            val soundsFolder = context.assets.list("sounds") ?: emptyArray()
            for (file in soundsFolder) {
                if (audioExtensions.any { file.endsWith(it, ignoreCase = true) }) {
                    val label = formatLabel(file)
                    soundList.add(SoundEffect(file, file, label, "sounds/$file"))
                }
            }

            // Check root assets/
            val rootFolder = context.assets.list("") ?: emptyArray()
            for (file in rootFolder) {
                if (audioExtensions.any { file.endsWith(it, ignoreCase = true) }) {
                    if (soundList.none { it.fileName == file }) {
                        val label = formatLabel(file)
                        soundList.add(SoundEffect(file, file, label, file))
                    }
                }
            }
        } catch (e: Exception) {
            Log.e(tag, "Error listing asset sounds", e)
        }

        return soundList
    }

    private fun formatLabel(fileName: String): String {
        val baseName = fileName.substringBeforeLast(".")
        return baseName.replace("_", " ").replace("-", " ")
            .split(" ")
            .joinToString(" ") { it.replaceFirstChar { c -> c.uppercase() } }
    }

    fun playSound(fileName: String): Boolean {
        return try {
            stopSound()
            val sounds = getAvailableSounds()
            val sound = sounds.find { it.fileName == fileName } ?: sounds.firstOrNull()

            if (sound == null) {
                Log.w(tag, "Sound file not found: $fileName")
                return false
            }

            val afd: AssetFileDescriptor = context.assets.openFd(sound.assetPath)
            mediaPlayer = MediaPlayer().apply {
                setAudioAttributes(
                    AudioAttributes.Builder()
                        .setContentType(AudioAttributes.CONTENT_TYPE_SONIFICATION)
                        .setUsage(AudioAttributes.USAGE_ALARM)
                        .build()
                )
                setDataSource(afd.fileDescriptor, afd.startOffset, afd.length)
                afd.close()
                prepare()
                start()
                setOnCompletionListener {
                    stopSound()
                }
            }
            Log.i(tag, "Playing sound effect: ${sound.label}")
            true
        } catch (e: Exception) {
            Log.e(tag, "Failed to play sound: $fileName", e)
            false
        }
    }

    fun stopSound() {
        try {
            mediaPlayer?.stop()
            mediaPlayer?.release()
            mediaPlayer = null
        } catch (_: Exception) {}
    }

    fun openSoundAssetStream(fileName: String): InputStream? {
        val sounds = getAvailableSounds()
        val sound = sounds.find { it.fileName == fileName } ?: return null
        return try {
            context.assets.open(sound.assetPath)
        } catch (e: Exception) {
            null
        }
    }

    fun getSoundsJson(): JSONArray {
        val array = JSONArray()
        for (s in getAvailableSounds()) {
            array.put(JSONObject().apply {
                put("fileName", s.fileName)
                put("label", s.label)
                put("url", "/sounds/${s.fileName}")
            })
        }
        return array
    }
}
