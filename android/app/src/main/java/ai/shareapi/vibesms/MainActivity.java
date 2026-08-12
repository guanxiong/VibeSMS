package ai.shareapi.vibesms;

import android.Manifest;
import android.app.Activity;
import android.content.ActivityNotFoundException;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.graphics.Typeface;
import android.net.Uri;
import android.os.Bundle;
import android.os.PowerManager;
import android.provider.Settings;
import android.text.InputType;
import android.view.View;
import android.widget.ArrayAdapter;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.Spinner;
import android.widget.TextView;

import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import java.util.Locale;
import java.util.Set;
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
    private Button keepAliveButton;
    private TextView bindResult;
    private LinearLayout bindingsContainer;
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
        keepAliveButton = findViewById(R.id.keepAliveButton);
        bindResult = findViewById(R.id.bindResult);
        bindingsContainer = findViewById(R.id.bindingsContainer);
        statusText = findViewById(R.id.statusText);

        findViewById(R.id.permissionButton).setOnClickListener(
                view -> requestPermissions(REQUIRED_PERMISSIONS, PERMISSION_REQUEST));
        bindButton.setOnClickListener(view -> bindSelectedSim());
        keepAliveButton.setOnClickListener(view -> requestBatteryExemption());
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
        refreshPermissionsAndSims();
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
        int selectedSlot = 0;
        Object selected = simSpinner.getSelectedItem();
        if (selected instanceof SimResolver.Option) {
            selectedSlot = ((SimResolver.Option) selected).simSlot;
        }

        Set<Integer> boundSlots = new HashSet<>();
        for (TerminalConfig.Binding binding : TerminalConfig.bindings(this)) {
            boundSlots.add(binding.simSlot);
        }
        simOptions.clear();
        for (SimResolver.Option option : SimResolver.activeOptions(this)) {
            if (!boundSlots.contains(option.simSlot)) {
                simOptions.add(option);
            }
        }
        ArrayAdapter<SimResolver.Option> adapter = new ArrayAdapter<>(
                this, android.R.layout.simple_spinner_item, simOptions);
        adapter.setDropDownViewResource(android.R.layout.simple_spinner_dropdown_item);
        simSpinner.setAdapter(adapter);
        for (int index = 0; index < simOptions.size(); index++) {
            if (simOptions.get(index).simSlot == selectedSlot) {
                simSpinner.setSelection(index);
                break;
            }
        }
        boolean hasUnboundSim = !simOptions.isEmpty();
        simSpinner.setEnabled(hasUnboundSim);
        bindButton.setEnabled(granted && hasUnboundSim);
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
                TerminalConfig.addBinding(
                        this, result.phoneNumber, option.simSlot, option.carrier, userKey);
                UploadScheduler.scheduleHeartbeat(this);
                UploadScheduler.enqueueHeartbeat(this);
                runOnUiThread(() -> {
                    keyInput.setText("");
                    bindResult.setText("绑定成功。Key 已从输入框清除。");
                    refreshPermissionsAndSims();
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
        bindingsContainer.removeAllViews();
        if (bindings.isEmpty()) {
            TextView empty = bindingText("尚未绑定。一个 Key 对应一个手机号和 SIM 卡槽。", 14);
            empty.setTextColor(getColor(R.color.muted));
            bindingsContainer.addView(empty);
            return;
        }

        for (int index = 0; index < bindings.size(); index++) {
            TerminalConfig.Binding binding = bindings.get(index);
            if (index > 0) {
                View divider = new View(this);
                divider.setBackgroundColor(getColor(R.color.paper));
                LinearLayout.LayoutParams dividerParams = new LinearLayout.LayoutParams(
                        LinearLayout.LayoutParams.MATCH_PARENT, dp(1));
                dividerParams.setMargins(0, dp(16), 0, dp(16));
                bindingsContainer.addView(divider, dividerParams);
            }

            StringBuilder summary = new StringBuilder();
            summary.append("SIM ").append(binding.simSlot)
                    .append("  ·  ").append(maskPhone(binding.phoneNumber));
            if (!binding.carrier.isBlank()) {
                summary.append("  ·  ").append(binding.carrier);
            }
            TextView summaryView = bindingText(summary.toString(), 14);
            summaryView.setTextColor(getColor(R.color.muted));
            bindingsContainer.addView(summaryView);

            if (binding.userKey == null || binding.userKey.isBlank()) {
                TextView missing = bindingText("读取 Key 未保存在本机，需要重新签发后绑定。", 12);
                missing.setTextColor(getColor(R.color.muted));
                LinearLayout.LayoutParams missingParams = new LinearLayout.LayoutParams(
                        LinearLayout.LayoutParams.MATCH_PARENT,
                        LinearLayout.LayoutParams.WRAP_CONTENT);
                missingParams.setMargins(0, dp(9), 0, 0);
                bindingsContainer.addView(missing, missingParams);
                continue;
            }

            TextView keyView = bindingText(binding.userKey, 12);
            keyView.setTypeface(Typeface.MONOSPACE);
            keyView.setTextColor(getColor(R.color.ink));
            keyView.setTextIsSelectable(true);
            LinearLayout.LayoutParams keyParams = new LinearLayout.LayoutParams(
                    LinearLayout.LayoutParams.MATCH_PARENT,
                    LinearLayout.LayoutParams.WRAP_CONTENT);
            keyParams.setMargins(0, dp(9), 0, 0);
            bindingsContainer.addView(keyView, keyParams);

            Button inboxButton = new Button(this);
            inboxButton.setText("打开 Web 收件箱");
            inboxButton.setAllCaps(false);
            inboxButton.setTextColor(getColor(R.color.white));
            inboxButton.setTextSize(14);
            inboxButton.setTypeface(Typeface.DEFAULT, Typeface.BOLD);
            inboxButton.setBackgroundResource(R.drawable.button_primary);
            inboxButton.setOnClickListener(view -> openInbox(binding.userKey));
            LinearLayout.LayoutParams buttonParams = new LinearLayout.LayoutParams(
                    LinearLayout.LayoutParams.MATCH_PARENT, dp(48));
            buttonParams.setMargins(0, dp(10), 0, 0);
            bindingsContainer.addView(inboxButton, buttonParams);
        }
    }

    private TextView bindingText(String value, int sizeSp) {
        TextView view = new TextView(this);
        view.setText(value);
        view.setTextSize(sizeSp);
        view.setLineSpacing(0, 1.15f);
        return view;
    }

    private void openInbox(String userKey) {
        Uri inbox = Uri.parse(TerminalConfig.API_BASE_URL + "/inbox/")
                .buildUpon()
                .encodedFragment("key=" + Uri.encode(userKey))
                .build();
        try {
            startActivity(new Intent(Intent.ACTION_VIEW, inbox));
        } catch (ActivityNotFoundException error) {
            bindResult.setText("没有可打开 Web 收件箱的浏览器。");
        }
    }

    private int dp(int value) {
        return Math.round(value * getResources().getDisplayMetrics().density);
    }

    private void renderStatus() {
        QueueDatabase database = new QueueDatabase(this);
        PowerManager power = getSystemService(PowerManager.class);
        boolean batteryExempt = power != null
                && power.isIgnoringBatteryOptimizations(getPackageName());
        String value = String.format(
                Locale.ROOT,
                "SERVER     %s\nDEVICE     %s\nTOKEN      %s\nNETWORK    %s\nQUEUE      %d"
                        + "\nKEEPALIVE  ALARM 9 MIN\nBATTERY    %s\nLAST       %s",
                TerminalConfig.API_BASE_URL,
                TerminalConfig.deviceId(this),
                TerminalConfig.deviceToken(this).isBlank() ? "NOT BOUND" : "SECURED",
                EventPayloads.network(this),
                database.count(),
                batteryExempt ? "EXEMPT" : "RESTRICTED",
                TerminalConfig.lastUpload(this));
        statusText.setText(value);
        keepAliveButton.setVisibility(batteryExempt ? View.GONE : View.VISIBLE);
        keepAliveButton.setEnabled(!TerminalConfig.deviceToken(this).isBlank());
    }

    private void requestBatteryExemption() {
        UploadScheduler.scheduleHeartbeat(this);
        Intent request = new Intent(
                Settings.ACTION_REQUEST_IGNORE_BATTERY_OPTIMIZATIONS,
                Uri.parse("package:" + getPackageName()));
        try {
            startActivity(request);
        } catch (ActivityNotFoundException error) {
            try {
                startActivity(new Intent(Settings.ACTION_IGNORE_BATTERY_OPTIMIZATION_SETTINGS));
            } catch (ActivityNotFoundException unavailable) {
                bindResult.setText("请在系统电池设置中允许 VibeSMS 后台运行。");
            }
        }
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
