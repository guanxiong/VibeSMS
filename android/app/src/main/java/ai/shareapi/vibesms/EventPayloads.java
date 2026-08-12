package ai.shareapi.vibesms;

import android.content.Context;
import android.content.Intent;
import android.net.ConnectivityManager;
import android.net.Network;
import android.net.NetworkCapabilities;
import android.os.BatteryManager;
import android.telephony.PhoneNumberUtils;
import android.telephony.SubscriptionManager;
import android.telephony.TelephonyManager;

import org.json.JSONException;
import org.json.JSONObject;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.time.Instant;
import java.util.Locale;

final class EventPayloads {
    private EventPayloads() {}

    static JSONObject sms(
            Context context,
            String sender,
            String content,
            long receivedAt,
            int simSlot,
            int subscriptionId) {
        return event(
                context,
                "sms",
                sender,
                content,
                receivedAt,
                simSlot,
                subscriptionId,
                "");
    }

    static JSONObject call(
            Context context,
            String sender,
            String callType,
            long receivedAt,
            int simSlot,
            int subscriptionId) {
        return event(
                context,
                "call",
                sender,
                callType,
                receivedAt,
                simSlot,
                subscriptionId,
                callType);
    }

    static JSONObject heartbeat(Context context) {
        JSONObject payload = new JSONObject();
        try {
            payload.put("device_id", TerminalConfig.deviceId(context));
            payload.put("app_version", BuildConfig.VERSION_NAME);
            payload.put("battery", battery(context));
            payload.put("network", network(context));
            payload.put("sent_at", Instant.now().toString());
        } catch (JSONException error) {
            throw new IllegalStateException("cannot create heartbeat", error);
        }
        return payload;
    }

    private static JSONObject event(
            Context context,
            String type,
            String sender,
            String content,
            long receivedAt,
            int simSlot,
            int subscriptionId,
            String callType) {
        String normalizedSender = normalizeSender(context, sender, subscriptionId);
        String stable = type + "|" + normalizedSender + "|" + content + "|"
                + receivedAt + "|" + simSlot + "|" + subscriptionId;
        JSONObject payload = new JSONObject();
        try {
            payload.put("event_id", sha256(stable));
            payload.put("event_type", type);
            payload.put("device_id", TerminalConfig.deviceId(context));
            payload.put("sender", normalizedSender);
            payload.put("content", content == null ? "" : content);
            payload.put("received_at", Instant.ofEpochMilli(receivedAt).toString());
            payload.put("sim_slot", simSlot);
            if (subscriptionId >= 0) {
                payload.put("sub_id", String.valueOf(subscriptionId));
            }
            if (!callType.isBlank()) {
                payload.put("call_type", callType);
            }
            payload.put("app_version", BuildConfig.VERSION_NAME);
            payload.put("battery", battery(context));
            payload.put("network", network(context));
        } catch (JSONException error) {
            throw new IllegalStateException("cannot create event", error);
        }
        return payload;
    }

    private static String normalizeSender(
            Context context, String sender, int subscriptionId) {
        String value = sender == null ? "" : sender.trim();
        if (value.isBlank() || "unknown".equalsIgnoreCase(value)) {
            return "unknown";
        }
        TelephonyManager manager = context.getSystemService(TelephonyManager.class);
        if (manager == null) {
            return value;
        }
        String countryIso;
        try {
            if (SubscriptionManager.isValidSubscriptionId(subscriptionId)) {
                manager = manager.createForSubscriptionId(subscriptionId);
            }
            countryIso = manager.getNetworkCountryIso();
            if (countryIso == null || countryIso.isBlank()) {
                countryIso = manager.getSimCountryIso();
            }
        } catch (RuntimeException ignored) {
            return value;
        }
        if (countryIso == null || countryIso.isBlank()) {
            return value;
        }
        String e164 = PhoneNumberUtils.formatNumberToE164(
                value, countryIso.toUpperCase(Locale.ROOT));
        return e164 == null || e164.isBlank() ? value : e164;
    }

    static String network(Context context) {
        ConnectivityManager manager = context.getSystemService(ConnectivityManager.class);
        if (manager == null) {
            return "UNKNOWN";
        }
        Network network = manager.getActiveNetwork();
        NetworkCapabilities capabilities = network == null
                ? null : manager.getNetworkCapabilities(network);
        if (capabilities == null) {
            return "OFFLINE";
        }
        if (capabilities.hasTransport(NetworkCapabilities.TRANSPORT_WIFI)) {
            return "WIFI";
        }
        if (capabilities.hasTransport(NetworkCapabilities.TRANSPORT_CELLULAR)) {
            return "CELLULAR";
        }
        if (capabilities.hasTransport(NetworkCapabilities.TRANSPORT_ETHERNET)) {
            return "ETHERNET";
        }
        return "OTHER";
    }

    private static String battery(Context context) {
        BatteryManager manager = context.getSystemService(BatteryManager.class);
        int percent = manager == null
                ? -1 : manager.getIntProperty(BatteryManager.BATTERY_PROPERTY_CAPACITY);
        return percent < 0 ? "unknown" : String.format(Locale.ROOT, "%d%%", percent);
    }

    private static String sha256(String value) {
        try {
            byte[] digest = MessageDigest.getInstance("SHA-256")
                    .digest(value.getBytes(StandardCharsets.UTF_8));
            StringBuilder builder = new StringBuilder(digest.length * 2);
            for (byte item : digest) {
                builder.append(String.format(Locale.ROOT, "%02x", item & 0xff));
            }
            return builder.toString();
        } catch (Exception error) {
            throw new IllegalStateException("SHA-256 unavailable", error);
        }
    }
}
