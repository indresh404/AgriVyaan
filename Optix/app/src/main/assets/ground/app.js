/**
 * Optix FPV Ground Control Station - Web Cockpit
 * Ultra-low latency WebRTC dual-camera streaming with tactical OSD HUD
 */

let ws = null;
let pc = null;
let currentMode = 'PHONE'; // PHONE | USB | BOTH
let dualLayout = 'split';  // split | pip
let currentZoom = 1.0;
let currentRotation = 0;
let isTorchOn = false;
let isStrobeOn = false;
let isStreaming = false;
let streamStartTime = null;
let streamTimerInterval = null;
let isMuted = true;
let isVideoFitCover = true;
let isOsdVisible = true;
let isReticleVisible = true;
let reconnectTimer = null;
let pingStartTime = 0;
let pingInterval = null;
let statsInterval = null;
let lastBytesReceived = 0;
let lastStatsTime = 0;
let pendingCandidates = [];

// Recording State
let isRecording = false;
let recordingStartTime = null;
let recordingTimerInterval = null;

// DOM Elements
const connStatusDot = document.getElementById('connStatusDot');
const connStatusText = document.getElementById('connStatusText');
const pingValue = document.getElementById('pingValue');
const wifiSignal = document.getElementById('wifiSignal');
const battLevel = document.getElementById('battLevel');
const osdVolts = document.getElementById('osdVolts');
const devTemp = document.getElementById('devTemp');
const screenState = document.getElementById('screenState');
const statResFps = document.getElementById('statResFps');
const statBitrate = document.getElementById('statBitrate');
const streamTimer = document.getElementById('streamTimer');
const osdActiveMode = document.getElementById('osdActiveMode');
const osdZoom = document.getElementById('osdZoom');
const osdRotation = document.getElementById('osdRotation');

const videoContainer = document.getElementById('videoContainer');
const wrapperPhone = document.getElementById('wrapperPhone');
const wrapperUsb = document.getElementById('wrapperUsb');
const remoteVideoPhone = document.getElementById('remoteVideoPhone');
const remoteVideoUsb = document.getElementById('remoteVideoUsb');
const focusRing = document.getElementById('focusRing');
const fpvOsdLayer = document.getElementById('fpvOsdLayer');
const fpvReticle = document.getElementById('fpvReticle');

const videoPlaceholder = document.getElementById('videoPlaceholder');
const placeholderTitle = document.getElementById('placeholderTitle');
const placeholderText = document.getElementById('placeholderText');
const btnQuickStart = document.getElementById('btnQuickStart');

const btnStreamToggle = document.getElementById('btnStreamToggle');
const btnStreamText = document.getElementById('btnStreamText');
const btnRecordToggle = document.getElementById('btnRecordToggle');
const btnRecordText = document.getElementById('btnRecordText');
const recIcon = document.getElementById('recIcon');
const osdRecBadge = document.getElementById('osdRecBadge');
const osdRecTimer = document.getElementById('osdRecTimer');
const btnDrawerRecord = document.getElementById('btnDrawerRecord');
const recordingNotice = document.getElementById('recordingNotice');
const recordingsList = document.getElementById('recordingsList');

const videoModal = document.getElementById('videoModal');
const modalVideoPlayer = document.getElementById('modalVideoPlayer');
const modalVideoTitle = document.getElementById('modalVideoTitle');
const btnModalDownload = document.getElementById('btnModalDownload');

const btnTorch = document.getElementById('btnTorch');
const btnStrobe = document.getElementById('btnStrobe');
const btnToggleReticle = document.getElementById('btnToggleReticle');
const zoomSlider = document.getElementById('zoomSlider');
const lblZoom = document.getElementById('lblZoom');
const soundBtnCluster = document.getElementById('soundBtnCluster');
const logOutput = document.getElementById('logOutput');

const toolsDrawer = document.getElementById('toolsDrawer');
const drawerBackdrop = document.getElementById('drawerBackdrop');

// Initialize on DOM Ready
document.addEventListener('DOMContentLoaded', () => {
  appendLog('OPTIX FPV Cockpit booting...', 'info');
  setupVideoInteractions();
  fetchSoundList();
  fetchRecordingsList();
  initMap();
  connectWebSocket();
});

// Soundboard API Fetch
async function fetchSoundList() {
  try {
    const res = await fetch('/api/sounds');
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const sounds = await res.json();
    renderSoundButtons(sounds);
  } catch (err) {
    console.warn('Could not load sound list:', err);
    renderSoundButtons([{ fileName: 'sound_effect_1.mp3', label: 'Sound Effect 1' }]);
  }
}

function renderSoundButtons(soundList) {
  if (!soundBtnCluster) return;
  soundBtnCluster.innerHTML = '';

  if (!soundList || soundList.length === 0) {
    soundBtnCluster.innerHTML = '<span style="font-size:0.75rem; color:#8b9bb4;">No audio files found</span>';
    return;
  }

  soundList.forEach((sound) => {
    const btn = document.createElement('button');
    btn.className = 'btn btn-action';
    btn.innerHTML = `🔊 ${sound.label || sound.fileName}`;
    btn.onclick = () => playSound(sound.fileName);
    soundBtnCluster.appendChild(btn);
  });

  const stopBtn = document.createElement('button');
  stopBtn.className = 'btn btn-danger';
  stopBtn.innerHTML = '⏹ Stop Audio';
  stopBtn.onclick = () => stopSound();
  soundBtnCluster.appendChild(stopBtn);
}

function playSound(fileName) {
  sendCommand('play_sound', { file: fileName });
  appendLog(`Audio alert triggered: ${fileName} on phone speaker`, 'info');
}

function stopSound() {
  sendCommand('stop_sound');
  appendLog('Stopped audio alert on phone speaker', 'info');
}

// WebSocket Connection
function connectWebSocket() {
  if (ws && (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING)) {
    return;
  }

  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const wsUrl = `${protocol}//${window.location.host}/ws`;

  setConnectionState('connecting', 'Connecting...');
  appendLog(`Opening link: ${wsUrl}`, 'info');

  try {
    ws = new WebSocket(wsUrl);

    ws.onopen = () => {
      setConnectionState('connected', 'Connected');
      appendLog('Ground station connected to drone!', 'success');

      ws.send(JSON.stringify({ cmd: 'start_stream', mode: currentMode }));
      ws.send(JSON.stringify({ cmd: 'get_status' }));

      if (lastTelemetryTime > 0) {
        sendCommand('sync_track', { since: lastTelemetryTime });
      }

      startHeartbeat();
      startStatsMonitor();
    };

    ws.onmessage = async (event) => {
      try {
        const msg = JSON.parse(event.data);
        await handleServerMessage(msg);
      } catch (e) {
        appendLog(`Message error: ${e.message}`, 'error');
      }
    };

    ws.onclose = () => {
      setConnectionState('disconnected', 'Disconnected');
      appendLog('Link lost. Reconnecting in 2s...', 'error');
      closePeerConnection();
      scheduleReconnect();
    };

    ws.onerror = () => {
      appendLog('WebSocket link error', 'error');
    };

  } catch (e) {
    appendLog(`Socket init error: ${e.message}`, 'error');
    scheduleReconnect();
  }
}

function scheduleReconnect() {
  if (reconnectTimer) clearTimeout(reconnectTimer);
  reconnectTimer = setTimeout(() => {
    connectWebSocket();
  }, 2000);
}

function setConnectionState(state, text) {
  if (connStatusDot) {
    connStatusDot.className = 'status-dot';
    if (state === 'connected') connStatusDot.classList.add('dot-green');
    else if (state === 'connecting') connStatusDot.classList.add('dot-amber');
    else connStatusDot.classList.add('dot-red');
  }
  if (connStatusText) connStatusText.textContent = text;
}

// Heartbeat & Ping
function startHeartbeat() {
  if (pingInterval) clearInterval(pingInterval);
  pingInterval = setInterval(() => {
    if (ws && ws.readyState === WebSocket.OPEN) {
      pingStartTime = Date.now();
      ws.send(JSON.stringify({ cmd: 'ping' }));
    }
  }, 3000);
}

// Server Message Handler
async function handleServerMessage(msg) {
  if (msg.type === 'offer') {
    appendLog('Received WebRTC stream offer from drone...', 'info');
    if (msg.mode && msg.mode !== currentMode) {
      applyModeUI(msg.mode);
    }
    await handleOffer(msg.sdp);
    return;
  }

  if (msg.type === 'mode_changed') {
    if (msg.mode && msg.mode !== currentMode) {
      applyModeUI(msg.mode);
      appendLog(`Drone camera mode updated: ${msg.mode}`, 'info');
    }
    return;
  }

  if (msg.type === 'candidate') {
    const cand = new RTCIceCandidate({
      candidate: msg.candidate,
      sdpMid: msg.sdpMid,
      sdpMLineIndex: msg.sdpMLineIndex
    });
    if (pc && pc.remoteDescription && pc.remoteDescription.type) {
      try {
        await pc.addIceCandidate(cand);
      } catch (e) {
        console.warn('ICE candidate error:', e);
      }
    } else {
      pendingCandidates.push(cand);
    }
    return;
  }

  if (msg.type === 'usb_status') {
    if (msg.connected) {
      appendLog(`🔌 USB Webcam detected: ${msg.deviceName}`, 'success');
    } else {
      appendLog('🔌 USB Webcam disconnected', 'info');
    }
    return;
  }

  if (msg.type === 'telemetry') {
    processTelemetry(msg);
    return;
  }

  if (msg.type === 'track_sync') {
    processTrackSync(msg.points);
    return;
  }

  if (msg.type === 'geofence_breach') {
    triggerGeofenceAlert(msg.reason);
    return;
  }

  if (msg.type === 'gps_warning') {
    appendLog(`⚠️ GPS Alert: ${msg.warning}`, 'error');
    return;
  }

  if (msg.type === 'state') {
    if (msg.wifiPercent !== undefined) {
      const dbm = msg.wifiRssi ? ` (${msg.wifiRssi} dBm)` : '';
      if (wifiSignal) wifiSignal.textContent = `Wi-Fi: ${msg.wifiPercent}%${dbm}`;
    }
    if (msg.batteryLevel !== undefined) {
      if (battLevel) battLevel.textContent = `${msg.batteryLevel}%`;
      if (osdVolts) {
        const estVolts = (3.6 + (msg.batteryLevel / 100) * 0.6).toFixed(2);
        osdVolts.textContent = `${estVolts}V`;
      }
    }
    if (msg.temperatureCelsius !== undefined && devTemp) {
      devTemp.textContent = `${msg.temperatureCelsius.toFixed(1)}°C`;
    }
    if (msg.screenOn !== undefined && screenState) {
      screenState.textContent = msg.screenOn ? 'SCR ON' : 'SCR OFF';
    }
    if (msg.isRecording !== undefined) {
      updateRecordingUI(msg.isRecording, msg.recordingStartTime);
    }
    if (msg.telemetry) {
      processTelemetry(msg.telemetry);
    }
    if (msg.qualityPreset) {
      updateQualityPresetUI(msg.qualityPreset);
    }
    return;
  }

  if (msg.type === 'recording_state') {
    updateRecordingUI(msg.isRecording, msg.startTime);
    if (msg.isRecording) {
      appendLog(`🔴 Local hardware recording active on phone: ${msg.fileName || ''}`, 'success');
    } else {
      appendLog(`⏹ Recording finished and saved to phone: ${msg.fileName || ''}`, 'info');
      fetchRecordingsList();
    }
    return;
  }

  if (msg.type === 'ack') {
    if (msg.cmd === 'ping') {
      const rtt = Date.now() - pingStartTime;
      if (pingValue) pingValue.textContent = `${rtt} ms`;
    } else if (msg.cmd === 'start_stream') {
      appendLog('Drone confirmed: Live stream starting', 'success');
      updateStreamButtonState(true);
    } else if (msg.cmd === 'stop_stream') {
      appendLog('Drone confirmed: Live stream stopped', 'info');
      updateStreamButtonState(false);
    } else if (msg.cmd === 'lock_screen') {
      if (msg.success) {
        appendLog('📱 Screen locked successfully on drone phone.', 'success');
        if (screenState) screenState.textContent = 'SCR OFF';
      } else {
        const err = msg.error || 'Device Admin permission is not active on phone.';
        appendLog(`⚠️ Screen Lock Failed: ${err}`, 'error');
        alert(`⚠️ Screen Lock Notice:\n\n${err}\n\nPlease open the Optix app on the drone phone, navigate to "Pre-Flight Check & Settings", and enable "Remote Screen Lock (Device Admin)".`);
      }
    } else if (msg.cmd === 'wake_screen') {
      appendLog('☀️ Drone phone screen woke up.', 'info');
      if (screenState) screenState.textContent = 'SCR ON';
    } else if (msg.cmd === 'start_recording') {
      if (msg.success) {
        updateRecordingUI(true, msg.startTime);
        appendLog(`🔴 Drone confirmed: Local recording started (${msg.fileName || ''})`, 'success');
      } else {
        appendLog('Failed to start recording on drone phone', 'error');
      }
    } else if (msg.cmd === 'stop_recording') {
      updateRecordingUI(false);
      appendLog(`⏹ Drone confirmed: Recording saved to phone storage (${msg.fileName || ''})`, 'success');
      fetchRecordingsList();
    } else if (msg.cmd === 'delete_recording') {
      if (msg.success) {
        appendLog(`🗑 Deleted recording: ${msg.fileName}`, 'info');
        fetchRecordingsList();
      }
    } else if (msg.cmd === 'toggle_torch' || msg.cmd === 'torch') {
      isTorchOn = msg.torchOn;
      if (btnTorch) btnTorch.classList.toggle('active', isTorchOn);
      if (isTorchOn && btnStrobe) {
        isStrobeOn = false;
        btnStrobe.classList.remove('active');
      }
      appendLog(`Torch is ${isTorchOn ? 'ON' : 'OFF'}`, 'info');
    } else if (msg.cmd === 'toggle_strobe') {
      isStrobeOn = msg.strobeOn;
      if (btnStrobe) btnStrobe.classList.toggle('active', isStrobeOn);
      if (isStrobeOn && btnTorch) {
        isTorchOn = false;
        btnTorch.classList.remove('active');
      }
      appendLog(`Airplane Beacon Strobe: ${isStrobeOn ? 'ACTIVATED' : 'STOPPED'}`, 'success');
    } else if (msg.cmd === 'switch_camera') {
      appendLog('Camera lens switched successfully!', 'success');
    } else if (msg.cmd === 'play_sound') {
      appendLog(`Audio playing on phone speaker: ${msg.file}`, 'success');
    } else if (msg.cmd === 'set_camera_quality') {
      if (msg.preset) updateQualityPresetUI(msg.preset);
      appendLog(`Quality preset set to: ${msg.preset}`, 'info');
    } else if (msg.cmd === 'take_snapshot') {
      if (msg.success) {
        appendLog(`📸 Photo snapshot saved with GPS EXIF: ${msg.fileName}`, 'success');
        loadPhotosPins();
      } else {
        appendLog('Failed to capture photo on drone phone', 'error');
      }
    } else if (msg.cmd === 'calibrate_baro') {
      appendLog('⛰ Barometer takeoff baseline calibrated to 0.0m AGL', 'success');
    } else if (msg.cmd === 'set_home') {
      appendLog('🏠 Home coordinate locked', 'success');
    }
    return;
  }

  if (msg.type === 'error') {
    appendLog(`Server Error: ${msg.message}`, 'error');
  }
}

