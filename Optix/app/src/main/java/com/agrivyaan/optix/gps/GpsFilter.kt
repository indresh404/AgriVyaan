package com.agrivyaan.optix.gps

import kotlin.math.abs

/**
 * Filter to smooth out GPS micro-jitter while preserving responsiveness.
 */
class GpsFilter {
    private var isInitialized = false
    private var latEstimate = 0.0
    private var lonEstimate = 0.0
    private var altEstimate = 0.0
    private var headingEstimate = 0.0

    // Kalman error covariance & process noise
    private var variance = 4.0 // Initial estimate variance (meters^2)
    private val q = 0.5        // Process noise

    fun filter(lat: Double, lon: Double, alt: Double, heading: Float, accuracy: Float): FilteredPoint {
        if (!isInitialized) {
            latEstimate = lat
            lonEstimate = lon
            altEstimate = alt
            headingEstimate = heading.toDouble()
            isInitialized = true
            return FilteredPoint(lat, lon, alt, heading)
        }

        // Measurement noise variance from reported GPS accuracy
        val r = (accuracy * accuracy).coerceAtLeast(1.0f).toDouble()

        // Time update (prediction)
        variance += q

        // Measurement update (Kalman Gain)
        val k = variance / (variance + r)
        latEstimate += k * (lat - latEstimate)
        lonEstimate += k * (lon - lonEstimate)
        altEstimate += k * (alt - altEstimate)
        variance *= (1.0 - k)

        // Heading circular smoothing (handling 0/360 wrap-around)
        var diff = heading - headingEstimate
        while (diff < -180.0) diff += 360.0
        while (diff > 180.0) diff -= 360.0
        headingEstimate = (headingEstimate + diff * 0.35 + 360.0) % 360.0

        return FilteredPoint(latEstimate, lonEstimate, altEstimate, headingEstimate.toFloat())
    }

    fun reset() {
        isInitialized = false
    }

    data class FilteredPoint(
        val lat: Double,
        val lon: Double,
        val alt: Double,
        val heading: Float
    )
}
