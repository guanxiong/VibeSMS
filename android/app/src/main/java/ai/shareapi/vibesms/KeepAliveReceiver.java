package ai.shareapi.vibesms;

import android.app.AlarmManager;
import android.app.PendingIntent;
import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.os.PowerManager;
import android.os.SystemClock;

import java.io.IOException;
import java.time.Instant;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/** Doze-aware heartbeat fallback with a short, bounded wake lock. */
public final class KeepAliveReceiver extends BroadcastReceiver {
    private static final String ACTION_HEARTBEAT =
            "ai.shareapi.vibesms.action.KEEPALIVE_HEARTBEAT";
    private static final int REQUEST_CODE = 8603;
    private static final long INTERVAL_MS = 9L * 60L * 1000L;
    private static final long WAKE_LOCK_TIMEOUT_MS = 45_000L;

    static void schedule(Context context) {
        if (TerminalConfig.deviceToken(context).isBlank()) {
            return;
        }
        AlarmManager manager = context.getSystemService(AlarmManager.class);
        if (manager == null) {
            return;
        }
        Intent intent = new Intent(context, KeepAliveReceiver.class)
                .setAction(ACTION_HEARTBEAT);
        PendingIntent heartbeat = PendingIntent.getBroadcast(
                context,
                REQUEST_CODE,
                intent,
                PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);
        manager.setAndAllowWhileIdle(
                AlarmManager.ELAPSED_REALTIME_WAKEUP,
                SystemClock.elapsedRealtime() + INTERVAL_MS,
                heartbeat);
    }

    @Override
    public void onReceive(Context context, Intent intent) {
        if (intent == null || !ACTION_HEARTBEAT.equals(intent.getAction())) {
            return;
        }
        schedule(context);
        String token = TerminalConfig.deviceToken(context);
        if (token.isBlank()) {
            return;
        }

        PendingResult pending = goAsync();
        PowerManager power = context.getSystemService(PowerManager.class);
        PowerManager.WakeLock wakeLock = power == null ? null : power.newWakeLock(
                PowerManager.PARTIAL_WAKE_LOCK, "VibeSMS:keepalive");
        if (wakeLock != null) {
            wakeLock.setReferenceCounted(false);
            wakeLock.acquire(WAKE_LOCK_TIMEOUT_MS);
        }

        ExecutorService executor = Executors.newSingleThreadExecutor();
        executor.execute(() -> {
            try {
                ApiClient.upload(
                        "/api/v1/devices/heartbeat",
                        EventPayloads.heartbeat(context).toString(),
                        token);
                TerminalConfig.recordUpload(context, "锁屏心跳成功 · " + Instant.now());
            } catch (IOException error) {
                String message = error.getMessage();
                TerminalConfig.recordUpload(
                        context,
                        "锁屏心跳失败 · "
                                + (message == null || message.isBlank() ? "network error" : message));
            } finally {
                if (wakeLock != null && wakeLock.isHeld()) {
                    wakeLock.release();
                }
                pending.finish();
                executor.shutdown();
            }
        });
    }
}