// WebRTC PeerConnection Setup
async function handleOffer(sdpOffer) {
  closePeerConnection();

  pc = new RTCPeerConnection({
    iceServers: []
  });

  pc.ondatachannel = (event) => {
    setupDataChannel(event.channel);
  };

  pc.onicecandidate = (event) => {
    if (event.candidate && ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({
        type: 'candidate',
        candidate: event.candidate.candidate,
        sdpMid: event.candidate.sdpMid,
        sdpMLineIndex: event.candidate.sdpMLineIndex
      }));
    }
  };

  pc.ontrack = (event) => {
    const track = event.track;
    const stream = (event.streams && event.streams[0]) ? event.streams[0] : new MediaStream([track]);
    const trackId = (track.id || '').toUpperCase();
    const streamId = (stream.id || '').toUpperCase();
    appendLog(`★ Video track received: ${track.id || track.kind}`, 'success');

    // Force zero-latency real-time FPV presentation on receiver
    if (event.receiver) {
      if ('playoutDelayHint' in event.receiver) event.receiver.playoutDelayHint = 0;
      if ('jitterBufferTarget' in event.receiver) event.receiver.jitterBufferTarget = 0;
    }

    const attachStream = (videoEl) => {
      if (!videoEl) return;
      if (videoEl.srcObject !== stream) {
        videoEl.srcObject = stream;
      }
      videoEl.muted = true;
      videoEl.playsInline = true;
      videoEl.onloadedmetadata = () => {
        if (videoPlaceholder) videoPlaceholder.style.display = 'none';
      };
      videoEl.onloadeddata = () => {
        if (videoPlaceholder) videoPlaceholder.style.display = 'none';
      };
      videoEl.oncanplay = () => {
        if (videoPlaceholder) videoPlaceholder.style.display = 'none';
      };
      videoEl.onplaying = () => {
        if (videoPlaceholder) videoPlaceholder.style.display = 'none';
      };
      const playPromise = videoEl.play();
      if (playPromise !== undefined) {
        playPromise.then(() => {
          if (videoPlaceholder) videoPlaceholder.style.display = 'none';
        }).catch(_ => {
          setTimeout(() => videoEl.play().catch(_ => {}), 150);
        });
      }
    };

    if (currentMode === 'USB') {
      attachStream(remoteVideoUsb);
      appendLog('Linked track to USB Webcam display', 'success');
    } else if (currentMode === 'PHONE') {
      attachStream(remoteVideoPhone);
      appendLog('Linked track to Phone Camera display', 'info');
    } else {
      // BOTH mode
      if (trackId.includes('USB') || streamId.includes('USB')) {
        attachStream(remoteVideoUsb);
        appendLog('Linked track to USB Dual view', 'info');
      } else {
        attachStream(remoteVideoPhone);
        appendLog('Linked track to Phone Dual view', 'info');
      }
    }

    if (videoPlaceholder) videoPlaceholder.style.display = 'none';
    setConnectionState('connected', 'Live Stream Active');
    updateStreamButtonState(true);
    startStreamTimer();
    updateViewportLayout();
  };

  pc.onconnectionstatechange = () => {
    appendLog(`WebRTC State: ${pc.connectionState}`, 'info');
    if (pc.connectionState === 'connected') {
      if (videoPlaceholder) videoPlaceholder.style.display = 'none';
      setConnectionState('connected', 'Live Stream Active');
      updateStreamButtonState(true);
      startStreamTimer();
    } else if (pc.connectionState === 'disconnected' || pc.connectionState === 'failed') {
      if (isStreaming) {
        if (videoPlaceholder) {
          videoPlaceholder.style.display = 'flex';
          placeholderTitle.textContent = 'STREAM RECONNECTING...';
          placeholderText.textContent = 'Re-establishing video link with drone...';
          btnQuickStart.style.display = 'inline-block';
        }
      }
    }
  };

  try {
    await pc.setRemoteDescription(new RTCSessionDescription({
      type: 'offer',
      sdp: sdpOffer
    }));

    // Process all candidates that arrived before remoteDescription was ready
    if (pendingCandidates.length > 0) {
      for (const cand of pendingCandidates) {
        try {
          await pc.addIceCandidate(cand);
        } catch (e) {
          console.warn('Queued candidate apply error:', e);
        }
      }
      pendingCandidates = [];
    }

    const answer = await pc.createAnswer();
    const boostedAnswerSdp = boostSdpBitrate(answer.sdp);
    const boostedAnswer = new RTCSessionDescription({
      type: 'answer',
      sdp: boostedAnswerSdp
    });

    await pc.setLocalDescription(boostedAnswer);
    appendLog('Transmitting answer to drone...', 'info');

    ws.send(JSON.stringify({
      type: 'answer',
      sdp: boostedAnswer.sdp
    }));

  } catch (err) {
    appendLog(`WebRTC negotiation error: ${err.message}`, 'error');
  }
}

function boostSdpBitrate(sdp) {
  let lines = sdp.split('\r\n');
  let result = [];
  let inVideo = false;

  for (let line of lines) {
    if (line.startsWith('b=AS:') || line.startsWith('b=TIAS:')) {
      continue;
    }
    if (line.startsWith('m=video')) {
      inVideo = true;
      result.push(line);
      result.push('b=AS:2500');
      result.push('b=TIAS:2500000');
      result.push('a=x-google-min-bitrate=1000');
      result.push('a=x-google-max-bitrate=2500');
      result.push('a=x-google-start-bitrate=1800');
      continue;
    }
    if (line.startsWith('m=audio') || line.startsWith('m=application')) {
      inVideo = false;
    }
    result.push(line);
  }
  return result.join('\r\n');
}

function closePeerConnection() {
  pendingCandidates = [];
  if (pc) {
    try { pc.close(); } catch (_) {}
    pc = null;
  }
  if (remoteVideoPhone) remoteVideoPhone.srcObject = null;
  if (remoteVideoUsb) remoteVideoUsb.srcObject = null;
}

// Live Stream Timer
function startStreamTimer() {
  if (!streamStartTime) {
    streamStartTime = Date.now();
  }
  if (streamTimerInterval) clearInterval(streamTimerInterval);
  streamTimerInterval = setInterval(() => {
    if (!streamStartTime) return;
    const elapsed = Math.floor((Date.now() - streamStartTime) / 1000);
    const hrs = String(Math.floor(elapsed / 3600)).padStart(2, '0');
    const mins = String(Math.floor((elapsed % 3600) / 60)).padStart(2, '0');
    const secs = String(elapsed % 60).padStart(2, '0');
    if (streamTimer) streamTimer.textContent = `${hrs}:${mins}:${secs}`;
  }, 1000);
}

function stopStreamTimer() {
  if (streamTimerInterval) clearInterval(streamTimerInterval);
  streamTimerInterval = null;
  streamStartTime = null;
  if (streamTimer) streamTimer.textContent = '00:00:00';
}

// Stream Control (Start/Stop Toggle)
function toggleStreamState() {
  if (isStreaming) {
    stopStream();
  } else {
    startStream();
  }
}

function startStream() {
  isStreaming = true;
  updateStreamButtonState(true);
  if (videoPlaceholder) {
    videoPlaceholder.style.display = 'flex';
    placeholderTitle.textContent = 'INITIALIZING STREAM...';
    placeholderText.textContent = 'Connecting to phone camera pipeline...';
    btnQuickStart.style.display = 'none';
  }
  sendCommand('start_stream', { mode: currentMode });
}

function stopStream() {
  isStreaming = false;
  sendCommand('stop_stream');
  closePeerConnection();
  stopStreamTimer();
  updateStreamButtonState(false);
  if (videoPlaceholder) {
    videoPlaceholder.style.display = 'flex';
    placeholderTitle.textContent = 'STREAM PAUSED';
    placeholderText.textContent = 'Camera is idle. Click Start Stream above or below.';
    btnQuickStart.style.display = 'inline-block';
  }
}

function updateStreamButtonState(active) {
  isStreaming = active;
  if (!btnStreamToggle) return;
  if (active) {
    btnStreamToggle.className = 'btn-top btn-stream-stop';
    btnStreamToggle.innerHTML = '<span class="btn-icon">⏹</span><span class="btn-text">STOP STREAM</span>';
  } else {
    btnStreamToggle.className = 'btn-top btn-stream-start';
    btnStreamToggle.innerHTML = '<span class="btn-icon">▶</span><span class="btn-text">START STREAM</span>';
  }
}

