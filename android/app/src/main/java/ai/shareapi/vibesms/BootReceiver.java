package ai.shareapi.vibesms;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;

public final class BootReceiver extends BroadcastReceiver {
    @Override
    public void onReceive(Context context, Intent intent) {
        if (TerminalConfig.deviceToken(context).isBlank()) {
            return;
        }
        KeepAliveService.start(context);
        UploadScheduler.scheduleHeartbeat(context);
        UploadScheduler.scheduleImmediate(context);
    }
}
