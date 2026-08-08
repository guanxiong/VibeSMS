package ai.shareapi.vibesms;

import android.app.job.JobInfo;
import android.app.job.JobScheduler;
import android.content.ComponentName;
import android.content.Context;

import org.json.JSONObject;

final class UploadScheduler {
    static final int IMMEDIATE_JOB_ID = 8601;
    static final int HEARTBEAT_JOB_ID = 8602;
    private static final long HEARTBEAT_INTERVAL_MS = 15L * 60L * 1000L;

    private UploadScheduler() {}

    static void enqueueEvent(Context context, JSONObject payload) {
        String eventId = payload.optString("event_id", "");
        if (eventId.isBlank()) {
            throw new IllegalArgumentException("event_id is required");
        }
        new QueueDatabase(context).enqueue(
                eventId, "/api/v1/events", payload.toString());
        scheduleImmediate(context);
    }

    static void enqueueHeartbeat(Context context) {
        long bucket = System.currentTimeMillis() / 60_000L;
        new QueueDatabase(context).enqueue(
                "heartbeat-" + bucket,
                "/api/v1/devices/heartbeat",
                EventPayloads.heartbeat(context).toString());
        scheduleImmediate(context);
    }

    static void scheduleImmediate(Context context) {
        JobScheduler scheduler = context.getSystemService(JobScheduler.class);
        if (scheduler == null) {
            return;
        }
        JobInfo job = new JobInfo.Builder(
                IMMEDIATE_JOB_ID,
                new ComponentName(context, UploadJobService.class))
                .setRequiredNetworkType(JobInfo.NETWORK_TYPE_ANY)
                .setPersisted(true)
                .setMinimumLatency(0)
                .setBackoffCriteria(10_000L, JobInfo.BACKOFF_POLICY_EXPONENTIAL)
                .build();
        scheduler.schedule(job);
    }

    static void scheduleHeartbeat(Context context) {
        JobScheduler scheduler = context.getSystemService(JobScheduler.class);
        if (scheduler == null) {
            return;
        }
        JobInfo job = new JobInfo.Builder(
                HEARTBEAT_JOB_ID,
                new ComponentName(context, UploadJobService.class))
                .setRequiredNetworkType(JobInfo.NETWORK_TYPE_ANY)
                .setPersisted(true)
                .setPeriodic(HEARTBEAT_INTERVAL_MS)
                .build();
        scheduler.schedule(job);
    }
}