// Commands Helper
function sendCommand(cmd, payload = {}) {
  if (!ws || ws.readyState !== WebSocket.OPEN) {
    appendLog(`Cannot send '${cmd}': Offline`, 'error');
    return;
  }
  ws.send(JSON.stringify({ cmd: cmd, ...payload }));
}

// Camera Flipping & Strobe
function switchCamera() {
  sendCommand('switch_camera');
  appendLog('Switching camera lens...', 'info');
}

function toggleStrobe() {
  isStrobeOn = !isStrobeOn;
  if (btnStrobe) btnStrobe.classList.toggle('active', isStrobeOn);
  if (isStrobeOn && isTorchOn) {
    isTorchOn = false;
    if (btnTorch) btnTorch.classList.remove('active');
  }
  sendCommand('toggle_strobe');
  appendLog(`Airplane Beacon: ${isStrobeOn ? 'ACTIVATED' : 'STOPPED'}`, 'success');
}

function toggleTorch() {
  isTorchOn = !isTorchOn;
  if (btnTorch) btnTorch.classList.toggle('active', isTorchOn);
  if (isTorchOn && isStrobeOn) {
    isStrobeOn = false;
    if (btnStrobe) btnStrobe.classList.remove('active');
  }
  sendCommand('toggle_torch');
  appendLog(`Torch: ${isTorchOn ? 'ON' : 'OFF'}`, 'info');
}

function cycleCameraSource() {
  if (currentMode === 'PHONE') {
    switchStreamMode('USB');
  } else if (currentMode === 'USB') {
    switchStreamMode('BOTH');
  } else {
    switchStreamMode('PHONE');
  }
}

// Camera Mode Switching
function applyModeUI(mode) {
  currentMode = mode;
  document.querySelectorAll('.btn-mode').forEach(b => b.classList.remove('active'));
  const activeBtn = document.getElementById(`btnMode${mode.charAt(0) + mode.slice(1).toLowerCase()}`);
  if (activeBtn) activeBtn.classList.add('active');

  const sourceBtnText = document.getElementById('btnCamSourceText');
  if (sourceBtnText) {
    if (mode === 'PHONE') sourceBtnText.textContent = 'CAM: PHONE';
    else if (mode === 'USB') sourceBtnText.textContent = 'CAM: USB';
    else sourceBtnText.textContent = 'CAM: DUAL';
  }

  if (osdActiveMode) {
    if (mode === 'PHONE') osdActiveMode.textContent = '[ PHONE CAMERA ]';
    else if (mode === 'USB') osdActiveMode.textContent = '[ USB WEBCAM ]';
    else osdActiveMode.textContent = '[ DUAL FPV ]';
  }

  updateViewportLayout();
}

function switchStreamMode(mode) {
  applyModeUI(mode);

  if (mode === 'USB') {
    if (remoteVideoPhone) remoteVideoPhone.srcObject = null;
  } else if (mode === 'PHONE') {
    if (remoteVideoUsb) remoteVideoUsb.srcObject = null;
  }

  sendCommand('set_mode', { mode: mode });
  appendLog(`Switched camera source to: ${mode}`, 'info');
}

function updateViewportLayout() {
  if (!videoContainer) return;
  videoContainer.className = 'video-container';

  if (currentMode === 'PHONE') {
    wrapperPhone.style.display = 'flex';
    wrapperUsb.style.display = 'none';
    videoContainer.classList.add('mode-phone');
  } else if (currentMode === 'USB') {
    wrapperPhone.style.display = 'none';
    wrapperUsb.style.display = 'flex';
    videoContainer.classList.add('mode-usb');
  } else if (currentMode === 'BOTH') {
    wrapperPhone.style.display = 'flex';
    wrapperUsb.style.display = 'flex';
    if (dualLayout === 'split') {
      videoContainer.classList.add('mode-both-split');
    } else {
      videoContainer.classList.add('mode-both-pip');
    }
  }
}

function toggleDualLayout() {
  if (currentMode !== 'BOTH') {
    switchStreamMode('BOTH');
    return;
  }
  dualLayout = dualLayout === 'split' ? 'pip' : 'split';
  updateViewportLayout();
  appendLog(`Dual layout: ${dualLayout.toUpperCase()}`, 'info');
}

// Digital Zoom & Mount Rotation
function onZoomSlider(val) {
  currentZoom = parseFloat(val);
  applyZoom();
}

function stepZoom(delta) {
  let next = currentZoom + delta;
  next = Math.max(1.0, Math.min(next, 6.0));
  currentZoom = parseFloat(next.toFixed(1));
  if (zoomSlider) zoomSlider.value = currentZoom;
  applyZoom();
}

function resetZoom() {
  currentZoom = 1.0;
  if (zoomSlider) zoomSlider.value = 1.0;
  applyZoom();
}

function applyZoom() {
  const str = currentZoom.toFixed(1) + 'x';
  if (lblZoom) lblZoom.textContent = str;
  if (osdZoom) osdZoom.textContent = str.toUpperCase();
  updateVideoTransform();
}

function setRotation(degrees) {
  currentRotation = degrees;
  if (osdRotation) osdRotation.textContent = `${degrees}°`;
  updateVideoTransform();
  document.querySelectorAll('.btn-mini').forEach(b => b.classList.remove('active'));
  const activeBtn = document.getElementById(`btnRot${degrees}`);
  if (activeBtn) activeBtn.classList.add('active');
  appendLog(`Mount rotation set to ${degrees}°`, 'info');
}

function updateVideoTransform() {
  const target = currentMode === 'USB' ? remoteVideoUsb : remoteVideoPhone;
  if (!target) return;
  target.style.transform = `rotate(${currentRotation}deg) scale(${currentZoom})`;
  target.style.transformOrigin = 'center center';
  target.style.transition = 'transform 0.15s ease-out';
}

function setQuality(w, h, fps) {
  sendCommand('set_quality', { width: w, height: h, fps: fps });
  appendLog(`Quality preset sent: ${w}x${h} @ ${fps}fps`, 'info');
}

// Snapshot Capture & Download
function captureSnapshot() {
  const target = currentMode === 'USB' ? remoteVideoUsb : remoteVideoPhone;
  if (!target || !target.videoWidth) {
    appendLog('Cannot capture snapshot: No active frame', 'error');
    return;
  }

  const canvas = document.createElement('canvas');
  canvas.width = target.videoWidth;
  canvas.height = target.videoHeight;
  const ctx = canvas.getContext('2d');

  if (currentRotation !== 0) {
    ctx.translate(canvas.width / 2, canvas.height / 2);
    ctx.rotate((currentRotation * Math.PI) / 180);
    ctx.drawImage(target, -canvas.width / 2, -canvas.height / 2);
  } else {
    ctx.drawImage(target, 0, 0);
  }

  const dataUrl = canvas.toDataURL('image/jpeg', 0.95);
  const a = document.createElement('a');
  a.href = dataUrl;
  const timeStr = new Date().toISOString().replace(/[:.]/g, '-');
  a.download = `Optix_${currentMode}_${timeStr}.jpg`;
  a.click();
  appendLog('High-res snapshot captured & saved locally!', 'success');

  // Trigger high-res camera capture on drone phone with EXIF GPS geotagging
  sendCommand('take_snapshot');
  appendLog('Requesting phone to embed EXIF GPS geotag & save snapshot...', 'info');
}

// FPV Reticle & OSD Toggles
function toggleReticle() {
  isReticleVisible = !isReticleVisible;
  if (fpvReticle) fpvReticle.classList.toggle('hidden', !isReticleVisible);
  if (btnToggleReticle) btnToggleReticle.classList.toggle('active', isReticleVisible);
  appendLog(`FPV Reticle: ${isReticleVisible ? 'SHOWN' : 'HIDDEN'}`, 'info');
}

function toggleOsdTelemetry() {
  isOsdVisible = !isOsdVisible;
  if (fpvOsdLayer) fpvOsdLayer.style.display = isOsdVisible ? 'flex' : 'none';
  const btn = document.getElementById('btnToggleOsd');
  if (btn) btn.classList.toggle('active', isOsdVisible);
  appendLog(`Telemetry OSD: ${isOsdVisible ? 'VISIBLE' : 'HIDDEN'}`, 'info');
}

function toggleVideoFit() {
  isVideoFitCover = !isVideoFitCover;
  if (remoteVideoPhone) remoteVideoPhone.classList.toggle('fill-mode', isVideoFitCover);
  if (remoteVideoUsb) remoteVideoUsb.classList.toggle('fill-mode', isVideoFitCover);
  const btnFit = document.getElementById('btnQuickFit');
  const btnIcon = document.getElementById('btnFitMode');
  if (btnFit) {
    const textSpan = document.getElementById('btnFitText');
    if (textSpan) textSpan.textContent = isVideoFitCover ? 'FILL' : 'FIT';
  }
  if (btnIcon) btnIcon.textContent = isVideoFitCover ? '🔳' : '🔲';
  appendLog(`Display mode: ${isVideoFitCover ? 'FULL-SCREEN EDGE-TO-EDGE FILL' : 'FULL CLEAR VIEW (16:9 NO CROP)'}`, 'info');
}

function requestUsbPermission() {
  sendCommand('request_usb_permission');
  appendLog('Sent USB camera permission request to phone screen. Please check phone!', 'info');
}

function toggleFullscreen() {
  if (!document.fullscreenElement) {
    document.documentElement.requestFullscreen().catch(_ => {});
  } else {
    document.exitFullscreen().catch(_ => {});
  }
}

function toggleAudio() {
  isMuted = !isMuted;
  if (remoteVideoPhone) remoteVideoPhone.muted = isMuted;
  if (remoteVideoUsb) remoteVideoUsb.muted = isMuted;
  const btnMute = document.getElementById('btnMute');
  if (btnMute) btnMute.textContent = isMuted ? '🔇' : '🔊';
  appendLog(`Audio: ${isMuted ? 'MUTED' : 'UNMUTED'}`, 'info');
}

// Tactical Tools Drawer
function toggleToolsDrawer() {
  if (!toolsDrawer) return;
  const isOpen = toolsDrawer.classList.contains('open');
  if (isOpen) {
    closeToolsDrawer();
  } else {
    openToolsDrawer();
  }
}

function openToolsDrawer() {
  if (toolsDrawer) toolsDrawer.classList.add('open');
  if (drawerBackdrop) drawerBackdrop.classList.add('active');
}

function closeToolsDrawer() {
  if (toolsDrawer) toolsDrawer.classList.remove('open');
  if (drawerBackdrop) drawerBackdrop.classList.remove('active');
}

// Tap to Focus & Touch Gestures
function setupVideoInteractions() {
  if (!remoteVideoPhone) return;

  remoteVideoPhone.addEventListener('click', (e) => {
    const rect = remoteVideoPhone.getBoundingClientRect();
    if (rect.width <= 0) return;
    const clickX = e.clientX - rect.left;
    const clickY = e.clientY - rect.top;

    if (focusRing) {
      focusRing.style.left = `${clickX}px`;
      focusRing.style.top = `${clickY}px`;
      focusRing.classList.add('active');
      setTimeout(() => focusRing.classList.remove('active'), 800);
    }

    if (remoteVideoPhone.paused) {
      remoteVideoPhone.play();
    }
  });

  remoteVideoPhone.addEventListener('wheel', (e) => {
    e.preventDefault();
    const delta = e.deltaY < 0 ? 0.2 : -0.2;
    stepZoom(delta);
  }, { passive: false });
}

// Live Video Bitrate & FPS Monitor
function startStatsMonitor() {
  if (statsInterval) clearInterval(statsInterval);
  statsInterval = setInterval(async () => {
    if (!pc) return;

    try {
      const stats = await pc.getStats();
      stats.forEach((report) => {
        if (report.type === 'inbound-rtp' && report.kind === 'video') {
          const now = report.timestamp;
          const bytes = report.bytesReceived;

          if (lastStatsTime > 0 && bytes >= lastBytesReceived) {
            const deltaMs = now - lastStatsTime;
            const deltaBytes = bytes - lastBytesReceived;
            const kbps = Math.round((deltaBytes * 8) / deltaMs);
            if (statBitrate) statBitrate.textContent = `${kbps} kbps`;
          }
          lastBytesReceived = bytes;
          lastStatsTime = now;

          if (report.frameWidth && report.frameHeight) {
            const fps = report.framesPerSecond ? Math.round(report.framesPerSecond) : 30;
            if (statResFps) statResFps.textContent = `${report.frameWidth}x${report.frameHeight} @ ${fps}fps`;
          }
        }
      });
    } catch (_) {}
  }, 1000);
}

