package in.gharsajag.caregiver

import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Intent
import android.os.Build
import androidx.core.app.NotificationCompat
import com.google.firebase.messaging.FirebaseMessagingService
import com.google.firebase.messaging.RemoteMessage

/** Notification is an invitation, NOT proof that a caregiver heard/answered. */
class CaregiverMessagingService : FirebaseMessagingService() {
    override fun onNewToken(token: String) {
        if (BuildConfig.FCM_ENABLED) DeviceRegistration.register(applicationContext, token)
    }

    override fun onMessageReceived(message: RemoteMessage) {
        if (!BuildConfig.FCM_ENABLED) return
        if (message.data["type"] != "voice_invite") return
        val id = message.data["call_id"] ?: return
        if (!Regex("^c_[0-9a-f]{32}$").matches(id)) return
        val manager = getSystemService(NotificationManager::class.java)
        val channelId = "parivar_voice_invites"
        if (Build.VERSION.SDK_INT >= 26) manager.createNotificationChannel(
            NotificationChannel(channelId, "Caregiver voice calls", NotificationManager.IMPORTANCE_HIGH))
        val open = Intent(this, CallActivity::class.java).putExtra("call_id", id)
        val pending = PendingIntent.getActivity(this, id.hashCode(), open, PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT)
        val notification = NotificationCompat.Builder(this, channelId)
            .setSmallIcon(android.R.drawable.ic_menu_call)
            .setContentTitle("Parivar Saathi caregiver call")
            .setContentText("A home is requesting a voice connection. Open to verify and answer.")
            .setCategory(NotificationCompat.CATEGORY_CALL)
            .setPriority(NotificationCompat.PRIORITY_HIGH)
            .setAutoCancel(true)
            .setContentIntent(pending)
            .addAction(android.R.drawable.ic_menu_call, "Open call", pending)
            .build()
        manager.notify(id, 1, notification)
    }
}
