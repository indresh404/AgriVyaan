package com.agrivyaan.optix.diagnostics

import android.content.Context
import android.hardware.camera2.CameraCharacteristics
import android.hardware.camera2.CameraManager
import android.hardware.usb.UsbManager
import android.os.Build
import com.agrivyaan.optix.power.BatteryInfo

object DiagnosticHelper {

    fun generateReport(context: Context, batteryInfo: BatteryInfo, currentIp: String): String {
        val sb = StringBuilder()
        sb.appendLine("=== OPTIX SYSTEM DIAGNOSTICS REPORT ===")
        sb.appendLine("App: Optix (AgriVyaan)")
        sb.appendLine("Device: ${Build.MANUFACTURER} ${Build.MODEL} (${Build.PRODUCT})")
        sb.appendLine("Brand/Board: ${Build.BRAND} / ${Build.BOARD} / ${Build.HARDWARE}")
        sb.appendLine("Android OS: ${Build.VERSION.RELEASE} (API ${Build.VERSION.SDK_INT})")
        sb.appendLine("Security Patch: ${Build.VERSION.SECURITY_PATCH}")
        sb.appendLine("IP Address: $currentIp")
        sb.appendLine("Battery Level: ${batteryInfo.level}% (Charging: ${batteryInfo.isCharging})")
        sb.appendLine("Battery Temperature: ${batteryInfo.temperatureCelsius}°C (Overheating: ${batteryInfo.isOverheating})")
        sb.appendLine()

        // Camera2 Diagnostic
        sb.appendLine("--- Camera2 Capabilities ---")
        try {
            val cameraManager = context.getSystemService(Context.CAMERA_SERVICE) as CameraManager
            val cameraIds = cameraManager.cameraIdList
            sb.appendLine("Available Camera IDs: ${cameraIds.joinToString(", ")}")

            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {
                try {
                    val concurrentSets = cameraManager.concurrentCameraIds
                    sb.appendLine("Concurrent Camera Sets: ${concurrentSets.size}")
                    for (set in concurrentSets) {
                        sb.appendLine("  -> Concurrent: [${set.joinToString(", ")}]")
                    }
                } catch (e: Exception) {
                    sb.appendLine("Concurrent Cameras Check: Failed (${e.message})")
                }
            }

            for (id in cameraIds) {
                val chars = cameraManager.getCameraCharacteristics(id)
                val facing = when (chars.get(CameraCharacteristics.LENS_FACING)) {
                    CameraCharacteristics.LENS_FACING_BACK -> "BACK"
                    CameraCharacteristics.LENS_FACING_FRONT -> "FRONT"
                    else -> "EXTERNAL"
                }
                val hwLevel = when (chars.get(CameraCharacteristics.INFO_SUPPORTED_HARDWARE_LEVEL)) {
                    CameraCharacteristics.INFO_SUPPORTED_HARDWARE_LEVEL_LEGACY -> "LEGACY"
                    CameraCharacteristics.INFO_SUPPORTED_HARDWARE_LEVEL_LIMITED -> "LIMITED"
                    CameraCharacteristics.INFO_SUPPORTED_HARDWARE_LEVEL_FULL -> "FULL"
                    CameraCharacteristics.INFO_SUPPORTED_HARDWARE_LEVEL_3 -> "LEVEL_3"
                    else -> "UNKNOWN"
                }
                sb.appendLine("Camera [$id] ($facing): HW Level = $hwLevel")
            }
        } catch (e: Exception) {
            sb.appendLine("Camera2 inspection error: ${e.message}")
        }
        sb.appendLine()

        // USB Devices
        sb.appendLine("--- USB Host Devices ---")
        try {
            val usbManager = context.getSystemService(Context.USB_SERVICE) as UsbManager
            val deviceList = usbManager.deviceList
            if (deviceList.isEmpty()) {
                sb.appendLine("No USB devices currently connected.")
            } else {
                for ((name, dev) in deviceList) {
                    val isUvc = dev.deviceClass == 14 || dev.deviceClass == 239
                    sb.appendLine("Device: $name | VID: 0x${dev.vendorId.toString(16)} | PID: 0x${dev.productId.toString(16)} | Class: ${dev.deviceClass} (UVC: $isUvc)")
                }
            }
        } catch (e: Exception) {
            sb.appendLine("USB inspection error: ${e.message}")
        }

        return sb.toString()
    }
}
