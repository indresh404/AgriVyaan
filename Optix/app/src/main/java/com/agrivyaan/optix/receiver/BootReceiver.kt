package com.agrivyaan.optix.receiver

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.os.Build
import android.util.Log
import com.agrivyaan.optix.service.StreamingService

class BootReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        if (intent.action == Intent.ACTION_BOOT_COMPLETED || intent.action == "android.intent.action.QUICKBOOT_POWERON") {
            val prefs = context.getSharedPreferences("optix_prefs", Context.MODE_PRIVATE)
            val startOnBoot = prefs.getBoolean("start_on_boot", false)
            Log.i("BootReceiver", "Boot completed received. Start on boot enabled: $startOnBoot")
            
            if (startOnBoot) {
                val serviceIntent = Intent(context, StreamingService::class.java).apply {
                    action = StreamingService.ACTION_START_SERVER_ONLY
                }
                try {
                    if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                        context.startForegroundService(serviceIntent)
                    } else {
                        context.startService(serviceIntent)
                    }
                    Log.i("BootReceiver", "Optix StreamingService started on boot")
                } catch (e: Exception) {
                    Log.e("BootReceiver", "Failed to start StreamingService on boot", e)
                }
            }
        }
    }
}
