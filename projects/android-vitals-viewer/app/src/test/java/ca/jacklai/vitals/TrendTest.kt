package ca.jacklai.vitals

import org.junit.Assert.*
import org.junit.Test

class TrendTest {
    private fun row(time: Long, value: Double?) = Reading("$time", "8867-4", "Heart rate", "/min", time, value, "Final")
    @Test fun usesElapsedTimeAndSortsSamples() {
        val points = chartPoints(listOf(row(100, 80.0), row(0, 60.0), row(10, 70.0)))
        assertEquals(listOf(0f to 1f, .1f to .5f, 1f to 0f), points)
    }
    @Test fun constantAndSingleValuesAreFinite() {
        assertEquals(.5f, chartPoints(listOf(row(0, 68.0))).single().first)
        assertTrue(chartPoints(listOf(row(0, 68.0), row(0, 68.0))).all { it.first.isFinite() && it.second.isFinite() })
    }
    @Test fun missingValuesLeaveNoFalseZero() { assertTrue(chartPoints(listOf(row(0, null))).isEmpty()) }
    @Test fun emptyChartIsEmpty() { assertTrue(chartPoints(emptyList()).isEmpty()) }
}