// Logging
function appendLog(text, level = 'info') {
  if (!logOutput) return;
  const item = document.createElement('div');
  item.className = `log-item ${level}`;
  const now = new Date();
  const time = `${String(now.getHours()).padStart(2,'0')}:${String(now.getMinutes()).padStart(2,'0')}:${String(now.getSeconds()).padStart(2,'0')}`;
  item.textContent = `[${time}] ${text}`;
  logOutput.appendChild(item);
  logOutput.scrollTop = logOutput.scrollHeight;
}

function clearLogs() {
  if (logOutput) logOutput.innerHTML = '';
}

// ==========================================================================
// Local Video Recording & Footage Management
// ==========================================================================

function toggleRecording() {
  if (!isRecording) {
    sendCommand('start_recording');
    appendLog('Sending command: START local phone video recording...', 'info');
  } else {
    sendCommand('stop_recording');
    appendLog('Sending command: STOP recording & finalize MP4 footage...', 'info');
  }
}

function updateRecordingUI(recording, startTime) {
  isRecording = !!recording;

  if (isRecording) {
    if (startTime && !recordingStartTime) {
      recordingStartTime = startTime;
    } else if (!recordingStartTime) {
      recordingStartTime = Date.now();
    }

    if (btnRecordToggle) {
      btnRecordToggle.classList.add('recording');
      if (btnRecordText) btnRecordText.textContent = 'STOP REC';
      if (recIcon) recIcon.textContent = '⏹';
    }
    if (btnDrawerRecord) {
      btnDrawerRecord.classList.add('recording');
      btnDrawerRecord.innerHTML = '⏹ Stop Phone Recording';
    }
    if (recordingNotice) recordingNotice.style.display = 'flex';
    if (osdRecBadge) osdRecBadge.style.display = 'inline-flex';

    startRecordingTimer();
  } else {
    recordingStartTime = null;
    stopRecordingTimer();

    if (btnRecordToggle) {
      btnRecordToggle.classList.remove('recording');
      if (btnRecordText) btnRecordText.textContent = 'REC';
      if (recIcon) recIcon.textContent = '⏺';
    }
    if (btnDrawerRecord) {
      btnDrawerRecord.classList.remove('recording');
      btnDrawerRecord.innerHTML = '⏺ Start Phone Recording';
    }
    if (recordingNotice) recordingNotice.style.display = 'none';
    if (osdRecBadge) osdRecBadge.style.display = 'none';
  }
}

function startRecordingTimer() {
  if (recordingTimerInterval) clearInterval(recordingTimerInterval);
  updateRecordingTimerDisplay();
  recordingTimerInterval = setInterval(updateRecordingTimerDisplay, 1000);
}

function stopRecordingTimer() {
  if (recordingTimerInterval) clearInterval(recordingTimerInterval);
  recordingTimerInterval = null;
}

function updateRecordingTimerDisplay() {
  if (!recordingStartTime || !osdRecTimer) return;
  const elapsed = Math.floor((Date.now() - recordingStartTime) / 1000);
  const hrs = String(Math.floor(elapsed / 3600)).padStart(2, '0');
  const mins = String(Math.floor((elapsed % 3600) / 60)).padStart(2, '0');
  const secs = String(elapsed % 60).padStart(2, '0');
  osdRecTimer.textContent = `REC ${hrs}:${mins}:${secs}`;
}

async function fetchRecordingsList() {
  if (!recordingsList) return;
  try {
    const res = await fetch('/api/recordings');
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const list = await res.json();
    renderRecordingsList(list);
  } catch (e) {
    console.warn('Failed to fetch recordings list:', e);
  }
}

function renderRecordingsList(list) {
  if (!recordingsList) return;
  recordingsList.innerHTML = '';

  if (!list || list.length === 0) {
    recordingsList.innerHTML = '<span style="font-size:0.75rem; color:#8b9bb4; padding:8px; display:block; text-align:center;">No recordings saved yet</span>';
    return;
  }

  list.forEach(rec => {
    const card = document.createElement('div');
    card.className = 'recording-card';
    card.innerHTML = `
      <div class="recording-card-title">📹 ${escapeHtml(rec.fileName)}</div>
      <div class="recording-card-meta">
        <span>📅 ${escapeHtml(rec.dateFormatted)}</span>
        <span>💾 ${escapeHtml(rec.sizeFormatted)}</span>
      </div>
      <div class="recording-btn-row">
        <a class="btn-card btn-card-download" href="/recordings/${encodeURIComponent(rec.fileName)}?download=1" download="${escapeHtml(rec.fileName)}" title="Download to PC/Laptop">
          ⬇ Download
        </a>
        <button class="btn-card btn-card-play" onclick="openVideoModal('${escapeJs(rec.fileName)}', '/recordings/${encodeURIComponent(rec.fileName)}')" title="Preview Footage">
          ▶ Play
        </button>
        <button class="btn-card btn-card-delete" onclick="deleteRecording('${escapeJs(rec.fileName)}')" title="Delete Footage">
          🗑
        </button>
      </div>
    `;
    recordingsList.appendChild(card);
  });
}

function openVideoModal(fileName, videoUrl) {
  if (!videoModal || !modalVideoPlayer) return;
  modalVideoTitle.textContent = fileName;
  modalVideoPlayer.src = videoUrl;
  if (btnModalDownload) {
    btnModalDownload.href = `${videoUrl}?download=1`;
    btnModalDownload.download = fileName;
  }
  videoModal.style.display = 'flex';
  modalVideoPlayer.play().catch(_ => {});
}

function closeVideoModal(e) {
  if (e && e.target !== videoModal && e.type !== 'click') return;
  if (modalVideoPlayer) {
    modalVideoPlayer.pause();
    modalVideoPlayer.src = '';
  }
  if (videoModal) videoModal.style.display = 'none';
}

async function deleteRecording(fileName) {
  if (!confirm(`Are you sure you want to delete "${fileName}" from phone storage?`)) return;
  try {
    const res = await fetch(`/api/recordings/${encodeURIComponent(fileName)}`, { method: 'DELETE' });
    const data = await res.json();
    if (data.success) {
      appendLog(`Deleted footage: ${fileName}`, 'info');
      fetchRecordingsList();
    } else {
      appendLog(`Could not delete footage: ${fileName}`, 'error');
    }
  } catch (err) {
    sendCommand('delete_recording', { fileName: fileName });
  }
}

