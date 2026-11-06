package ca.jacklai.vitals

import org.json.JSONObject
import java.time.Instant

/** A projection of the bridge report. Units and unsupported results stay explicit. */
data class Reading(val id: String, val code: String, val label: String, val unit: String,
                   val time: Long?, val value: Double?, val note: String)
data class Visit(val id: String, val start: String, val readings: List<Reading>)
data class VisitReport(val patient: String, val visits: List<Visit>, val unassigned: Int, val excluded: Int)

object ReportParser {
    val labels = linkedMapOf("8867-4" to "Heart rate", "8310-5" to "Temperature",
        "59408-5" to "SpO₂", "2708-6" to "SpO₂")
    fun parse(raw: String, patient: String): VisitReport {
        val report = JSONObject(raw)
        require(report.getBoolean("synthetic_only")) { "Only fictional records are supported" }
        require(report.getString("patient_id") == patient) { "Patient does not match" }
        val visits = report.getJSONArray("visits")
        val seenVisits = mutableSetOf<String>()
        val seenReadings = mutableSetOf<String>()
        val parsed = (0 until visits.length()).map { i ->
            val visit = visits.getJSONObject(i)
            val id = visit.getString("id")
            require(id.isNotBlank() && seenVisits.add(id)) { "Duplicate or missing visit" }
            val readings = visit.getJSONArray("observations")
            Visit(id, visit.optJSONObject("period")?.optString("start").orEmpty(),
                (0 until readings.length()).mapNotNull { j ->
                    val obs = readings.getJSONObject(j)
                    val obsId = obs.getString("id")
                    require(obsId.isNotBlank() && seenReadings.add(obsId)) { "Duplicate or missing observation" }
                    val coding = obs.optJSONObject("code")?.optJSONArray("coding")
                    val code = coding?.let { codes -> (0 until codes.length()).map { codes.getJSONObject(it) }
                        .firstOrNull { it.optString("system") == "http://loinc.org" && it.optString("code") in labels }
                        ?.getString("code") } ?: return@mapNotNull null
                    val quantity = obs.optJSONObject("valueQuantity")
                    val unit = quantity?.optString("code").orEmpty()
                    val status = obs.optString("status")
                    val allowedUnit = when (code) {
                        "8867-4" -> unit == "/min"
                        "8310-5" -> unit in setOf("Cel", "[degF]")
                        else -> unit == "%"
                    }
                    val number = quantity?.opt("value") as? Number
                    val time = runCatching { Instant.parse(obs.getString("effectiveDateTime")).toEpochMilli() }.getOrNull()
                    val note = when {
                        status !in setOf("final", "amended", "corrected", "preliminary") -> "Unavailable ($status)"
                        obs.has("modifierExtension") || obs.has("component") -> "Needs review"
                        obs.has("dataAbsentReason") -> "Missing measurement"
                        quantity?.has("comparator") == true -> "Qualified value; see source"
                        number == null || !number.toDouble().isFinite() -> "Missing measurement"
                        quantity?.optString("system") != "http://unitsofmeasure.org" || !allowedUnit -> "Unsupported unit: $unit"
                        time == null -> "Missing measurement time"
                        status == "preliminary" -> "Preliminary"
                        else -> "Final"
                    }
                    val value = if (note in setOf("Final", "Preliminary")) number?.toDouble() else null
                    Reading(obsId, code, labels.getValue(code), unit, time, value, note)
                })
        }.sortedBy { it.start }
        return VisitReport(patient, parsed, report.getJSONArray("unassigned_observations").length(),
            report.getJSONArray("excluded_observations").length())
    }
}

/** Coordinates use elapsed time, rather than making uneven samples look equally spaced. */
fun chartPoints(readings: List<Reading>): List<Pair<Float, Float>> {
    val valid = readings.filter { it.time != null && it.value != null }.sortedBy { it.time }
    if (valid.isEmpty()) return emptyList()
    val first = valid.first().time!!
    val span = (valid.last().time!! - first).coerceAtLeast(1)
    val min = valid.minOf { it.value!! }
    val range = (valid.maxOf { it.value!! } - min).let { if (it == 0.0) 1.0 else it }
    return valid.map { (if (valid.size == 1) .5f else (it.time!! - first).toFloat() / span) to
        (1f - ((it.value!! - min) / range).toFloat()) }
}
