@echo off
set ADB="%LOCALAPPDATA%\Android\Sdk\platform-tools\adb.exe"
if not exist %ADB% (
    set ADB=adb
)

echo [1/4] Installing Optix APK onto device...
%ADB% install -r -d "app\build\outputs\apk\debug\app-debug.apk"
if errorlevel 1 (
    echo [!] Sideload failed. Uninstalling old build first for clean install...
    %ADB% uninstall com.agrivyaan.optix
    %ADB% install "app\build\outputs\apk\debug\app-debug.apk"
)

echo [2/4] Granting Camera and Audio permissions...
%ADB% shell pm grant com.agrivyaan.optix android.permission.CAMERA
%ADB% shell pm grant com.agrivyaan.optix android.permission.RECORD_AUDIO

echo [3/4] Forwarding Ground Control port to port 8081
%ADB% forward tcp:8081 tcp:8080

echo [4/4] Starting Optix app on phone...
%ADB% shell am start -n com.agrivyaan.optix/.MainActivity

echo.
echo =======================================================
echo  OPTIX RUNNING SUCCESSFULLY!
echo  Open Ground Station in your browser:
echo  - Direct USB Link:   http://localhost:8081
echo  - Wi-Fi / Drone LAN: Check IP shown on phone screen
echo =======================================================
