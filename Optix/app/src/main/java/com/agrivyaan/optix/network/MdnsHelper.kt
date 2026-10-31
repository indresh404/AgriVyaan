package com.agrivyaan.optix.network

import android.content.Context
import android.net.nsd.NsdManager
import android.net.nsd.NsdServiceInfo
import android.util.Log

class MdnsHelper(private val context: Context) {

    private val nsdManager = context.getSystemService(Context.NSD_SERVICE) as? NsdManager
    private var registrationListener: NsdManager.RegistrationListener? = null
    private var isRegistered = false

    fun registerService(port: Int = 8080, serviceName: String = "dronecam") {
        if (nsdManager == null || isRegistered) return

        val serviceInfo = NsdServiceInfo().apply {
            this.serviceName = serviceName
            this.serviceType = "_http._tcp."
            this.port = port
        }

        registrationListener = object : NsdManager.RegistrationListener {
            override fun onServiceRegistered(serviceInfo: NsdServiceInfo) {
                isRegistered = true
                Log.i("MdnsHelper", "mDNS Service registered: ${serviceInfo.serviceName}.local on port $port")
            }

            override fun onRegistrationFailed(serviceInfo: NsdServiceInfo, errorCode: Int) {
                isRegistered = false
                Log.e("MdnsHelper", "mDNS Registration failed: code $errorCode")
            }

            override fun onServiceUnregistered(serviceInfo: NsdServiceInfo) {
                isRegistered = false
                Log.i("MdnsHelper", "mDNS Service unregistered")
            }

            override fun onUnregistrationFailed(serviceInfo: NsdServiceInfo, errorCode: Int) {
                isRegistered = false
                Log.e("MdnsHelper", "mDNS Unregistration failed: code $errorCode")
            }
        }

        try {
            nsdManager.registerService(serviceInfo, NsdManager.PROTOCOL_DNS_SD, registrationListener)
        } catch (e: Exception) {
            Log.e("MdnsHelper", "Failed to register mDNS service", e)
        }
    }

    fun unregisterService() {
        if (!isRegistered || nsdManager == null || registrationListener == null) return
        try {
            nsdManager.unregisterService(registrationListener)
        } catch (e: Exception) {
            Log.e("MdnsHelper", "Error unregistering mDNS service", e)
        } finally {
            isRegistered = false
            registrationListener = null
        }
    }
}
