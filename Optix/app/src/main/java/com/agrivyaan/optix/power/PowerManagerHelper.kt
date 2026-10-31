package com.agrivyaan.optix.power

import android.annotation.SuppressLint
import android.app.admin.DevicePolicyManager
import android.content.BroadcastReceiver
import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.net.wifi.WifiManager
import android.os.BatteryManager
import android.os.Build
import android.os.PowerManager
import android.util.Log
import com.agrivyaan.optix.receiver.OptixAdminReceiver
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow

data class BatteryInfo(
    val level: Int = 100,
    val isCharging: Boolean = false,
    val temperatureCelsius: Float = 25.0f,
    val isOverheating: Boolean = false
)

class PowerManagerHelper(private val context: Context) {

    private val powerManager = context.getSystemService(Context.POWER_SERVICE) as PowerManager
    private val wifiManager = context.applicationContext.getSystemService(Context.WIFI_SERVICE) as WifiManager
    private val devicePolicyManager = context.getSystemService(Context.DEVICE_POLICY_SERVICE) as? DevicePolicyManager

    private var wakeLock: PowerManager.WakeLock? = null
    private var wifiLock: WifiManager.WifiLock? = null

    private val _batteryInfo = MutableStateFlow(BatteryInfo())
    val batteryInfo: StateFlow<BatteryInfo> = _batteryInfo.asStateFlow()

    private val batteryReceiver = object : BroadcastReceiver() {
        override fun onReceive(c: Context?, intent: Intent?) {
            if (intent == null) return
            val level = intent.getIntExtra(BatteryManager.EXTRA_LEVEL, -1)
            val scale = intent.getIntExtra(BatteryManager.EXTRA_SCALE, -1)
            val pct = if (level >= 0 && scale > 0) (level * 100) / scale else 50
            
            val status = intent.getIntExtra(BatteryManager.EXTRA_STATUS, -1)
            val charging = status == BatteryManager.BATTERY_STATUS_CHARGING ||
                    status == BatteryManager.BATTERY_STATUS_FULL
            
            val tempTenths = intent.getIntExtra(BatteryManager.EXTRA_TEMPERATURE, 250)
            val tempC = tempTenths / 10.0f
            val overheating = tempC >= 42.0f // Samsung Exynos 9611 throttle threshold

            _batteryInfo.value = BatteryInfo(
                level = pct,
                isCharging = charging,
                temperatureCelsius = tempC,
                isOverheating = overheating
            )
        }
    }

    @SuppressLint("WakelockTimeout")
    fun acquireLocks() {
        try {
            if (wakeLock == null) {
                wakeLock = powerManager.newWakeLock(
                    PowerManager.PARTIAL_WAKE_LOCK,
                    "Optix::StreamingPartialWakeLock"
                ).apply {
                    setReferenceCounted(false)
                    acquire()
                }
                Log.d(TAG, "Partial WakeLock acquired")
            }

            if (wifiLock == null) {
                val mode = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
                    WifiManager.WIFI_MODE_FULL_LOW_LATENCY
                } else {
                    @Suppress("DEPRECATION")
                    WifiManager.WIFI_MODE_FULL_HIGH_PERF
                }
                wifiLock = wifiManager.createWifiLock(mode, "Optix::StreamingWifiLock").apply {
                    setReferenceCounted(false)
                    acquire()
                }
                Log.d(TAG, "WifiLock acquired")
            }

            // Register battery monitor
            val filter = IntentFilter(Intent.ACTION_BATTERY_CHANGED)
            context.registerReceiver(batteryReceiver, filter)
        } catch (e: Exception) {
            Log.e(TAG, "Error acquiring power locks", e)
        }
    }

    fun releaseLocks() {
        try {
            wakeLock?.let {
                if (it.isHeld) it.release()
            }
            wakeLock = null

            wifiLock?.let {
                if (it.isHeld) it.release()
            }
            wifiLock = null

            try {
                context.unregisterReceiver(batteryReceiver)
            } catch (_: Exception) {}

            Log.d(TAG, "Power and Wifi locks released")
        } catch (e: Exception) {
            Log.e(TAG, "Error releasing locks", e)
        }
    }

    fun isScreenOn(): Boolean {
        return powerManager.isInteractive
    }

    @SuppressLint("WakelockTimeout")
    fun wakeScreen() {
        try {
            @Suppress("DEPRECATION")
            val screenLock = powerManager.newWakeLock(
                PowerManager.SCREEN_BRIGHT_WAKE_LOCK or
                PowerManager.ACQUIRE_CAUSES_WAKEUP or
                PowerManager.ON_AFTER_RELEASE,
                "Optix::RemoteScreenWake"
            )
            screenLock.acquire(3000)

            // Also launch WakeActivity
            val intent = Intent(context, WakeActivity::class.java).apply {
                addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_REORDER_TO_FRONT)
            }
            context.startActivity(intent)
            Log.d(TAG, "Screen wake triggered")
        } catch (e: Exception) {
            Log.e(TAG, "Failed to wake screen", e)
        }
    }

    fun isDeviceAdminActive(): Boolean {
        val adminComponent = ComponentName(context, OptixAdminReceiver::class.java)
        return devicePolicyManager?.isAdminActive(adminComponent) == true
    }

    fun getRequestDeviceAdminIntent(): Intent {
        val adminComponent = ComponentName(context, OptixAdminReceiver::class.java)
        return Intent(DevicePolicyManager.ACTION_ADD_DEVICE_ADMIN).apply {
            putExtra(DevicePolicyManager.EXTRA_DEVICE_ADMIN, adminComponent)
            putExtra(
                DevicePolicyManager.EXTRA_ADD_EXPLANATION,
                "Optix requires Device Admin permission to turn off and lock the phone screen remotely from the ground station to prevent overheating and save battery during flight."
            )
        }
    }

    fun lockScreenNow(): Boolean {
        return try {
            val adminComponent = ComponentName(context, OptixAdminReceiver::class.java)
            if (devicePolicyManager?.isAdminActive(adminComponent) == true) {
                devicePolicyManager.lockNow()
                true
            } else {
                Log.w(TAG, "Device Admin not active, cannot lock screen")
                false
            }
        } catch (e: Exception) {
            Log.e(TAG, "Failed to lock screen", e)
            false
        }
    }

    companion object {
        private const val TAG = "PowerManagerHelper"
    }
}
