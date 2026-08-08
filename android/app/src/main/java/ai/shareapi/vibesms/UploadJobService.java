package ai.shareapi.vibesms;

import android.app.job.JobParameters;
import android.app.job.JobService;

import java.io.IOException;
import java.time.Instant;
import java.util.List;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

public final class UploadJobService extends JobService {
    private final ExecutorService executor = Executors.newSingleThreadExecutor();

    @Override
    public boolean onStartJob(JobParameters parameters) {
        executor.execute(() -> {
            boolean retry = runJob(parameters.getJobId());
            jobFinished(parameters, retry);
        });
        return true;
    }

    @Override
    public boolean onStopJob(JobParameters parameters) {
        return true;
    }

    @Override
    public void onDestroy() {
        executor.shutdownNow();
        super.onDestroy();
    }

    private boolean runJob(int jobId) {
        String token = TerminalConfig.deviceToken(this);
        if (token.isBlank()) {
            return false;
        }
        boolean retry = false;
        if (jobId == UploadScheduler.HEARTBEAT_JOB_ID) {
            try {
                ApiClient.upload(
                        "/api/v1/devices/heartbeat",
                        EventPayloads.heartbeat(this).toString(),
                        token);
                TerminalConfig.recordUpload(this, "心跳成功 · " + Instant.now());
            } catch (IOException error) {
                TerminalConfig.recordUpload(this, "心跳失败 · " + safe(error.getMessage()));
                retry = true;
            }
        }

        QueueDatabase database = new QueueDatabase(this);
        List<QueueDatabase.Item> pending = database.pending(50);
        for (QueueDatabase.Item item : pending) {
            try {
                ApiClient.upload(item.path, item.payload, token);
                database.markSent(item.id);
                TerminalConfig.recordUpload(this, "事件上传成功 · " + Instant.now());
            } catch (IOException error) {
                database.markFailed(item, safe(error.getMessage()));
                TerminalConfig.recordUpload(this, "上传失败 · " + safe(error.getMessage()));
                retry = true;
                break;
            }
        }
        if (database.count() > 0) {
            retry = true;
        }
        return retry;
    }

    private static String safe(String value) {
        if (value == null || value.isBlank()) {
            return "network error";
        }
        return value.length() > 160 ? value.substring(0, 160) : value;
    }
}
