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
    await handleOffer(msg.sdp);
    return;
  }

  if (msg.type === 'candidate') {
    if (pc && pc.remoteDescription) {
      try {
        await pc.addIceCandidate(new RTCIceCandidate({
          candidate: msg.candidate,
          sdpMid: msg.sdpMid,
          sdpMLineIndex: msg.sdpMLineIndex
        }));
      } catch (e) {
        console.warn('ICE candidate error:', e);
      }
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
      videoEl.onloadeddata = () => {
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
    if (line.startsWith('m=video')) {
      inVideo = true;
      result.push(line);
      result.push('b=AS:2500');
      result.push('b=TIAS:2500000');
      result.push('a=x-google-min-bitrate=1500');
      result.push('a=x-google-max-bitrate=2500');
      result.push('a=x-google-start-bitrate=2000');
      continue;
    }
    if (line.startsWith('m=audio') || line.startsWith('m=application')) {
      inVideo = false;
    }
    if (inVideo && line.startsWith('c=IN')) {
      result.push(line);
      result.push('b=AS:2500');
      continue;
    }
    result.push(line);
  }
  return result.join('\r\n');
}

function closePeerConnection() {
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
function switchStreamMode(mode) {
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
  appendLog('High-res snapshot captured & saved!', 'success');
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
