package ai.pickup.app

import android.graphics.Bitmap
import androidx.compose.ui.test.hasScrollAction
import androidx.compose.ui.test.hasText
import androidx.compose.ui.test.performScrollToNode
import androidx.compose.ui.test.hasSetTextAction
import androidx.compose.ui.test.junit4.createAndroidComposeRule
import androidx.compose.ui.test.onAllNodesWithText
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
import androidx.compose.ui.test.performScrollTo
import androidx.compose.ui.test.performTextInput
import androidx.compose.ui.test.performTouchInput
import androidx.compose.ui.test.swipeUp
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import java.io.File

/**
 * Walks through the app and saves screenshots to the app's files/screens folder.
 * Run by .github/workflows/screenshots.yml against a local dev backend filled by
 * backend/scripts/seed_demo.py. Not part of the normal test run.
 */
@RunWith(AndroidJUnit4::class)
class ScreenshotTour {
    @get:Rule
    val rule = createAndroidComposeRule<MainActivity>()

    private val instrumentation get() = InstrumentationRegistry.getInstrumentation()

    private fun shot(name: String) {
        rule.waitForIdle()
        Thread.sleep(1200) // let animations and images settle
        val bitmap = instrumentation.uiAutomation.takeScreenshot()
        val dir = File(instrumentation.targetContext.filesDir, "screens").apply { mkdirs() }
        File(dir, "$name.png").outputStream().use { bitmap.compress(Bitmap.CompressFormat.PNG, 100, it) }
    }

    // Ignores case: section headers are drawn in capitals.
    private fun waitFor(text: String, timeoutMs: Long = 20_000) {
        rule.waitUntil(timeoutMs) { rule.onAllNodesWithText(text, substring = true, ignoreCase = true).fetchSemanticsNodes().isNotEmpty() }
    }

    private fun tap(text: String) {
        waitFor(text)
        rule.onAllNodesWithText(text, substring = true)[0].performClick()
    }

    /** Calls further down the list aren't composed until scrolled to. */
    private fun scrollToAndTap(text: String) {
        runCatching { rule.onAllNodes(hasScrollAction())[0].performScrollToNode(hasText(text, substring = true)) }
        tap(text)
    }

    private fun type(value: String) {
        rule.waitUntil(20_000) { rule.onAllNodes(hasSetTextAction()).fetchSemanticsNodes().isNotEmpty() }
        rule.onAllNodes(hasSetTextAction())[0].performTextInput(value)
    }

    private fun back() {
        rule.activityRule.scenario.onActivity { it.onBackPressedDispatcher.onBackPressed() }
        rule.waitForIdle()
    }

    private fun signIn(phoneDigits: String, capture: Boolean) {
        waitFor("Get started")
        if (capture) shot("01-welcome")
        tap("Get started")
        waitFor("What's your mobile number?")
        type(phoneDigits)
        if (capture) shot("02-phone-number")
        tap("Send code")
        waitFor("Enter the code")
        type("123456") // the code screen submits on its own at six digits
    }

    /** A brand-new user: the onboarding screens. */
    @Test
    fun onboarding() {
        signIn("9800000001", capture = true)
        waitFor("Make it yours")
        type("Asha Rao")
        shot("03-profile")
        tap("Continue")
        waitFor("A few permissions")
        shot("04-permissions")
        tap("Continue")
        waitFor("Point missed calls to your assistant", 30_000)
        shot("05-forwarding-setup")
    }

    /** A user with a few days of calls: the main app. */
    @Test
    fun mainApp() {
        signIn("9800000002", capture = false)
        waitFor("Live:", 30_000)
        waitFor("Blue Dart")
        shot("10-home-calls")

        tap("Live:")
        waitFor("confirm Asha's appointment")
        shot("11-live-call")
        back()

        scrollToAndTap("Rohit · TalentEdge")
        waitFor("senior product manager")
        shot("12-call-summary")
        back()

        scrollToAndTap("+91 74285 31902")
        waitFor("KYC")
        shot("13-scam-call")
        back()

        tap("Ask Pickup")
        waitFor("remind me at 6")
        shot("14-ask-pickup-chat")

        tap("Settings")
        waitFor("How Pickup answers")
        shot("15-settings")
        rule.onAllNodes(hasScrollAction())[0].performTouchInput { swipeUp(); swipeUp() }
        shot("16-settings-more")

        rule.onNodeWithText("Instructions").performScrollTo().performClick()
        waitFor("Ready-made packs")
        shot("17-instructions")
        back()

        rule.onNodeWithText("Check my setup").performScrollTo().performClick()
        waitFor("Report a problem")
        shot("18-check-my-setup")
    }
}
