package ai.shareapi.vibesms;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.provider.Telephony;
import android.telephony.SmsMessage;

public final class SmsReceiver extends BroadcastReceiver {
    @Override
    public void onReceive(Context context, Intent intent) {
        if (!Telephony.Sms.Intents.SMS_RECEIVED_ACTION.equals(intent.getAction())) {
            return;
        }
        SmsMessage[] messages = Telephony.Sms.Intents.getMessagesFromIntent(intent);
        if (messages == null || messages.length == 0) {
            return;
        }
        StringBuilder content = new StringBuilder();
        String sender = "unknown";
        long receivedAt = messages[0].getTimestampMillis();
        for (SmsMessage message : messages) {
            if (message == null) {
                continue;
            }
            if ("unknown".equals(sender) && message.getDisplayOriginatingAddress() != null) {
                sender = message.getDisplayOriginatingAddress();
            }
            if (message.getDisplayMessageBody() != null) {
                content.append(message.getDisplayMessageBody());
            }
        }
        if (content.length() == 0) {
            return;
        }
        int simSlot = SimResolver.resolveSlot(context, intent);
        if (simSlot == 0 || !TerminalConfig.isSlotBound(context, simSlot)) {
            return;
        }
        UploadScheduler.enqueueEvent(
                context,
                EventPayloads.sms(
                        context,
                        sender,
                        content.toString(),
                        receivedAt,
                        simSlot,
                        SimResolver.subscriptionId(intent)));
    }
}
