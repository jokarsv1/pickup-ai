package ai.pickup.app.telephony

/**
 * Decides, inside Android's 5-second screening window, whether an incoming call rings or goes to
 * the assistant. Pure logic so it can be unit-tested; [PickupScreeningService] feeds it.
 *
 * Declining a call makes the carrier forward it ("forward when busy") to the assistant number.
 */
object ScreeningPolicy {

    enum class Decision { RING, SEND_TO_ASSISTANT }

    data class Input(
        val number: String?, // E.164, or null for a hidden number
        val isIncoming: Boolean,
        val isContact: Boolean,
        val mode: String, // assistant_first | ring_first | off
        val screenContacts: Boolean,
        val lineVerified: Boolean,
        val snoozedUntilMillis: Long?,
        val nowMillis: Long,
        val assistantNumber: String?,
        val verifyUntilMillis: Long,
        val alwaysRing: Set<String>,
        val alwaysScreen: Set<String>,
        val activeSims: Int,
        val configuredSims: Int,
        /** TRAI's 1600 (banks, insurers, government) and 1601 (service) numbers ring. */
        val ringVerifiedBusiness: Boolean = true,
        /** The same number calling again within [REPEAT_WINDOW_MILLIS] rings: urgent callers try twice. */
        val ringRepeatCallers: Boolean = true,
        /** When this number was last sent to the assistant, if recently. */
        val lastSentToAssistantMillis: Long? = null,
    )

    const val REPEAT_WINDOW_MILLIS = 3 * 60 * 1000L

    /** TRAI's verified business series (TCCCPR Third Amendment, 2026). */
    fun isVerifiedBusiness(number: String): Boolean = number.startsWith("+911600") || number.startsWith("+911601")

    fun decide(input: Input): Decision {
        if (!input.isIncoming) return Decision.RING
        val number = input.number

        // Our own numbers: the forwarding test call is declined on purpose (that's the test),
        // and a take-over transfer must always ring so the user can join.
        if (number != null && number == input.assistantNumber) {
            return if (input.nowMillis < input.verifyUntilMillis) Decision.SEND_TO_ASSISTANT else Decision.RING
        }
        if (number != null && number in input.alwaysRing) return Decision.RING

        // Never decline a call that the carrier can't forward: on a dual-SIM phone the screening
        // service can't tell which SIM a call came in on, so every active SIM must be set up.
        val forwardingReady = input.lineVerified && input.configuredSims >= input.activeSims.coerceAtLeast(1)
        if (!forwardingReady) return Decision.RING
        if (input.mode == "off") return Decision.RING
        val snoozed = input.snoozedUntilMillis != null && input.nowMillis < input.snoozedUntilMillis
        if (snoozed) return Decision.RING

        if (number != null && number in input.alwaysScreen) return Decision.SEND_TO_ASSISTANT
        if (number != null && input.ringVerifiedBusiness && isVerifiedBusiness(number)) return Decision.RING
        val last = input.lastSentToAssistantMillis
        if (number != null && input.ringRepeatCallers && last != null && input.nowMillis - last in 0 until REPEAT_WINDOW_MILLIS) {
            return Decision.RING
        }
        if (input.isContact && !input.screenContacts) return Decision.RING
        // "Ring me first": let it ring; the carrier's no-answer forwarding sends it on if ignored.
        if (input.mode == "ring_first") return Decision.RING
        return Decision.SEND_TO_ASSISTANT
    }
}
