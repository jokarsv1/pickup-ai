package ai.pickup.app.telephony

import ai.pickup.app.PickupApp
import ai.pickup.app.data.AppJson
import ai.pickup.app.data.ScreeningPolicyDto
import android.telecom.Call
import android.telecom.CallScreeningService
import android.telecom.CallScreeningService.CallResponse
import android.util.Log
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.launch
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.withTimeoutOrNull
import java.time.OffsetDateTime

/**
 * Sees every incoming call before it rings (contacts too, because we hold READ_CONTACTS).
 * Unknown callers are declined, which makes the carrier forward them to the user's assistant.
 * Android requires an answer within 5 seconds, so everything here is local and fast.
 */
class PickupScreeningService : CallScreeningService() {

    override fun onScreenCall(callDetails: Call.Details) {
        val app = application as PickupApp
        val incoming = callDetails.callDirection == Call.Details.DIRECTION_INCOMING
        if (!incoming) {
            respondToCall(callDetails, CallResponse.Builder().build())
            return
        }
        val number = PhoneUtils.toE164(this, callDetails.handle?.schemeSpecificPart)
        val contactName = PhoneUtils.lookupContactName(this, number) // on the phone only; never uploaded
        val decision = try {
            decide(app, number, contactName != null)
        } catch (e: Exception) {
            Log.w(TAG, "Screening failed, letting the call ring", e)
            ScreeningPolicy.Decision.RING
        }
        val sendToAssistant = decision == ScreeningPolicy.Decision.SEND_TO_ASSISTANT
        val response = CallResponse.Builder()
            .setDisallowCall(sendToAssistant)
            .setRejectCall(sendToAssistant)
            .setSkipNotification(sendToAssistant)
            .build()
        respondToCall(callDetails, response)

        if (sendToAssistant && number != null) {
            RecentScreens.markSent(this, number)
            // Tell the backend who really called (the carrier may show our number instead), so it can
            // also tell the user if the carrier never delivers the call. A saved contact's name goes
            // with this one call only.
            app.graph.scope.launch { runCatching { app.graph.repository.sendHint(number, "declined", contactName) } }
        }
    }

    private fun decide(app: PickupApp, number: String?, isContact: Boolean): ScreeningPolicy.Decision {
        val store = app.graph.store
        val snapshot = runBlocking { withTimeoutOrNull(1500) { Triple(store.policyJson.first(), store.verifyUntil(), store.sims()) } }
            ?: return ScreeningPolicy.Decision.RING
        val (policyJson, verifyUntil, configuredSims) = snapshot
        val policy = policyJson?.let { runCatching { AppJson.decodeFromString(ScreeningPolicyDto.serializer(), it) }.getOrNull() }
            ?: return ScreeningPolicy.Decision.RING
        return ScreeningPolicy.decide(
            ScreeningPolicy.Input(
                number = number,
                isIncoming = true,
                isContact = isContact,
                mode = policy.screeningMode,
                screenContacts = policy.screenContacts,
                lineVerified = policy.lineStatus == "verified",
                snoozedUntilMillis = policy.snoozeUntil?.let { runCatching { OffsetDateTime.parse(it).toInstant().toEpochMilli() }.getOrNull() },
                nowMillis = System.currentTimeMillis(),
                assistantNumber = policy.assistantNumber,
                verifyUntilMillis = verifyUntil,
                alwaysRing = policy.alwaysRing.toSet(),
                alwaysScreen = policy.alwaysScreen.toSet(),
                activeSims = PhoneUtils.activeSimCount(this),
                configuredSims = configuredSims,
                ringVerifiedBusiness = policy.ringVerifiedBusiness,
                ringRepeatCallers = policy.ringRepeatCallers,
                lastSentToAssistantMillis = number?.let { RecentScreens.lastSent(this, it) },
            )
        )
    }

    companion object {
        private const val TAG = "PickupScreening"
    }
}
