package ai.shareapi.vibesms;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.telephony.TelephonyManager;

public final class CallReceiver extends BroadcastReceiver {
    private static final String PREFS = "vibesms_call_state";
    private static final long DUPLICATE_WINDOW_MS = 2_000L;

    @Override
    public void onReceive(Context context, Intent intent) {
        if (!TelephonyManager.ACTION_PHONE_STATE_CHANGED.equals(intent.getAction())) {
            return;
        }
        String state = intent.getStringExtra(TelephonyManager.EXTRA_STATE);
        if (state == null || state.isBlank()) {
            return;
        }
        // With READ_PHONE_STATE and READ_CALL_LOG Android sends this broadcast twice in
        // an unspecified order. Only one copy contains EXTRA_INCOMING_NUMBER. Ignoring
        // the copy without that extra prevents it from winning duplicate suppression.
        if (!intent.hasExtra(TelephonyManager.EXTRA_INCOMING_NUMBER)) {
            return;
        }
        SharedPreferences preferences = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE);
        long now = System.currentTimeMillis();
        if (state.equals(preferences.getString("last_state", ""))
                && now - preferences.getLong("last_state_at", 0) < DUPLICATE_WINDOW_MS) {
            return;
        }

        String number = intent.getStringExtra(TelephonyManager.EXTRA_INCOMING_NUMBER);
        if (number == null || number.isBlank()) {
            number = TelephonyManager.EXTRA_STATE_RINGING.equals(state)
                    ? "unknown"
                    : preferences.getString("last_number", "unknown");
        }
        int simSlot = SimResolver.resolveSlot(context, intent);
        if (simSlot == 0) {
            simSlot = preferences.getInt("last_slot", TerminalConfig.onlyBoundSlot(context));
        }
        preferences.edit()
                .putString("last_state", state)
                .putLong("last_state_at", now)
                .putString("last_number", number)
                .putInt("last_slot", simSlot)
                .apply();

        if (simSlot == 0 || !TerminalConfig.isSlotBound(context, simSlot)) {
            return;
        }
        String callType;
        if (TelephonyManager.EXTRA_STATE_RINGING.equals(state)) {
            callType = "来电振铃";
        } else if (TelephonyManager.EXTRA_STATE_OFFHOOK.equals(state)) {
            callType = "通话中";
        } else if (TelephonyManager.EXTRA_STATE_IDLE.equals(state)) {
            callType = "通话结束";
        } else {
            callType = state;
        }
        UploadScheduler.enqueueEvent(
                context,
                EventPayloads.call(
                        context,
                        number,
                        callType,
                        now,
                        simSlot,
                        SimResolver.subscriptionId(intent)));
    }
}
