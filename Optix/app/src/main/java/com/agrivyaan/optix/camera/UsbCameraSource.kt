package com.agrivyaan.optix.camera

import android.content.Context
import android.hardware.usb.UsbDevice
import android.util.Log
import android.view.Surface
import com.serenegiant.usb.IFrameCallback
import com.serenegiant.usb.USBMonitor
import com.serenegiant.usb.UVCCamera
import com.serenegiant.usb.UVCParam
import org.webrtc.CapturerObserver
import org.webrtc.NV21Buffer
import org.webrtc.SurfaceTextureHelper
import org.webrtc.VideoCapturer
import org.webrtc.VideoFrame
import java.nio.ByteBuffer

class UsbCameraSource(
    private val context: Context,
    private val onDeviceStatusChanged: ((isConnected: Boolean, deviceName: String?) -> Unit)? = null,
    private val onCameraReady: (() -> Unit)? = null
) : VideoCapturer {

    private val tag = "UsbCameraSource"

    private var surfaceTextureHelper: SurfaceTextureHelper? = null
    private var capturerObserver: CapturerObserver? = null

    private var usbMonitor: USBMonitor? = null
    private var uvcCamera: UVCCamera? = null
    private var activeDevice: UsbDevice? = null
    private var previewSurface: Surface? = null

    private var captureWidth = 1280
    private var captureHeight = 720
    private var captureFps = 30
    private var isCapturing = false
    private var isPreviewing = false
    private var isListeningToTexture = false
    private var hasReceivedFirstFrame = false

    private val connectListener = object : USBMonitor.OnDeviceConnectListener {
        override fun onAttach(device: UsbDevice) {
            Log.i(tag, "USB device attached: ${device.deviceName} (VID: 0x${device.vendorId.toString(16)}, PID: 0x${device.productId.toString(16)})")
            if (isUvcDevice(device)) {
                usbMonitor?.requestPermission(device)
            }
        }

        override fun onDetach(device: UsbDevice) {
            Log.i(tag, "USB device detached: ${device.deviceName}")
            if (device == activeDevice) {
                stopCamera()
                onDeviceStatusChanged?.invoke(false, null)
            }
        }

        override fun onDeviceOpen(
            device: UsbDevice,
            ctrlBlock: USBMonitor.UsbControlBlock,
            createNew: Boolean
        ) {
            Log.i(tag, "USB device opened with permission: ${device.deviceName}")
            activeDevice = device
            openUvcCamera(ctrlBlock)
            onDeviceStatusChanged?.invoke(true, device.productName ?: device.deviceName)
        }

        override fun onDeviceClose(device: UsbDevice, ctrlBlock: USBMonitor.UsbControlBlock) {
            Log.i(tag, "USB device closed: ${device.deviceName}")
            stopCamera()
            onDeviceStatusChanged?.invoke(false, null)
        }

        override fun onCancel(device: UsbDevice) {
            Log.w(tag, "USB device permission cancelled: ${device.deviceName}")
            onDeviceStatusChanged?.invoke(false, "Permission Denied")
        }
    }

    private fun isUvcDevice(device: UsbDevice): Boolean {
        // Any device connected to phone OTG should be accepted
        return true
    }

    fun reopenCamera() {
        try {
            if (uvcCamera != null && isCapturing && isPreviewing) {
                Log.i(tag, "reopenCamera: UVC camera already active and previewing, skipping duplicate reopen")
                return
            }
            if (usbMonitor == null) {
                usbMonitor = USBMonitor(context, connectListener)
                usbMonitor?.register()
            }
            if (usbMonitor?.isRegistered != true) {
                usbMonitor?.register()
            }
            val devices = usbMonitor?.deviceList
            Log.i(tag, "reopenCamera called. Found ${devices?.size ?: 0} USB devices")
            if (!devices.isNullOrEmpty()) {
                for (device in devices) {
                    Log.i(tag, "Opening/requesting USB device: ${device.deviceName} (${device.productName})")
                    usbMonitor?.requestPermission(device)
                    return
                }
            } else {
                Log.w(tag, "reopenCamera: No USB device detected yet.")
            }
        } catch (e: Exception) {
            Log.e(tag, "Error in reopenCamera", e)
        }
    }

    fun requestDevicePermission() {
        reopenCamera()
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
        Log.i(tag, "startCapture called: ${width}x${height} @ ${framerate}fps")
        this.captureWidth = width
        this.captureHeight = height
        this.captureFps = framerate

        if (isCapturing && uvcCamera != null && isPreviewing) {
            Log.i(tag, "startCapture: Camera is already running and previewing")
            return
        }
        this.isCapturing = true

        surfaceTextureHelper?.setTextureSize(width, height)
        if (!isListeningToTexture) {
            isListeningToTexture = true
            surfaceTextureHelper?.startListening { videoFrame ->
                if (!hasReceivedFirstFrame) {
                    hasReceivedFirstFrame = true
                    Log.i(tag, "First USB camera texture frame received: ${videoFrame.rotatedWidth}x${videoFrame.rotatedHeight}")
                }
                capturerObserver?.onFrameCaptured(videoFrame)
            }
        }

        try {
            if (usbMonitor == null) {
                usbMonitor = USBMonitor(context, connectListener)
            }
            usbMonitor?.register()

            val devices = usbMonitor?.deviceList
            if (!devices.isNullOrEmpty()) {
                for (device in devices) {
                    if (isUvcDevice(device)) {
                        Log.i(tag, "Found existing UVC device. Requesting permission: ${device.deviceName}")
                        usbMonitor?.requestPermission(device)
                        break
                    }
                }
            } else {
                Log.i(tag, "No USB device detected yet. Waiting for OTG plug-in...")
            }
        } catch (e: Exception) {
            Log.e(tag, "Error registering USBMonitor", e)
        }
    }

    private fun openUvcCamera(ctrlBlock: USBMonitor.UsbControlBlock) {
        try {
            // Clean up any existing camera instance first to prevent device busy collisions
            try {
                uvcCamera?.stopPreview()
                uvcCamera?.destroy()
            } catch (_: Exception) {}
            uvcCamera = null
            previewSurface?.release()
            previewSurface = null

            val camera = UVCCamera(UVCParam())
            val openCode = camera.open(ctrlBlock)
            Log.i(tag, "UVCCamera.open result: $openCode")
            uvcCamera = camera

            val texture = surfaceTextureHelper?.surfaceTexture
            if (texture != null) {
                var sizeConfigured = false
                var finalWidth = 640
                var finalHeight = 480

                val supportedSizes = try {
                    camera.supportedSizeList
                } catch (e: Exception) {
                    Log.w(tag, "Could not query supportedSizeList", e)
                    null
                }
                Log.i(tag, "UVC Camera supported size count: ${supportedSizes?.size ?: 0}")

                if (!supportedSizes.isNullOrEmpty()) {
                    val sortedSizes = supportedSizes.sortedWith(
                        compareByDescending<com.serenegiant.usb.Size> { it.width == captureWidth && it.height == captureHeight }
                            .thenByDescending { it.width == 1280 && it.height == 720 }
                            .thenByDescending { it.width == 640 && it.height == 480 }
                            .thenByDescending { it.width * it.height }
                    )
                    for (sz in sortedSizes) {
                        try {
                            camera.setPreviewSize(sz)
                            finalWidth = sz.width
                            finalHeight = sz.height
                            texture.setDefaultBufferSize(sz.width, sz.height)
                            surfaceTextureHelper?.setTextureSize(sz.width, sz.height)
                            sizeConfigured = true
                            Log.i(tag, "Successfully configured UVC preview size with Size: ${sz.width}x${sz.height} type=${sz.type} fps=${sz.fps}")
                            break
                        } catch (e: Exception) {
                            Log.w(tag, "Failed to apply size ${sz.width}x${sz.height}: ${e.message}")
                        }
                    }
                }

                if (!sizeConfigured) {
                    val fallbacks = listOf(
                        Triple(640, 480, UVCCamera.FRAME_FORMAT_MJPEG),
                        Triple(640, 480, UVCCamera.FRAME_FORMAT_YUYV),
                        Triple(1280, 720, UVCCamera.FRAME_FORMAT_MJPEG),
                        Triple(320, 240, UVCCamera.FRAME_FORMAT_YUYV)
                    )
                    for ((w, h, fmt) in fallbacks) {
                        try {
                            camera.setPreviewSize(w, h, fmt, 30)
                            finalWidth = w
                            finalHeight = h
                            texture.setDefaultBufferSize(w, h)
                            surfaceTextureHelper?.setTextureSize(w, h)
                            sizeConfigured = true
                            Log.i(tag, "Fallback configured UVC preview size: ${w}x${h} format $fmt")
                            break
                        } catch (e: Exception) {
                            Log.w(tag, "Fallback ${w}x${h} format $fmt failed: ${e.message}")
                        }
                    }
                }

                if (!sizeConfigured) {
                    try {
                        camera.setPreviewSize(640, 480)
                        finalWidth = 640
                        finalHeight = 480
                        texture.setDefaultBufferSize(640, 480)
                        surfaceTextureHelper?.setTextureSize(640, 480)
                        sizeConfigured = true
                    } catch (e: Exception) {
                        Log.e(tag, "All setPreviewSize attempts failed!", e)
                    }
                }

                // Attach direct NV21 frame callback: decodes hardware frames directly into WebRTC video buffers!
                camera.setFrameCallback(object : IFrameCallback {
                    private var byteArray: ByteArray? = null

                    override fun onFrame(frame: ByteBuffer) {
                        try {
                            val length = frame.remaining()
                            if (length <= 0) return

                            var bytes = byteArray
                            if (bytes == null || bytes.size != length) {
                                bytes = ByteArray(length)
                                byteArray = bytes
                            }

                            frame.get(bytes)

                            if (!hasReceivedFirstFrame) {
                                hasReceivedFirstFrame = true
                                Log.i(tag, "Direct NV21 frame received from USB webcam! (${finalWidth}x${finalHeight})")
                            }

                            val nv21Buffer = NV21Buffer(bytes, finalWidth, finalHeight, null)
                            val videoFrame = VideoFrame(nv21Buffer, 0, System.nanoTime())
                            capturerObserver?.onFrameCaptured(videoFrame)
                            videoFrame.release()
                        } catch (e: Exception) {
                            Log.e(tag, "Error processing UVC NV21 frame", e)
                        }
                    }
                }, UVCCamera.PIXEL_FORMAT_NV21)

                try {
                    previewSurface?.release()
                    previewSurface = Surface(texture)
                    camera.setPreviewDisplay(previewSurface)
                } catch (e: Exception) {
                    Log.w(tag, "setPreviewDisplay warning: ${e.message}")
                }

                camera.startPreview()
                isPreviewing = true
                capturerObserver?.onCapturerStarted(true)
                Log.i(tag, "UVC Camera preview active with NV21 frame pipeline (${finalWidth}x${finalHeight})!")
                onCameraReady?.invoke()
            }
        } catch (e: Exception) {
            Log.e(tag, "Failed to open and preview UVC Camera", e)
            isPreviewing = false
            capturerObserver?.onCapturerStopped()
        }
    }

    private fun stopCamera() {
        try {
            isPreviewing = false
            uvcCamera?.stopPreview()
            uvcCamera?.destroy()
            uvcCamera = null
            previewSurface?.release()
            previewSurface = null
            activeDevice = null
            capturerObserver?.onCapturerStopped()
            Log.i(tag, "UVC Camera stopped")
        } catch (e: Exception) {
            Log.e(tag, "Error stopping UVC camera", e)
        }
    }

    override fun stopCapture() {
        isCapturing = false
        stopCamera()
        try {
            if (isListeningToTexture) {
                surfaceTextureHelper?.stopListening()
                isListeningToTexture = false
            }
            usbMonitor?.unregister()
            usbMonitor?.destroy()
            usbMonitor = null
        } catch (e: Exception) {
            Log.e(tag, "Error in stopCapture", e)
        }
    }

    override fun changeCaptureFormat(width: Int, height: Int, framerate: Int) {
        this.captureWidth = width
        this.captureHeight = height
        this.captureFps = framerate
        surfaceTextureHelper?.setTextureSize(width, height)
        try {
            uvcCamera?.setPreviewSize(width, height)
        } catch (_: Exception) {}
    }

    override fun dispose() {
        stopCapture()
    }

    override fun isScreencast(): Boolean = false
}
