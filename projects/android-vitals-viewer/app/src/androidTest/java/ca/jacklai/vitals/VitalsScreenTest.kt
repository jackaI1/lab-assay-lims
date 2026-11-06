package ca.jacklai.vitals

import androidx.compose.material3.MaterialTheme
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createComposeRule
import org.junit.Rule
import org.junit.Test

class VitalsScreenTest {
    @get:Rule val compose = createComposeRule()
    @Test fun emptyCacheExplainsHowToBegin() {
        compose.setContent { MaterialTheme { VitalsScreen(ScreenState(), { _, _ -> }, {}, {}) } }
        compose.onNodeWithText("No saved measurements").performScrollTo().assertIsDisplayed()
    }
    @Test fun offlineStatusAndTimestampStayVisible() {
        compose.setContent { MaterialTheme { VitalsScreen(ScreenState(message = "Offline or bridge unreachable. Showing saved snapshot.", savedAt = 1000), { _, _ -> }, {}, {}) } }
        compose.onNodeWithText("Offline or bridge unreachable. Showing saved snapshot.").performScrollTo().assertIsDisplayed()
        compose.onNodeWithText("Saved Jan 1, 00:00 UTC").performScrollTo().assertIsDisplayed()
    }
    @Test fun refreshDisabledUntilAuthenticated() {
        compose.setContent { MaterialTheme { VitalsScreen(ScreenState(), { _, _ -> }, {}, {}) } }
        compose.onNodeWithText("Refresh").performScrollTo().assertIsNotEnabled()
    }
    @Test fun changingVisitChangesValues() {
        val row = Reading("o", "8867-4", "Heart rate", "/min", 0, 68.0, "Final")
        val report = VisitReport("fictional", listOf(Visit("first", "today", listOf(row)),
            Visit("second", "tomorrow", listOf(row.copy(value = 80.0)))), 1, 2)
        compose.setContent { MaterialTheme { VitalsScreen(ScreenState(report = report), { _, _ -> }, {}, {}) } }
        compose.onNodeWithText("68.0 bpm").performScrollTo().assertIsDisplayed()
        compose.onNodeWithText("Visit second").performScrollTo().performClick()
        compose.onNodeWithText("80.0 bpm").performScrollTo().assertIsDisplayed()
        compose.onAllNodesWithText("No measurement recorded").assertCountEquals(2) // Missing vital is explicit.
    }
    @Test fun expiredSessionGivesRecoveryAction() {
        compose.setContent { MaterialTheme { VitalsScreen(ScreenState(message = "Session expired. Sign in again. Showing saved snapshot."), { _, _ -> }, {}, {}) } }
        compose.onNodeWithText("Session expired. Sign in again. Showing saved snapshot.").performScrollTo().assertIsDisplayed()
        compose.onNodeWithText("Sign in with SMART on FHIR").performScrollTo().assertIsEnabled()
    }
}
