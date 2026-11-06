package ca.jacklai.vitals

import android.graphics.Bitmap
import androidx.test.core.app.ActivityScenario
import androidx.test.platform.app.InstrumentationRegistry
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createEmptyComposeRule
import androidx.test.espresso.web.sugar.Web.onWebView
import androidx.test.espresso.web.webdriver.DriverAtoms.*
import androidx.test.espresso.web.webdriver.Locator
import org.junit.Rule
import org.junit.Test
import java.io.File
import java.net.HttpURLConnection
import java.net.URL

class BridgeJourneyTest {
    @get:Rule val compose = createEmptyComposeRule()
    private fun waitFor(text: String) {
        compose.waitUntil(30_000) { compose.onAllNodesWithText(text).fetchSemanticsNodes().isNotEmpty() }
    }
    private fun approve() {
        compose.waitUntil(30_000) {
            runCatching {
                onWebView().withElement(findElement(Locator.LINK_TEXT, "Approve fictional records")).perform(webClick())
            }.isSuccess
        }
    }
    @Test fun consentRefreshRestartCacheAndExpiredSession() {
        val context = InstrumentationRegistry.getInstrumentation().targetContext
        context.deleteDatabase("fictional-vitals.db")
        context.getSharedPreferences("connection", 0).edit().clear().commit()
        var activity = ActivityScenario.launch(MainActivity::class.java)
        try {
            compose.onNodeWithText("Sign in with SMART on FHIR").performScrollTo().performClick()
            waitFor("Approve access to the fictional records in the bridge sign-in page.")
            // Espresso waits for the real WebView consent page; no cookie or token is injected.
            approve()
            waitFor("Up to date. Fictional records only.")
            compose.onNodeWithText("70.0 bpm").performScrollTo().assertIsDisplayed()
            compose.onNodeWithText("SpO₂").performScrollTo().assertIsDisplayed()
            compose.onNodeWithText("99.0 %").performScrollTo().assertIsDisplayed()
            compose.onNodeWithText("Heart rate").performScrollTo()
            val screenshot = InstrumentationRegistry.getInstrumentation().uiAutomation.takeScreenshot()
            val output = InstrumentationRegistry.getArguments().getString("additionalTestOutputDir")
                ?.let(::File) ?: context.getExternalFilesDir(null)!!
            output.mkdirs()
            File(output, "vitals.png").outputStream().use {
                screenshot.compress(Bitmap.CompressFormat.PNG, 100, it)
            }
            screenshot.recycle()
            Thread.sleep(6_000) // 15-second tokens refresh inside the bridge's 10-second safety window.
            compose.onNodeWithText("Refresh").performScrollTo().performClick()
            waitFor("Up to date. Fictional records only.")
            val status = URL("http://localhost:8000/sandbox/status").openConnection() as HttpURLConnection
            try {
                val result = org.json.JSONObject(status.inputStream.bufferedReader().use { it.readText() })
                check(result.getInt("refresh_count") > 0)
            } finally { status.disconnect() }
            // New Activity/ViewModel has no session. The persisted Room report still opens.
            activity.close()
            activity = ActivityScenario.launch(MainActivity::class.java)
            waitFor("Saved snapshot. Sign in to check for updates.")
            compose.onNodeWithText("70.0 bpm").performScrollTo().assertIsDisplayed()
            compose.onNodeWithText("Sign in with SMART on FHIR").performScrollTo().performClick()
            waitFor("Approve access to the fictional records in the bridge sign-in page.")
            approve()
            waitFor("Up to date. Fictional records only.")
            val request = URL("http://localhost:8000/sandbox/expire").openConnection() as HttpURLConnection
            try { request.requestMethod = "POST"; check(request.responseCode == 200) } finally { request.disconnect() }
            compose.onNodeWithText("Refresh").performScrollTo().performClick()
            waitFor("Session expired. Sign in again. Showing saved snapshot.")
            compose.onNodeWithText("70.0 bpm").performScrollTo().assertIsDisplayed()
            compose.onNodeWithText("Sign out and clear cache").performScrollTo().performClick()
            waitFor("Signed out. Saved snapshots cleared.")
            compose.onNodeWithText("No saved measurements").performScrollTo().assertIsDisplayed()
        } finally { activity.close() }
    }
}
