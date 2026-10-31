package com.agrivyaan.optix.camera

import android.annotation.SuppressLint
import android.content.ContentValues
import android.content.Context
import android.graphics.ImageFormat
import android.graphics.Rect
import android.hardware.camera2.*
import android.hardware.camera2.params.MeteringRectangle
import android.media.ImageReader
import android.os.Build
import android.os.Environment
import android.os.Handler
import android.os.HandlerThread
import android.provider.MediaStore
import android.util.Log
import android.util.Range
import android.view.Surface
import org.json.JSONArray
import org.json.JSONObject
import org.webrtc.*
import java.io.File
import java.io.FileOutputStream
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import kotlin.math.max
import kotlin.math.min

class PhoneCameraSource(
    private val context: Context,
    private val onCapabilitiesReady: ((JSONObject) -> Unit)? = null
) : VideoCapturer {

    private val tag = "PhoneCameraSource"

    private var surfaceTextureHelper: SurfaceTextureHelper? = null
    private var capturerObserver: CapturerObserver? = null

    private val cameraManager = context.getSystemService(Context.CAMERA_SERVICE) as CameraManager
    private var cameraDevice: CameraDevice? = null
    private var captureSession: CameraCaptureSession? = null
    private var previewRequestBuilder: CaptureRequest.Builder? = null
    private var previewSurface: Surface? = null
    private var imageReader: ImageReader? = null

    private var cameraThread: HandlerThread? = null
    private var cameraHandler: Handler? = null

    // Camera settings
    private var selectedCameraId: String = "0"
    private var isBackFacing: Boolean = true
    private var captureWidth = 1280
    private var captureHeight = 720
    private var captureFps = 30
    private var frameRotation = 0

    // Control States
    private var currentZoom: Float = 1.0f
    private var isTorchOn: Boolean = false
    private var currentExposure: Int = 0
    private var isAeLocked: Boolean = false
    private var currentWbMode: Int = CaptureRequest.CONTROL_AWB_MODE_AUTO

    // Hardware limits from characteristics
    private var minZoomRatio: Float = 1.0f
    private var maxZoomRatio: Float = 8.0f
    private var exposureRange: Range<Int> = Range(0, 0)
    private var exposureStep: Float = 1.0f
    private var hasTorch: Boolean = false
    private var activeSensorRect: Rect = Rect()

    init {
        startBackgroundThread()
        selectInitialCamera()
    }

    private fun startBackgroundThread() {
        cameraThread = HandlerThread("PhoneCameraBackgroundThread").apply { start() }
        cameraHandler = Handler(cameraThread!!.looper)
    }

    private fun stopBackgroundThread() {
        cameraThread?.quitSafely()
        try {
            cameraThread?.join()
            cameraThread = null
            cameraHandler = null
        } catch (_: Exception) {}
    }

    private fun selectInitialCamera() {
        try {
            for (id in cameraManager.cameraIdList) {
                val chars = cameraManager.getCameraCharacteristics(id)
                val facing = chars.get(CameraCharacteristics.LENS_FACING)
                if (facing == CameraCharacteristics.LENS_FACING_BACK) {
                    selectedCameraId = id
                    isBackFacing = true
                    readCameraCapabilities(chars)
                    break
                }
            }
        } catch (e: Exception) {
            Log.e(tag, "Failed to inspect cameras", e)
        }
    }

    private fun readCameraCapabilities(chars: CameraCharacteristics) {
        try {
            activeSensorRect = chars.get(CameraCharacteristics.SENSOR_INFO_ACTIVE_ARRAY_SIZE) ?: Rect(0, 0, 1920, 1080)
            hasTorch = chars.get(CameraCharacteristics.FLASH_INFO_AVAILABLE) ?: false

            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {
                val zoomRange = chars.get(CameraCharacteristics.CONTROL_ZOOM_RATIO_RANGE)
                if (zoomRange != null) {
                    minZoomRatio = zoomRange.lower
                    maxZoomRatio = zoomRange.upper
                }
            } else {
                val maxZoom = chars.get(CameraCharacteristics.SCALER_AVAILABLE_MAX_DIGITAL_ZOOM) ?: 1.0f
                minZoomRatio = 1.0f
                maxZoomRatio = max(maxZoom, 1.0f)
            }

            exposureRange = chars.get(CameraCharacteristics.CONTROL_AE_COMPENSATION_RANGE) ?: Range(0, 0)
            val rationalStep = chars.get(CameraCharacteristics.CONTROL_AE_COMPENSATION_STEP)
            exposureStep = rationalStep?.toFloat() ?: 1.0f

            Log.i(tag, "Camera $selectedCameraId limits: Zoom=[$minZoomRatio, $maxZoomRatio], Exp=[${exposureRange.lower}, ${exposureRange.upper}]")
            onCapabilitiesReady?.invoke(getCapabilitiesJson())
        } catch (e: Exception) {
            Log.e(tag, "Error reading camera capabilities", e)
        }
    }

    override fun initialize(
        helper: SurfaceTextureHelper,
        appContext: Context,
        observer: CapturerObserver
    ) {
        this.surfaceTextureHelper = helper
        this.capturerObserver = observer
    }

    override fun startCapture(width: Int, height: Int, framerate: Int) {
        Log.i(tag, "startCapture requested: ${width}x${height} @ ${framerate}fps")
        this.captureWidth = width
        this.captureHeight = height
        this.captureFps = framerate

        surfaceTextureHelper?.setTextureSize(width, height)
        surfaceTextureHelper?.setFrameRotation(frameRotation)

        surfaceTextureHelper?.startListening { videoFrame ->
            capturerObserver?.onFrameCaptured(videoFrame)
        }

        openCameraInternal()
    }

    @SuppressLint("MissingPermission")
    private fun openCameraInternal() {
        val handler = cameraHandler ?: return
        try {
            cameraManager.openCamera(selectedCameraId, object : CameraDevice.StateCallback() {
                override fun onOpened(camera: CameraDevice) {
                    cameraDevice = camera
                    startCaptureSession()
                    capturerObserver?.onCapturerStarted(true)
                }

                override fun onDisconnected(camera: CameraDevice) {
                    camera.close()
                    cameraDevice = null
                    capturerObserver?.onCapturerStopped()
                }

                override fun onError(camera: CameraDevice, error: Int) {
                    Log.e(tag, "Camera open error: $error")
                    camera.close()
                    cameraDevice = null
                    capturerObserver?.onCapturerStopped()
                }
            }, handler)
        } catch (e: Exception) {
            Log.e(tag, "Exception opening camera", e)
            capturerObserver?.onCapturerStopped()
        }
    }

    private fun startCaptureSession() {
        val camera = cameraDevice ?: return
        val helper = surfaceTextureHelper ?: return
        val handler = cameraHandler ?: return

        try {
            val texture = helper.surfaceTexture
            texture.setDefaultBufferSize(captureWidth, captureHeight)
            previewSurface = Surface(texture)

            imageReader = ImageReader.newInstance(captureWidth, captureHeight, ImageFormat.JPEG, 2)

            val surfaces = listOf(previewSurface!!, imageReader!!.surface)

            @Suppress("DEPRECATION")
            camera.createCaptureSession(surfaces, object : CameraCaptureSession.StateCallback() {
                override fun onConfigured(session: CameraCaptureSession) {
                    captureSession = session
                    applyRepeatingRequest()
                }

                override fun onConfigureFailed(session: CameraCaptureSession) {
                    Log.e(tag, "Capture session configuration failed")
                }
            }, handler)

        } catch (e: Exception) {
            Log.e(tag, "Failed to start capture session", e)
        }
    }

    private fun applyRepeatingRequest() {
        val camera = cameraDevice ?: return
        val session = captureSession ?: return
        val surface = previewSurface ?: return
        val handler = cameraHandler ?: return

        try {
            previewRequestBuilder = camera.createCaptureRequest(CameraDevice.TEMPLATE_RECORD).apply {
                addTarget(surface)

                // AF & AE
                set(CaptureRequest.CONTROL_MODE, CaptureRequest.CONTROL_MODE_AUTO)
                set(CaptureRequest.CONTROL_AF_MODE, CaptureRequest.CONTROL_AF_MODE_CONTINUOUS_VIDEO)
                set(CaptureRequest.CONTROL_AE_MODE, CaptureRequest.CONTROL_AE_MODE_ON)
                set(CaptureRequest.CONTROL_AWB_MODE, currentWbMode)

                // Torch
                if (hasTorch && isTorchOn) {
                    set(CaptureRequest.FLASH_MODE, CaptureRequest.FLASH_MODE_TORCH)
                } else {
                    set(CaptureRequest.FLASH_MODE, CaptureRequest.FLASH_MODE_OFF)
                }

                // Exposure
                set(CaptureRequest.CONTROL_AE_EXPOSURE_COMPENSATION, currentExposure)
                set(CaptureRequest.CONTROL_AE_LOCK, isAeLocked)

                // Zoom
                applyZoomToBuilder(this, currentZoom)

                // Frame rate
                set(CaptureRequest.CONTROL_AE_TARGET_FPS_RANGE, Range(captureFps, captureFps))
            }

            session.setRepeatingRequest(previewRequestBuilder!!.build(), null, handler)
            Log.d(tag, "Repeating capture request applied")
        } catch (e: Exception) {
            Log.e(tag, "Error applying repeating request", e)
        }
    }

    private fun applyZoomToBuilder(builder: CaptureRequest.Builder, zoom: Float) {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {
            val clamped = max(minZoomRatio, min(zoom, maxZoomRatio))
            builder.set(CaptureRequest.CONTROL_ZOOM_RATIO, clamped)
        } else {
            // SCALER_CROP_REGION fallback
            val clamped = max(1.0f, min(zoom, maxZoomRatio))
            val cropW = (activeSensorRect.width() / clamped).toInt()
            val cropH = (activeSensorRect.height() / clamped).toInt()
            val cropX = (activeSensorRect.width() - cropW) / 2
            val cropY = (activeSensorRect.height() - cropH) / 2
            val cropRect = Rect(cropX, cropY, cropX + cropW, cropY + cropH)
            builder.set(CaptureRequest.SCALER_CROP_REGION, cropRect)
        }
    }

    // Remote Camera Controls
    fun setZoom(zoom: Float) {
        currentZoom = max(minZoomRatio, min(zoom, maxZoomRatio))
        Log.i(tag, "Set zoom: $currentZoom")
        updateRepeatingRequest()
    }

    fun setTorch(enabled: Boolean) {
        isTorchOn = enabled
        Log.i(tag, "Set torch: $isTorchOn")
        updateRepeatingRequest()
    }

    fun setExposure(value: Int) {
        currentExposure = max(exposureRange.lower, min(value, exposureRange.upper))
        Log.i(tag, "Set exposure: $currentExposure")
        updateRepeatingRequest()
    }

    fun setAeLock(locked: Boolean) {
        isAeLocked = locked
        Log.i(tag, "Set AE Lock: $isAeLocked")
        updateRepeatingRequest()
    }

    fun setWhiteBalance(modeStr: String) {
        currentWbMode = when (modeStr.uppercase()) {
            "DAYLIGHT" -> CaptureRequest.CONTROL_AWB_MODE_DAYLIGHT
            "CLOUDY" -> CaptureRequest.CONTROL_AWB_MODE_CLOUDY_DAYLIGHT
            "INCANDESCENT" -> CaptureRequest.CONTROL_AWB_MODE_INCANDESCENT
            "FLUORESCENT" -> CaptureRequest.CONTROL_AWB_MODE_FLUORESCENT
            else -> CaptureRequest.CONTROL_AWB_MODE_AUTO
        }
        Log.i(tag, "Set White Balance: $modeStr ($currentWbMode)")
        updateRepeatingRequest()
    }

    fun setRotation(degrees: Int) {
        frameRotation = degrees
        surfaceTextureHelper?.setFrameRotation(degrees)
        Log.i(tag, "Set Frame Rotation: $degrees")
    }

    fun tapToFocus(normX: Float, normY: Float) {
        val session = captureSession ?: return
        val builder = previewRequestBuilder ?: return
        val handler = cameraHandler ?: return

        try {
            val clampedX = max(0f, min(1f, normX))
            val clampedY = max(0f, min(1f, normY))

            val focusX = (clampedX * activeSensorRect.width()).toInt()
            val focusY = (clampedY * activeSensorRect.height()).toInt()
            val boxSize = 120

            val left = max(0, focusX - boxSize)
            val top = max(0, focusY - boxSize)
            val right = min(activeSensorRect.width(), focusX + boxSize)
            val bottom = min(activeSensorRect.height(), focusY + boxSize)

            val focusRect = Rect(left, top, right, bottom)
            val meteringRect = MeteringRectangle(focusRect, MeteringRectangle.METERING_WEIGHT_MAX)

            builder.set(CaptureRequest.CONTROL_AF_REGIONS, arrayOf(meteringRect))
            builder.set(CaptureRequest.CONTROL_AE_REGIONS, arrayOf(meteringRect))
            builder.set(CaptureRequest.CONTROL_AF_MODE, CaptureRequest.CONTROL_AF_MODE_AUTO)
            builder.set(CaptureRequest.CONTROL_AF_TRIGGER, CaptureRequest.CONTROL_AF_TRIGGER_START)

            session.capture(builder.build(), null, handler)
            builder.set(CaptureRequest.CONTROL_AF_TRIGGER, CaptureRequest.CONTROL_AF_TRIGGER_IDLE)
            session.setRepeatingRequest(builder.build(), null, handler)
            Log.i(tag, "Tap to focus executed at ($normX, $normY)")
        } catch (e: Exception) {
            Log.e(tag, "Tap to focus error", e)
        }
    }

    fun takeSnapshot(onSaved: (filePath: String) -> Unit) {
        val session = captureSession ?: return
        val camera = cameraDevice ?: return
        val reader = imageReader ?: return
        val handler = cameraHandler ?: return

        reader.setOnImageAvailableListener({ ir ->
            val image = ir.acquireLatestImage() ?: return@setOnImageAvailableListener
            try {
                val buffer = image.planes[0].buffer
                val bytes = ByteArray(buffer.remaining())
                buffer.get(bytes)
                image.close()

                val timeStamp = SimpleDateFormat("yyyyMMdd_HHmmss", Locale.US).format(Date())
                val fileName = "OPTIX_${timeStamp}.jpg"

                val savedPath = saveSnapshotLocally(fileName, bytes)
                Log.i(tag, "Snapshot saved to: $savedPath")
                onSaved(savedPath)
            } catch (e: Exception) {
                Log.e(tag, "Failed to save snapshot", e)
            }
        }, handler)

        try {
            val captureBuilder = camera.createCaptureRequest(CameraDevice.TEMPLATE_STILL_CAPTURE).apply {
                addTarget(reader.surface)
                set(CaptureRequest.CONTROL_AF_MODE, CaptureRequest.CONTROL_AF_MODE_CONTINUOUS_PICTURE)
                set(CaptureRequest.JPEG_ORIENTATION, frameRotation)
                applyZoomToBuilder(this, currentZoom)
            }
            session.capture(captureBuilder.build(), null, handler)
            Log.i(tag, "Still capture request issued")
        } catch (e: Exception) {
            Log.e(tag, "Error triggering snapshot capture", e)
        }
    }

    private fun saveSnapshotLocally(fileName: String, bytes: ByteArray): String {
        return if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            val values = ContentValues().apply {
                put(MediaStore.Images.Media.DISPLAY_NAME, fileName)
                put(MediaStore.Images.Media.MIME_TYPE, "image/jpeg")
                put(MediaStore.Images.Media.RELATIVE_PATH, Environment.DIRECTORY_PICTURES + "/Optix")
            }
            val uri = context.contentResolver.insert(MediaStore.Images.Media.EXTERNAL_CONTENT_URI, values)
            if (uri != null) {
                context.contentResolver.openOutputStream(uri)?.use { os ->
                    os.write(bytes)
                }
                uri.toString()
            } else {
                fileName
            }
        } else {
            val dir = File(Environment.getExternalStoragePublicDirectory(Environment.DIRECTORY_PICTURES), "Optix")
            if (!dir.exists()) dir.mkdirs()
            val file = File(dir, fileName)
            FileOutputStream(file).use { fos -> fos.write(bytes) }
            file.absolutePath
        }
    }

    fun switchCamera(onComplete: (() -> Unit)? = null) {
        try {
            val targetFacing = if (isBackFacing) CameraCharacteristics.LENS_FACING_FRONT else CameraCharacteristics.LENS_FACING_BACK
            for (id in cameraManager.cameraIdList) {
                val chars = cameraManager.getCameraCharacteristics(id)
                if (chars.get(CameraCharacteristics.LENS_FACING) == targetFacing) {
                    selectedCameraId = id
                    isBackFacing = !isBackFacing
                    readCameraCapabilities(chars)
                    break
                }
            }
            stopCapture()
            startCapture(captureWidth, captureHeight, captureFps)
            onComplete?.invoke()
            Log.i(tag, "Switched camera to: $selectedCameraId (Back: $isBackFacing)")
        } catch (e: Exception) {
            Log.e(tag, "Failed to switch camera", e)
        }
    }

    private fun updateRepeatingRequest() {
        val session = captureSession ?: return
        val builder = previewRequestBuilder ?: return
        val handler = cameraHandler ?: return

        try {
            // Apply updated zoom
            applyZoomToBuilder(builder, currentZoom)

            // Torch
            if (hasTorch && isTorchOn) {
                builder.set(CaptureRequest.FLASH_MODE, CaptureRequest.FLASH_MODE_TORCH)
            } else {
                builder.set(CaptureRequest.FLASH_MODE, CaptureRequest.FLASH_MODE_OFF)
            }

            // Exposure
            builder.set(CaptureRequest.CONTROL_AE_EXPOSURE_COMPENSATION, currentExposure)
            builder.set(CaptureRequest.CONTROL_AE_LOCK, isAeLocked)
            builder.set(CaptureRequest.CONTROL_AWB_MODE, currentWbMode)

            session.setRepeatingRequest(builder.build(), null, handler)
        } catch (e: Exception) {
            Log.e(tag, "Failed to update repeating request", e)
        }
    }

    fun getCapabilitiesJson(): JSONObject {
        return JSONObject().apply {
            put("type", "capabilities")
            put("camera", if (isBackFacing) "PHONE_BACK" else "PHONE_FRONT")
            put("zoom", JSONObject().apply {
                put("min", minZoomRatio)
                put("max", maxZoomRatio)
                put("current", currentZoom)
                put("step", 0.1)
            })
            put("exposure", JSONObject().apply {
                put("min", exposureRange.lower)
                put("max", exposureRange.upper)
                put("step", exposureStep)
                put("current", currentExposure)
            })
            put("torch", hasTorch)
            put("torchOn", isTorchOn)
            put("aeLocked", isAeLocked)
            put("whiteBalance", JSONArray(listOf("AUTO", "DAYLIGHT", "CLOUDY", "INCANDESCENT", "FLUORESCENT")))
            put("resolutions", JSONArray(listOf("1920x1080", "1280x720", "640x480")))
            put("fpsPresets", JSONArray(listOf(15, 24, 30)))
            put("rotation", frameRotation)
        }
    }

    override fun stopCapture() {
        Log.i(tag, "stopCapture called")
        try {
            surfaceTextureHelper?.stopListening()
            captureSession?.stopRepeating()
            captureSession?.close()
            captureSession = null

            cameraDevice?.close()
            cameraDevice = null

            imageReader?.close()
            imageReader = null

            previewSurface?.release()
            previewSurface = null

            capturerObserver?.onCapturerStopped()
        } catch (e: Exception) {
            Log.e(tag, "Error in stopCapture", e)
        }
    }

    override fun changeCaptureFormat(width: Int, height: Int, framerate: Int) {
        stopCapture()
        startCapture(width, height, framerate)
    }

    override fun dispose() {
        stopCapture()
        stopBackgroundThread()
    }

    override fun isScreencast(): Boolean = false
}
