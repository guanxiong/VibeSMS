package ai.shareapi.vibesms;

import android.Manifest;
import android.app.Activity;
import android.content.ActivityNotFoundException;
import android.content.ComponentName;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.graphics.Typeface;
import android.graphics.text.LineBreaker;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.os.PowerManager;
import android.provider.Settings;
import android.text.Layout;
import android.text.InputType;
import android.view.View;
import android.widget.ArrayAdapter;
import android.widget.Button;
import android.widget.CheckBox;
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
    private LinearLayout statusContainer;
    private View permissionPanel;
    private View huaweiKeepAlivePanel;
    private TextView huaweiKeepAliveWarning;
    private TextView huaweiBatteryState;
    private CheckBox huaweiAppLaunchConfirmed;
    private CheckBox huaweiSleepNetworkConfirmed;
    private boolean tokenRepairInProgress;
    private final List<SimResolver.Option> simOptions = new ArrayList<>();
    private final Handler statusHandler = new Handler(Looper.getMainLooper());
    private final Runnable statusRefresh = new Runnable() {
        @Override
        public void run() {
            renderStatus();
            statusHandler.postDelayed(this, 5_000L);
        }
    };

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
        statusContainer = findViewById(R.id.statusContainer);
        huaweiKeepAlivePanel = findViewById(R.id.huaweiKeepAlivePanel);
        huaweiKeepAliveWarning = findViewById(R.id.huaweiKeepAliveWarning);
        huaweiBatteryState = findViewById(R.id.huaweiBatteryState);
        huaweiAppLaunchConfirmed = findViewById(R.id.huaweiAppLaunchConfirmed);
        huaweiSleepNetworkConfirmed = findViewById(R.id.huaweiSleepNetworkConfirmed);

        findViewById(R.id.permissionButton).setOnClickListener(
                view -> requestPermissions(REQUIRED_PERMISSIONS, PERMISSION_REQUEST));
        bindButton.setOnClickListener(view -> bindSelectedSim());
        keepAliveButton.setOnClickListener(view -> requestBatteryExemption());
        findViewById(R.id.huaweiAppLaunchButton).setOnClickListener(
                view -> openHuaweiAppLaunchSettings());
        findViewById(R.id.huaweiBatterySettingsButton).setOnClickListener(
                view -> openHuaweiBatterySettings());
        huaweiAppLaunchConfirmed.setChecked(
                TerminalConfig.huaweiAppLaunchConfirmed(this));
        huaweiSleepNetworkConfirmed.setChecked(
                TerminalConfig.huaweiSleepNetworkConfirmed(this));
        huaweiAppLaunchConfirmed.setOnCheckedChangeListener((button, checked) -> {
            TerminalConfig.setHuaweiAppLaunchConfirmed(this, checked);
            renderHuaweiKeepAlive();
        });
        huaweiSleepNetworkConfirmed.setOnCheckedChangeListener((button, checked) -> {
            TerminalConfig.setHuaweiSleepNetworkConfirmed(this, checked);
            renderHuaweiKeepAlive();
        });
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
            KeepAliveService.start(this);
            UploadScheduler.scheduleHeartbeat(this);
            UploadScheduler.scheduleImmediate(this);
        }
        renderAll();
        repairDeviceTokenIfNeeded();
    }

    @Override
    protected void onResume() {
        super.onResume();
        KeepAliveService.start(this);
        refreshPermissionsAndSims();
        renderAll();
    }

    @Override
    protected void onStart() {
        super.onStart();
        statusHandler.removeCallbacks(statusRefresh);
        statusHandler.post(statusRefresh);
    }

    @Override
    protected void onStop() {
        statusHandler.removeCallbacks(statusRefresh);
        super.onStop();
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
                this, R.layout.spinner_item, simOptions);
        adapter.setDropDownViewResource(R.layout.spinner_dropdown_item);
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
                KeepAliveService.start(this);
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

    private void repairDeviceTokenIfNeeded() {
        if (tokenRepairInProgress || !TerminalConfig.deviceToken(this).isBlank()) {
            return;
        }
        TerminalConfig.Binding recoverable = null;
        for (TerminalConfig.Binding binding : TerminalConfig.bindings(this)) {
            if (binding.userKey != null && !binding.userKey.isBlank()) {
                recoverable = binding;
                break;
            }
        }
        if (recoverable == null) {
            return;
        }
        tokenRepairInProgress = true;
        TerminalConfig.Binding binding = recoverable;
        bindResult.setText("正在恢复终端连接…");
        executor.execute(() -> {
            try {
                ApiClient.BindingResult result = ApiClient.bind(
                        binding.userKey,
                        TerminalConfig.deviceId(this),
                        binding.simSlot);
                TerminalConfig.replaceDeviceToken(this, result.deviceToken);
                TerminalConfig.addBinding(
                        this,
                        result.phoneNumber.isBlank() ? binding.phoneNumber : result.phoneNumber,
                        binding.simSlot,
                        binding.carrier,
                        binding.userKey);
                KeepAliveService.start(this);
                UploadScheduler.scheduleHeartbeat(this);
                UploadScheduler.enqueueHeartbeat(this);
                runOnUiThread(() -> {
                    tokenRepairInProgress = false;
                    bindResult.setText("终端连接已自动恢复。");
                    renderAll();
                });
            } catch (Exception error) {
                String message = error.getMessage() == null ? "恢复失败" : error.getMessage();
                runOnUiThread(() -> {
                    tokenRepairInProgress = false;
                    bindResult.setText("终端连接恢复失败：" + message);
                    renderStatus();
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
                summary.append("\n").append(binding.carrier);
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

            TextView keyView = bindingText(binding.userKey, 11);
            keyView.setTypeface(Typeface.MONOSPACE);
            keyView.setTextColor(getColor(R.color.lime));
            keyView.setTextIsSelectable(true);
            keyView.setBackgroundResource(R.drawable.key_background);
            keyView.setPadding(dp(12), dp(10), dp(12), dp(10));
            keyView.setBreakStrategy(LineBreaker.BREAK_STRATEGY_SIMPLE);
            keyView.setHyphenationFrequency(Layout.HYPHENATION_FREQUENCY_NONE);
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
            inboxButton.setTypeface(Typeface.create("sans-serif-medium", Typeface.NORMAL));
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
        view.setTypeface(Typeface.create("sans-serif", Typeface.NORMAL));
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
        statusContainer.removeAllViews();
        addStatusRow("版本", BuildConfig.VERSION_NAME);
        addStatusRow(
                "连接",
                String.format(
                        Locale.ROOT,
                        "%s · %s · 队列 %d",
                        TerminalConfig.deviceToken(this).isBlank() ? "未绑定" : "已加密",
                        EventPayloads.network(this),
                        database.count()));
        addStatusRow("保活", "每 9 分钟唤醒");
        addStatusRow("电池", batteryExempt ? "已允许后台运行" : "受系统节能限制");
        addStatusRow("最后心跳", TerminalConfig.lastUpload(this));
        addStatusRow("设备", TerminalConfig.deviceId(this));
        addStatusRow("服务器", Uri.parse(TerminalConfig.API_BASE_URL).getHost());
        keepAliveButton.setVisibility(batteryExempt ? View.GONE : View.VISIBLE);
        keepAliveButton.setEnabled(!TerminalConfig.deviceToken(this).isBlank());
        renderHuaweiKeepAlive();
    }

    private void renderHuaweiKeepAlive() {
        if (!isHuaweiDevice()) {
            huaweiKeepAlivePanel.setVisibility(View.GONE);
            return;
        }
        huaweiKeepAlivePanel.setVisibility(View.VISIBLE);
        huaweiKeepAliveWarning.setTextColor(getColor(R.color.orange));
        PowerManager power = getSystemService(PowerManager.class);
        boolean batteryExempt = power != null
                && power.isIgnoringBatteryOptimizations(getPackageName());
        huaweiBatteryState.setText(batteryExempt
                ? "电池优化：已放行 ✓"
                : "电池优化：待放行（见终端状态）");

        boolean manualConfirmed = huaweiAppLaunchConfirmed.isChecked()
                && huaweiSleepNetworkConfirmed.isChecked();
        if (TerminalConfig.deviceToken(this).isBlank()) {
            huaweiKeepAliveWarning.setText("绑定后将自动验证锁屏心跳。");
            return;
        }
        if (!batteryExempt || !manualConfirmed) {
            huaweiKeepAliveWarning.setText("请完成并确认下面两项设置。");
            return;
        }
        long lastSuccess = TerminalConfig.lastSuccessfulUploadAt(this);
        if (lastSuccess <= 0L) {
            huaweiKeepAliveWarning.setText("设置已确认，等待第一次成功心跳。");
            return;
        }
        long offlineMinutes = Math.max(0L, (System.currentTimeMillis() - lastSuccess) / 60_000L);
        if (offlineMinutes > 20L) {
            huaweiKeepAliveWarning.setText(
                    String.format(Locale.ROOT, "心跳中断 %d 分钟，请复查设置。", offlineMinutes));
        } else {
            huaweiKeepAliveWarning.setText("设置已确认，心跳正常 ✓");
            huaweiKeepAliveWarning.setTextColor(getColor(R.color.green));
        }
    }

    private boolean isHuaweiDevice() {
        String manufacturer = Build.MANUFACTURER == null ? "" : Build.MANUFACTURER;
        String brand = Build.BRAND == null ? "" : Build.BRAND;
        return manufacturer.toLowerCase(Locale.ROOT).contains("huawei")
                || brand.toLowerCase(Locale.ROOT).contains("huawei");
    }

    private void openHuaweiAppLaunchSettings() {
        Intent[] candidates = {
                componentIntent(
                        "com.huawei.systemmanager",
                        "com.huawei.systemmanager.startupmgr.ui.StartupNormalAppListActivity"),
                componentIntent(
                        "com.huawei.systemmanager",
                        "com.huawei.systemmanager.appcontrol.activity.StartupAppControlActivity"),
                new Intent(
                        Settings.ACTION_APPLICATION_DETAILS_SETTINGS,
                        Uri.parse("package:" + getPackageName()))
        };
        if (!startFirstAvailable(candidates)) {
            bindResult.setText("无法直接打开启动管理，请按页面路径在系统设置中操作。");
        }
    }

    private void openHuaweiBatterySettings() {
        Intent[] candidates = {
                componentIntent(
                        "com.huawei.systemmanager",
                        "com.huawei.systemmanager.power.ui.HwPowerManagerActivity"),
                new Intent(Settings.ACTION_BATTERY_SAVER_SETTINGS),
                new Intent(Settings.ACTION_SETTINGS)
        };
        if (!startFirstAvailable(candidates)) {
            bindResult.setText("无法直接打开电池设置，请按页面路径在系统设置中操作。");
        }
    }

    private Intent componentIntent(String packageName, String className) {
        return new Intent().setComponent(new ComponentName(packageName, className));
    }

    private boolean startFirstAvailable(Intent[] candidates) {
        for (Intent candidate : candidates) {
            try {
                startActivity(candidate);
                return true;
            } catch (ActivityNotFoundException | SecurityException ignored) {
                // Huawei changes private Settings activities between system versions.
            }
        }
        return false;
    }

    private void addStatusRow(String label, String value) {
        LinearLayout row = new LinearLayout(this);
        row.setOrientation(LinearLayout.HORIZONTAL);
        row.setBaselineAligned(false);

        TextView labelView = bindingText(label, 10);
        labelView.setTextColor(getColor(R.color.green));
        labelView.setTypeface(Typeface.create("sans-serif-medium", Typeface.NORMAL));
        labelView.setLetterSpacing(0.04f);
        LinearLayout.LayoutParams labelParams = new LinearLayout.LayoutParams(
                dp(72), LinearLayout.LayoutParams.WRAP_CONTENT);
        row.addView(labelView, labelParams);

        int valueSize = "最后心跳".equals(label) || "设备".equals(label) ? 11 : 12;
        TextView valueView = bindingText(value == null ? "" : value, valueSize);
        valueView.setTextColor(getColor(R.color.ink));
        valueView.setTextIsSelectable(true);
        valueView.setBreakStrategy(LineBreaker.BREAK_STRATEGY_SIMPLE);
        valueView.setHyphenationFrequency(Layout.HYPHENATION_FREQUENCY_NONE);
        LinearLayout.LayoutParams valueParams = new LinearLayout.LayoutParams(
                0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f);
        row.addView(valueView, valueParams);

        LinearLayout.LayoutParams rowParams = new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT,
                LinearLayout.LayoutParams.WRAP_CONTENT);
        rowParams.setMargins(0, 0, 0, dp(9));
        statusContainer.addView(row, rowParams);
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
