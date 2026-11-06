package ca.jacklai.vitals

import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config

const val PATIENT = "11111111-1111-4111-8111-111111111111"
fun fixture() = ReportParserTest::class.java.getResource("/report.json")!!.readText()
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [35])
class ReportParserTest {
    private fun changed(change: (JSONObject) -> Unit): VisitReport {
        val report = JSONObject(fixture())
        change(report.getJSONArray("visits").getJSONObject(0).getJSONArray("observations").getJSONObject(0))
        return ReportParser.parse(report.toString(), PATIENT)
    }
    @Test fun parsesRealBridgeReportWithSeparateVisitsAndThreeVitals() {
        val report = ReportParser.parse(fixture(), PATIENT)
        assertEquals(2, report.visits.size)
        assertEquals(18, report.visits.sumOf { it.readings.size })
        assertEquals(setOf("Heart rate", "Temperature", "SpO₂"), report.visits.first().readings.map { it.label }.toSet())
    }
    @Test(expected = IllegalArgumentException::class) fun rejectsDifferentPatient() { ReportParser.parse(fixture(), "other") }
    @Test(expected = IllegalArgumentException::class) fun rejectsNonFictionalData() {
        ReportParser.parse(JSONObject(fixture()).put("synthetic_only", false).toString(), PATIENT)
    }
    @Test fun zeroIsAValue() {
        assertEquals(0.0, changed { it.getJSONObject("valueQuantity").put("value", 0) }.visits.first().readings.first().value!!, 0.0)
    }
    @Test fun absentValueDoesNotBecomeZero() {
        val row = changed { it.remove("valueQuantity"); it.put("dataAbsentReason", JSONObject().put("text", "not measured")) }.visits.first().readings.first()
        assertNull(row.value); assertEquals("Missing measurement", row.note)
    }
    @Test fun fahrenheitIsPreserved() {
        val row = changed { it.getJSONObject("code").getJSONArray("coding").getJSONObject(0).put("code", "8310-5")
            it.getJSONObject("valueQuantity").put("code", "[degF]").put("value", 98.2) }.visits.first().readings.first()
        assertEquals("[degF]", row.unit); assertEquals(98.2, row.value!!, .001)
    }
    @Test fun wrongUnitIsNotPlotted() {
        assertNull(changed { it.getJSONObject("valueQuantity").put("code", "kg") }.visits.first().readings.first().value)
    }
    @Test fun qualifiedValueIsNotAnExactPoint() {
        assertNull(changed { it.getJSONObject("valueQuantity").put("comparator", "<") }.visits.first().readings.first().value)
    }
    @Test fun cancelledValueIsNotPlotted() {
        assertNull(changed { it.put("status", "cancelled") }.visits.first().readings.first().value)
    }
    @Test fun preliminaryValuesAreLabelled() {
        assertEquals("Preliminary", changed { it.put("status", "preliminary") }.visits.first().readings.first().note)
    }
    @Test fun invalidTimeIsNotPlotted() {
        assertNull(changed { it.put("effectiveDateTime", "yesterday") }.visits.first().readings.first().value)
    }
    @Test fun numericStringIsNotSilentlyAccepted() {
        assertNull(changed { it.getJSONObject("valueQuantity").put("value", "68") }.visits.first().readings.first().value)
    }
    @Test fun nonLoincCodeIsIgnored() {
        assertEquals(8, changed { it.getJSONObject("code").getJSONArray("coding").getJSONObject(0).put("system", "other") }.visits.first().readings.size)
    }
    @Test(expected = IllegalArgumentException::class) fun duplicateObservationRejectsReport() {
        val obj = JSONObject(fixture())
        val observations = obj.getJSONArray("visits").getJSONObject(0).getJSONArray("observations")
        observations.put(observations.getJSONObject(0))
        ReportParser.parse(obj.toString(), PATIENT)
    }
}
