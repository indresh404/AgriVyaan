package com.agrivyaan.optix.webrtc

import android.content.Context
import android.hardware.camera2.CameraCharacteristics
import android.hardware.camera2.CameraManager
import android.util.Log
import com.agrivyaan.optix.camera.UsbCameraSource
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import org.json.JSONObject
import org.webrtc.*

enum class StreamMode {
    PHONE, USB, BOTH
}

class WebRtcManager(
    private val context: Context,
    private val onSendSignalingMessage: (JSONObject) -> Unit
) {
    private val tag = "WebRtcManager"
    private val scope = CoroutineScope(Dispatchers.Main)

    private val eglBase: EglBase = EglBase.create()
    private var peerConnectionFactory: PeerConnectionFactory? = null
    private var phoneTextureHelper: SurfaceTextureHelper? = null
    private var usbTextureHelper: SurfaceTextureHelper? = null

    // Phone Camera Capturer & Track
    private var phoneCapturer: CameraVideoCapturer? = null
    private var phoneSource: VideoSource? = null
    private var phoneVideoTrack: VideoTrack? = null
    private var availablePhoneDevices: List<String> = emptyList()
    private var currentPhoneDeviceIndex = 0

    // USB Webcam Capturer & Track
    private var usbCapturer: UsbCameraSource? = null
    private var usbSource: VideoSource? = null
    private var usbVideoTrack: VideoTrack? = null
    private var isUsbConnected = false

    // Active PeerConnection
    private var peerConnection: PeerConnection? = null
    private var dataChannel: DataChannel? = null

    // State
    private val _isStreaming = MutableStateFlow(false)
    val isStreaming: StateFlow<Boolean> = _isStreaming.asStateFlow()

    private var activeMode = StreamMode.PHONE
    private var currentWidth = 1280
    private var currentHeight = 720
    private var currentFps = 30
    private var rearCameraId: String? = null
    private var isTorchOn = false

    init {
        initializePeerConnectionFactory()
        enumeratePhoneCameras()
        // Pre-warm camera capture
        startPhoneCamera(currentWidth, currentHeight, currentFps)
        startUsbCamera(currentWidth, currentHeight, currentFps)
    }

    private fun enumeratePhoneCameras() {
        try {
            val enumerator = Camera2Enumerator(context)
            availablePhoneDevices = enumerator.deviceNames.toList()
            for ((idx, name) in availablePhoneDevices.withIndex()) {
                if (enumerator.isBackFacing(name)) {
                    rearCameraId = name
                    currentPhoneDeviceIndex = idx
                    break
                }
            }
            Log.i(tag, "Discovered phone cameras: $availablePhoneDevices, selected: $rearCameraId")
        } catch (e: Exception) {
            Log.e(tag, "Failed to enumerate cameras", e)
        }
    }

    private fun initializePeerConnectionFactory() {
        val initOptions = PeerConnectionFactory.InitializationOptions.builder(context)
            .setEnableInternalTracer(true)
            .createInitializationOptions()
        PeerConnectionFactory.initialize(initOptions)

        val encoderFactory = DefaultVideoEncoderFactory(
            eglBase.eglBaseContext,
            true, // enableIntelVp8
            true  // enableH264HighProfile
        )
        val decoderFactory = DefaultVideoDecoderFactory(eglBase.eglBaseContext)

        peerConnectionFactory = PeerConnectionFactory.builder()
            .setVideoEncoderFactory(encoderFactory)
            .setVideoDecoderFactory(decoderFactory)
            .setOptions(PeerConnectionFactory.Options())
            .createPeerConnectionFactory()

        phoneTextureHelper = SurfaceTextureHelper.create("OptixPhoneCamThread", eglBase.eglBaseContext)
        usbTextureHelper = SurfaceTextureHelper.create("OptixUsbCamThread", eglBase.eglBaseContext)
        Log.i(tag, "PeerConnectionFactory & SurfaceTextureHelpers initialized")
    }

    @Synchronized
    fun startPhoneCamera(width: Int = 1280, height: Int = 720, fps: Int = 30) {
        if (phoneCapturer != null) return
        currentWidth = width
        currentHeight = height
        currentFps = fps

        try {
            val enumerator = Camera2Enumerator(context)
            val selectedDevice = availablePhoneDevices.getOrNull(currentPhoneDeviceIndex) ?: "0"

            Log.i(tag, "Starting Phone Camera2 device: $selectedDevice")
            phoneCapturer = enumerator.createCapturer(selectedDevice, object : CameraVideoCapturer.CameraEventsHandler {
                override fun onCameraError(errorDescription: String?) {
                    Log.e(tag, "Phone camera error: $errorDescription")
                }
                override fun onCameraDisconnected() {
                    Log.w(tag, "Phone camera disconnected")
                }
                override fun onCameraFreezed(errorDescription: String?) {
                    Log.w(tag, "Phone camera freezed: $errorDescription")
                }
                override fun onCameraOpening(cameraName: String?) {
                    Log.i(tag, "Phone camera opening: $cameraName")
                }
                override fun onFirstFrameAvailable() {
                    Log.i(tag, "First phone camera frame available!")
                }
                override fun onCameraClosed() {
                    Log.i(tag, "Phone camera closed")
                }
            })

            val factory = peerConnectionFactory ?: return
            phoneSource = factory.createVideoSource(phoneCapturer!!.isScreencast)
            phoneCapturer!!.initialize(phoneTextureHelper, context, phoneSource!!.capturerObserver)
            phoneCapturer!!.startCapture(width, height, fps)

            phoneVideoTrack = factory.createVideoTrack("OPTIX_PHONE_TRACK", phoneSource).apply {
                setEnabled(true)
            }
            _isStreaming.value = true
        } catch (e: Exception) {
            Log.e(tag, "Error starting phone camera", e)
        }
    }

    @Synchronized
    fun startUsbCamera(width: Int = 1280, height: Int = 720, fps: Int = 30) {
        if (usbCapturer != null) return
        try {
            val factory = peerConnectionFactory ?: return
            usbCapturer = UsbCameraSource(
                context = context,
                onDeviceStatusChanged = { connected, name ->
                    isUsbConnected = connected
                    Log.i(tag, "USB Camera status changed: connected=$connected, name=$name")
                    val json = JSONObject().apply {
                        put("type", "usb_status")
                        put("connected", connected)
                        put("deviceName", name ?: "")
                    }
                    onSendSignalingMessage(json)
                },
                onCameraReady = {
                    Log.i(tag, "USB Camera is READY with active preview pipeline!")
                    scope.launch(Dispatchers.Main) {
                        if (activeMode == StreamMode.USB || activeMode == StreamMode.BOTH) {
                            Log.i(tag, "USB Camera ready: starting/updating live stream to client")
                            startStreamingToClient()
                        }
                    }
                }
            )

            usbSource = factory.createVideoSource(false)
            usbCapturer!!.initialize(usbTextureHelper!!, context, usbSource!!.capturerObserver)
            usbCapturer!!.startCapture(width, height, fps)

            usbVideoTrack = factory.createVideoTrack("OPTIX_USB_TRACK", usbSource).apply {
                setEnabled(true)
            }
            Log.i(tag, "USB Camera pipeline initialized and listening for OTG device")
        } catch (e: Exception) {
            Log.e(tag, "Error starting USB camera pipeline", e)
        }
    }

    @Synchronized
    fun setStreamMode(mode: StreamMode) {
        val previousMode = activeMode
        activeMode = mode
        Log.i(tag, "Stream mode changed from $previousMode to: $mode")

        if (mode == StreamMode.USB) {
            try {
                phoneCapturer?.stopCapture()
                phoneVideoTrack?.setEnabled(false)
            } catch (e: Exception) {
                Log.w(tag, "Pausing phone capturer: ${e.message}")
            }
            usbCapturer?.reopenCamera()
            usbCapturer?.startCapture(currentWidth, currentHeight, currentFps)
            usbVideoTrack?.setEnabled(true)
        } else if (mode == StreamMode.PHONE) {
            ensurePhoneCameraCapturing()
            phoneVideoTrack?.setEnabled(true)
            usbVideoTrack?.setEnabled(false)
        } else if (mode == StreamMode.BOTH) {
            ensurePhoneCameraCapturing()
            phoneVideoTrack?.setEnabled(true)
            usbCapturer?.reopenCamera()
            usbCapturer?.startCapture(currentWidth, currentHeight, currentFps)
            usbVideoTrack?.setEnabled(true)
        }

        // Renegotiate peer connection with updated tracks
        startStreamingToClient()
    }

    private fun ensurePhoneCameraCapturing() {
        try {
            if (phoneCapturer == null) {
                val enumerator = Camera2Enumerator(context)
                val deviceName = availablePhoneDevices.getOrNull(currentPhoneDeviceIndex)
                    ?: availablePhoneDevices.firstOrNull() ?: "0"
                if (phoneSource != null && phoneTextureHelper != null) {
                    phoneCapturer = enumerator.createCapturer(deviceName, null)
                    phoneCapturer?.initialize(phoneTextureHelper, context, phoneSource!!.capturerObserver)
                }
            }
            phoneCapturer?.startCapture(currentWidth, currentHeight, currentFps)
        } catch (e: Exception) {
            Log.w(tag, "ensurePhoneCameraCapturing: ${e.message}")
        }
    }

    @Synchronized
    fun ensureCameraRunning() {
        try {
            if (activeMode == StreamMode.PHONE || activeMode == StreamMode.BOTH) {
                ensurePhoneCameraCapturing()
                phoneVideoTrack?.setEnabled(true)
            }
            if (activeMode == StreamMode.USB || activeMode == StreamMode.BOTH) {
                usbCapturer?.reopenCamera()
                usbCapturer?.startCapture(currentWidth, currentHeight, currentFps)
                usbVideoTrack?.setEnabled(true)
            }
            _isStreaming.value = true
            Log.i(tag, "Camera capture confirmed active for mode: $activeMode")
        } catch (e: Exception) {
            Log.e(tag, "Error in ensureCameraRunning", e)
        }
    }

    private var streamNegotiationJob: Job? = null

    @Synchronized
    fun startStreamingToClient() {
        streamNegotiationJob?.cancel()
        streamNegotiationJob = scope.launch {
            delay(80) // Debounce and coalesce rapid consecutive stream requests
            executeStartStreamingToClient()
        }
    }

    @Synchronized
    private fun executeStartStreamingToClient() {
        ensureCameraRunning()
        closePeerConnection()

        val factory = peerConnectionFactory ?: run {
            Log.e(tag, "PeerConnectionFactory is null!")
            return
        }

        val rtcConfig = PeerConnection.RTCConfiguration(emptyList()).apply {
            sdpSemantics = PeerConnection.SdpSemantics.UNIFIED_PLAN
            continualGatheringPolicy = PeerConnection.ContinualGatheringPolicy.GATHER_CONTINUALLY
        }

        peerConnection = factory.createPeerConnection(rtcConfig, object : PeerConnection.Observer {
            override fun onIceCandidate(candidate: IceCandidate?) {
                if (candidate != null) {
                    val json = JSONObject().apply {
                        put("type", "candidate")
                        put("candidate", candidate.sdp)
                        put("sdpMid", candidate.sdpMid)
                        put("sdpMLineIndex", candidate.sdpMLineIndex)
                    }
                    onSendSignalingMessage(json)
                }
            }

            override fun onIceCandidatesRemoved(candidates: Array<out IceCandidate>?) {}
            override fun onSignalingChange(state: PeerConnection.SignalingState?) {
                Log.d(tag, "SignalingState: $state")
            }
            override fun onIceConnectionChange(state: PeerConnection.IceConnectionState?) {
                Log.d(tag, "IceConnectionState: $state")
            }
            override fun onIceConnectionReceivingChange(receiving: Boolean) {}
            override fun onIceGatheringChange(state: PeerConnection.IceGatheringState?) {
                Log.d(tag, "IceGatheringState: $state")
            }
            override fun onAddStream(stream: MediaStream?) {}
            override fun onRemoveStream(stream: MediaStream?) {}
            override fun onDataChannel(dc: DataChannel?) {
                dataChannel = dc
            }
            override fun onRenegotiationNeeded() {
                Log.d(tag, "Renegotiation needed")
            }
            override fun onAddTrack(receiver: RtpReceiver?, mediaStreams: Array<out MediaStream>?) {}
        })

        // Add Video Tracks based on active mode
        if (activeMode == StreamMode.PHONE || activeMode == StreamMode.BOTH) {
            phoneVideoTrack?.let { track ->
                peerConnection?.addTrack(track, listOf("optix_phone_stream"))
                Log.i(tag, "Added Phone Video Track to PeerConnection")
            }
        }

        if (activeMode == StreamMode.USB || activeMode == StreamMode.BOTH) {
            usbVideoTrack?.let { track ->
                peerConnection?.addTrack(track, listOf("optix_usb_stream"))
                Log.i(tag, "Added USB Webcam Track to PeerConnection")
            }
        }

        // Data Channel for ground controls
        val dcInit = DataChannel.Init().apply {
            ordered = true
            maxRetransmits = -1
        }
        dataChannel = peerConnection?.createDataChannel("control", dcInit)

        // Create Offer with high quality constraints
        val mediaConstraints = MediaConstraints().apply {
            mandatory.add(MediaConstraints.KeyValuePair("OfferToReceiveVideo", "false"))
            mandatory.add(MediaConstraints.KeyValuePair("OfferToReceiveAudio", "false"))
        }

        peerConnection?.createOffer(object : SdpObserver {
            override fun onCreateSuccess(sdp: SessionDescription?) {
                if (sdp == null) return
                // Boost video bitrate in SDP for high visual fidelity
                val boostedSdp = boostSdpBitrate(sdp.description)
                val modifiedDesc = SessionDescription(sdp.type, boostedSdp)

                peerConnection?.setLocalDescription(object : SdpObserver {
                    override fun onCreateSuccess(desc: SessionDescription?) {}
                    override fun onSetSuccess() {
                        Log.i(tag, "Local SDP offer set (4.5Mbps high-quality). Transmitting to ground...")
                        val json = JSONObject().apply {
                            put("type", "offer")
                            put("sdp", modifiedDesc.description)
                            put("mode", activeMode.name)
                        }
                        onSendSignalingMessage(json)
                    }
                    override fun onCreateFailure(err: String?) {
                        Log.e(tag, "Set local description failure: $err")
                    }
                    override fun onSetFailure(err: String?) {
                        Log.e(tag, "Set local description failure: $err")
                    }
                }, modifiedDesc)
            }

            override fun onSetSuccess() {}
            override fun onCreateFailure(err: String?) {
                Log.e(tag, "Create offer failed: $err")
            }
            override fun onSetFailure(err: String?) {
                Log.e(tag, "Set description failed: $err")
            }
        }, mediaConstraints)
    }

    private fun boostSdpBitrate(sdp: String): String {
        val lines = sdp.split("\r\n").toMutableList()
        val result = mutableListOf<String>()
        var inVideo = false

        for (line in lines) {
            if (line.startsWith("m=video")) {
                inVideo = true
                result.add(line)
                // 2500 kbps: Ultra-smooth low latency without Wi-Fi bufferbloat
                result.add("b=AS:2500")
                result.add("b=TIAS:2500000")
                result.add("a=x-google-min-bitrate=1500")
                result.add("a=x-google-max-bitrate=2500")
                result.add("a=x-google-start-bitrate=2000")
                continue
            }
            if (line.startsWith("m=audio") || line.startsWith("m=application")) {
                inVideo = false
            }
            if (inVideo && line.startsWith("c=IN")) {
                result.add(line)
                result.add("b=AS:2500")
                continue
            }
            result.add(line)
        }
        return result.joinToString("\r\n")
    }

    fun handleRemoteAnswer(sdpDescription: String) {
        val sdp = SessionDescription(SessionDescription.Type.ANSWER, sdpDescription)
        peerConnection?.setRemoteDescription(object : SdpObserver {
            override fun onCreateSuccess(p0: SessionDescription?) {}
            override fun onSetSuccess() {
                Log.i(tag, "Remote SDP answer set successfully. Live stream transmitting!")
            }
            override fun onCreateFailure(err: String?) {
                Log.e(tag, "Remote SDP answer error: $err")
            }
            override fun onSetFailure(err: String?) {
                Log.e(tag, "Remote SDP answer set failure: $err")
            }
        }, sdp)
    }

    fun handleRemoteIceCandidate(sdp: String, sdpMid: String?, sdpMLineIndex: Int) {
        val candidate = IceCandidate(sdpMid ?: "0", sdpMLineIndex, sdp)
        peerConnection?.addIceCandidate(candidate)
    }

    @Synchronized
    fun closePeerConnection() {
        try {
            dataChannel?.close()
            dataChannel?.dispose()
            dataChannel = null

            peerConnection?.close()
            peerConnection?.dispose()
            peerConnection = null
        } catch (e: Exception) {
            Log.e(tag, "Error closing PeerConnection", e)
        }
    }

    // Camera Controls with dedicated IO hardware scope (never blocks main or websocket thread)
    private val hardwareScope = CoroutineScope(Dispatchers.IO)
    private var isStrobeActive = false
    private var strobeJob: Job? = null

    fun toggleTorch(): Boolean {
        isStrobeActive = false
        strobeJob?.cancel()
        strobeJob = null
        isTorchOn = !isTorchOn
        val target = isTorchOn
        hardwareScope.launch {
            setTorchHardware(target)
        }
        return isTorchOn
    }

    fun toggleStrobe(): Boolean {
        isStrobeActive = !isStrobeActive
        strobeJob?.cancel()
        strobeJob = null

        if (isStrobeActive) {
            isTorchOn = false
            strobeJob = hardwareScope.launch {
                Log.i(tag, "Airplane strobe light loop started")
                while (isActive && isStrobeActive) {
                    setTorchHardware(true)
                    delay(100)
                    setTorchHardware(false)
                    delay(120)
                    setTorchHardware(true)
                    delay(100)
                    setTorchHardware(false)
                    delay(700)
                }
                setTorchHardware(false)
                Log.i(tag, "Airplane strobe light loop stopped")
            }
            Log.i(tag, "Airplane strobe light ACTIVATED")
        } else {
            hardwareScope.launch {
                setTorchHardware(false)
            }
            Log.i(tag, "Airplane strobe light DEACTIVATED")
        }
        return isStrobeActive
    }

    private fun setTorchHardware(enabled: Boolean) {
        try {
            val cameraManager = context.getSystemService(Context.CAMERA_SERVICE) as CameraManager
            val camId = rearCameraId ?: "0"
            cameraManager.setTorchMode(camId, enabled)
        } catch (e: Exception) {
            Log.w(tag, "Torch hardware control ($enabled): ${e.message}")
        }
    }

    fun switchCamera() {
        if (availablePhoneDevices.size <= 1) {
            Log.w(tag, "Only one camera available, cannot switch")
            return
        }

        val nextIndex = (currentPhoneDeviceIndex + 1) % availablePhoneDevices.size
        val nextDevice = availablePhoneDevices[nextIndex]
        Log.i(tag, "Switching phone camera from index $currentPhoneDeviceIndex to $nextIndex ($nextDevice)...")

        // Try in-place switch with explicit device name
        phoneCapturer?.switchCamera(object : CameraVideoCapturer.CameraSwitchHandler {
            override fun onCameraSwitchDone(isFrontFacing: Boolean) {
                currentPhoneDeviceIndex = nextIndex
                Log.i(tag, "In-place camera switch successful! FrontFacing: $isFrontFacing")
            }

            override fun onCameraSwitchError(errorDescription: String?) {
                Log.w(tag, "In-place switch failed ($errorDescription), executing clean restart switch...")
                restartPhoneCameraWithDevice(nextIndex)
            }
        }, nextDevice)
    }

    private fun restartPhoneCameraWithDevice(index: Int) {
        try {
            phoneCapturer?.stopCapture()
            phoneCapturer?.dispose()
            phoneCapturer = null

            currentPhoneDeviceIndex = index
            val enumerator = Camera2Enumerator(context)
            val selectedDevice = availablePhoneDevices[currentPhoneDeviceIndex]

            phoneCapturer = enumerator.createCapturer(selectedDevice, null)
            phoneCapturer?.initialize(phoneTextureHelper, context, phoneSource!!.capturerObserver)
            phoneCapturer?.startCapture(currentWidth, currentHeight, currentFps)
            Log.i(tag, "Clean restart switch complete to: $selectedDevice")
        } catch (e: Exception) {
            Log.e(tag, "Failed to restart camera with device index $index", e)
        }
    }

    fun requestUsbPermission() {
        usbCapturer?.requestDevicePermission()
    }

    fun setQualityPreset(width: Int, height: Int, fps: Int) {
        currentWidth = width
        currentHeight = height
        currentFps = fps
        phoneCapturer?.changeCaptureFormat(width, height, fps)
        usbCapturer?.changeCaptureFormat(width, height, fps)
        Log.i(tag, "Quality format set to ${width}x${height} @ ${fps}fps")
    }

    fun stopCameraCapture() {
        try {
            phoneCapturer?.stopCapture()
            usbCapturer?.stopCapture()
            _isStreaming.value = false
        } catch (_: Exception) {}
    }

    fun release() {
        strobeJob?.cancel()
        setTorchHardware(false)
        closePeerConnection()
        try {
            phoneCapturer?.stopCapture()
            phoneCapturer?.dispose()
            usbCapturer?.stopCapture()
            usbCapturer?.dispose()
            phoneTextureHelper?.dispose()
            usbTextureHelper?.dispose()
            peerConnectionFactory?.dispose()
            eglBase.release()
        } catch (_: Exception) {}
    }
}
