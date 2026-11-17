package ai.pickup.app.notify

import ai.pickup.app.MainActivity
import ai.pickup.app.R
import android.Manifest
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.net.Uri
import androidx.core.app.NotificationCompat
import androidx.core.app.NotificationManagerCompat
import androidx.core.app.RemoteInput
import ai.pickup.app.telephony.PhoneUtils

/**
 * One notification per call, updated in place: live transcript and smart replies while the
 * assistant talks, then the summary with next steps. On Android 16 it is promoted to a Live Update
 * (status-bar chip, top of the shade).
 */
object CallNotifications {
    const val CH_LIVE = "live_calls"
    const val CH_SUMMARY = "call_summaries"
    const val CH_SETUP = "setup"
    const val KEY_REPLY = "reply_text"
    const val EXTRA_CALL_ID = "call_id"
    const val EXTRA_OPEN = "open"

    fun createChannels(context: Context) {
        val nm = context.getSystemService(NotificationManager::class.java) ?: return
        nm.createNotificationChannels(
            listOf(
                NotificationChannel(CH_LIVE, context.getString(R.string.channel_live), NotificationManager.IMPORTANCE_HIGH).apply {
                    description = context.getString(R.string.channel_live_desc)
                },
                NotificationChannel(CH_SUMMARY, context.getString(R.string.channel_summary), NotificationManager.IMPORTANCE_DEFAULT).apply {
                    description = context.getString(R.string.channel_summary_desc)
                },
                NotificationChannel(CH_SETUP, context.getString(R.string.channel_setup), NotificationManager.IMPORTANCE_LOW).apply {
                    description = context.getString(R.string.channel_setup_desc)
                },
            )
        )
    }

    fun notificationId(callId: String): Int = callId.hashCode()

    private fun canPost(context: Context): Boolean =
        PhoneUtils.hasPermission(context, Manifest.permission.POST_NOTIFICATIONS) &&
            NotificationManagerCompat.from(context).areNotificationsEnabled()

    private fun openIntent(context: Context, callId: String?, screen: String): PendingIntent {
        val intent = Intent(context, MainActivity::class.java)
            .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_SINGLE_TOP)
            .putExtra(EXTRA_OPEN, screen)
            .putExtra(EXTRA_CALL_ID, callId)
        val requestCode = (callId ?: screen).hashCode() + screen.hashCode()
        return PendingIntent.getActivity(context, requestCode, intent, PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE)
    }

    private fun actionIntent(context: Context, action: String, callId: String, mutable: Boolean = false): PendingIntent {
        val intent = Intent(context, NotificationActionReceiver::class.java).setAction(action).putExtra(EXTRA_CALL_ID, callId)
        val flags = PendingIntent.FLAG_UPDATE_CURRENT or (if (mutable) PendingIntent.FLAG_MUTABLE else PendingIntent.FLAG_IMMUTABLE)
        return PendingIntent.getBroadcast(context, (action + callId).hashCode(), intent, flags)
    }

    data class Line(val speaker: String, val text: String)

    fun showLive(
        context: Context,
        callId: String,
        title: String,
        reason: String?,
        lines: List<Line>,
        replies: List<String>,
        liveControls: Boolean = true,
        statusText: String? = null,
    ) {
        if (!canPost(context)) return
        val transcript = lines.takeLast(4).joinToString("\n") { line ->
            val who = when (line.speaker) {
                "caller" -> "Caller"
                "owner" -> "You"
                else -> "Pickup"
            }
            "$who: ${line.text}"
        }
        val subtitle = statusText ?: reason?.takeIf { it.isNotBlank() } ?: lines.lastOrNull()?.text ?: "Your assistant is talking to them"
        val builder = NotificationCompat.Builder(context, CH_LIVE)
            .setSmallIcon(R.drawable.ic_stat_pickup)
            .setContentTitle(title)
            .setContentText(subtitle)
            .setStyle(NotificationCompat.BigTextStyle().bigText(if (transcript.isBlank()) subtitle else "$subtitle\n\n$transcript"))
            .setCategory(NotificationCompat.CATEGORY_STATUS)
            .setOngoing(true)
            .setOnlyAlertOnce(true)
            .setShowWhen(true)
            .setUsesChronometer(true)
            .setRequestPromotedOngoing(true)
            .setShortCriticalText("Live")
            .setContentIntent(openIntent(context, callId, "live"))
        if (liveControls) {
            val remoteInput = RemoteInput.Builder(KEY_REPLY)
                .setLabel("Tell your assistant what to say")
                .setChoices(replies.take(3).toTypedArray())
                .build()
            builder.addAction(
                NotificationCompat.Action.Builder(R.drawable.ic_stat_pickup, "Reply", actionIntent(context, NotificationActionReceiver.ACTION_REPLY, callId, mutable = true))
                    .addRemoteInput(remoteInput)
                    .setAllowGeneratedReplies(true)
                    .build()
            )
            builder.addAction(R.drawable.ic_stat_pickup, "Join call", actionIntent(context, NotificationActionReceiver.ACTION_JOIN, callId))
        }
        builder.addAction(R.drawable.ic_stat_pickup, "End", actionIntent(context, NotificationActionReceiver.ACTION_END, callId))
        notify(context, notificationId(callId), builder)
    }

    fun showSummary(context: Context, callId: String, title: String, summary: String, callbackNumber: String?, isSpam: Boolean) {
        if (!canPost(context)) return
        val builder = NotificationCompat.Builder(context, CH_SUMMARY)
            .setSmallIcon(R.drawable.ic_stat_pickup)
            .setContentTitle(if (isSpam) "$title · likely spam" else title)
            .setContentText(summary)
            .setStyle(NotificationCompat.BigTextStyle().bigText(summary))
            .setCategory(NotificationCompat.CATEGORY_MESSAGE)
            .setAutoCancel(true)
            .setContentIntent(openIntent(context, callId, "call"))
        if (callbackNumber != null && !isSpam) {
            val dial = Intent(Intent.ACTION_DIAL, Uri.parse("tel:" + Uri.encode(callbackNumber)))
            val pi = PendingIntent.getActivity(context, ("cb$callId").hashCode(), dial, PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT)
            builder.addAction(R.drawable.ic_stat_pickup, "Call back", pi)
        }
        notify(context, notificationId(callId), builder)
    }

    fun showSetup(context: Context, title: String, text: String) {
        if (!canPost(context)) return
        val builder = NotificationCompat.Builder(context, CH_SETUP)
            .setSmallIcon(R.drawable.ic_stat_pickup)
            .setContentTitle(title)
            .setContentText(text)
            .setAutoCancel(true)
            .setContentIntent(openIntent(context, null, "home"))
        notify(context, 4242, builder)
    }

    fun cancel(context: Context, callId: String) = NotificationManagerCompat.from(context).cancel(notificationId(callId))

    @Suppress("MissingPermission") // checked in canPost()
    private fun notify(context: Context, id: Int, builder: NotificationCompat.Builder) {
        NotificationManagerCompat.from(context).notify(id, builder.build())
    }
}
