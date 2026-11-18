package ai.pickup.app.telephony

import android.content.Context

/**
 * Remembers, on the phone, which numbers were sent to the assistant in the last few minutes, so a
 * second call from the same number rings (someone urgent usually tries again). Kept small and
 * read synchronously: screening has to answer within Android's 5-second window.
 */
object RecentScreens {
    private const val PREFS = "recent_screens"
    private const val KEEP_MILLIS = 10 * 60 * 1000L

    fun lastSent(context: Context, number: String): Long? {
        val at = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).getLong(number, -1L)
        return at.takeIf { it > 0 && System.currentTimeMillis() - it < KEEP_MILLIS }
    }

    fun markSent(context: Context, number: String, now: Long = System.currentTimeMillis()) {
        val prefs = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
        val editor = prefs.edit()
        prefs.all.forEach { (key, value) -> if (value !is Long || now - value > KEEP_MILLIS) editor.remove(key) }
        editor.putLong(number, now).apply()
    }
}
