package ai.shareapi.vibesms;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.app.Service;
import android.content.Context;
import android.content.Intent;
import android.os.Build;
import android.os.IBinder;
import android.util.Log;

/** User-visible foreground process anchor for vendor ROMs that freeze background apps. */
public final class KeepAliveService extends Service {
    private static final String TAG = "VibeSMS-KeepAlive";
    private static final String CHANNEL_ID = "vibesms_terminal_keepalive";
    private static final int NOTIFICATION_ID = 8604;

    static void start(Context context) {
        if (TerminalConfig.deviceToken(context).isBlank()) {
            return;
        }
        Intent service = new Intent(context, KeepAliveService.class);
        try {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                context.startForegroundService(service);
            } else {
                context.startService(service);
            }
        } catch (RuntimeException error) {
            Log.w(TAG, "Foreground service start was rejected", error);
            // The exact alarm and JobScheduler paths remain available if a newer Android
            // version temporarily rejects a background foreground-service start.
        }
    }

    @Override
    public void onCreate() {
        super.onCreate();
        Log.i(TAG, "Foreground keep-alive service created");
        NotificationManager manager = getSystemService(NotificationManager.class);
        if (manager != null && Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            NotificationChannel channel = new NotificationChannel(
                    CHANNEL_ID,
                    "终端保活",
                    NotificationManager.IMPORTANCE_LOW);
            channel.setDescription("保持 VibeSMS 在锁屏后接收短信、来电并上报终端状态");
            channel.setShowBadge(false);
            manager.createNotificationChannel(channel);
        }

        Intent openApp = new Intent(this, MainActivity.class)
                .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_CLEAR_TOP);
        PendingIntent contentIntent = PendingIntent.getActivity(
                this,
                NOTIFICATION_ID,
                openApp,
                PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);
        Notification notification = new Notification.Builder(this, CHANNEL_ID)
                .setSmallIcon(android.R.drawable.stat_notify_sync_noanim)
                .setContentTitle("VibeSMS 终端保活中")
                .setContentText("锁屏后继续接收并同步短信与来电")
                .setContentIntent(contentIntent)
                .setCategory(Notification.CATEGORY_SERVICE)
                .setOngoing(true)
                .setOnlyAlertOnce(true)
                .build();
        startForeground(NOTIFICATION_ID, notification);
        UploadScheduler.scheduleHeartbeat(this);
    }

    @Override
    public int onStartCommand(Intent intent, int flags, int startId) {
        Log.i(TAG, "Foreground keep-alive service started");
        UploadScheduler.scheduleHeartbeat(this);
        return START_STICKY;
    }

    @Override
    public void onDestroy() {
        Log.w(TAG, "Foreground keep-alive service destroyed");
        super.onDestroy();
    }

    @Override
    public IBinder onBind(Intent intent) {
        return null;
    }
}
