# Optix FPV DroneCam Ground Control & Offline Live Map

Optix is an ultra-low-latency FPV video streaming, flight telemetry, and tactical offline mapping system for agriculture and drone inspection. The Android phone flies onboard the drone, streaming dual-camera feeds (Phone Camera + USB OTG Webcam) and real-time GPS telemetry to any ground station device (laptops, tablets, phones) over local Wi-Fi without internet or external servers.

---

## Key Features

1. **Dual-Camera Ultra-Low Latency Streaming (WebRTC)**:
   - Zero-latency hardware H.264 video pipeline.
   - Dual lens support: Phone rear camera + external USB OTG webcam.
   - Seamless simultaneous multi-admin viewing (multiple ground stations can view without disconnecting each other).
   - Dynamic adaptive Wi-Fi quality scaling (automatically adjusts bitrate and resolution when Wi-Fi RSSI drops to eliminate lag).

2. **Real-Time GPS Telemetry & Black-Box Recording**:
   - LocationManager GPS + GNSS Status (satellites visible/used, fix type).
   - Sensor fusion heading: Rotation vector compass at low speeds (<1 m/s), GPS bearing when moving.
   - Relative altitude (Barometer TYPE_PRESSURE) calibrated to takeoff baseline (AGL), and absolute GPS altitude (MSL).
   - Jitter-smoothing filter for display while preserving raw GPS points for the saved flight track.
   - 100% offline black-box flight track recording into local SQLite database on phone storage with a 10-minute in-memory ring buffer. Automatically fills missed track points when ground station reconnects!
   - Export flight tracks per session as **GPX 1.1**, **KML 2.2**, and **CSV** for Google Earth and GIS analysis.

3. **100% Offline Tactical Map (Bundled Leaflet + MBTiles SQLite)**:
   - Zero CDN dependencies: Leaflet JS/CSS and marker assets bundled directly in app assets.
   - Offline map tiles served directly from the phone via `/tiles/{layer}/{z}/{x}/{y}.png` from local MBTiles SQLite databases.
   - Plain tactical grid fallback: If no offline tiles are loaded, the drone track, markers, and HUD continue working seamlessly on a coordinate grid with scale bars.
   - Area Downloader Tool: Download bounding box areas into MBTiles with progress, pause, resume, and cancel.
   - Multiple layers: Street, Satellite, Terrain, and Tactical Grid.

4. **Tactical Flight Tools**:
   - **Interactive Waypoints**: Drop markers on the map (Pest Spot, Water Pump, Hazard), saved to phone SQLite.
   - **Field Boundary Polygons**: Draw polygons directly on the map; automatically calculates spherical surface area (hectares, acres, m²) and perimeter (meters).
   - **Geofence Safety Boundary**: Configure safety radius around Home or lock to a saved field polygon. Visual alert banner and loud audio siren if breached.
   - **Distance Measurement**: Measure point-to-point and path distance.
   - **Geotagged Snapshots**: JPEG snapshots embedded with EXIF GPS latitude, longitude, altitude, and timestamp, with interactive pins on the map.
   - **Video Subtitles**: Synchronized `.srt` GPS sidecar files generated for all local video recordings.

---

## Offline Map Tile Licensing Notice

> [!IMPORTANT]
> **Map Tile Usage Policy & Licensing**:
> Do **NOT** bulk-download tiles from `tile.openstreetmap.org`. Doing so violates the OpenStreetMap Tile Usage Policy and can lead to IP bans.
> 
> For offline mapping in production, please use:
> 1. Your own self-hosted tile server (e.g. TileServer GL, Mapnik).
> 2. Open map extracts such as **Protomaps** or **OpenMapTiles** (.mbtiles format), which can be copied directly to the phone's `Documents/DroneCam/Maps/` directory.
> 3. Permitted tile providers with your personal API key (e.g. Mapbox, Stadia Maps, Thunderforest).
>
> The tile URL template is customizable in the ground station offline map downloader settings (`/api/maps/download`).

---

## Acceptance Testing Guide

1. **Outdoors GPS Fix**:
   - Step outside with a clear sky view.
   - Open Optix on phone. The Pre-Flight GPS card will transition from "WAITING FOR FIX" to "GPS READY" once 3D fix is acquired with accuracy under 5m and 8+ satellites.
2. **Offline Local Streaming**:
   - Connect laptop/tablet to the phone's Wi-Fi hotspot (turn off mobile data and internet).
   - Open browser to `http://<phone-ip>:8080`.
   - The tactical cockpit loads with live video and offline map with zero external internet required.
3. **Flight Track & Distance**:
   - Walk 200m outdoors: The live drone marker with rotated heading arrow moves smoothly, leaving a colored polyline flight track. Distance and speed update at 1–2 Hz.
4. **Screen-Off Continuous Recording**:
   - Turn phone screen off during movement.
   - Optix continues background GPS logging via foreground service (`FOREGROUND_SERVICE_LOCATION`).
   - Ground station stays connected or catches up upon reconnect.
5. **Reconnection Black-Box Sync**:
   - Turn off Wi-Fi on laptop for 30 seconds, then reconnect.
   - WebRTC data channel re-establishes and ground station auto-syncs all missed points from the phone's black box ring buffer.
6. **Field Boundary & Area Calculation**:
   - On the ground station map, tap 📐 (Draw Field), click 3 or 4 points around a field, and click 📐 to finish.
   - Area in hectares and acres along with perimeter are calculated and displayed.
7. **Geofence Siren**:
   - Open 🛡️ (Geofence), set radius to 50m.
   - Move beyond 50m from home: The ground station flashes a red siren banner and triggers an audio alarm.
8. **GPX / KML Export**:
   - Open 📈 (Flight Tracks), click GPX or KML to download the session. Open in Google Earth or GPX viewer to view the exact walked path.
9. **Geotagged Photo**:
   - Click 📸 (SNAP) on top bar: The phone captures a photo with GPS EXIF tags and places a photo pin on the map.