function escapeHtml(str) {
  if (!str) return '';
  return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

function escapeJs(str) {
  if (!str) return '';
  return str.replace(/'/g, "\\'").replace(/"/g, '\\"');
}



// ==========================================================================
// WebRTC Ultra-Low Latency Data Channel & Reconnection Sync
// ==========================================================================

let dataChannel = null;
let lastTelemetry = null;
let lastTelemetryTime = 0;
let gpsWatchdogTimer = null;
let coordFormat = 'DECIMAL'; // DECIMAL | DMS

function setupDataChannel(channel) {
  dataChannel = channel;
  appendLog('WebRTC data channel handshake initialized...', 'info');

  dataChannel.onopen = () => {
    appendLog('★ WebRTC ultra-low-latency telemetry channel OPEN', 'success');
    if (lastTelemetryTime > 0) {
      sendCommand('sync_track', { since: lastTelemetryTime });
    }
  };

  dataChannel.onclose = () => {
    appendLog('WebRTC data channel closed', 'info');
  };

  dataChannel.onerror = (err) => {
    console.warn('Data channel error:', err);
  };

  dataChannel.onmessage = (event) => {
    try {
      const msg = JSON.parse(event.data);
      if (msg.type === 'telemetry') {
        processTelemetry(msg);
      } else if (msg.type === 'track_sync') {
        processTrackSync(msg.points);
      } else if (msg.type === 'geofence_breach') {
        triggerGeofenceAlert(msg.reason);
      } else if (msg.type === 'gps_warning') {
        appendLog(`⚠️ GPS Alert: ${msg.warning}`, 'error');
      }
    } catch (e) {
      console.warn('DataChannel JSON parse error:', e);
    }
  };
}

// ==========================================================================
// Viewport Layout Switcher (Video Big / Map Big / Split / PiP)
// ==========================================================================

let currentViewLayout = 'video';

function setViewLayout(mode) {
  currentViewLayout = mode;
  const viewport = document.getElementById('viewport');
  if (!viewport) return;

  viewport.classList.remove('layout-video-big', 'layout-map-big', 'layout-split', 'layout-pip');

  const btnVid = document.getElementById('btnLayoutVideo');
  const btnMap = document.getElementById('btnLayoutMap');
  const btnSplit = document.getElementById('btnLayoutSplit');
  const btnPip = document.getElementById('btnLayoutPip');

  [btnVid, btnMap, btnSplit, btnPip].forEach(btn => { if (btn) btn.classList.remove('active'); });

  if (mode === 'video') {
    viewport.classList.add('layout-video-big');
    if (btnVid) btnVid.classList.add('active');
  } else if (mode === 'map') {
    viewport.classList.add('layout-map-big');
    if (btnMap) btnMap.classList.add('active');
  } else if (mode === 'split') {
    viewport.classList.add('layout-split');
    if (btnSplit) btnSplit.classList.add('active');
  } else if (mode === 'pip') {
    viewport.classList.add('layout-pip');
    if (btnPip) btnPip.classList.add('active');
  }

  appendLog(`Viewport layout switched to: ${mode.toUpperCase()}`, 'info');

  setTimeout(() => {
    if (leafletMap) {
      leafletMap.invalidateSize();
    }
  }, 250);
}

// ==========================================================================
// Tactical Offline Leaflet Map System
// ==========================================================================

let leafletMap = null;
let activeTileLayer = null;
let activeMapLayerName = 'default';
const mapLayersList = ['default', 'satellite', 'terrain', 'grid'];
let currentLayerIndex = 0;

let droneMarker = null;
let accuracyCircle = null;
let homeMarker = null;
let homeLine = null;
let adminMarker = null;
let flightTrackLine = null;
let flightTrackPoints = [];
let isFollowDrone = true;
let isHeadingUp = false;

// Layer Groups
let waypointsLayerGroup = null;
let fieldsLayerGroup = null;
let photosLayerGroup = null;
let measureLayerGroup = null;
let geofenceLayerGroup = null;

function initMap() {
  if (leafletMap || typeof L === 'undefined') return;
  const mapEl = document.getElementById('leafletMap');
  if (!mapEl) return;

  // Initialize Leaflet Map (centered on default coords until GPS fix)
  leafletMap = L.map('leafletMap', {
    zoomControl: false,
    attributionControl: false
  }).setView([20.5937, 78.9629], 15);

  L.control.zoom({ position: 'bottomright' }).addTo(leafletMap);
  L.control.scale({ imperial: false, metric: true, position: 'bottomleft' }).addTo(leafletMap);

  // Layer groups
  waypointsLayerGroup = L.layerGroup().addTo(leafletMap);
  fieldsLayerGroup = L.layerGroup().addTo(leafletMap);
  photosLayerGroup = L.layerGroup().addTo(leafletMap);
  measureLayerGroup = L.layerGroup().addTo(leafletMap);
  geofenceLayerGroup = L.layerGroup().addTo(leafletMap);

  // Setup Tile Layer from phone server MBTiles endpoint
  setupTileLayer('default');

  // Custom Tactical Drone Marker (SVG Arrow rotated to Heading)
  const droneIcon = L.divIcon({
    className: 'drone-map-marker-div',
    html: `<div id="droneMarkerIcon" class="drone-marker-inner">
             <svg width="42" height="42" viewBox="0 0 42 42">
               <circle cx="21" cy="21" r="16" fill="#00e5ff" fill-opacity="0.25" stroke="#00e5ff" stroke-width="2"/>
               <polygon points="21,5 29,31 21,25 13,31" fill="#00e5ff" stroke="#090d14" stroke-width="1.5"/>
               <circle cx="21" cy="21" r="3.5" fill="#ffffff"/>
             </svg>
           </div>`,
    iconSize: [42, 42],
    iconAnchor: [21, 21]
  });

  droneMarker = L.marker([20.5937, 78.9629], { icon: droneIcon, zIndexOffset: 1000 }).addTo(leafletMap);

  accuracyCircle = L.circle([20.5937, 78.9629], {
    radius: 12,
    color: '#00e5ff',
    weight: 1,
    fillColor: '#00e5ff',
    fillOpacity: 0.12
  }).addTo(leafletMap);

  // Flight Track Polyline
  flightTrackLine = L.polyline([], {
    color: '#00e5ff',
    weight: 3.5,
    opacity: 0.85,
    lineJoin: 'round'
  }).addTo(leafletMap);

  // Home Marker
  const homeIcon = L.divIcon({
    className: 'home-marker-div',
    html: `<div class="home-marker-badge">🏠 HOME</div>`,
    iconSize: [60, 24],
    iconAnchor: [30, 12]
  });
  homeMarker = L.marker([0, 0], { icon: homeIcon, opacity: 0, zIndexOffset: 900 }).addTo(leafletMap);
  homeLine = L.polyline([], { color: '#ffea00', weight: 1.5, dashArray: '4, 6', opacity: 0.7 }).addTo(leafletMap);

  // Map Click Listener for interactive tools
  leafletMap.on('click', handleMapClick);

  // Load existing data from phone
  loadWaypoints();
  loadFields();
  loadGeofence();
  loadPhotosPins();
}

function setupTileLayer(layerName = 'default') {
  if (!leafletMap) return;
  activeMapLayerName = layerName;

  if (activeTileLayer) {
    leafletMap.removeLayer(activeTileLayer);
    activeTileLayer = null;
  }

  const gridEl = document.getElementById('mapGridFallback');

  if (layerName === 'grid') {
    if (gridEl) gridEl.style.display = 'block';
    return;
  }

  // Load from phone's offline MBTiles endpoint
  const tileUrl = `/tiles/${encodeURIComponent(layerName)}/{z}/{x}/{y}.png`;
  activeTileLayer = L.tileLayer(tileUrl, {
    maxZoom: 19,
    minZoom: 1,
    tileSize: 256
  });

  activeTileLayer.on('tileerror', () => {
    // If tiles are missing or not downloaded for this region, show tactical grid subtly
    if (gridEl) gridEl.style.display = 'block';
  });

  activeTileLayer.on('tileload', () => {
    if (gridEl) gridEl.style.display = 'none';
  });

  activeTileLayer.addTo(leafletMap);
}

function cycleMapLayer() {
  currentLayerIndex = (currentLayerIndex + 1) % mapLayersList.length;
  const layer = mapLayersList[currentLayerIndex];
  setupTileLayer(layer);
  appendLog(`Switched map layer: ${layer.toUpperCase()}`, 'info');
}

function toggleFollowDrone() {
  isFollowDrone = !isFollowDrone;
  const btn = document.getElementById('btnFollowDrone');
  if (btn) btn.classList.toggle('active', isFollowDrone);
  appendLog(`Drone Center Follow: ${isFollowDrone ? 'ACTIVE' : 'MANUAL PAN'}`, 'info');
  if (isFollowDrone && lastTelemetry && leafletMap) {
    leafletMap.panTo([lastTelemetry.lat, lastTelemetry.lon], { animate: true });
  }
}

function toggleHeadingUp() {
  isHeadingUp = !isHeadingUp;
  const btn = document.getElementById('btnHeadingUp');
  if (btn) btn.classList.toggle('active', isHeadingUp);
  const mapEl = document.getElementById('leafletMap');
  if (!mapEl) return;

  if (isHeadingUp && lastTelemetry) {
    const deg = Math.round(lastTelemetry.heading || 0);
    mapEl.style.transform = `rotate(${-deg}deg)`;
    appendLog(`Heading-Up mode: ${deg}°`, 'info');
  } else {
    mapEl.style.transform = 'rotate(0deg)';
    appendLog('North-Up mode active', 'info');
  }
}

function fitTrackToBounds() {
  if (!leafletMap || flightTrackPoints.length === 0) {
    appendLog('No flight track points recorded yet to fit', 'info');
    return;
  }
  const latLngs = flightTrackPoints.map(p => [p.lat, p.lon]);
  const bounds = L.latLngBounds(latLngs);
  leafletMap.fitBounds(bounds, { padding: [40, 40] });
  appendLog('Zoomed map to fit entire flight track', 'info');
}

// ==========================================================================
// Telemetry Processing & HUD Updates
// ==========================================================================

function processTelemetry(data) {
  if (!data) return;
  lastTelemetry = data;
  lastTelemetryTime = data.timestamp || Date.now();
  resetGpsWatchdog();

  const lat = data.lat !== undefined ? data.lat : data.rawLat;
  const lon = data.lon !== undefined ? data.lon : data.rawLon;
  const heading = data.heading !== undefined ? data.heading : 0;
  const speed = data.speedKmh !== undefined ? data.speedKmh : ((data.speed || 0) * 3.6);
  const altGps = data.altitudeGps !== undefined ? data.altitudeGps : 0;
  const altBaro = data.altitudeBaro !== undefined ? data.altitudeBaro : 0;
  const accuracy = data.accuracy !== undefined ? data.accuracy : 15;
  const satsUsed = data.satellitesUsed !== undefined ? data.satellitesUsed : 0;
  const satsVis = data.satellitesVisible !== undefined ? data.satellitesVisible : 0;
  const fixType = data.fixType || 'Searching';
  const headingSource = data.headingSource || 'GPS';

  // Update Top HUD Telemetry Strip
  const elHeading = document.getElementById('mapHeadingVal');
  const elHeadingSource = document.getElementById('mapHeadingSource');
  if (elHeading) elHeading.textContent = `${Math.round(heading).toString().padStart(3, '0')}°`;
  if (elHeadingSource) elHeadingSource.textContent = headingSource;

  const elCoords = document.getElementById('mapCoordsText');
  if (elCoords) {
    if (coordFormat === 'DMS') {
      elCoords.textContent = `${toDMS(lat, true)}, ${toDMS(lon, false)}`;
    } else {
      elCoords.textContent = `${lat.toFixed(6)}°, ${lon.toFixed(6)}°`;
    }
  }

  const elAltBaro = document.getElementById('mapAltBaro');
  const elAltGps = document.getElementById('mapAltGps');
  if (elAltBaro) elAltBaro.textContent = `${altBaro.toFixed(1)}m`;
  if (elAltGps) elAltGps.textContent = `${altGps.toFixed(1)}m`;

  const elSpeedKmh = document.getElementById('mapSpeedKmh');
  const elSpeedMps = document.getElementById('mapSpeedMps');
  if (elSpeedKmh) elSpeedKmh.textContent = `${speed.toFixed(1)} km/h`;
  if (elSpeedMps) elSpeedMps.textContent = `(${(speed / 3.6).toFixed(1)} m/s)`;

  // Update Bottom Status Strip
  const elFixType = document.getElementById('mapFixType');
  const elSatCount = document.getElementById('mapSatCount');
  const elAccuracy = document.getElementById('mapAccuracy');
  if (elFixType) {
    elFixType.textContent = fixType;
    elFixType.className = `fix-tag ${fixType.toLowerCase().includes('3d') ? 'fix-3d' : ''}`;
  }
  if (elSatCount) elSatCount.textContent = `${satsUsed}/${satsVis} sats`;
  if (elAccuracy) elAccuracy.textContent = `±${accuracy.toFixed(1)}m`;

  // Home Point Telemetry
  if (data.homeLat && data.homeLon && (data.homeLat !== 0 || data.homeLon !== 0)) {
    const distHome = calculateDistance(lat, lon, data.homeLat, data.homeLon);
    const bearHome = calculateBearing(lat, lon, data.homeLat, data.homeLon);
    const elHomeDist = document.getElementById('mapHomeDistance');
    const elHomeBear = document.getElementById('mapHomeBearing');
    if (elHomeDist) elHomeDist.textContent = distHome > 1000 ? `HOME: ${(distHome / 1000).toFixed(2)}km` : `HOME: ${Math.round(distHome)}m`;
    if (elHomeBear) elHomeBear.textContent = `(${Math.round(bearHome)}°)`;

    if (homeMarker) {
      homeMarker.setLatLng([data.homeLat, data.homeLon]);
      homeMarker.setOpacity(1);
    }
    if (homeLine) {
      homeLine.setLatLngs([[lat, lon], [data.homeLat, data.homeLon]]);
    }
  }

  // Update Leaflet Marker & Accuracy
  if (leafletMap && droneMarker) {
    const newPos = [lat, lon];
    droneMarker.setLatLng(newPos);

    const iconDiv = document.getElementById('droneMarkerIcon');
    if (iconDiv) {
      iconDiv.style.transform = `rotate(${heading}deg)`;
    }

    if (accuracyCircle) {
      accuracyCircle.setLatLng(newPos);
      accuracyCircle.setRadius(accuracy);
    }

    // Add point to track
    addTrackPoint(lat, lon, speed, altBaro, data.timestamp);

    // Follow drone if enabled
    if (isFollowDrone) {
      leafletMap.panTo(newPos, { animate: true, duration: 0.3 });
    }

    // Apply heading up rotation if active
    if (isHeadingUp) {
      const mapEl = document.getElementById('leafletMap');
      if (mapEl) mapEl.style.transform = `rotate(${-Math.round(heading)}deg)`;
    }
  }
}

function addTrackPoint(lat, lon, speed, alt, timestamp) {
  flightTrackPoints.push({ lat, lon, speed, alt, timestamp });
  if (flightTrackPoints.length > 8000) {
    flightTrackPoints.shift();
  }
  if (flightTrackLine) {
    flightTrackLine.addLatLng([lat, lon]);
  }
}

function processTrackSync(points) {
  if (!points || !points.length) return;
  appendLog(`Syncing ${points.length} black-box track points from phone...`, 'info');
  for (const p of points) {
    const lat = p.lat !== undefined ? p.lat : p.rawLat;
    const lon = p.lon !== undefined ? p.lon : p.rawLon;
    if (lat && lon) {
      addTrackPoint(lat, lon, p.speedKmh || 0, p.altitudeBaro || 0, p.timestamp || Date.now());
    }
  }
  appendLog(`★ Black-box synchronization complete (${points.length} points restored)`, 'success');
}

function resetGpsWatchdog() {
  if (gpsWatchdogTimer) clearTimeout(gpsWatchdogTimer);
  const iconDiv = document.getElementById('droneMarkerIcon');
  if (iconDiv) iconDiv.classList.remove('marker-stale');

  gpsWatchdogTimer = setTimeout(() => {
    const elapsed = Math.round((Date.now() - (lastTelemetryTime || Date.now())) / 1000);
    appendLog(`⚠️ GPS fix lost: Last seen ${elapsed}s ago`, 'error');
    const iconDiv = document.getElementById('droneMarkerIcon');
    if (iconDiv) iconDiv.classList.add('marker-stale');
    const elFixType = document.getElementById('mapFixType');
    if (elFixType) elFixType.textContent = `Lost (${elapsed}s)`;
  }, 10000);
}

function toDMS(deg, isLat) {
  const absolute = Math.abs(deg);
  const degrees = Math.floor(absolute);
  const minutesNotTruncated = (absolute - degrees) * 60;
  const minutes = Math.floor(minutesNotTruncated);
  const seconds = Math.floor((minutesNotTruncated - minutes) * 60);
  const dir = deg >= 0 ? (isLat ? 'N' : 'E') : (isLat ? 'S' : 'W');
  return `${degrees}°${minutes}'${seconds}"${dir}`;
}

function toggleCoordFormat() {
  coordFormat = coordFormat === 'DECIMAL' ? 'DMS' : 'DECIMAL';
  if (lastTelemetry) processTelemetry(lastTelemetry);
}

function copyCoordinates(e) {
  if (e) e.stopPropagation();
  if (!lastTelemetry) return;
  const text = `${lastTelemetry.lat.toFixed(6)}, ${lastTelemetry.lon.toFixed(6)}`;
  navigator.clipboard.writeText(text).then(() => {
    appendLog(`Copied coordinates to clipboard: ${text}`, 'success');
  }).catch(() => {
    appendLog(`Coordinates: ${text}`, 'info');
  });
}

function resetHomePoint() {
  if (!lastTelemetry) {
    appendLog('Cannot reset home: No active GPS fix', 'error');
    return;
  }
  sendCommand('set_home', { lat: lastTelemetry.lat, lon: lastTelemetry.lon });
  appendLog('Sent request to set Home to current drone position', 'info');
}

// ==========================================================================
// Interactive Map Tools: Waypoints, Field Drawing, Measure, Admin Pin
// ==========================================================================

let isDroppingWaypoint = false;
let pendingWaypointCoord = null;
let isDrawingField = false;
let fieldDrawPoints = [];
let fieldDrawPolyline = null;
let isMeasuring = false;
let measurePoints = [];

function handleMapClick(e) {
  const lat = e.latlng.lat;
  const lon = e.latlng.lng;

  if (isDroppingWaypoint) {
    isDroppingWaypoint = false;
    openWaypointModal(lat, lon);
    return;
  }

  if (isDrawingField) {
    fieldDrawPoints.push(e.latlng);
    if (!fieldDrawPolyline) {
      fieldDrawPolyline = L.polyline([e.latlng], { color: '#00e676', weight: 2.5, dashArray: '5, 5' }).addTo(leafletMap);
    } else {
      fieldDrawPolyline.addLatLng(e.latlng);
    }
    appendLog(`Field vertex ${fieldDrawPoints.length} added. Double-click or click tool again to finish.`, 'info');
    return;
  }

  if (isMeasuring) {
    measurePoints.push(e.latlng);
    if (measurePoints.length === 1) {
      measureLayerGroup.clearLayers();
      L.circleMarker(e.latlng, { radius: 5, color: '#ffeb3b', fillColor: '#ffeb3b', fillOpacity: 0.8 }).addTo(measureLayerGroup);
      appendLog('Measure start point set. Click next point...', 'info');
    } else {
      const p1 = measurePoints[measurePoints.length - 2];
      const p2 = measurePoints[measurePoints.length - 1];
      const dist = calculateDistance(p1.lat, p1.lng, p2.lat, p2.lng);
      L.polyline([p1, p2], { color: '#ffeb3b', weight: 2.5, dashArray: '4, 4' }).addTo(measureLayerGroup);
      L.circleMarker(p2, { radius: 5, color: '#ffeb3b', fillColor: '#ffeb3b', fillOpacity: 0.8 }).addTo(measureLayerGroup);
      appendLog(`Leg distance: ${dist > 1000 ? (dist / 1000).toFixed(2) + ' km' : dist.toFixed(1) + ' m'}`, 'success');
    }
  }
}

function startDropWaypoint() {
  isDroppingWaypoint = true;
  appendLog('📍 Click anywhere on the map to place a waypoint marker', 'info');
}

function openWaypointModal(lat, lon) {
  pendingWaypointCoord = { lat, lon };
  const coordPrev = document.getElementById('wpCoordsPreview');
  if (coordPrev) coordPrev.textContent = `Coordinates: ${lat.toFixed(6)}°, ${lon.toFixed(6)}°`;
  const modal = document.getElementById('waypointModal');
  if (modal) modal.style.display = 'flex';
}

function closeWaypointModal() {
  const modal = document.getElementById('waypointModal');
  if (modal) modal.style.display = 'none';
  pendingWaypointCoord = null;
}

async function saveWaypointConfirm() {
  if (!pendingWaypointCoord) return;
  const name = document.getElementById('wpName').value.trim() || 'Waypoint';
  const category = document.getElementById('wpCategory').value;
  const desc = document.getElementById('wpDesc').value.trim();

  try {
    const res = await fetch('/api/waypoints', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        name,
        category,
        description: desc,
        lat: pendingWaypointCoord.lat,
        lon: pendingWaypointCoord.lon
      })
    });
    const data = await res.json();
    if (data.success) {
      appendLog(`Saved waypoint: ${name}`, 'success');
      loadWaypoints();
    }
  } catch (e) {
    appendLog(`Failed to save waypoint: ${e.message}`, 'error');
  }
  closeWaypointModal();
}

