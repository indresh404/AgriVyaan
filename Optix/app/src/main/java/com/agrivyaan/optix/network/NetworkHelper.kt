package com.agrivyaan.optix.network

import android.content.Context
import android.net.ConnectivityManager
import android.net.LinkProperties
import android.net.Network
import android.net.NetworkCapabilities
import android.net.wifi.WifiManager
import android.os.Build
import android.util.Log
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import java.net.Inet4Address
import java.net.NetworkInterface
import kotlin.math.max
import kotlin.math.min

data class NetworkSignalInfo(
    val ip: String = "127.0.0.1",
    val rssiDbm: Int = -55,
    val signalPercent: Int = 85,
    val isConnected: Boolean = true
)

class NetworkHelper(private val context: Context) {

    private val connectivityManager =
        context.getSystemService(Context.CONNECTIVITY_SERVICE) as ConnectivityManager

    private val wifiManager =
        context.applicationContext.getSystemService(Context.WIFI_SERVICE) as? WifiManager

    private val _signalInfo = MutableStateFlow(NetworkSignalInfo(ip = getIpAddressInternal()))
    val signalInfo: StateFlow<NetworkSignalInfo> = _signalInfo.asStateFlow()

    val ipAddress: StateFlow<String>
        get() = MutableStateFlow(_signalInfo.value.ip)

    private val networkCallback = object : ConnectivityManager.NetworkCallback() {
        override fun onAvailable(network: Network) {
            updateNetworkStats()
        }

        override fun onLost(network: Network) {
            updateNetworkStats()
        }

        override fun onLinkPropertiesChanged(network: Network, linkProperties: LinkProperties) {
            updateNetworkStats()
        }

        override fun onCapabilitiesChanged(network: Network, capabilities: NetworkCapabilities) {
            updateNetworkStats()
        }
    }

    fun startMonitoring() {
        try {
            connectivityManager.registerDefaultNetworkCallback(networkCallback)
            updateNetworkStats()
        } catch (e: Exception) {
            Log.e("NetworkHelper", "Error registering network callback", e)
            updateNetworkStats()
        }
    }

    fun stopMonitoring() {
        try {
            connectivityManager.unregisterNetworkCallback(networkCallback)
        } catch (_: Exception) {}
    }

    fun updateNetworkStats() {
        val ip = getIpAddressInternal()
        var rssi = -60

        try {
            // Priority 1: NetworkCapabilities signalStrength (Android 10+)
            val activeNet = connectivityManager.activeNetwork
            if (activeNet != null) {
                val caps = connectivityManager.getNetworkCapabilities(activeNet)
                if (caps != null && Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
                    val ss = caps.signalStrength
                    if (ss != 0 && ss > -127) {
                        rssi = ss
                    }
                }
            }

            // Priority 2: WifiInfo from WifiManager
            if (rssi == -60 && wifiManager != null) {
                @Suppress("DEPRECATION")
                val info = wifiManager.connectionInfo
                if (info != null && info.rssi != -127 && info.rssi != 0) {
                    rssi = info.rssi
                }
            }
        } catch (_: Exception) {}

        // Calculate 0-100% signal quality: -100 dBm = 0%, -50 dBm = 100%
        val pct = max(0, min(100, (2 * (rssi + 100))))

        _signalInfo.value = NetworkSignalInfo(
            ip = ip,
            rssiDbm = rssi,
            signalPercent = pct,
            isConnected = ip != "127.0.0.1" && ip.isNotEmpty()
        )
    }

    private fun getIpAddressInternal(): String {
        try {
            val activeNetwork = connectivityManager.activeNetwork
            if (activeNetwork != null) {
                val linkProps = connectivityManager.getLinkProperties(activeNetwork)
                linkProps?.linkAddresses?.forEach { linkAddr ->
                    val addr = linkAddr.address
                    if (addr is Inet4Address && !addr.isLoopbackAddress) {
                        return addr.hostAddress ?: ""
                    }
                }
            }

            val interfaces = NetworkInterface.getNetworkInterfaces()
            while (interfaces.hasMoreElements()) {
                val intf = interfaces.nextElement()
                if (!intf.isUp || intf.isLoopback) continue

                val addrs = intf.inetAddresses
                while (addrs.hasMoreElements()) {
                    val addr = addrs.nextElement()
                    if (addr is Inet4Address && !addr.isLoopbackAddress) {
                        val host = addr.hostAddress
                        if (!host.isNullOrEmpty() && !host.startsWith("127.")) {
                            return host
                        }
                    }
                }
            }
        } catch (e: Exception) {
            Log.e("NetworkHelper", "Error getting IP address", e)
        }
        return "127.0.0.1"
    }
}
