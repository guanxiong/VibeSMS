package ai.shareapi.vibesms;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;

import java.io.IOException;
import java.time.Instant;
import java.util.List;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/** ADB-only, one-shot terminal provisioning entry point. */
public final class ProvisionReceiver extends BroadcastReceiver {
    static final String ACTION_PROVISION = "ai.shareapi.vibesms.action.PROVISION";
    static final String EXTRA_KEY = "vibesms_key";
    static final String EXTRA_SIM_SLOT = "sim_slot";

    @Override
    public void onReceive(Context context, Intent intent) {
        if (intent == null || !ACTION_PROVISION.equals(intent.getAction())) {
            return;
        }
        String userKey = intent.getStringExtra(EXTRA_KEY);
        int simSlot = intent.getIntExtra(EXTRA_SIM_SLOT, 0);
        if (userKey == null || !userKey.startsWith("vbs_live_") || userKey.length() < 24) {
            setResultCode(2);
            setResultData("invalid VibeSMS Key");
            return;
        }
        if (simSlot != 1 && simSlot != 2) {
            setResultCode(2);
            setResultData("sim_slot must be 1 or 2");
            return;
        }

        SimResolver.Option selected = findSim(context, simSlot);
        if (selected == null) {
            setResultCode(3);
            setResultData("selected SIM is not active");
            return;
        }

        PendingResult pending = goAsync();
        ExecutorService executor = Executors.newSingleThreadExecutor();
        executor.execute(() -> {
            try {
                ApiClient.BindingResult result = ApiClient.bind(
                        userKey, TerminalConfig.deviceId(context), simSlot);
                TerminalConfig.replaceDeviceToken(context, result.deviceToken);
                TerminalConfig.addBinding(
                        context, result.phoneNumber, simSlot, selected.carrier);
                UploadScheduler.scheduleHeartbeat(context);
                try {
                    ApiClient.upload(
                            "/api/v1/devices/heartbeat",
                            EventPayloads.heartbeat(context).toString(),
                            result.deviceToken);
                    TerminalConfig.recordUpload(context, "心跳成功 · " + Instant.now());
                } catch (IOException error) {
                    UploadScheduler.enqueueHeartbeat(context);
                    throw error;
                }
                pending.setResultCode(0);
                pending.setResultData("VibeSMS terminal provisioned");
            } catch (Exception error) {
                String message = error.getMessage();
                pending.setResultCode(4);
                pending.setResultData(message == null || message.isBlank()
                        ? "provisioning failed" : message);
            } finally {
                pending.finish();
                executor.shutdown();
            }
        });
    }

    private static SimResolver.Option findSim(Context context, int simSlot) {
        List<SimResolver.Option> options = SimResolver.activeOptions(context);
        for (SimResolver.Option option : options) {
            if (option.simSlot == simSlot) {
                return option;
            }
        }
        return null;
    }
}
