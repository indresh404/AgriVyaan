package com.agrivyaan.optix.ui

import android.content.ClipData
import android.content.ClipboardManager
import android.content.Context
import android.graphics.Bitmap
import android.widget.Toast
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Build
import androidx.compose.material.icons.filled.Info
import androidx.compose.material.icons.filled.PlayArrow
import androidx.compose.material.icons.filled.Stop
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.agrivyaan.optix.diagnostics.DiagnosticHelper
import com.agrivyaan.optix.network.QrCodeGenerator
import com.agrivyaan.optix.service.CameraMode
import com.agrivyaan.optix.service.ServiceUiState
import com.agrivyaan.optix.service.StreamingService

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun MainScreen(
    state: ServiceUiState,
    onStartService: () -> Unit,
    onStopService: () -> Unit,
    onOpenPreFlight: () -> Unit,
    onDetectUsb: () -> Unit = {}
) {
    val context = LocalContext.current
    val scrollState = rememberScrollState()

    var showDiagnosticsDialog by remember { mutableStateOf(false) }
    var diagnosticsReport by remember { mutableStateOf("") }

    val fullUrl = remember(state.ipAddress, state.port) {
        "http://${state.ipAddress}:${state.port}"
    }

    val qrBitmap = remember(fullUrl) {
        QrCodeGenerator.generateQrBitmap(fullUrl, 400)
    }

    val statusDotColor = when {
        !state.isRunning -> Color(0xFF757575)
        state.clientsCount > 0 -> Color(0xFF00E676) // Viewer connected
        else -> Color(0xFF29B6F6) // Server running
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Text(
                            "OPTIX",
                            fontWeight = FontWeight.Black,
                            letterSpacing = 2.sp,
                            color = MaterialTheme.colorScheme.primary
                        )
                        Spacer(modifier = Modifier.width(8.dp))
                        Surface(
                            shape = RoundedCornerShape(4.dp),
                            color = MaterialTheme.colorScheme.primaryContainer
                        ) {
                            Text(
                                "DRONE CAM",
                                fontSize = 10.sp,
                                fontWeight = FontWeight.Bold,
                                modifier = Modifier.padding(horizontal = 6.dp, vertical = 2.dp),
                                color = MaterialTheme.colorScheme.onPrimaryContainer
                            )
                        }
                    }
                },
                actions = {
                    IconButton(onClick = {
                        diagnosticsReport = DiagnosticHelper.generateReport(
                            context = context,
                            batteryInfo = state.batteryInfo,
                            currentIp = state.ipAddress
                        )
                        showDiagnosticsDialog = true
                    }) {
                        Icon(Icons.Default.Info, contentDescription = "Diagnostics")
                    }
                },
                colors = TopAppBarDefaults.topAppBarColors(
                    containerColor = MaterialTheme.colorScheme.surface
                )
            )
        }
    ) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .verticalScroll(scrollState)
                .padding(16.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.spacedBy(16.dp)
        ) {
            // Status Banner
            Card(
                modifier = Modifier.fillMaxWidth(),
                colors = CardDefaults.cardColors(
                    containerColor = MaterialTheme.colorScheme.surfaceVariant
                )
            ) {
                Row(
                    modifier = Modifier.padding(14.dp),
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Box(
                        modifier = Modifier
                            .size(14.dp)
                            .clip(CircleShape)
                            .background(statusDotColor)
                    )
                    Spacer(modifier = Modifier.width(10.dp))
                    Column(modifier = Modifier.weight(1f)) {
                        Text(
                            text = state.statusText,
                            fontWeight = FontWeight.Bold,
                            fontSize = 15.sp
                        )
                        Text(
                            text = if (state.isRunning) "Live streamer online • No PIN required" else "Service offline. Tap Start below.",
                            fontSize = 12.sp,
                            color = MaterialTheme.colorScheme.onSurfaceVariant.copy(alpha = 0.7f)
                        )
                    }
                }
            }

            // Connection URL & QR Card
            Card(
                modifier = Modifier.fillMaxWidth(),
                colors = CardDefaults.cardColors(
                    containerColor = MaterialTheme.colorScheme.surface
                ),
                elevation = CardDefaults.cardElevation(defaultElevation = 2.dp)
            ) {
                Column(
                    modifier = Modifier.padding(18.dp),
                    horizontalAlignment = Alignment.CenterHorizontally
                ) {
                    Text(
                        "SCAN ONCE TO CONNECT GROUND STATION",
                        fontSize = 11.sp,
                        fontWeight = FontWeight.Bold,
                        color = MaterialTheme.colorScheme.primary,
                        letterSpacing = 1.sp
                    )
                    Spacer(modifier = Modifier.height(6.dp))
                    Text(
                        text = fullUrl,
                        fontSize = 22.sp,
                        fontWeight = FontWeight.ExtraBold,
                        fontFamily = FontFamily.Monospace,
                        color = MaterialTheme.colorScheme.onSurface
                    )
                    Text(
                        text = "Instant live stream • Free access",
                        fontSize = 12.sp,
                        color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.6f)
                    )

                    Spacer(modifier = Modifier.height(14.dp))

                    // QR Code
                    if (qrBitmap != null) {
                        Image(
                            bitmap = qrBitmap.asImageBitmap(),
                            contentDescription = "QR Code URL",
                            modifier = Modifier
                                .size(200.dp)
                                .clip(RoundedCornerShape(10.dp))
                                .background(Color.White)
                                .padding(10.dp)
                        )
                    }

                    Spacer(modifier = Modifier.height(14.dp))

                    // Copy URL Button
                    OutlinedButton(
                        onClick = {
                            val clipboard = context.getSystemService(Context.CLIPBOARD_SERVICE) as ClipboardManager
                            val clip = ClipData.newPlainText("Optix Ground URL", fullUrl)
                            clipboard.setPrimaryClip(clip)
                            Toast.makeText(context, "URL Copied to Clipboard", Toast.LENGTH_SHORT).show()
                        }
                    ) {
                        Text("Copy Ground URL")
                    }
                }
            }

            // Telemetry Bar
            Card(
                modifier = Modifier.fillMaxWidth(),
                colors = CardDefaults.cardColors(
                    containerColor = MaterialTheme.colorScheme.surfaceVariant
                )
            ) {
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(12.dp),
                    horizontalArrangement = Arrangement.SpaceAround,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Column(horizontalAlignment = Alignment.CenterHorizontally) {
                        Text("BATTERY", fontSize = 10.sp, fontWeight = FontWeight.Bold)
                        Text(
                            "${state.batteryInfo.level}% ${if (state.batteryInfo.isCharging) "⚡" else ""}",
                            fontWeight = FontWeight.Bold,
                            fontSize = 14.sp
                        )
                    }
                    Column(horizontalAlignment = Alignment.CenterHorizontally) {
                        Text("TEMP", fontSize = 10.sp, fontWeight = FontWeight.Bold)
                        Text(
                            "${String.format("%.1f", state.batteryInfo.temperatureCelsius)}°C",
                            fontWeight = FontWeight.Bold,
                            fontSize = 14.sp,
                            color = if (state.batteryInfo.isOverheating) Color.Red else Color.Unspecified
                        )
                    }
                    Column(horizontalAlignment = Alignment.CenterHorizontally) {
                        Text("VIEWERS", fontSize = 10.sp, fontWeight = FontWeight.Bold)
                        Text(
                            "${state.clientsCount}",
                            fontWeight = FontWeight.Bold,
                            fontSize = 14.sp
                        )
                    }
                }
            }

            // Camera Mode Selection
            Column(
                modifier = Modifier.fillMaxWidth(),
                horizontalAlignment = Alignment.CenterHorizontally
            ) {
                Text("CAMERA MODE", fontSize = 11.sp, fontWeight = FontWeight.Bold)
                Spacer(modifier = Modifier.height(6.dp))
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    FilterChip(
                        selected = state.cameraMode == CameraMode.PHONE,
                        onClick = { StreamingService.setCameraMode(CameraMode.PHONE) },
                        label = { Text("Phone") },
                        modifier = Modifier.weight(1f)
                    )
                    FilterChip(
                        selected = state.cameraMode == CameraMode.USB,
                        onClick = { StreamingService.setCameraMode(CameraMode.USB) },
                        label = { Text("USB Cam") },
                        modifier = Modifier.weight(1f)
                    )
                    FilterChip(
                        selected = state.cameraMode == CameraMode.BOTH,
                        onClick = { StreamingService.setCameraMode(CameraMode.BOTH) },
                        label = { Text("Both") },
                        modifier = Modifier.weight(1f)
                    )
                }
            }

            // USB OTG Camera Card
            Card(
                modifier = Modifier.fillMaxWidth(),
                colors = CardDefaults.cardColors(
                    containerColor = MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.5f)
                ),
                shape = RoundedCornerShape(12.dp)
            ) {
                Column(modifier = Modifier.padding(14.dp)) {
                    Text(
                        "🔌 USB OTG WEBCAM",
                        fontWeight = FontWeight.Bold,
                        fontSize = 12.sp,
                        color = MaterialTheme.colorScheme.primary
                    )
                    Spacer(modifier = Modifier.height(4.dp))
                    Text(
                        text = "Plug in your USB camera via OTG adapter and tap below to grant Android hardware access.",
                        fontSize = 11.sp,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                    Spacer(modifier = Modifier.height(8.dp))
                    Button(
                        onClick = onDetectUsb,
                        modifier = Modifier.fillMaxWidth(),
                        colors = ButtonDefaults.buttonColors(
                            containerColor = MaterialTheme.colorScheme.primary
                        )
                    ) {
                        Text("DETECT & GRANT USB PERMISSION", fontSize = 12.sp, fontWeight = FontWeight.Bold)
                    }
                }
            }

            // Big Start/Stop Button
            Button(
                onClick = {
                    if (state.isRunning) onStopService() else onStartService()
                },
                modifier = Modifier
                    .fillMaxWidth()
                    .height(56.dp),
                colors = ButtonDefaults.buttonColors(
                    containerColor = if (state.isRunning) Color(0xFFD32F2F) else Color(0xFF2E7D32)
                ),
                shape = RoundedCornerShape(12.dp)
            ) {
                Icon(
                    imageVector = if (state.isRunning) Icons.Default.Stop else Icons.Default.PlayArrow,
                    contentDescription = null
                )
                Spacer(modifier = Modifier.width(8.dp))
                Text(
                    text = if (state.isRunning) "STOP STREAMING SERVICE" else "START STREAMING SERVICE",
                    fontWeight = FontWeight.Bold,
                    fontSize = 15.sp
                )
            }

            // Pre-Flight Check Button
            OutlinedButton(
                onClick = onOpenPreFlight,
                modifier = Modifier.fillMaxWidth()
            ) {
                Icon(Icons.Default.Build, contentDescription = null, modifier = Modifier.size(18.dp))
                Spacer(modifier = Modifier.width(8.dp))
                Text("Pre-Flight Check & Settings")
            }
        }
    }

    // Diagnostics Dialog
    if (showDiagnosticsDialog) {
        AlertDialog(
            onDismissRequest = { showDiagnosticsDialog = false },
            title = { Text("System Diagnostics") },
            text = {
                Text(
                    text = diagnosticsReport,
                    fontFamily = FontFamily.Monospace,
                    fontSize = 11.sp,
                    modifier = Modifier.verticalScroll(rememberScrollState())
                )
            },
            confirmButton = {
                TextButton(
                    onClick = {
                        val clipboard = context.getSystemService(Context.CLIPBOARD_SERVICE) as ClipboardManager
                        val clip = ClipData.newPlainText("Optix Diagnostics", diagnosticsReport)
                        clipboard.setPrimaryClip(clip)
                        Toast.makeText(context, "Report Copied", Toast.LENGTH_SHORT).show()
                    }
                ) {
                    Text("Copy Report")
                }
            },
            dismissButton = {
                TextButton(onClick = { showDiagnosticsDialog = false }) {
                    Text("Close")
                }
            }
        )
    }
}