async function loadWaypoints() {
  try {
    const res = await fetch('/api/waypoints');
    if (!res.ok) return;
    const list = await res.json();
    if (!waypointsLayerGroup) return;
    waypointsLayerGroup.clearLayers();

    list.forEach(wp => {
      const pinIcon = L.divIcon({
        className: 'wp-marker-div',
        html: `<div class="wp-marker-pin" title="${escapeHtml(wp.name)}">📍</div>`,
        iconSize: [24, 24],
        iconAnchor: [12, 24]
      });
      const marker = L.marker([wp.lat, wp.lon], { icon: pinIcon }).addTo(waypointsLayerGroup);
      marker.bindPopup(`
        <div style="color:#090d14; font-family:sans-serif;">
          <b>${escapeHtml(wp.name)}</b><br>
          <span style="font-size:0.8rem; color:#666;">${escapeHtml(wp.category)}</span><br>
          <span style="font-size:0.75rem;">${escapeHtml(wp.description || '')}</span><br>
          <button style="margin-top:6px; background:#e53935; color:#fff; border:none; padding:4px 8px; border-radius:4px; cursor:pointer;" onclick="deleteWaypoint('${wp.id}')">Delete</button>
        </div>
      `);
    });
  } catch (_) {}
}

async function deleteWaypoint(id) {
  try {
    await fetch(`/api/waypoints/delete?id=${encodeURIComponent(id)}`, { method: 'POST' });
    loadWaypoints();
    appendLog('Deleted waypoint marker', 'info');
  } catch (_) {}
}

function startDrawField() {
  if (isDrawingField) {
    finishFieldDrawing();
    return;
  }
  isDrawingField = true;
  fieldDrawPoints = [];
  if (fieldDrawPolyline) {
    leafletMap.removeLayer(fieldDrawPolyline);
    fieldDrawPolyline = null;
  }
  const btn = document.getElementById('btnDrawField');
  if (btn) btn.classList.add('active');
  appendLog('📐 Field Drawing active: Click vertices on map. Click 📐 button again when done.', 'info');
}

function finishFieldDrawing() {
  isDrawingField = false;
  const btn = document.getElementById('btnDrawField');
  if (btn) btn.classList.remove('active');

  if (fieldDrawPoints.length < 3) {
    appendLog('Field polygon requires at least 3 points', 'error');
    if (fieldDrawPolyline) leafletMap.removeLayer(fieldDrawPolyline);
    return;
  }

  const areaM2 = calculatePolygonArea(fieldDrawPoints);
  const ha = areaM2 / 10000;
  const acres = areaM2 * 0.000247105;
  const perim = calculatePolygonPerimeter(fieldDrawPoints);

  const elHa = document.getElementById('fieldAreaHectares');
  const elAcres = document.getElementById('fieldAreaAcres');
  const elPerim = document.getElementById('fieldPerimeter');
  if (elHa) elHa.textContent = `${ha.toFixed(2)} ha`;
  if (elAcres) elAcres.textContent = `${acres.toFixed(2)} acres`;
  if (elPerim) elPerim.textContent = `${perim.toFixed(1)} m`;

  const modal = document.getElementById('fieldModal');
  if (modal) modal.style.display = 'flex';
}

function closeFieldModal() {
  const modal = document.getElementById('fieldModal');
  if (modal) modal.style.display = 'none';
  if (fieldDrawPolyline) {
    leafletMap.removeLayer(fieldDrawPolyline);
    fieldDrawPolyline = null;
  }
}

async function saveFieldConfirm() {
  const name = document.getElementById('fieldName').value.trim() || 'Field';
  const pts = fieldDrawPoints.map(p => [p.lat, p.lng]);
  try {
    const res = await fetch('/api/fields', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, points: pts })
    });
    const data = await res.json();
    if (data.success) {
      appendLog(`Saved field boundary: ${name}`, 'success');
      loadFields();
    }
  } catch (e) {
    appendLog(`Error saving field: ${e.message}`, 'error');
  }
  closeFieldModal();
}

async function loadFields() {
  try {
    const res = await fetch('/api/fields');
    if (!res.ok) return;
    const fields = await res.json();
    if (!fieldsLayerGroup) return;
    fieldsLayerGroup.clearLayers();

    const select = document.getElementById('geofenceFieldSelect');
    if (select) {
      select.innerHTML = '<option value="">Circular Radius Around Home</option>';
    }

    fields.forEach(f => {
      const polygon = L.polygon(f.points, {
        color: '#00e676',
        weight: 2,
        fillColor: '#00e676',
        fillOpacity: 0.15
      }).addTo(fieldsLayerGroup);

      polygon.bindPopup(`
        <div style="color:#090d14; font-family:sans-serif;">
          <b>${escapeHtml(f.name)}</b><br>
          <span>Area: <b>${f.areaHectares.toFixed(2)} ha</b> (${f.areaAcres.toFixed(2)} acres)</span><br>
          <span>Perimeter: ${f.perimeterMeters.toFixed(1)} m</span><br>
          <button style="margin-top:6px; background:#e53935; color:#fff; border:none; padding:4px 8px; border-radius:4px; cursor:pointer;" onclick="deleteField('${f.id}')">Delete Field</button>
        </div>
      `);

      if (select) {
        const opt = document.createElement('option');
        opt.value = f.id;
        opt.textContent = `${f.name} (${f.areaHectares.toFixed(1)} ha)`;
        select.appendChild(opt);
      }
    });
  } catch (_) {}
}

async function deleteField(id) {
  try {
    await fetch(`/api/fields/delete?id=${encodeURIComponent(id)}`, { method: 'POST' });
    loadFields();
    appendLog('Deleted field boundary polygon', 'info');
  } catch (_) {}
}

function toggleMeasureTool() {
  isMeasuring = !isMeasuring;
  const btn = document.getElementById('btnMeasure');
  if (btn) btn.classList.toggle('active', isMeasuring);

  if (!isMeasuring) {
    measurePoints = [];
    if (measureLayerGroup) measureLayerGroup.clearLayers();
    appendLog('Measure tool deactivated', 'info');
  } else {
    measurePoints = [];
    if (measureLayerGroup) measureLayerGroup.clearLayers();
    appendLog('📏 Distance Measure active: Click points on map to measure path distance', 'info');
  }
}

function setAdminPositionPrompt() {
  const coord = prompt('Enter your Ground Station Admin latitude,longitude (or click OK to use current map center):');
  let lat, lon;
  if (coord && coord.includes(',')) {
    const parts = coord.split(',');
    lat = parseFloat(parts[0].trim());
    lon = parseFloat(parts[1].trim());
  } else if (leafletMap) {
    const c = leafletMap.getCenter();
    lat = c.lat;
    lon = c.lng;
  }
  if (!lat || !lon) return;

  if (adminMarker) {
    adminMarker.setLatLng([lat, lon]);
  } else {
    const adminIcon = L.divIcon({
      className: 'admin-marker-div',
      html: `<div class="admin-marker-badge">👤 ADMIN GCS</div>`,
      iconSize: [80, 24],
      iconAnchor: [40, 12]
    });
    adminMarker = L.marker([lat, lon], { icon: adminIcon }).addTo(leafletMap);
  }
  appendLog(`Placed Admin GCS marker at: ${lat.toFixed(6)}, ${lon.toFixed(6)}`, 'success');
}

