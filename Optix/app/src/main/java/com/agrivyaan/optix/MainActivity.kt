package com.agrivyaan.optix

import android.Manifest
import android.app.PendingIntent
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.content.pm.PackageManager
import android.hardware.usb.UsbDevice
import android.hardware.usb.UsbManager
import android.os.Build
import android.os.Bundle
import android.util.Log
import android.widget.Toast
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.core.content.ContextCompat
import com.agrivyaan.optix.service.StreamingService
import com.agrivyaan.optix.ui.MainScreen
import com.agrivyaan.optix.ui.OnboardingScreen
import com.agrivyaan.optix.ui.theme.OptixTheme

class MainActivity : ComponentActivity() {

    companion object {
        const val ACTION_USB_PERMISSION = "com.agrivyaan.optix.USB_PERMISSION"
    }

    private val requiredPermissions = buildList {
        add(Manifest.permission.CAMERA)
        add(Manifest.permission.RECORD_AUDIO)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            add(Manifest.permission.POST_NOTIFICATIONS)
        }
    }.toTypedArray()

    private val permissionLauncher = registerForActivityResult(
        ActivityResultContracts.RequestMultiplePermissions()
    ) { results ->
        val cameraGranted = results[Manifest.permission.CAMERA] ?: false
        if (cameraGranted) {
            Log.i("MainActivity", "Camera permission granted. Starting streaming service automatically.")
            startStreamingService()
        } else {
            Toast.makeText(this, "Camera permission is required for Optix streaming!", Toast.LENGTH_LONG).show()
        }
    }

    private val usbReceiver = object : BroadcastReceiver() {
        override fun onReceive(context: Context?, intent: Intent?) {
            when (intent?.action) {
                ACTION_USB_PERMISSION -> {
                    val device: UsbDevice? = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
                        intent.getParcelableExtra(UsbManager.EXTRA_DEVICE, UsbDevice::class.java)
                    } else {
                        @Suppress("DEPRECATION")
                        intent.getParcelableExtra(UsbManager.EXTRA_DEVICE)
                    }
                    val granted = intent.getBooleanExtra(UsbManager.EXTRA_PERMISSION_GRANTED, false)
                    if (granted && device != null) {
                        Log.i("MainActivity", "USB Camera Permission GRANTED for ${device.deviceName}")
                        Toast.makeText(this@MainActivity, "USB Camera Permission Granted! (${device.productName ?: device.deviceName})", Toast.LENGTH_SHORT).show()
                        notifyUsbPermissionGranted()
                    } else {
                        Log.w("MainActivity", "USB Camera Permission DENIED by user")
                        Toast.makeText(this@MainActivity, "USB Camera Permission Denied", Toast.LENGTH_SHORT).show()
                    }
                }
                UsbManager.ACTION_USB_DEVICE_ATTACHED -> {
                    Log.i("MainActivity", "USB device attached broadcast received")
                    checkAndRequestUsbPermission()
                }
                UsbManager.ACTION_USB_DEVICE_DETACHED -> {
                    Log.i("MainActivity", "USB device detached broadcast received")
                }
            }
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        val filter = IntentFilter().apply {
            addAction(ACTION_USB_PERMISSION)
            addAction(UsbManager.ACTION_USB_DEVICE_ATTACHED)
            addAction(UsbManager.ACTION_USB_DEVICE_DETACHED)
        }
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            registerReceiver(usbReceiver, filter, Context.RECEIVER_EXPORTED)
        } else {
            registerReceiver(usbReceiver, filter)
        }

        checkAndRequestPermissions()
        checkAndRequestUsbPermission()

        setContent {
            OptixTheme {
                Surface(color = MaterialTheme.colorScheme.background) {
                    val serviceState by StreamingService.uiState.collectAsState()
                    var currentScreen by remember { mutableStateOf("main") }

                    if (currentScreen == "onboarding") {
                        OnboardingScreen(
                            onBack = { currentScreen = "main" }
                        )
                    } else {
                        MainScreen(
                            state = serviceState,
                            onStartService = { startStreamingService() },
                            onStopService = { stopStreamingService() },
                            onOpenPreFlight = { currentScreen = "onboarding" },
                            onDetectUsb = { checkAndRequestUsbPermission() }
                        )
                    }
                }
            }
        }
    }

    override fun onResume() {
        super.onResume()
        checkAndRequestUsbPermission()
    }

    override fun onDestroy() {
        super.onDestroy()
        try {
            unregisterReceiver(usbReceiver)
        } catch (_: Exception) {}
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        handleUsbIntent(intent)
    }

    private fun handleUsbIntent(intent: Intent?) {
        if (intent?.action == UsbManager.ACTION_USB_DEVICE_ATTACHED) {
            checkAndRequestUsbPermission()
        }
    }

    fun checkAndRequestUsbPermission() {
        val usbManager = getSystemService(Context.USB_SERVICE) as? UsbManager ?: return
        val deviceList = usbManager.deviceList
        Log.i("MainActivity", "checkAndRequestUsbPermission: scanning ${deviceList.size} devices")

        if (deviceList.isEmpty()) {
            Toast.makeText(this, "No USB device detected. Please plug webcam into OTG adapter.", Toast.LENGTH_SHORT).show()
            return
        }

        for (device in deviceList.values) {
            Log.i("MainActivity", "Found USB Device: ${device.deviceName} (Name: ${device.productName})")
            if (!usbManager.hasPermission(device)) {
                Log.i("MainActivity", "Prompting USB permission dialog for ${device.deviceName} (${device.productName})")
                val flags = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
                    PendingIntent.FLAG_MUTABLE or PendingIntent.FLAG_UPDATE_CURRENT
                } else {
                    PendingIntent.FLAG_UPDATE_CURRENT
                }
                val permIntent = Intent(ACTION_USB_PERMISSION).apply {
                    setPackage(packageName)
                }
                val permissionIntent = PendingIntent.getBroadcast(
                    this, 0, permIntent, flags
                )
                usbManager.requestPermission(device, permissionIntent)
                Toast.makeText(this, "Please tap ALLOW in the USB Camera dialog", Toast.LENGTH_LONG).show()
                return
            } else {
                Log.i("MainActivity", "USB Device already has permission: ${device.deviceName}")
                Toast.makeText(this, "USB Camera Ready: ${device.productName ?: device.deviceName}", Toast.LENGTH_SHORT).show()
                notifyUsbPermissionGranted()
            }
        }
    }

    private fun isUvcDevice(device: UsbDevice): Boolean {
        if (device.deviceClass == 14 || device.deviceClass == 239) return true
        for (i in 0 until device.interfaceCount) {
            val intf = device.getInterface(i)
            if (intf.interfaceClass == 14 || intf.interfaceClass == 239) {
                return true
            }
        }
        return false
    }

    private fun notifyUsbPermissionGranted() {
        val intent = Intent(this, StreamingService::class.java).apply {
            action = StreamingService.ACTION_USB_PERMISSION_GRANTED
        }
        try {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                startForegroundService(intent)
            } else {
                startService(intent)
            }
        } catch (_: Exception) {}
    }

    private fun checkAndRequestPermissions() {
        val missing = requiredPermissions.filter {
            ContextCompat.checkSelfPermission(this, it) != PackageManager.PERMISSION_GRANTED
        }
        if (missing.isNotEmpty()) {
            permissionLauncher.launch(missing.toTypedArray())
        } else {
            if (!StreamingService.uiState.value.isRunning) {
                startStreamingService()
            }
        }
    }

    private fun startStreamingService() {
        val hasCamera = ContextCompat.checkSelfPermission(this, Manifest.permission.CAMERA) == PackageManager.PERMISSION_GRANTED
        if (!hasCamera) {
            permissionLauncher.launch(arrayOf(Manifest.permission.CAMERA))
            return
        }

        val intent = Intent(this, StreamingService::class.java).apply {
            action = StreamingService.ACTION_START_STREAMING
        }
        try {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                startForegroundService(intent)
            } else {
                startService(intent)
            }
            Log.i("MainActivity", "startForegroundService requested successfully")
        } catch (e: Exception) {
            Log.e("MainActivity", "Failed to startForegroundService", e)
            Toast.makeText(this, "Service start error: ${e.message}", Toast.LENGTH_LONG).show()
        }
    }

    private fun stopStreamingService() {
        val intent = Intent(this, StreamingService::class.java).apply {
            action = StreamingService.ACTION_STOP_STREAMING
        }
        startService(intent)
    }
}
