package ai.pickup.app

import ai.pickup.app.telephony.ScreeningPolicy
import ai.pickup.app.telephony.ScreeningPolicy.Decision.RING
import ai.pickup.app.telephony.ScreeningPolicy.Decision.SEND_TO_ASSISTANT
import org.junit.Assert.assertEquals
import org.junit.Test

class ScreeningPolicyTest {
    private val now = 1_000_000L
    private fun input(
        number: String? = "+917000000001",
        isContact: Boolean = false,
        mode: String = "assistant_first",
        screenContacts: Boolean = false,
        lineVerified: Boolean = true,
        snoozedUntil: Long? = null,
        verifyUntil: Long = 0,
        alwaysRing: Set<String> = emptySet(),
        alwaysScreen: Set<String> = emptySet(),
        activeSims: Int = 1,
        configuredSims: Int = 1,
        incoming: Boolean = true,
        ringVerifiedBusiness: Boolean = true,
        ringRepeatCallers: Boolean = true,
        lastSent: Long? = null,
    ) = ScreeningPolicy.Input(
        number, incoming, isContact, mode, screenContacts, lineVerified, snoozedUntil, now, "+918047491899",
        verifyUntil, alwaysRing, alwaysScreen, activeSims, configuredSims, ringVerifiedBusiness, ringRepeatCallers, lastSent,
    )

    // TRAI's verified business numbers: banks, insurers, government (1600) and service calls (1601).
    @Test fun verifiedBanksAndGovernmentRing() = assertEquals(RING, ScreeningPolicy.decide(input(number = "+911600123456")))
    @Test fun verifiedServiceCallsRing() = assertEquals(RING, ScreeningPolicy.decide(input(number = "+911601234567")))
    @Test fun verifiedBusinessCanGoToAssistantIfChosen() =
        assertEquals(SEND_TO_ASSISTANT, ScreeningPolicy.decide(input(number = "+911600123456", ringVerifiedBusiness = false)))
    @Test fun promotionalSeriesIsTreatedLikeAnyUnknownCaller() =
        assertEquals(SEND_TO_ASSISTANT, ScreeningPolicy.decide(input(number = "+911400123456")))

    // Someone urgent calls again: the second call within 3 minutes rings.
    @Test fun repeatCallerRings() = assertEquals(RING, ScreeningPolicy.decide(input(lastSent = now - 60_000)))
    @Test fun repeatAfterWindowGoesToAssistant() =
        assertEquals(SEND_TO_ASSISTANT, ScreeningPolicy.decide(input(lastSent = now - ScreeningPolicy.REPEAT_WINDOW_MILLIS - 1)))
    @Test fun repeatCallerRuleCanBeTurnedOff() =
        assertEquals(SEND_TO_ASSISTANT, ScreeningPolicy.decide(input(lastSent = now - 60_000, ringRepeatCallers = false)))
    @Test fun alwaysScreenBeatsRepeatAndVerified() {
        assertEquals(SEND_TO_ASSISTANT, ScreeningPolicy.decide(input(lastSent = now - 1_000, alwaysScreen = setOf("+917000000001"))))
        assertEquals(SEND_TO_ASSISTANT, ScreeningPolicy.decide(input(number = "+911600123456", alwaysScreen = setOf("+911600123456"))))
    }

    @Test fun unknownCallerGoesToAssistant() = assertEquals(SEND_TO_ASSISTANT, ScreeningPolicy.decide(input()))
    @Test fun hiddenNumberGoesToAssistant() = assertEquals(SEND_TO_ASSISTANT, ScreeningPolicy.decide(input(number = null)))
    @Test fun outgoingCallsAreNeverTouched() = assertEquals(RING, ScreeningPolicy.decide(input(incoming = false)))
    @Test fun contactsRingByDefault() = assertEquals(RING, ScreeningPolicy.decide(input(isContact = true)))
    @Test fun contactsScreenedWhenAsked() = assertEquals(SEND_TO_ASSISTANT, ScreeningPolicy.decide(input(isContact = true, screenContacts = true)))
    @Test fun nothingDeclinedBeforeForwardingIsVerified() = assertEquals(RING, ScreeningPolicy.decide(input(lineVerified = false)))
    @Test fun offModeRings() = assertEquals(RING, ScreeningPolicy.decide(input(mode = "off")))
    @Test fun ringFirstRings() = assertEquals(RING, ScreeningPolicy.decide(input(mode = "ring_first")))
    @Test fun snoozeRings() = assertEquals(RING, ScreeningPolicy.decide(input(snoozedUntil = now + 60_000)))
    @Test fun expiredSnoozeScreens() = assertEquals(SEND_TO_ASSISTANT, ScreeningPolicy.decide(input(snoozedUntil = now - 1)))
    @Test fun alwaysRingWins() = assertEquals(RING, ScreeningPolicy.decide(input(alwaysRing = setOf("+917000000001"))))
    @Test fun alwaysScreenBeatsContact() =
        assertEquals(SEND_TO_ASSISTANT, ScreeningPolicy.decide(input(isContact = true, alwaysScreen = setOf("+917000000001"))))

    @Test fun dualSimNeedsBothSimsSetUp() {
        assertEquals(RING, ScreeningPolicy.decide(input(activeSims = 2, configuredSims = 1)))
        assertEquals(SEND_TO_ASSISTANT, ScreeningPolicy.decide(input(activeSims = 2, configuredSims = 2)))
    }

    @Test fun takeOverTransferFromAssistantAlwaysRings() =
        assertEquals(RING, ScreeningPolicy.decide(input(number = "+918047491899", mode = "assistant_first")))

    @Test fun verificationCallIsDeclinedEvenBeforeVerified() =
        assertEquals(SEND_TO_ASSISTANT, ScreeningPolicy.decide(input(number = "+918047491899", lineVerified = false, verifyUntil = now + 60_000)))
}
