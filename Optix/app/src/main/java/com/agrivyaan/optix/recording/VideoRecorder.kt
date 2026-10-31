package com.agrivyaan.optix.recording

import android.content.Context
import android.media.MediaCodec
import android.media.MediaCodecInfo
import android.media.MediaFormat
import android.media.MediaMuxer
import android.opengl.GLES20
import android.os.Handler
import android.os.HandlerThread
import android.util.Log
import android.view.Surface
import org.webrtc.EglBase
import org.webrtc.GlRectDrawer
import org.webrtc.VideoFrame
import org.webrtc.VideoFrameDrawer
import org.webrtc.VideoSink
import java.io.File
import java.util.concurrent.atomic.AtomicBoolean

/**
 * Ultra-low latency, zero-lag hardware video recorder.
 * Encodes camera frames directly using Android's hardware H.264 encoder (MediaCodec)
 * via an OpenGL recordable surface, muxing directly to MP4 on local storage.
 * Runs completely on a dedicated background thread, offloading 100% of encoding
 * to hardware GPU/DSP without impacting live WebRTC streaming performance.
 */
class VideoRecorder(
    private val context: Context,
    private val outputFile: File,
    private val width: Int = 1280,
    private val height: Int = 720,
    private val fps: Int = 30,
    private val bitRate: Int = 6_000_000,
    private val sharedEglContext: EglBase.Context
) : VideoSink {

    private val tag = "VideoRecorder"

    private var handlerThread: HandlerThread? = null
    private var recordHandler: Handler? = null

    private var mediaCodec: MediaCodec? = null
    private var inputSurface: Surface? = null
    private var mediaMuxer: MediaMuxer? = null
    private var videoTrackIndex: Int = -1
    private var isMuxerStarted: Boolean = false

    private var recordEgl: EglBase? = null
    private var frameDrawer: VideoFrameDrawer? = null
    private var rectDrawer: GlRectDrawer? = null

    private val isRecording = AtomicBoolean(false)
    private val bufferInfo = MediaCodec.BufferInfo()

    private var startTimeNs: Long = 0L
    private var frameCount: Long = 0L

    fun start(): Boolean {
        if (isRecording.get()) return true

        return try {
            outputFile.parentFile?.mkdirs()
            if (outputFile.exists()) {
                outputFile.delete()
            }

            handlerThread = HandlerThread("OptixVideoRecorderThread").apply { start() }
            recordHandler = Handler(handlerThread!!.looper)

            // 1. Configure Hardware H.264 Encoder
            val format = MediaFormat.createVideoFormat(MediaFormat.MIMETYPE_VIDEO_AVC, width, height).apply {
                setInteger(MediaFormat.KEY_COLOR_FORMAT, MediaCodecInfo.CodecCapabilities.COLOR_FormatSurface)
                setInteger(MediaFormat.KEY_BIT_RATE, bitRate)
                setInteger(MediaFormat.KEY_FRAME_RATE, fps)
                setInteger(MediaFormat.KEY_I_FRAME_INTERVAL, 1) // 1s keyframe interval for instant seeking
                try {
                    setInteger(MediaFormat.KEY_BITRATE_MODE, MediaCodecInfo.EncoderCapabilities.BITRATE_MODE_VBR)
                } catch (_: Exception) {}
            }

            val codec = MediaCodec.createEncoderByType(MediaFormat.MIMETYPE_VIDEO_AVC)
            codec.configure(format, null, null, MediaCodec.CONFIGURE_FLAG_ENCODE)
            inputSurface = codec.createInputSurface()
            codec.start()
            mediaCodec = codec

            // 2. Configure MP4 Muxer
            mediaMuxer = MediaMuxer(outputFile.absolutePath, MediaMuxer.OutputFormat.MUXER_OUTPUT_MPEG_4)

            // 3. Initialize EGL & OpenGL Drawer on recorder thread
            val initLock = Object()
            var initSuccess = false

            recordHandler?.post {
                try {
                    val egl = EglBase.create(sharedEglContext, EglBase.CONFIG_RECORDABLE)
                    egl.createSurface(inputSurface)
                    egl.makeCurrent()
                    recordEgl = egl

                    frameDrawer = VideoFrameDrawer()
                    rectDrawer = GlRectDrawer()
                    initSuccess = true
                    Log.i(tag, "Hardware recorder EGL & Codec initialized: ${width}x${height} @ ${fps}fps ($bitRate bps)")
                } catch (e: Exception) {
                    Log.e(tag, "Failed to initialize recorder EGL on thread", e)
                } finally {
                    synchronized(initLock) {
                        initLock.notifyAll()
                    }
                }
            }

            synchronized(initLock) {
                initLock.wait(2000)
            }

            if (!initSuccess) {
                stop()
                return false
            }

            startTimeNs = 0L
            frameCount = 0L
            isRecording.set(true)
            Log.i(tag, "Video recording started -> ${outputFile.name}")
            true
        } catch (e: Exception) {
            Log.e(tag, "Failed to start VideoRecorder", e)
            stop()
            false
        }
    }

    override fun onFrame(frame: VideoFrame) {
        if (!isRecording.get()) return

        frame.retain()
        val handler = recordHandler ?: run {
            frame.release()
            return
        }

        handler.post {
            try {
                if (isRecording.get()) {
                    renderFrame(frame)
                }
            } catch (e: Exception) {
                Log.e(tag, "Error rendering recording frame", e)
            } finally {
                frame.release()
            }
        }
    }

    private fun renderFrame(frame: VideoFrame) {
        val egl = recordEgl ?: return
        val drawer = rectDrawer ?: return
        val vfd = frameDrawer ?: return

        egl.makeCurrent()
        GLES20.glClearColor(0f, 0f, 0f, 1f)
        GLES20.glClear(GLES20.GL_COLOR_BUFFER_BIT)

        // Draw frame with intrinsic rotation handling
        vfd.drawFrame(frame, drawer, null, 0, 0, width, height)

        val nowNs = System.nanoTime()
        if (startTimeNs == 0L) {
            startTimeNs = nowNs
        }
        val ptsNs = nowNs - startTimeNs

        egl.swapBuffers(ptsNs)
        frameCount++

        drainEncoder(false)
    }

    private fun drainEncoder(endOfStream: Boolean) {
        val codec = mediaCodec ?: return
        val muxer = mediaMuxer ?: return

        if (endOfStream) {
            try {
                codec.signalEndOfInputStream()
            } catch (e: Exception) {
                Log.w(tag, "Error signaling EOS to encoder", e)
            }
        }

        val timeoutUs = if (endOfStream) 10000L else 0L

        while (true) {
            val status = codec.dequeueOutputBuffer(bufferInfo, timeoutUs)
            if (status == MediaCodec.INFO_TRY_AGAIN_LATER) {
                if (!endOfStream) break else continue
            } else if (status == MediaCodec.INFO_OUTPUT_FORMAT_CHANGED) {
                if (isMuxerStarted) {
                    Log.w(tag, "Encoder format changed twice, ignoring")
                } else {
                    val newFormat = codec.outputFormat
                    videoTrackIndex = muxer.addTrack(newFormat)
                    muxer.start()
                    isMuxerStarted = true
                    Log.i(tag, "MediaMuxer started with track $videoTrackIndex format: $newFormat")
                }
            } else if (status >= 0) {
                val encodedData = codec.getOutputBuffer(status)
                if (encodedData != null) {
                    if ((bufferInfo.flags and MediaCodec.BUFFER_FLAG_CODEC_CONFIG) != 0) {
                        bufferInfo.size = 0
                    }

                    if (bufferInfo.size != 0) {
                        if (isMuxerStarted) {
                            encodedData.position(bufferInfo.offset)
                            encodedData.limit(bufferInfo.offset + bufferInfo.size)
                            muxer.writeSampleData(videoTrackIndex, encodedData, bufferInfo)
                        }
                    }

                    codec.releaseOutputBuffer(status, false)

                    if ((bufferInfo.flags and MediaCodec.BUFFER_FLAG_END_OF_STREAM) != 0) {
                        break
                    }
                }
            }
        }
    }

    fun stop(): File? {
        if (!isRecording.compareAndSet(true, false)) {
            return if (outputFile.exists() && outputFile.length() > 0) outputFile else null
        }

        Log.i(tag, "Stopping VideoRecorder (recorded $frameCount frames)...")
        val handler = recordHandler
        val stopLock = Object()

        handler?.post {
            try {
                drainEncoder(true)

                try {
                    mediaCodec?.stop()
                } catch (_: Exception) {}
                try {
                    mediaCodec?.release()
                } catch (_: Exception) {}
                mediaCodec = null

                if (isMuxerStarted) {
                    try {
                        mediaMuxer?.stop()
                    } catch (_: Exception) {}
                    try {
                        mediaMuxer?.release()
                    } catch (_: Exception) {}
                    mediaMuxer = null
                    isMuxerStarted = false
                }

                frameDrawer?.release()
                frameDrawer = null
                rectDrawer?.release()
                rectDrawer = null

                recordEgl?.release()
                recordEgl = null
                inputSurface?.release()
                inputSurface = null
            } catch (e: Exception) {
                Log.e(tag, "Error during recorder cleanup", e)
            } finally {
                synchronized(stopLock) {
                    stopLock.notifyAll()
                }
            }
        }

        synchronized(stopLock) {
            try {
                stopLock.wait(3000)
            } catch (_: Exception) {}
        }

        handlerThread?.quitSafely()
        try {
            handlerThread?.join(1000)
        } catch (_: Exception) {}
        handlerThread = null
        recordHandler = null

        val valid = outputFile.exists() && outputFile.length() > 1024
        Log.i(tag, "Recorder stopped. Output file: ${outputFile.name} (Valid: $valid, Size: ${outputFile.length()} bytes)")
        return if (valid) outputFile else null
    }
}
