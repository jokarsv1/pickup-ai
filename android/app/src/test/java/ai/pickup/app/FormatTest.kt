package ai.pickup.app

import ai.pickup.app.util.Format
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test
import java.time.Instant
import java.time.LocalDate
import java.time.ZoneId

class FormatTest {
    @Test fun indianMobiles() {
        assertEquals("+919876543210", Format.normalizeIndianMobile("98765 43210"))
        assertEquals("+919876543210", Format.normalizeIndianMobile("09876543210"))
        assertEquals("+919876543210", Format.normalizeIndianMobile("+91 98765-43210"))
        assertNull(Format.normalizeIndianMobile("12345"))
        assertNull(Format.normalizeIndianMobile("5876543210"))
    }

    @Test fun dayLabels() {
        val zone = ZoneId.of("Asia/Kolkata")
        val today = LocalDate.of(2026, 11, 17)
        assertEquals("Today", Format.dayLabel("2026-11-17T09:00:00+05:30", today, zone))
        assertEquals("Today", Format.dayLabel("2026-11-17T04:28:00.123456", today, zone)) // no zone: UTC
        assertEquals("Yesterday", Format.dayLabel("2026-11-16T23:00:00+05:30", today, zone))
        assertEquals("Sun, 15 Nov", Format.dayLabel("2026-11-15T10:00:00+05:30", today, zone))
    }

    @Test fun durationsAndCountdowns() {
        assertEquals("1m 5s", Format.duration(65))
        assertEquals("", Format.duration(null))
        assertEquals("3 days", Format.until("2026-11-20T12:00:00Z", Instant.parse("2026-11-17T11:00:00Z")))
        assertNull(Format.until("2026-11-10T12:00:00Z", Instant.parse("2026-11-17T11:00:00Z")))
    }

    @Test fun firstNames() {
        assertEquals("Asha", Format.firstName("Asha Rao"))
        assertEquals("", Format.firstName(null))
    }
}