// ==========================================================================
// Geofence Safety Boundary
// ==========================================================================

let geofenceSettings = { active: false, radiusMeters: 300, fieldId: '' };

function openGeofenceModal() {
  const modal = document.getElementById('geofenceModal');
  if (modal) modal.style.display = 'flex';
  loadGeofence();
}

function closeGeofenceModal() {
  const modal = document.getElementById('geofenceModal');
  if (modal) modal.style.display = 'none';
}

async function loadGeofence() {
  try {
    const res = await fetch('/api/geofence');
    if (!res.ok) return;
    const data = await res.json();
    geofenceSettings = data;

    const btnOn = document.getElementById('btnGeofenceOn');
    const btnOff = document.getElementById('btnGeofenceOff');
    if (btnOn) btnOn.classList.toggle('active', data.active);
    if (btnOff) btnOff.classList.toggle('active', !data.active);

    const slider = document.getElementById('geofenceRadiusSlider');
    const lbl = document.getElementById('lblGeofenceRadius');
    if (slider) slider.value = data.radiusMeters;
    if (lbl) lbl.textContent = Math.round(data.radiusMeters);

    const select = document.getElementById('geofenceFieldSelect');
    if (select && data.fieldId) select.value = data.fieldId;

    renderGeofenceOverlay();
  } catch (_) {}
}

function toggleGeofenceEnabled(active) {
  geofenceSettings.active = active;
  const btnOn = document.getElementById('btnGeofenceOn');
  const btnOff = document.getElementById('btnGeofenceOff');
  if (btnOn) btnOn.classList.toggle('active', active);
  if (btnOff) btnOff.classList.toggle('active', !active);

  saveGeofenceSettings();
}

function updateGeofenceRadiusUI(val) {
  geofenceSettings.radiusMeters = parseFloat(val);
  const lbl = document.getElementById('lblGeofenceRadius');
  if (lbl) lbl.textContent = Math.round(val);
  renderGeofenceOverlay();
  saveGeofenceSettings();
}

function updateGeofenceField(fieldId) {
  geofenceSettings.fieldId = fieldId;
  saveGeofenceSettings();
}

async function saveGeofenceSettings() {
  try {
    await fetch('/api/geofence', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(geofenceSettings)
    });
    renderGeofenceOverlay();
  } catch (_) {}
}

function renderGeofenceOverlay() {
  if (!geofenceLayerGroup) return;
  geofenceLayerGroup.clearLayers();

  if (!geofenceSettings.active) return;

  if (lastTelemetry && lastTelemetry.homeLat && lastTelemetry.homeLon) {
    L.circle([lastTelemetry.homeLat, lastTelemetry.homeLon], {
      radius: geofenceSettings.radiusMeters,
      color: '#ff1744',
      weight: 2,
      dashArray: '6, 6',
      fillColor: '#ff1744',
      fillOpacity: 0.08
    }).addTo(geofenceLayerGroup);
  }
}

function triggerGeofenceAlert(reason) {
  const banner = document.getElementById('geofenceAlertBanner');
  const text = document.getElementById('geofenceAlertText');
  if (banner) banner.style.display = 'flex';
  if (text) text.textContent = `🚨 GEOFENCE BREACH: ${reason || 'Drone outside safety boundary!'}`;
  appendLog(`🚨 GEOFENCE BREACH DETECTED: ${reason || 'Outside boundary'}`, 'error');
  playSound('sound_effect_1.mp3');
}

function dismissGeofenceAlert() {
  const banner = document.getElementById('geofenceAlertBanner');
  if (banner) banner.style.display = 'none';
  stopSound();
}

// ==========================================================================
// Offline Map Manager (MBTiles & Area Downloader)
// ==========================================================================

let mapDownloadPollTimer = null;

function openMapsModal() {
  const modal = document.getElementById('mapsModal');
  if (modal) modal.style.display = 'flex';
  loadMapLayersList();
}

function closeMapsModal() {
  const modal = document.getElementById('mapsModal');
  if (modal) modal.style.display = 'none';
  if (mapDownloadPollTimer) clearInterval(mapDownloadPollTimer);
}

function switchMapModalTab(tab) {
  const secLayers = document.getElementById('secMapLayers');
  const secDownload = document.getElementById('secMapDownload');
  const tabLayers = document.getElementById('tabMapLayers');
  const tabDownload = document.getElementById('tabMapDownload');

  if (tab === 'layers') {
    if (secLayers) secLayers.style.display = 'block';
    if (secDownload) secDownload.style.display = 'none';
    if (tabLayers) tabLayers.classList.add('active');
    if (tabDownload) tabDownload.classList.remove('active');
    loadMapLayersList();
  } else {
    if (secLayers) secLayers.style.display = 'none';
    if (secDownload) secDownload.style.display = 'block';
    if (tabLayers) tabLayers.classList.remove('active');
    if (tabDownload) tabDownload.classList.add('active');
  }
}

async function loadMapLayersList() {
  const container = document.getElementById('mapLayersList');
  if (!container) return;

  try {
    const res = await fetch('/api/maps');
    const layers = await res.json();
    container.innerHTML = '';

    if (!layers || layers.length === 0) {
      container.innerHTML = '<span style="color:#8b9bb4; font-size:0.8rem; padding:8px; display:block;">No offline MBTiles layers found on phone storage. Use the "Download Map Area" tab or import .mbtiles into Documents/DroneCam/Maps.</span>';
      return;
    }

    layers.forEach(layer => {
      const card = document.createElement('div');
      card.className = 'recording-card';
      const sizeMb = (layer.sizeBytes / (1024 * 1024)).toFixed(1);
      const isSelected = activeMapLayerName === layer.id;

      card.innerHTML = `
        <div class="recording-card-title">🗺️ ${escapeHtml(layer.name)} ${isSelected ? '<span class="chip-badge">ACTIVE</span>' : ''}</div>
        <div class="recording-card-meta">
          <span>Zooms: ${layer.minZoom}-${layer.maxZoom}</span>
          <span>💾 ${sizeMb} MB</span>
        </div>
        <div class="recording-btn-row">
          <button class="btn-card btn-card-play" onclick="selectMapLayer('${escapeJs(layer.id)}')">
            ${isSelected ? 'Active Layer' : 'Set as Active Map'}
          </button>
          <button class="btn-card btn-card-delete" onclick="deleteMapLayer('${escapeJs(layer.id)}')">
            🗑
          </button>
        </div>
      `;
      container.appendChild(card);
    });
  } catch (_) {
    container.innerHTML = '<span style="color:#e53935; font-size:0.8rem;">Failed to fetch map layers</span>';
  }
}

function selectMapLayer(id) {
  setupTileLayer(id);
  loadMapLayersList();
  appendLog(`Active offline map layer set to: ${id}`, 'success');
}

async function deleteMapLayer(id) {
  if (!confirm(`Delete map layer "${id}" from phone storage?`)) return;
  try {
    await fetch(`/api/maps/delete?id=${encodeURIComponent(id)}`, { method: 'POST' });
    loadMapLayersList();
    appendLog(`Deleted map layer: ${id}`, 'info');
  } catch (_) {}
}

let downloadBounds = null;

function useCurrentMapBoundsForDownload() {
  if (!leafletMap) return;
  const b = leafletMap.getBounds();
  downloadBounds = {
    minLat: b.getSouth(),
    minLon: b.getWest(),
    maxLat: b.getNorth(),
    maxLon: b.getEast()
  };
  const summary = document.getElementById('dlBoundsSummary');
  if (summary) {
    summary.textContent = `Selected Area: [${downloadBounds.minLat.toFixed(4)}, ${downloadBounds.minLon.toFixed(4)}] to [${downloadBounds.maxLat.toFixed(4)}, ${downloadBounds.maxLon.toFixed(4)}]`;
  }
  appendLog('Map bounding box captured for offline download', 'info');
}

async function estimateMapDownload() {
  if (!downloadBounds) useCurrentMapBoundsForDownload();
  const minZ = parseInt(document.getElementById('dlMinZoom').value, 10) || 11;
  const maxZ = parseInt(document.getElementById('dlMaxZoom').value, 10) || 16;
  const resultDiv = document.getElementById('dlEstimateResult');

  try {
    const res = await fetch(`/api/maps/estimate?minLat=${downloadBounds.minLat}&minLon=${downloadBounds.minLon}&maxLat=${downloadBounds.maxLat}&maxLon=${downloadBounds.maxLon}&minZoom=${minZ}&maxZoom=${maxZ}`);
    const data = await res.json();
    if (resultDiv) {
      resultDiv.style.display = 'block';
      resultDiv.textContent = `Estimated Tiles: ${data.totalTiles.toLocaleString()} (~${data.estMb} MB storage)`;
    }
  } catch (e) {
    appendLog(`Estimate error: ${e.message}`, 'error');
  }
}

async function startMapAreaDownload() {
  if (!downloadBounds) useCurrentMapBoundsForDownload();
  const name = document.getElementById('dlMapName').value.trim() || 'flight_area';
  const urlTemplate = document.getElementById('dlUrlTemplate').value.trim();
  const minZ = parseInt(document.getElementById('dlMinZoom').value, 10) || 11;
  const maxZ = parseInt(document.getElementById('dlMaxZoom').value, 10) || 16;

  if (!urlTemplate) {
    alert('Please provide a valid tile server URL template.');
    return;
  }

  try {
    const res = await fetch('/api/maps/download', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        name,
        urlTemplate,
        minLat: downloadBounds.minLat,
        minLon: downloadBounds.minLon,
        maxLat: downloadBounds.maxLat,
        maxLon: downloadBounds.maxLon,
        minZoom: minZ,
        maxZoom: maxZ
      })
    });
    const data = await res.json();
    if (data.success) {
      appendLog(`Started offline map download: ${name}`, 'success');
      showDownloadControls(true);
      startPollingDownloadProgress();
    } else {
      appendLog('Could not start download', 'error');
    }
  } catch (e) {
    appendLog(`Download start error: ${e.message}`, 'error');
  }
}

function showDownloadControls(isDownloading) {
  const pCont = document.getElementById('dlProgressContainer');
  const btnStart = document.getElementById('btnStartDl');
  const btnPause = document.getElementById('btnPauseDl');
  const btnCancel = document.getElementById('btnCancelDl');

  if (pCont) pCont.style.display = isDownloading ? 'block' : 'none';
  if (btnStart) btnStart.style.display = isDownloading ? 'none' : 'inline-block';
  if (btnPause) btnPause.style.display = isDownloading ? 'inline-block' : 'none';
  if (btnCancel) btnCancel.style.display = isDownloading ? 'inline-block' : 'none';
}

function startPollingDownloadProgress() {
  if (mapDownloadPollTimer) clearInterval(mapDownloadPollTimer);
  mapDownloadPollTimer = setInterval(async () => {
    try {
      const res = await fetch('/api/maps/download/progress');
      const data = await res.json();
      const pBar = document.getElementById('dlProgressBar');
      const pText = document.getElementById('dlProgressText');

      if (pBar) pBar.style.width = `${data.percent}%`;
      if (pText) pText.textContent = `${data.downloaded} / ${data.total} tiles (${data.percent}%) - Status: ${data.status}`;

      if (data.status === 'completed' || data.status === 'idle') {
        clearInterval(mapDownloadPollTimer);
        showDownloadControls(false);
        appendLog('★ Map area download complete and saved to MBTiles!', 'success');
        loadMapLayersList();
      }
    } catch (_) {}
  }, 1000);
}

async function pauseMapDownload() {
  await fetch('/api/maps/download/pause', { method: 'POST' });
  appendLog('Map download paused', 'info');
}

async function cancelMapDownload() {
  await fetch('/api/maps/download/cancel', { method: 'POST' });
  if (mapDownloadPollTimer) clearInterval(mapDownloadPollTimer);
  showDownloadControls(false);
  appendLog('Map download cancelled', 'info');
}

// ==========================================================================
// Flight Tracks & Black-Box History
// ==========================================================================

function openTracksModal() {
  const modal = document.getElementById('tracksModal');
  if (modal) modal.style.display = 'flex';
  loadTracksList();
}

