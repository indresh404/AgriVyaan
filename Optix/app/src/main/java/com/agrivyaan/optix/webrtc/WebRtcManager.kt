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

import java.nio.ByteBuffer
import java.util.Collections
import java.util.concurrent.ConcurrentHashMap

enum class StreamMode {
    PHONE, USB, BOTH
}

enum class QualityPreset(val width: Int, val height: Int, val fps: Int, val targetBitrateKbps: Int) {
    FAST_LOW_LATENCY(854, 480, 30, 800),     // 480p, 800 kbps: Ultra-fast low latency, weak Wi-Fi saving
    BALANCED(1280, 720, 30, 2000),           // 720p, 2000 kbps: High performance balanced
    HIGH_FIDELITY(1920, 1080, 30, 3500)      // 1080p, 3500 kbps: Full HD clarity
}

class WebRtcManager(
    private val context: Context,
    private val onSendSignalingMessage: (clientId: String, JSONObject) -> Unit
) {
    private val tag = "WebRtcManager"
    private val scope = CoroutineScope(Dispatchers.Main)

    private val eglBase: EglBase = EglBase.create()
    val eglContext: EglBase.Context get() = eglBase.eglBaseContext
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

    // Hardware recording sink
    private var recordingSink: VideoSink? = null

    // Active PeerConnections & DataChannels keyed by unique client/viewer ID
    private val clientPeerConnections = ConcurrentHashMap<String, PeerConnection>()
    private val clientDataChannels = ConcurrentHashMap<String, DataChannel>()
    private val pendingRemoteCandidates = ConcurrentHashMap<String, MutableList<IceCandidate>>()
    val clientPeerConnectionsCount: Int get() = clientPeerConnections.size

    // State
    private val _isStreaming = MutableStateFlow(false)
    val isStreaming: StateFlow<Boolean> = _isStreaming.asStateFlow()

    private var activeMode = StreamMode.PHONE
    private var isPhoneCapturing = false
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
                    isPhoneCapturing = true
                }
                override fun onCameraClosed() {
                    Log.i(tag, "Phone camera closed")
                    isPhoneCapturing = false
                }
            })

            val factory = peerConnectionFactory ?: return
            phoneSource = factory.createVideoSource(phoneCapturer!!.isScreencast)
            phoneCapturer!!.initialize(phoneTextureHelper, context, phoneSource!!.capturerObserver)
            phoneCapturer!!.startCapture(width, height, fps)
            isPhoneCapturing = true

            phoneVideoTrack = factory.createVideoTrack("OPTIX_PHONE_TRACK", phoneSource).apply {
                setEnabled(true)
            }
            attachRecordingSinkToActiveTrack()
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
                    onSendSignalingMessage("*", json)
                },
                onCameraReady = {
                    Log.i(tag, "USB Camera is READY with active preview pipeline!")
                    scope.launch(Dispatchers.Main) {
                        if (activeMode == StreamMode.USB || activeMode == StreamMode.BOTH) {
                            Log.i(tag, "USB Camera ready: starting/updating live stream to all clients")
                            renegotiateAllClients()
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
            attachRecordingSinkToActiveTrack()
            Log.i(tag, "USB Camera pipeline initialized and listening for OTG device")
        } catch (e: Exception) {
            Log.e(tag, "Error starting USB camera pipeline", e)
        }
    }

    @Synchronized
    fun setStreamMode(mode: StreamMode) {
        if (activeMode == mode) {
            Log.d(tag, "Stream mode already $mode, no-op")
            return
        }
        val previousMode = activeMode
        activeMode = mode
        Log.i(tag, "Stream mode changed from $previousMode to: $mode")

        if (mode == StreamMode.USB) {
            try {
                phoneCapturer?.stopCapture()
                isPhoneCapturing = false
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

        // Reattach hardware recording sink to active track
        attachRecordingSinkToActiveTrack()

        // Renegotiate peer connections for all clients with updated tracks
        renegotiateAllClients()
    }

    @Synchronized
    fun setRecordingSink(sink: VideoSink?) {
        recordingSink?.let { old ->
            phoneVideoTrack?.removeSink(old)
            usbVideoTrack?.removeSink(old)
        }
        recordingSink = sink
        attachRecordingSinkToActiveTrack()
        Log.i(tag, "Recording sink updated: $sink (activeMode: $activeMode)")
    }

    private fun attachRecordingSinkToActiveTrack() {
        val sink = recordingSink ?: return
        when (activeMode) {
            StreamMode.PHONE -> {
                usbVideoTrack?.removeSink(sink)
                phoneVideoTrack?.removeSink(sink)
                phoneVideoTrack?.addSink(sink)
            }
            StreamMode.USB -> {
                phoneVideoTrack?.removeSink(sink)
                usbVideoTrack?.removeSink(sink)
                usbVideoTrack?.addSink(sink)
            }
            StreamMode.BOTH -> {
                usbVideoTrack?.removeSink(sink)
                phoneVideoTrack?.removeSink(sink)
                phoneVideoTrack?.addSink(sink)
            }
        }
    }

    private fun ensurePhoneCameraCapturing() {
        try {
            if (phoneCapturer == null || phoneVideoTrack == null) {
                startPhoneCamera(currentWidth, currentHeight, currentFps)
            } else if (!isPhoneCapturing) {
                phoneCapturer?.startCapture(currentWidth, currentHeight, currentFps)
                isPhoneCapturing = true
            }
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
                if (isUsbConnected && usbCapturer != null) {
                    usbVideoTrack?.setEnabled(true)
                }
            }
            _isStreaming.value = true
            Log.i(tag, "Camera capture confirmed active for mode: $activeMode")
        } catch (e: Exception) {
            Log.e(tag, "Error in ensureCameraRunning", e)
        }
    }

    @Synchronized
    fun startStreamingToClient(clientId: String) {
        scope.launch {
            ensureCameraRunning()
            closeClientConnection(clientId)

            val factory = peerConnectionFactory ?: run {
                Log.e(tag, "PeerConnectionFactory is null!")
                return@launch
            }

            val rtcConfig = PeerConnection.RTCConfiguration(emptyList()).apply {
                sdpSemantics = PeerConnection.SdpSemantics.UNIFIED_PLAN
                continualGatheringPolicy = PeerConnection.ContinualGatheringPolicy.GATHER_CONTINUALLY
            }

            val pc = factory.createPeerConnection(rtcConfig, object : PeerConnection.Observer {
                override fun onIceCandidate(candidate: IceCandidate?) {
                    if (candidate != null) {
                        val json = JSONObject().apply {
                            put("type", "candidate")
                            put("candidate", candidate.sdp)
                            put("sdpMid", candidate.sdpMid)
                            put("sdpMLineIndex", candidate.sdpMLineIndex)
                        }
                        onSendSignalingMessage(clientId, json)
                    }
                }

                override fun onIceCandidatesRemoved(candidates: Array<out IceCandidate>?) {}
                override fun onSignalingChange(state: PeerConnection.SignalingState?) {
                    Log.d(tag, "[$clientId] SignalingState: $state")
                }
                override fun onIceConnectionChange(state: PeerConnection.IceConnectionState?) {
                    Log.d(tag, "[$clientId] IceConnectionState: $state")
                }
                override fun onIceConnectionReceivingChange(receiving: Boolean) {}
                override fun onIceGatheringChange(state: PeerConnection.IceGatheringState?) {
                    Log.d(tag, "[$clientId] IceGatheringState: $state")
                }
                override fun onAddStream(stream: MediaStream?) {}
                override fun onRemoveStream(stream: MediaStream?) {}
                override fun onDataChannel(dc: DataChannel?) {
                    if (dc != null) clientDataChannels[clientId] = dc
                }
                override fun onRenegotiationNeeded() {
                    Log.d(tag, "[$clientId] Renegotiation needed")
                }
                override fun onAddTrack(receiver: RtpReceiver?, mediaStreams: Array<out MediaStream>?) {}
            }) ?: return@launch

            clientPeerConnections[clientId] = pc

            // Add Video Tracks based on active mode
            if (activeMode == StreamMode.PHONE || activeMode == StreamMode.BOTH) {
                phoneVideoTrack?.let { track ->
                    pc.addTrack(track, listOf("optix_phone_stream"))
                    Log.i(tag, "Added Phone Video Track for client: $clientId")
                }
            }

            if (activeMode == StreamMode.USB || activeMode == StreamMode.BOTH) {
                usbVideoTrack?.let { track ->
                    pc.addTrack(track, listOf("optix_usb_stream"))
                    Log.i(tag, "Added USB Webcam Track for client: $clientId")
                }
            }

            // Data Channel for ground controls
            val dcInit = DataChannel.Init().apply {
                ordered = true
                maxRetransmits = -1
            }
            val dc = pc.createDataChannel("control", dcInit)
            if (dc != null) clientDataChannels[clientId] = dc

            // Create Offer with high quality constraints
            val mediaConstraints = MediaConstraints().apply {
                mandatory.add(MediaConstraints.KeyValuePair("OfferToReceiveVideo", "false"))
                mandatory.add(MediaConstraints.KeyValuePair("OfferToReceiveAudio", "false"))
            }

            pc.createOffer(object : SdpObserver {
                override fun onCreateSuccess(sdp: SessionDescription?) {
                    if (sdp == null) return
                    // Boost video bitrate in SDP for high visual fidelity
                    val boostedSdp = boostSdpBitrate(sdp.description)
                    val modifiedDesc = SessionDescription(sdp.type, boostedSdp)

                    pc.setLocalDescription(object : SdpObserver {
                        override fun onCreateSuccess(desc: SessionDescription?) {}
                        override fun onSetSuccess() {
                            Log.i(tag, "Local SDP offer set for $clientId. Transmitting to client...")
                            val json = JSONObject().apply {
                                put("type", "offer")
                                put("sdp", modifiedDesc.description)
                                put("mode", activeMode.name)
                            }
                            onSendSignalingMessage(clientId, json)
                        }
                        override fun onCreateFailure(err: String?) {
                            Log.e(tag, "Set local description failure for $clientId: $err")
                        }
                        override fun onSetFailure(err: String?) {
                            Log.e(tag, "Set local description failure for $clientId: $err")
                        }
                    }, modifiedDesc)
                }

                override fun onSetSuccess() {}
                override fun onCreateFailure(err: String?) {
                    Log.e(tag, "Create offer failed for $clientId: $err")
                }
                override fun onSetFailure(err: String?) {
                    Log.e(tag, "Set description failed for $clientId: $err")
                }
            }, mediaConstraints)
        }
    }

    @Synchronized
    fun renegotiateAllClients() {
        val clients = clientPeerConnections.keys.toList()
        Log.i(tag, "Renegotiating all active viewer clients (${clients.size})...")
        for (clientId in clients) {
            startStreamingToClient(clientId)
        }
    }

    private fun boostSdpBitrate(sdp: String): String {
        val lines = sdp.split("\r\n")
        val result = mutableListOf<String>()
        var inVideo = false

        for (line in lines) {
            // Remove existing bandwidth lines to avoid duplicates
            if (line.startsWith("b=AS:") || line.startsWith("b=TIAS:")) {
                continue
            }
            if (line.startsWith("m=video")) {
                inVideo = true
                result.add(line)
                // 2500 kbps: Ultra-smooth low latency without Wi-Fi bufferbloat
                result.add("b=AS:2500")
                result.add("b=TIAS:2500000")
                result.add("a=x-google-min-bitrate=1000")
                result.add("a=x-google-max-bitrate=2500")
                result.add("a=x-google-start-bitrate=1800")
                continue
            }
            if (line.startsWith("m=audio") || line.startsWith("m=application")) {
                inVideo = false
            }
            result.add(line)
        }
        return result.joinToString("\r\n")
    }

    fun handleRemoteAnswer(clientId: String, sdpDescription: String) {
        val pc = clientPeerConnections[clientId] ?: run {
            Log.w(tag, "No PeerConnection found for client $clientId to set remote answer")
            return
        }
        val sdp = SessionDescription(SessionDescription.Type.ANSWER, sdpDescription)
        pc.setRemoteDescription(object : SdpObserver {
            override fun onCreateSuccess(p0: SessionDescription?) {}
            override fun onSetSuccess() {
                Log.i(tag, "Remote SDP answer set successfully for client $clientId! Live stream transmitting!")
                // Flush pending remote candidates for this client
                pendingRemoteCandidates.remove(clientId)?.let { list ->
                    synchronized(list) {
                        for (cand in list) {
                            try {
                                pc.addIceCandidate(cand)
                            } catch (e: Exception) {
                                Log.w(tag, "Error applying queued ICE candidate for $clientId: ${e.message}")
                            }
                        }
                    }
                }
            }
            override fun onCreateFailure(err: String?) {
                Log.e(tag, "Remote SDP answer error for $clientId: $err")
            }
            override fun onSetFailure(err: String?) {
                Log.e(tag, "Remote SDP answer set failure for $clientId: $err")
            }
        }, sdp)
    }

    fun handleRemoteIceCandidate(clientId: String, sdp: String, sdpMid: String?, sdpMLineIndex: Int) {
        val pc = clientPeerConnections[clientId]
        val candidate = IceCandidate(sdpMid ?: "0", sdpMLineIndex, sdp)
        if (pc != null && pc.remoteDescription != null) {
            pc.addIceCandidate(candidate)
        } else {
            pendingRemoteCandidates.getOrPut(clientId) {
                Collections.synchronizedList(mutableListOf())
            }.add(candidate)
        }
    }

    @Synchronized
    fun closeClientConnection(clientId: String) {
        try {
            pendingRemoteCandidates.remove(clientId)
            clientDataChannels.remove(clientId)?.let { dc ->
                try {
                    dc.close()
                    dc.dispose()
                } catch (_: Exception) {}
            }
            clientPeerConnections.remove(clientId)?.let { pc ->
                try {
                    pc.close()
                    pc.dispose()
                } catch (_: Exception) {}
            }
            Log.i(tag, "Closed PeerConnection for client $clientId. (Remaining active viewers: ${clientPeerConnections.size})")
        } catch (e: Exception) {
            Log.e(tag, "Error closing PeerConnection for $clientId", e)
        }
    }

    @Synchronized
    fun closeAllPeerConnections() {
        for (clientId in clientPeerConnections.keys.toList()) {
            closeClientConnection(clientId)
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

    fun applyQualityPreset(preset: QualityPreset) {
        setQualityPreset(preset.width, preset.height, preset.fps)
        Log.i(tag, "Applied quality preset: ${preset.name} (${preset.width}x${preset.height} @ ${preset.fps}fps, ${preset.targetBitrateKbps} kbps)")
    }

    fun broadcastDataChannel(message: String): Boolean {
        if (clientDataChannels.isEmpty()) return false
        return try {
            val bytes = message.toByteArray(Charsets.UTF_8)
            val buffer = DataChannel.Buffer(ByteBuffer.wrap(bytes), false)
            var sent = false
            for (dc in clientDataChannels.values) {
                if (dc.state() == DataChannel.State.OPEN) {
                    dc.send(buffer)
                    sent = true
                }
            }
            sent
        } catch (e: Exception) {
            Log.w(tag, "broadcastDataChannel error: ${e.message}")
            false
        }
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
        closeAllPeerConnections()
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
