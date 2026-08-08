package ai.shareapi.vibesms;

import android.content.Context;
import android.content.Intent;
import android.telephony.SubscriptionInfo;
import android.telephony.SubscriptionManager;

import java.util.ArrayList;
import java.util.List;

final class SimResolver {
    private static final String[] SUBSCRIPTION_EXTRAS = {
            "subscription", "android.telephony.extra.SUBSCRIPTION_INDEX", "subscription_id"
    };
    private static final String[] SLOT_EXTRAS = {
            "slot", "phone", "simSlot", "android.telephony.extra.SLOT_INDEX"
    };

    private SimResolver() {}

    static final class Option {
        final int simSlot;
        final int subscriptionId;
        final String carrier;
        final String label;

        Option(int simSlot, int subscriptionId, String carrier, String label) {
            this.simSlot = simSlot;
            this.subscriptionId = subscriptionId;
            this.carrier = carrier;
            this.label = label;
        }

        @Override
        public String toString() {
            return label;
        }
    }

    static int subscriptionId(Intent intent) {
        for (String name : SUBSCRIPTION_EXTRAS) {
            int value = intent.getIntExtra(name, SubscriptionManager.INVALID_SUBSCRIPTION_ID);
            if (SubscriptionManager.isValidSubscriptionId(value)) {
                return value;
            }
        }
        return SubscriptionManager.INVALID_SUBSCRIPTION_ID;
    }

    static int resolveSlot(Context context, Intent intent) {
        int subscriptionId = subscriptionId(intent);
        if (SubscriptionManager.isValidSubscriptionId(subscriptionId)) {
            int zeroBasedSlot = SubscriptionManager.getSlotIndex(subscriptionId);
            if (zeroBasedSlot >= 0 && zeroBasedSlot <= 1) {
                return zeroBasedSlot + 1;
            }
        }
        for (String name : SLOT_EXTRAS) {
            if (!intent.hasExtra(name)) {
                continue;
            }
            int value = intent.getIntExtra(name, -1);
            if (value == 0 || value == 1) {
                return value + 1;
            }
        }
        return TerminalConfig.onlyBoundSlot(context);
    }

    static List<Option> activeOptions(Context context) {
        List<Option> result = new ArrayList<>();
        SubscriptionManager manager = context.getSystemService(SubscriptionManager.class);
        if (manager != null) {
            try {
                List<SubscriptionInfo> subscriptions = manager.getActiveSubscriptionInfoList();
                if (subscriptions != null) {
                    for (SubscriptionInfo info : subscriptions) {
                        int slot = info.getSimSlotIndex() + 1;
                        if (slot != 1 && slot != 2) {
                            continue;
                        }
                        CharSequence carrier = info.getCarrierName();
                        CharSequence display = info.getDisplayName();
                        String displayName = display == null ? "" : display.toString();
                        String name = carrier == null || carrier.toString().isBlank()
                                ? displayName : carrier.toString();
                        result.add(new Option(
                                slot,
                                info.getSubscriptionId(),
                                name,
                                "SIM " + slot + (name.isBlank() ? "" : " · " + name)));
                    }
                }
            } catch (SecurityException ignored) {
                // The permission panel remains visible until the user grants access.
            }
        }
        if (result.isEmpty()) {
            result.add(new Option(1, SubscriptionManager.INVALID_SUBSCRIPTION_ID, "", "SIM 1"));
            result.add(new Option(2, SubscriptionManager.INVALID_SUBSCRIPTION_ID, "", "SIM 2"));
        }
        return result;
    }
}