function closeTracksModal() {
  const modal = document.getElementById('tracksModal');
  if (modal) modal.style.display = 'none';
}

async function loadTracksList() {
  const listEl = document.getElementById('tracksList');
  if (!listEl) return;

  try {
    const res = await fetch('/api/tracks');
    const tracks = await res.json();
    listEl.innerHTML = '';

    if (!tracks || tracks.length === 0) {
      listEl.innerHTML = '<span style="color:#8b9bb4; font-size:0.8rem; padding:8px; display:block;">No flight track sessions recorded yet.</span>';
      return;
    }

    tracks.forEach(track => {
      const card = document.createElement('div');
      card.className = 'recording-card';
      const durSec = Math.round(track.durationMs / 1000);
      const mins = Math.floor(durSec / 60);
      const secs = durSec % 60;

      card.innerHTML = `
        <div class="recording-card-title">📈 ${escapeHtml(track.sessionName)}</div>
        <div class="recording-card-meta">
          <span>Points: <b>${track.pointCount}</b></span>
          <span>Duration: <b>${mins}m ${secs}s</b></span>
        </div>
        <div class="recording-btn-row">
          <a class="btn-card btn-card-download" href="/api/tracks/export?sessionId=${encodeURIComponent(track.sessionId)}&format=gpx" download="${track.sessionName}.gpx" title="Export GPX (Google Earth / QGIS)">
            GPX
          </a>
          <a class="btn-card btn-card-download" href="/api/tracks/export?sessionId=${encodeURIComponent(track.sessionId)}&format=kml" download="${track.sessionName}.kml" title="Export KML">
            KML
          </a>
          <a class="btn-card btn-card-download" href="/api/tracks/export?sessionId=${encodeURIComponent(track.sessionId)}&format=csv" download="${track.sessionName}.csv" title="Export CSV Spreadsheet">
            CSV
          </a>
          <button class="btn-card btn-card-play" onclick="loadTrackOnMap('${escapeJs(track.sessionId)}')" title="Display on Live Map">
            ▶ View
          </button>
          <button class="btn-card btn-card-delete" onclick="deleteTrackSession('${escapeJs(track.sessionId)}')">
            🗑
          </button>
        </div>
      `;
      listEl.appendChild(card);
    });
  } catch (_) {
    listEl.innerHTML = '<span style="color:#e53935; font-size:0.8rem;">Failed to fetch flight tracks</span>';
  }
}

async function loadTrackOnMap(sessionId) {
  try {
    const res = await fetch(`/api/tracks/points?sessionId=${encodeURIComponent(sessionId)}`);
    const points = await res.json();
    if (!points || !points.length) {
      appendLog('No points in selected track', 'info');
      return;
    }

    flightTrackPoints = [];
    if (flightTrackLine) flightTrackLine.setLatLngs([]);

    points.forEach(p => {
      addTrackPoint(p.lat, p.lon, p.speedKmh, p.altitudeBaro, p.timestamp);
    });

    fitTrackToBounds();
    closeTracksModal();
    appendLog(`Loaded previous track session on map (${points.length} points)`, 'success');
  } catch (e) {
    appendLog(`Could not load track: ${e.message}`, 'error');
  }
}

async function deleteTrackSession(sessionId) {
  if (!confirm('Are you sure you want to delete this flight track session?')) return;
  try {
    await fetch(`/api/tracks/delete?sessionId=${encodeURIComponent(sessionId)}`, { method: 'POST' });
    loadTracksList();
    appendLog('Deleted flight track session', 'info');
  } catch (_) {}
}

// ==========================================================================
// Geotagged Photo Snapshots Gallery & Map Pins
// ==========================================================================

function openPhotosModal() {
  const modal = document.getElementById('photosModal');
  if (modal) modal.style.display = 'flex';
  loadPhotosGallery();
}

function closePhotosModal() {
  const modal = document.getElementById('photosModal');
  if (modal) modal.style.display = 'none';
}

async function loadPhotosGallery() {
  const grid = document.getElementById('photosGrid');
  if (!grid) return;

  try {
    const res = await fetch('/api/photos');
    const photos = await res.json();
    grid.innerHTML = '';

    if (!photos || photos.length === 0) {
      grid.innerHTML = '<span style="color:#8b9bb4; font-size:0.8rem; padding:8px; display:block;">No geotagged photos captured yet. Use the SNAP button on top to capture high-res snapshots.</span>';
      return;
    }

    photos.forEach(photo => {
      const card = document.createElement('div');
      card.className = 'photo-card';
      card.innerHTML = `
        <img src="/photos/${encodeURIComponent(photo.fileName)}" alt="${escapeHtml(photo.fileName)}" style="width:100%; height:120px; object-fit:cover; border-radius:4px; display:block; background:#000;">
        <div style="font-size:0.75rem; font-weight:bold; margin-top:6px; color:#fff; word-break:break-all;">${escapeHtml(photo.fileName)}</div>
        <div style="font-size:0.7rem; color:#8b9bb4;">Lat: ${photo.lat.toFixed(5)}° Lon: ${photo.lon.toFixed(5)}°</div>
        <div style="font-size:0.7rem; color:#00e5ff;">Alt: ${photo.altitude.toFixed(1)}m</div>
        <div class="recording-btn-row" style="margin-top:6px;">
          <a class="btn-card btn-card-download" href="/photos/${encodeURIComponent(photo.fileName)}?download=1" download="${escapeHtml(photo.fileName)}">⬇ Save</a>
          <button class="btn-card btn-card-delete" onclick="deletePhoto('${escapeJs(photo.fileName)}')">🗑</button>
        </div>
      `;
      grid.appendChild(card);
    });
  } catch (_) {
    grid.innerHTML = '<span style="color:#e53935; font-size:0.8rem;">Failed to fetch photos</span>';
  }
}

async function loadPhotosPins() {
  try {
    const res = await fetch('/api/photos');
    if (!res.ok) return;
    const photos = await res.json();
    if (!photosLayerGroup) return;
    photosLayerGroup.clearLayers();

    photos.forEach(photo => {
      if (photo.lat && photo.lon) {
        const pinIcon = L.divIcon({
          className: 'photo-marker-div',
          html: `<div class="photo-marker-badge" title="${escapeHtml(photo.fileName)}">📸</div>`,
          iconSize: [26, 26],
          iconAnchor: [13, 13]
        });
        const marker = L.marker([photo.lat, photo.lon], { icon: pinIcon }).addTo(photosLayerGroup);
        marker.bindPopup(`
          <div style="color:#090d14; font-family:sans-serif; max-width:220px;">
            <img src="/photos/${encodeURIComponent(photo.fileName)}" style="width:100%; border-radius:4px; margin-bottom:4px;">
            <b style="font-size:0.8rem;">${escapeHtml(photo.fileName)}</b><br>
            <span style="font-size:0.75rem; color:#555;">GPS: ${photo.lat.toFixed(5)}°, ${photo.lon.toFixed(5)}°</span><br>
            <span style="font-size:0.75rem; color:#0288d1;">Alt: ${photo.altitude.toFixed(1)}m</span><br>
            <a href="/photos/${encodeURIComponent(photo.fileName)}?download=1" download style="display:inline-block; margin-top:6px; background:#00e676; color:#000; padding:3px 8px; border-radius:3px; text-decoration:none; font-weight:bold; font-size:0.75rem;">Download JPEG</a>
          </div>
        `);
      }
    });
  } catch (_) {}
}

async function deletePhoto(fileName) {
  if (!confirm(`Delete photo "${fileName}"?`)) return;
  try {
    await fetch(`/api/photos/delete?fileName=${encodeURIComponent(fileName)}`, { method: 'POST' });
    loadPhotosGallery();
    loadPhotosPins();
    appendLog(`Deleted photo: ${fileName}`, 'info');
  } catch (_) {}
}

// ==========================================================================
// Dynamic Quality Preset & Sensor Calibration
// ==========================================================================

let currentQualityPreset = 'AUTO';
const qualityPresetsList = ['AUTO', 'FAST', 'BALANCED', 'HIGH'];

function cycleQualityPreset() {
  const nextIdx = (qualityPresetsList.indexOf(currentQualityPreset) + 1) % qualityPresetsList.length;
  setQualityPreset(qualityPresetsList[nextIdx]);
}

function setQualityPreset(preset) {
  currentQualityPreset = preset;
  updateQualityPresetUI(preset);
  sendCommand('set_camera_quality', { preset });
  appendLog(`Quality preset set to: ${preset}`, 'info');
}

function updateQualityPresetUI(preset) {
  currentQualityPreset = preset;
  const lbl = document.getElementById('lblCamQuality');
  if (lbl) lbl.textContent = preset === 'AUTO' ? 'AUTO (WIFI)' : preset;

  const btns = {
    'AUTO': document.getElementById('btnQAuto'),
    'FAST': document.getElementById('btnQFast'),
    'BALANCED': document.getElementById('btnQBal'),
    'HIGH': document.getElementById('btnQHigh')
  };
  Object.keys(btns).forEach(k => {
    if (btns[k]) btns[k].classList.toggle('active', k === preset);
  });
}

function calibrateBarometer() {
  sendCommand('calibrate_baro');
  appendLog('Calibrating takeoff barometer baseline to 0.0m AGL...', 'info');
}

function setGpsUpdateRate(intervalMs) {
  sendCommand('set_gps_rate', { intervalMs });
  ['btnGpsRate2', 'btnGpsRate1', 'btnGpsRate05'].forEach(id => {
    const b = document.getElementById(id);
    if (b) b.classList.remove('active');
  });
  if (intervalMs === 500) {
    const b = document.getElementById('btnGpsRate2');
    if (b) b.classList.add('active');
  } else if (intervalMs === 1000) {
    const b = document.getElementById('btnGpsRate1');
    if (b) b.classList.add('active');
  } else {
    const b = document.getElementById('btnGpsRate05');
    if (b) b.classList.add('active');
  }
  appendLog(`GPS update rate set to: ${intervalMs} ms`, 'info');
}

// ==========================================================================
// Spherical Geometry Calculations
// ==========================================================================

function calculateDistance(lat1, lon1, lat2, lon2) {
  const R = 6371000; // Earth radius in meters
  const dLat = (lat2 - lat1) * Math.PI / 180;
  const dLon = (lon2 - lon1) * Math.PI / 180;
  const a = Math.sin(dLat / 2) * Math.sin(dLat / 2) +
            Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) *
            Math.sin(dLon / 2) * Math.sin(dLon / 2);
  const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
  return R * c;
}

function calculateBearing(lat1, lon1, lat2, lon2) {
  const y = Math.sin((lon2 - lon1) * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180);
  const x = Math.cos(lat1 * Math.PI / 180) * Math.sin(lat2 * Math.PI / 180) -
            Math.sin(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) * Math.cos((lon2 - lon1) * Math.PI / 180);
  const brng = (Math.atan2(y, x) * 180 / Math.PI + 360) % 360;
  return brng;
}

function calculatePolygonArea(latlngs) {
  const R = 6378137;
  if (latlngs.length < 3) return 0;
  let total = 0;
  for (let i = 0; i < latlngs.length; i++) {
    const p1 = latlngs[i];
    const p2 = latlngs[(i + 1) % latlngs.length];
    const lat1 = p1.lat * Math.PI / 180;
    const lat2 = p2.lat * Math.PI / 180;
    const lon1 = p1.lng * Math.PI / 180;
    const lon2 = p2.lng * Math.PI / 180;
    total += (lon2 - lon1) * (2 + Math.sin(lat1) + Math.sin(lat2));
  }
  total = Math.abs(total * R * R / 2.0);
  return total;
}

function calculatePolygonPerimeter(latlngs) {
  let perim = 0;
  for (let i = 0; i < latlngs.length; i++) {
    const p1 = latlngs[i];
    const p2 = latlngs[(i + 1) % latlngs.length];
    perim += calculateDistance(p1.lat, p1.lng, p2.lat, p2.lng);
  }
  return perim;
}
