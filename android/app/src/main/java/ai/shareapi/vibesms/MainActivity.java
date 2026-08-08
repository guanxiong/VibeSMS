package ai.shareapi.vibesms;

import android.Manifest;
import android.app.Activity;
import android.content.pm.PackageManager;
import android.os.Bundle;
import android.text.InputType;
import android.view.View;
import android.widget.ArrayAdapter;
import android.widget.Button;
import android.widget.EditText;
import android.widget.Spinner;
import android.widget.TextView;

import java.util.ArrayList;
import java.util.List;
import java.util.Locale;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

public final class MainActivity extends Activity {
    private static final int PERMISSION_REQUEST = 401;
    private static final String[] REQUIRED_PERMISSIONS = {
            Manifest.permission.RECEIVE_SMS,
            Manifest.permission.READ_PHONE_STATE,
            Manifest.permission.READ_CALL_LOG
    };

    private final ExecutorService executor = Executors.newSingleThreadExecutor();
    private EditText keyInput;
    private Spinner simSpinner;
    private Button bindButton;
    private TextView bindResult;
    private TextView bindingsText;
    private TextView statusText;
    private View permissionPanel;
    private final List<SimResolver.Option> simOptions = new ArrayList<>();

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_main);

        permissionPanel = findViewById(R.id.permissionPanel);
        keyInput = findViewById(R.id.keyInput);
        keyInput.setInputType(InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_VARIATION_PASSWORD);
        simSpinner = findViewById(R.id.simSpinner);
        bindButton = findViewById(R.id.bindButton);
        bindResult = findViewById(R.id.bindResult);
        bindingsText = findViewById(R.id.bindingsText);
        statusText = findViewById(R.id.statusText);

        findViewById(R.id.permissionButton).setOnClickListener(
                view -> requestPermissions(REQUIRED_PERMISSIONS, PERMISSION_REQUEST));
        bindButton.setOnClickListener(view -> bindSelectedSim());
        findViewById(R.id.syncButton).setOnClickListener(view -> {
            if (TerminalConfig.deviceToken(this).isBlank()) {
                bindResult.setText("请先绑定至少一个号码。");
                return;
            }
            UploadScheduler.enqueueHeartbeat(this);
            UploadScheduler.scheduleHeartbeat(this);
            bindResult.setText("已加入同步队列。");
            renderStatus();
        });

        refreshPermissionsAndSims();
        if (!TerminalConfig.deviceToken(this).isBlank()) {
            UploadScheduler.scheduleHeartbeat(this);
            UploadScheduler.scheduleImmediate(this);
        }
        renderAll();
    }

    @Override
    protected void onResume() {
        super.onResume();
        renderAll();
    }

    @Override
    public void onRequestPermissionsResult(
            int requestCode, String[] permissions, int[] grantResults) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults);
        if (requestCode == PERMISSION_REQUEST) {
            refreshPermissionsAndSims();
            bindResult.setText(allPermissionsGranted()
                    ? "权限已就绪，可以绑定 SIM。"
                    : "需要短信、电话和通话记录权限才能完整接码。");
        }
    }

    @Override
    protected void onDestroy() {
        executor.shutdownNow();
        super.onDestroy();
    }

    private void refreshPermissionsAndSims() {
        boolean granted = allPermissionsGranted();
        permissionPanel.setVisibility(granted ? View.GONE : View.VISIBLE);
        bindButton.setEnabled(granted);
        simOptions.clear();
        simOptions.addAll(SimResolver.activeOptions(this));
        ArrayAdapter<SimResolver.Option> adapter = new ArrayAdapter<>(
                this, android.R.layout.simple_spinner_item, simOptions);
        adapter.setDropDownViewResource(android.R.layout.simple_spinner_dropdown_item);
        simSpinner.setAdapter(adapter);
    }

    private boolean allPermissionsGranted() {
        for (String permission : REQUIRED_PERMISSIONS) {
            if (checkSelfPermission(permission) != PackageManager.PERMISSION_GRANTED) {
                return false;
            }
        }
        return true;
    }

    private void bindSelectedSim() {
        String userKey = keyInput.getText().toString().trim();
        if (!userKey.startsWith("vbs_live_") || userKey.length() < 24) {
            bindResult.setText("请输入有效的 VibeSMS Key。");
            return;
        }
        Object selected = simSpinner.getSelectedItem();
        if (!(selected instanceof SimResolver.Option)) {
            bindResult.setText("没有可绑定的 SIM。");
            return;
        }
        SimResolver.Option option = (SimResolver.Option) selected;
        bindButton.setEnabled(false);
        bindResult.setText("正在通过 HTTPS 绑定…");
        executor.execute(() -> {
            try {
                ApiClient.BindingResult result = ApiClient.bind(
                        userKey,
                        TerminalConfig.deviceId(this),
                        option.simSlot);
                TerminalConfig.replaceDeviceToken(this, result.deviceToken);
                TerminalConfig.addBinding(this, result.phoneNumber, option.simSlot, option.carrier);
                UploadScheduler.scheduleHeartbeat(this);
                UploadScheduler.enqueueHeartbeat(this);
                runOnUiThread(() -> {
                    keyInput.setText("");
                    bindResult.setText("绑定成功。Key 已从输入框清除。");
                    bindButton.setEnabled(true);
                    renderAll();
                });
            } catch (Exception error) {
                String message = error.getMessage() == null ? "绑定失败" : error.getMessage();
                runOnUiThread(() -> {
                    bindResult.setText("绑定失败：" + message);
                    bindButton.setEnabled(allPermissionsGranted());
                });
            }
        });
    }

    private void renderAll() {
        renderBindings();
        renderStatus();
    }

    private void renderBindings() {
        List<TerminalConfig.Binding> bindings = TerminalConfig.bindings(this);
        if (bindings.isEmpty()) {
            bindingsText.setText("尚未绑定。一个 Key 对应一个手机号和 SIM 卡槽。");
            return;
        }
        StringBuilder value = new StringBuilder();
        for (TerminalConfig.Binding binding : bindings) {
            if (value.length() > 0) {
                value.append('\n');
            }
            value.append("SIM ").append(binding.simSlot)
                    .append("  ·  ").append(maskPhone(binding.phoneNumber));
            if (!binding.carrier.isBlank()) {
                value.append("  ·  ").append(binding.carrier);
            }
        }
        bindingsText.setText(value.toString());
    }

    private void renderStatus() {
        QueueDatabase database = new QueueDatabase(this);
        String value = String.format(
                Locale.ROOT,
                "SERVER   %s\nDEVICE   %s\nTOKEN    %s\nNETWORK  %s\nQUEUE    %d\nLAST     %s",
                TerminalConfig.API_BASE_URL,
                TerminalConfig.deviceId(this),
                TerminalConfig.deviceToken(this).isBlank() ? "NOT BOUND" : "SECURED",
                EventPayloads.network(this),
                database.count(),
                TerminalConfig.lastUpload(this));
        statusText.setText(value);
    }

    private static String maskPhone(String phoneNumber) {
        if (phoneNumber == null || phoneNumber.length() < 7) {
            return phoneNumber == null ? "" : phoneNumber;
        }
        return phoneNumber.substring(0, 3)
                + "••••"
                + phoneNumber.substring(phoneNumber.length() - 4);
    }
}
