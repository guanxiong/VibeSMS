package ai.shareapi.vibesms;

import org.json.JSONException;
import org.json.JSONObject;

import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;

final class ApiClient {
    private static final int CONNECT_TIMEOUT_MS = 12_000;
    private static final int READ_TIMEOUT_MS = 18_000;

    private ApiClient() {}

    static final class BindingResult {
        final String phoneNumber;
        final String deviceToken;

        BindingResult(String phoneNumber, String deviceToken) {
            this.phoneNumber = phoneNumber;
            this.deviceToken = deviceToken;
        }
    }

    static BindingResult bind(String userKey, String deviceId, int simSlot) throws IOException {
        JSONObject payload = new JSONObject();
        try {
            payload.put("device_id", deviceId);
            payload.put("sim_slot", simSlot);
        } catch (JSONException error) {
            throw new IOException("cannot create binding request", error);
        }
        Response response = post(
                "/api/v1/bindings", payload.toString(), "Bearer " + userKey, false);
        JSONObject result = parseObject(response.body);
        String token = result.optString("device_token", "");
        if (token.isBlank()) {
            throw new IOException("server did not return a device token");
        }
        return new BindingResult(result.optString("phone_number", ""), token);
    }

    static void upload(String path, String payload, String deviceToken) throws IOException {
        post(path, payload, deviceToken, true);
    }

    private static Response post(
            String path, String payload, String credential, boolean deviceCredential)
            throws IOException {
        byte[] body = payload.getBytes(StandardCharsets.UTF_8);
        URL url = new URL(TerminalConfig.API_BASE_URL + path);
        if (!"https".equalsIgnoreCase(url.getProtocol())) {
            throw new IOException("VibeSMS API must use HTTPS");
        }
        HttpURLConnection connection = (HttpURLConnection) url.openConnection();
        try {
            connection.setRequestMethod("POST");
            connection.setConnectTimeout(CONNECT_TIMEOUT_MS);
            connection.setReadTimeout(READ_TIMEOUT_MS);
            connection.setDoOutput(true);
            connection.setUseCaches(false);
            connection.setFixedLengthStreamingMode(body.length);
            connection.setRequestProperty("Content-Type", "application/json; charset=utf-8");
            connection.setRequestProperty("Accept", "application/json");
            connection.setRequestProperty("User-Agent", "VibeSMS-Android/" + BuildConfig.VERSION_NAME);
            if (deviceCredential) {
                connection.setRequestProperty("X-Gateway-Token", credential);
            } else {
                connection.setRequestProperty("Authorization", credential);
            }
            try (OutputStream output = connection.getOutputStream()) {
                output.write(body);
            }
            int status = connection.getResponseCode();
            InputStream stream = status >= 200 && status < 300
                    ? connection.getInputStream() : connection.getErrorStream();
            String responseBody = read(stream);
            if (status < 200 || status >= 300) {
                String message = "HTTP " + status;
                try {
                    String serverError = new JSONObject(responseBody).optString("error", "");
                    if (!serverError.isBlank()) {
                        message += ": " + serverError;
                    }
                } catch (JSONException ignored) {
                    // Keep the status-only error and never include request headers.
                }
                throw new IOException(message);
            }
            return new Response(status, responseBody);
        } finally {
            connection.disconnect();
        }
    }

    private static JSONObject parseObject(String value) throws IOException {
        try {
            return new JSONObject(value);
        } catch (JSONException error) {
            throw new IOException("server returned invalid JSON", error);
        }
    }

    private static String read(InputStream stream) throws IOException {
        if (stream == null) {
            return "";
        }
        try (InputStream input = stream; ByteArrayOutputStream output = new ByteArrayOutputStream()) {
            byte[] buffer = new byte[4096];
            int count;
            while ((count = input.read(buffer)) != -1) {
                output.write(buffer, 0, count);
            }
            return output.toString(StandardCharsets.UTF_8.name());
        }
    }

    private static final class Response {
        final int status;
        final String body;

        Response(int status, String body) {
            this.status = status;
            this.body = body;
        }
    }
}
