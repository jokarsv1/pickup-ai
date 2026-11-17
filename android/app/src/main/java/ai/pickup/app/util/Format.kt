package ai.pickup.app.util

import java.time.Duration
import java.time.Instant
import java.time.LocalDate
import java.time.LocalDateTime
import java.time.OffsetDateTime
import java.time.ZoneId
import java.time.ZoneOffset
import java.time.format.DateTimeFormatter
import java.util.Locale

object Format {
    private val time = DateTimeFormatter.ofPattern("h:mm a", Locale.ENGLISH)
    private val dayMonth = DateTimeFormatter.ofPattern("EEE, d MMM", Locale.ENGLISH)
    private val full = DateTimeFormatter.ofPattern("d MMM, h:mm a", Locale.ENGLISH)

    /** Server times are UTC; a time without a zone (older servers on SQLite) is read as UTC too. */
    fun parse(iso: String?): OffsetDateTime? = iso?.let {
        runCatching { OffsetDateTime.parse(it) }.getOrNull()
            ?: runCatching { LocalDateTime.parse(it).atOffset(ZoneOffset.UTC) }.getOrNull()
    }

    fun epochMillis(iso: String?): Long? = parse(iso)?.toInstant()?.toEpochMilli()

    fun clock(iso: String?, zone: ZoneId = ZoneId.systemDefault()): String = parse(iso)?.atZoneSameInstant(zone)?.format(time) ?: ""

    fun dateTime(iso: String?, zone: ZoneId = ZoneId.systemDefault()): String = parse(iso)?.atZoneSameInstant(zone)?.format(full) ?: ""

    /** "Today", "Yesterday" or "Mon, 16 Nov" for list section headers. */
    fun dayLabel(iso: String?, today: LocalDate = LocalDate.now(), zone: ZoneId = ZoneId.systemDefault()): String {
        val date = parse(iso)?.atZoneSameInstant(zone)?.toLocalDate() ?: return "Earlier"
        return when (date) {
            today -> "Today"
            today.minusDays(1) -> "Yesterday"
            else -> date.format(dayMonth)
        }
    }

    fun duration(seconds: Int?): String {
        if (seconds == null || seconds <= 0) return ""
        val m = seconds / 60
        val s = seconds % 60
        return if (m > 0) "${m}m ${s}s" else "${s}s"
    }

    /** "in 3 days", "in 5 hours" for trial and snooze countdowns. */
    fun until(iso: String?, now: Instant = Instant.now()): String? {
        val target = parse(iso)?.toInstant() ?: return null
        val d = Duration.between(now, target)
        if (d.isNegative) return null
        return when {
            d.toDays() >= 1 -> "${d.toDays()} day${if (d.toDays() == 1L) "" else "s"}"
            d.toHours() >= 1 -> "${d.toHours()} hour${if (d.toHours() == 1L) "" else "s"}"
            else -> "${d.toMinutes().coerceAtLeast(1)} min"
        }
    }

    fun greeting(hour: Int): String = when (hour) {
        in 5..11 -> "Good morning"
        in 12..16 -> "Good afternoon"
        else -> "Good evening"
    }

    fun firstName(name: String?): String = name?.trim()?.split(" ")?.firstOrNull()?.takeIf { it.isNotBlank() } ?: ""

    /** Indian mobile numbers typed without the country code. */
    fun normalizeIndianMobile(input: String): String? {
        val digits = input.filter { it.isDigit() }
        return when {
            digits.length == 10 && digits.first() in "6789" -> "+91$digits"
            digits.length == 12 && digits.startsWith("91") && digits[2] in "6789" -> "+$digits"
            digits.length == 11 && digits.startsWith("0") && digits[1] in "6789" -> "+91${digits.drop(1)}"
            else -> null
        }
    }
}
