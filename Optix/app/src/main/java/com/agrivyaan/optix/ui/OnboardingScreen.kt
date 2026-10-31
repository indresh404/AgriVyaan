package com.agrivyaan.optix.ui

import android.Manifest
import android.app.admin.DevicePolicyManager
import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Build
import android.os.PowerManager
import android.provider.Settings
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material.icons.filled.Warning
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.core.content.ContextCompat
import com.agrivyaan.optix.receiver.OptixAdminReceiver

data class CheckItem(
    val id: String,
    val title: String,
    val description: String,
    val isAutoDetected: Boolean,
    val isPassed: Boolean,
    val actionLabel: String,
    val onAction: (Context) -> Unit
)

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun OnboardingScreen(
    onBack: () -> Unit,
    onRequestDeviceAdmin: () -> Unit = {}
) {
    val context = LocalContext.current
    var refreshTrigger by remember { mutableStateOf(0) }

    val cameraPermissionLauncher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.RequestPermission()
    ) {
        refreshTrigger++
    }

    // Battery Optimization check
    val powerManager = remember { context.getSystemService(Context.POWER_SERVICE) as PowerManager }
    val isBatteryIgnored = remember(refreshTrigger) {
        powerManager.isIgnoringBatteryOptimizations(context.packageName)
    }

    // Device Admin check for Screen Lock
    val devicePolicyManager = remember { context.getSystemService(Context.DEVICE_POLICY_SERVICE) as? DevicePolicyManager }
    val adminComponent = remember { ComponentName(context, OptixAdminReceiver::class.java) }
    val isDeviceAdminActive = remember(refreshTrigger) {
        devicePolicyManager?.isAdminActive(adminComponent) == true
    }

    // Camera permission check
    val hasCameraPerm = remember(refreshTrigger) {
        ContextCompat.checkSelfPermission(context, Manifest.permission.CAMERA) == PackageManager.PERMISSION_GRANTED
    }

    // Overlay permission check (System alert window)
    val hasOverlayPerm = remember(refreshTrigger) {
        Settings.canDrawOverlays(context)
    }

    // Manual checks stored in SharedPreferences
    val prefs = remember { context.getSharedPreferences("optix_onboarding", Context.MODE_PRIVATE) }
    var sleepingAppsDone by remember { mutableStateOf(prefs.getBoolean("sleeping_apps", false)) }
    var adaptiveBatteryDone by remember { mutableStateOf(prefs.getBoolean("adaptive_battery", false)) }
    var autoResetDone by remember { mutableStateOf(prefs.getBoolean("auto_reset", false)) }
    var wifiSleepDone by remember { mutableStateOf(prefs.getBoolean("wifi_sleep", false)) }

    val items = listOf(
        CheckItem(
            id = "camera",
            title = "1. Camera Permission",
            description = "Required to capture phone rear camera stream.",
            isAutoDetected = true,
            isPassed = hasCameraPerm,
            actionLabel = if (hasCameraPerm) "Granted" else "Grant",
            onAction = { cameraPermissionLauncher.launch(Manifest.permission.CAMERA) }
        ),
        CheckItem(
            id = "overlay",
            title = "2. Display Over Other Apps",
            description = "Allows waking the screen remotely while the phone is locked.",
            isAutoDetected = true,
            isPassed = hasOverlayPerm,
            actionLabel = if (hasOverlayPerm) "Granted" else "Configure",
            onAction = {
                val intent = Intent(
                    Settings.ACTION_MANAGE_OVERLAY_PERMISSION,
                    Uri.parse("package:${context.packageName}")
                )
                context.startActivity(intent)
            }
        ),
        CheckItem(
            id = "battery_unrestricted",
            title = "3. Battery Optimization: Unrestricted",
            description = "Prevents Android from killing Optix when the screen is turned off.",
            isAutoDetected = true,
            isPassed = isBatteryIgnored,
            actionLabel = if (isBatteryIgnored) "Unrestricted" else "Set Unrestricted",
            onAction = {
                val intent = Intent(Settings.ACTION_REQUEST_IGNORE_BATTERY_OPTIMIZATIONS).apply {
                    data = Uri.parse("package:${context.packageName}")
                }
                try {
                    context.startActivity(intent)
                } catch (_: Exception) {
                    val appInfoIntent = Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS).apply {
                        data = Uri.parse("package:${context.packageName}")
                    }
                    context.startActivity(appInfoIntent)
                }
            }
        ),
        CheckItem(
            id = "device_admin",
            title = "4. Remote Screen Lock (Device Admin)",
            description = "Required to remotely lock and turn off the screen from the ground station to prevent overheating and save battery.",
            isAutoDetected = true,
            isPassed = isDeviceAdminActive,
            actionLabel = if (isDeviceAdminActive) "Active" else "Enable Admin",
            onAction = {
                onRequestDeviceAdmin()
                refreshTrigger++
            }
        ),
        CheckItem(
            id = "sleeping_apps",
            title = "5. Samsung: Background Usage Limits",
            description = "Turn OFF 'Put unused apps to sleep'. Ensure Optix is NOT in Sleeping or Deep Sleeping apps.",
            isAutoDetected = false,
            isPassed = sleepingAppsDone,
            actionLabel = if (sleepingAppsDone) "Done" else "Open Settings",
            onAction = {
                openSamsungBatterySettings(context)
                sleepingAppsDone = !sleepingAppsDone
                prefs.edit().putBoolean("sleeping_apps", sleepingAppsDone).apply()
            }
        ),
        CheckItem(
            id = "adaptive_battery",
            title = "6. Adaptive Battery & Power Saving OFF",
            description = "Turn OFF 'Adaptive battery' and 'Power saving mode' during drone flight.",
            isAutoDetected = false,
            isPassed = adaptiveBatteryDone,
            actionLabel = if (adaptiveBatteryDone) "Done" else "Open Settings",
            onAction = {
                openSamsungBatterySettings(context)
                adaptiveBatteryDone = !adaptiveBatteryDone
                prefs.edit().putBoolean("adaptive_battery", adaptiveBatteryDone).apply()
            }
        ),
        CheckItem(
            id = "auto_reset",
            title = "7. Disable Permission Auto-Reset",
            description = "Turn OFF 'Remove permissions if app isn't used' in App Info > Permissions.",
            isAutoDetected = false,
            isPassed = autoResetDone,
            actionLabel = if (autoResetDone) "Done" else "Open App Info",
            onAction = {
                val intent = Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS).apply {
                    data = Uri.parse("package:${context.packageName}")
                }
                context.startActivity(intent)
                autoResetDone = !autoResetDone
                prefs.edit().putBoolean("auto_reset", autoResetDone).apply()
            }
        ),
        CheckItem(
            id = "wifi_sleep",
            title = "8. Wi-Fi Power Saving & Mobile Switch OFF",
            description = "Settings > Connections > Wi-Fi > Advanced: Turn OFF 'Switch to mobile data' & Wi-Fi power saving.",
            isAutoDetected = false,
            isPassed = wifiSleepDone,
            actionLabel = if (wifiSleepDone) "Done" else "Open Wi-Fi",
            onAction = {
                context.startActivity(Intent(Settings.ACTION_WIFI_SETTINGS))
                wifiSleepDone = !wifiSleepDone
                prefs.edit().putBoolean("wifi_sleep", wifiSleepDone).apply()
            }
        )
    )

    val allPassed = items.all { it.isPassed }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Pre-Flight Check & Settings") },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "Back")
                    }
                },
                colors = TopAppBarDefaults.topAppBarColors(
                    containerColor = MaterialTheme.colorScheme.surface
                )
            )
        }
    ) { padding ->
        LazyColumn(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp)
        ) {
            item {
                Card(
                    modifier = Modifier.fillMaxWidth(),
                    colors = CardDefaults.cardColors(
                        containerColor = if (allPassed) Color(0xFF1B5E20) else Color(0xFF4A3400)
                    )
                ) {
                    Row(
                        modifier = Modifier.padding(16.dp),
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Icon(
                            imageVector = if (allPassed) Icons.Default.CheckCircle else Icons.Default.Warning,
                            contentDescription = null,
                            tint = Color.White,
                            modifier = Modifier.size(32.dp)
                        )
                        Spacer(modifier = Modifier.width(12.dp))
                        Column {
                            Text(
                                text = if (allPassed) "Ready for Flight!" else "Pre-Flight Setup Incomplete",
                                fontWeight = FontWeight.Bold,
                                color = Color.White,
                                fontSize = 16.sp
                            )
                            Text(
                                text = if (allPassed) "All background optimizations and permissions are configured." else "Complete the steps below for reliable screen-off streaming.",
                                color = Color.White.copy(alpha = 0.85f),
                                fontSize = 13.sp
                            )
                        }
                    }
                }
            }

            items(items) { item ->
                Card(
                    modifier = Modifier.fillMaxWidth(),
                    shape = RoundedCornerShape(10.dp),
                    colors = CardDefaults.cardColors(
                        containerColor = MaterialTheme.colorScheme.surfaceVariant
                    )
                ) {
                    Column(modifier = Modifier.padding(14.dp)) {
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.SpaceBetween,
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            Text(
                                text = item.title,
                                fontWeight = FontWeight.SemiBold,
                                fontSize = 15.sp,
                                modifier = Modifier.weight(1f)
                            )
                            Icon(
                                imageVector = if (item.isPassed) Icons.Default.CheckCircle else Icons.Default.Warning,
                                contentDescription = null,
                                tint = if (item.isPassed) Color(0xFF00E676) else Color(0xFFFFB300),
                                modifier = Modifier.size(20.dp)
                            )
                        }

                        Spacer(modifier = Modifier.height(6.dp))
                        Text(
                            text = item.description,
                            fontSize = 13.sp,
                            color = MaterialTheme.colorScheme.onSurfaceVariant.copy(alpha = 0.8f)
                        )

                        Spacer(modifier = Modifier.height(10.dp))
                        Button(
                            onClick = { item.onAction(context) },
                            colors = ButtonDefaults.buttonColors(
                                containerColor = if (item.isPassed) Color(0xFF2E7D32) else MaterialTheme.colorScheme.primary
                            ),
                            modifier = Modifier.align(Alignment.End)
                        ) {
                            Text(item.actionLabel, fontSize = 12.sp)
                        }
                    }
                }
            }

            item {
                Spacer(modifier = Modifier.height(12.dp))
                Button(
                    onClick = onBack,
                    modifier = Modifier.fillMaxWidth()
                ) {
                    Text("Return to Flight Control")
                }
            }
        }
    }
}

private fun openSamsungBatterySettings(context: Context) {
    try {
        // Try Samsung Device Care Battery Intent
        val intent = Intent().apply {
            setClassName("com.samsung.android.lool", "com.samsung.android.sm.ui.battery.BatteryActivity")
        }
        context.startActivity(intent)
    } catch (_: Exception) {
        try {
            val appInfo = Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS).apply {
                data = Uri.parse("package:${context.packageName}")
            }
            context.startActivity(appInfo)
        } catch (_: Exception) {
            context.startActivity(Intent(Settings.ACTION_SETTINGS))
        }
    }
}
