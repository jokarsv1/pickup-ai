package ai.pickup.app.telephony

import android.Manifest
import android.app.role.RoleManager
import android.content.ActivityNotFoundException
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.provider.CalendarContract
import android.provider.ContactsContract
import android.telephony.PhoneNumberUtils
import android.telephony.SubscriptionManager
import android.telephony.TelephonyManager
import android.widget.Toast
import androidx.core.content.ContextCompat
import java.time.OffsetDateTime
import java.util.Locale

object PhoneUtils {

    fun hasPermission(context: Context, permission: String): Boolean =
        ContextCompat.checkSelfPermission(context, permission) == PackageManager.PERMISSION_GRANTED

    fun countryIso(context: Context): String {
        val tm = context.getSystemService(TelephonyManager::class.java)
        val iso = tm?.simCountryIso?.takeIf { it.isNotBlank() } ?: tm?.networkCountryIso?.takeIf { it.isNotBlank() } ?: "in"
        return iso.uppercase(Locale.ROOT)
    }

    /** E.164 for comparisons with what the backend stores. */
    fun toE164(context: Context, raw: String?): String? {
        if (raw.isNullOrBlank()) return null
        val cleaned = raw.trim()
        PhoneNumberUtils.formatNumberToE164(cleaned, countryIso(context))?.let { return it }
        val digits = cleaned.filter { it.isDigit() }
        return when {
            cleaned.startsWith("+") && digits.length >= 8 -> "+$digits"
            digits.length == 10 && countryIso(context) == "IN" -> "+91$digits"
            digits.length == 11 && digits.startsWith("0") && countryIso(context) == "IN" -> "+91${digits.drop(1)}"
            digits.length == 12 && digits.startsWith("91") -> "+$digits"
            else -> null
        }
    }

    fun carrierName(context: Context): String? =
        context.getSystemService(TelephonyManager::class.java)?.simOperatorName?.takeIf { it.isNotBlank() }

    /** Active SIMs; 1 when we can't read it (permission denied), which keeps screening conservative. */
    fun activeSimCount(context: Context): Int {
        if (!hasPermission(context, Manifest.permission.READ_PHONE_STATE)) return 1
        return try {
            context.getSystemService(SubscriptionManager::class.java)?.activeSubscriptionInfoCount?.coerceAtLeast(1) ?: 1
        } catch (e: SecurityException) {
            1
        }
    }

    fun isScreeningRoleHeld(context: Context): Boolean {
        val rm = context.getSystemService(RoleManager::class.java) ?: return false
        return rm.isRoleAvailable(RoleManager.ROLE_CALL_SCREENING) && rm.isRoleHeld(RoleManager.ROLE_CALL_SCREENING)
    }

    fun screeningRoleIntent(context: Context): Intent? {
        val rm = context.getSystemService(RoleManager::class.java) ?: return null
        if (!rm.isRoleAvailable(RoleManager.ROLE_CALL_SCREENING)) return null
        return rm.createRequestRoleIntent(RoleManager.ROLE_CALL_SCREENING)
    }

    /**
     * Opens the dialer with a forwarding code typed in. Android only lets the default phone app
     * dial forwarding codes by itself, so the user taps the call button once per code.
     */
    fun openDialer(context: Context, digits: String) {
        val intent = Intent(Intent.ACTION_DIAL, Uri.parse("tel:" + Uri.encode(digits))).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        try {
            context.startActivity(intent)
        } catch (e: ActivityNotFoundException) {
            Toast.makeText(context, "No phone app found", Toast.LENGTH_SHORT).show()
        }
    }

    fun lookupContactName(context: Context, number: String?): String? {
        if (number.isNullOrBlank() || !hasPermission(context, Manifest.permission.READ_CONTACTS)) return null
        val uri = Uri.withAppendedPath(ContactsContract.PhoneLookup.CONTENT_FILTER_URI, Uri.encode(number))
        return try {
            context.contentResolver.query(uri, arrayOf(ContactsContract.PhoneLookup.DISPLAY_NAME), null, null, null)?.use { cursor ->
                if (cursor.moveToFirst()) cursor.getString(0) else null
            }
        } catch (e: Exception) {
            null
        }
    }

    fun saveContactIntent(name: String, number: String): Intent =
        Intent(ContactsContract.Intents.Insert.ACTION)
            .setType(ContactsContract.RawContacts.CONTENT_TYPE)
            .putExtra(ContactsContract.Intents.Insert.NAME, name)
            .putExtra(ContactsContract.Intents.Insert.PHONE, number)
            .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)

    fun reminderIntent(title: String, dueIso: String?): Intent {
        val start = dueIso?.let { runCatching { OffsetDateTime.parse(it).toInstant().toEpochMilli() }.getOrNull() }
            ?: (System.currentTimeMillis() + 60 * 60 * 1000)
        return Intent(Intent.ACTION_INSERT)
            .setData(CalendarContract.Events.CONTENT_URI)
            .putExtra(CalendarContract.Events.TITLE, title)
            .putExtra(CalendarContract.EXTRA_EVENT_BEGIN_TIME, start)
            .putExtra(CalendarContract.EXTRA_EVENT_END_TIME, start + 15 * 60 * 1000)
            .putExtra(CalendarContract.Events.HAS_ALARM, true)
            .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
    }

    fun callIntent(number: String): Intent = Intent(Intent.ACTION_DIAL, Uri.parse("tel:" + Uri.encode(number))).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)

    fun startSafely(context: Context, intent: Intent) {
        try {
            context.startActivity(intent)
        } catch (e: ActivityNotFoundException) {
            Toast.makeText(context, "No app can do that on this phone", Toast.LENGTH_SHORT).show()
        }
    }
}
