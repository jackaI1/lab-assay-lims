package ca.jacklai.vitals

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.compose.BackHandler
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import java.time.Instant
import java.time.ZoneOffset
import java.time.format.DateTimeFormatter
import java.util.Locale

private val Ink = Color(0xFF16324B)
private val Blue = Color(0xFF1261A0)
private val Teal = Color(0xFF007D78)
private val VitalsColors = lightColorScheme(primary = Blue, secondary = Teal, background = Color.White,
    surface = Color.White, onSurface = Ink, onBackground = Ink)
private fun timestamp(time: Long) = DateTimeFormatter.ofPattern("MMM d, HH:mm 'UTC'", Locale.US)
    .withZone(ZoneOffset.UTC).format(Instant.ofEpochMilli(time))
fun displayUnit(unit: String) = when (unit) {
    "/min" -> "bpm"
    "Cel" -> "°C"
    "[degF]" -> "°F"
    else -> unit
}
fun displayValue(value: Double) = String.format(Locale.US, "%.1f", value)

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent {
            MaterialTheme(colorScheme = VitalsColors) {
                val vm: VitalsViewModel = viewModel()
                val state by vm.state.collectAsStateWithLifecycle()
                Surface(Modifier.fillMaxSize()) {
                    if (state.login) {
                        BackHandler { vm.cancelLogin() }
                        LoginScreen(state.source, vm::authorized, vm::cancelLogin)
                    } else VitalsScreen(state, vm::connect, vm::refresh, vm::logout)
                }
            }
        }
    }
}

@Composable
fun VitalsScreen(state: ScreenState, connect: (String, String) -> Unit, refresh: () -> Unit, logout: () -> Unit) {
    var source by rememberSaveable(state.source) { mutableStateOf(state.source) }
    var patient by rememberSaveable(state.patient) { mutableStateOf(state.patient) }
    var selected by rememberSaveable(state.patient, state.source) { mutableStateOf("") }
    Column(Modifier.fillMaxSize().safeDrawingPadding().verticalScroll(rememberScrollState()).padding(20.dp),
        verticalArrangement = Arrangement.spacedBy(14.dp)) {
        Text("Vitals Viewer", style = MaterialTheme.typography.headlineLarge, fontWeight = FontWeight.Bold)
        Text("Fictional patient visits", style = MaterialTheme.typography.titleMedium, color = Teal)
        Text("Compare measurements within a visit, then keep a copy for when the connection drops.")
        OutlinedTextField(source, { source = it }, label = { Text("Bridge URL") }, singleLine = true,
            enabled = !state.busy, modifier = Modifier.fillMaxWidth())
        OutlinedTextField(patient, { patient = it }, label = { Text("Fictional patient UUID") }, singleLine = true,
            enabled = !state.busy, modifier = Modifier.fillMaxWidth())
        Button(onClick = { connect(source, patient) }, enabled = !state.busy, modifier = Modifier.fillMaxWidth()) {
            Text("Sign in with SMART on FHIR")
        }
        Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
            OutlinedButton(onClick = refresh, enabled = !state.busy && state.signedIn) { Text("Refresh") }
            TextButton(onClick = logout, enabled = !state.busy) { Text("Sign out and clear cache") }
        }
        if (state.busy) LinearProgressIndicator(Modifier.fillMaxWidth())
        Text(state.message, style = MaterialTheme.typography.bodyMedium)
        state.savedAt?.let { Text("Saved ${timestamp(it)}", style = MaterialTheme.typography.labelLarge) }
        val report = state.report
        if (report == null) {
            HorizontalDivider()
            Text("No saved measurements", style = MaterialTheme.typography.titleLarge)
            Text("Start the local sandbox, then sign in and approve access. Only fictional records are supported.")
        } else {
            Text("${report.visits.size} visits · ${report.unassigned} need review · ${report.excluded} excluded")
            report.visits.forEach { visit ->
                FilterChip(selected = selected == visit.id || (selected.isEmpty() && report.visits.first() == visit),
                    onClick = { selected = visit.id }, label = { Text("Visit ${visit.id}") })
            }
            val visit = report.visits.firstOrNull { it.id == selected } ?: report.visits.firstOrNull()
            if (visit == null) Text("No visits returned. Unassigned readings are not placed on a chart.")
            visit?.let {
                Text("Visit starts ${it.start.ifBlank { "at an unknown time" }}", style = MaterialTheme.typography.bodyMedium)
                listOf("Heart rate", "Temperature", "SpO₂").forEach { label ->
                    HorizontalDivider()
                    Text(label, style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.SemiBold)
                    val rows = it.readings.filter { r -> r.label == label }
                    if (rows.isEmpty()) Text("No measurement recorded")
                    rows.groupBy { r -> r.unit }.forEach { (unit, readings) ->
                        val valid = readings.filter { r -> r.value != null && r.time != null }.sortedBy { r -> r.time }
                        if (valid.isNotEmpty()) {
                            Text("${displayValue(valid.last().value!!)} ${displayUnit(unit)}", style = MaterialTheme.typography.headlineMedium, color = Blue)
                            TrendChart(valid, "$label (${displayUnit(unit)})")
                        }
                        readings.sortedBy { r -> r.time }.forEach { r ->
                            Text("${r.time?.let(::timestamp) ?: "Time unavailable"}: ${r.value?.let(::displayValue) ?: "No value"} ${displayUnit(r.unit)} · ${r.note}",
                                style = MaterialTheme.typography.bodyMedium)
                        }
                    }
                }
                Text("Each unit has its own chart. Preliminary values are labelled. No diagnosis or alert thresholds are inferred.",
                    style = MaterialTheme.typography.bodySmall)
            }
        }
    }
}

@Composable
private fun TrendChart(readings: List<Reading>, label: String) {
    val points = chartPoints(readings)
    val range = "${displayValue(readings.minOf { it.value!! })} to ${displayValue(readings.maxOf { it.value!! })}"
    Canvas(Modifier.fillMaxWidth().height(100.dp).semantics {
        contentDescription = "$label trend, ${readings.size} measurements, range $range. Values listed below."
    }) {
        val inset = 10.dp.toPx()
        fun position(p: Pair<Float, Float>) = Offset(inset + p.first * (size.width - 2 * inset), inset + p.second * (size.height - 2 * inset))
        drawLine(Color(0xFFCCD9E2), Offset(inset, size.height - inset), Offset(size.width - inset, size.height - inset))
        points.zipWithNext().forEach { (a, b) -> drawLine(Blue, position(a), position(b), 3.dp.toPx()) }
        points.forEach { drawCircle(Teal, 4.dp.toPx(), position(it)) }
    }
    Text("Range $range · ${timestamp(readings.first().time!!)} to ${timestamp(readings.last().time!!)}",
        style = MaterialTheme.typography.bodySmall)
}
