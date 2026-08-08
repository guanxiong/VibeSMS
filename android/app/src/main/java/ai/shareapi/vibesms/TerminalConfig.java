package ai.shareapi.vibesms;

import android.content.Context;
import android.content.SharedPreferences;
import android.provider.Settings;
import android.security.keystore.KeyGenParameterSpec;
import android.security.keystore.KeyProperties;
import android.util.Base64;

import org.json.JSONArray;
import org.json.JSONException;
import org.json.JSONObject;

import java.nio.charset.StandardCharsets;
import java.security.KeyStore;
import java.util.ArrayList;
import java.util.List;

import javax.crypto.Cipher;
import javax.crypto.KeyGenerator;
import javax.crypto.SecretKey;
import javax.crypto.spec.GCMParameterSpec;

final class TerminalConfig {
    static final String API_BASE_URL = "https://sms.shareapi.ai";
    private static final String PREFS = "vibesms_terminal";
    private static final String TOKEN_KEY = "device_token_encrypted";
    private static final String BINDINGS_KEY = "bindings";
    private static final String LAST_UPLOAD_KEY = "last_upload";
    private static final String KEYSTORE = "AndroidKeyStore";
    private static final String KEY_ALIAS = "vibesms-device-token-v1";

    private TerminalConfig() {}

    static final class Binding {
        final String phoneNumber;
        final int simSlot;
        final String carrier;

        Binding(String phoneNumber, int simSlot, String carrier) {
            this.phoneNumber = phoneNumber;
            this.simSlot = simSlot;
            this.carrier = carrier;
        }
    }

    static String deviceId(Context context) {
        String androidId = Settings.Secure.getString(
                context.getContentResolver(), Settings.Secure.ANDROID_ID);
        if (androidId == null || androidId.isBlank()) {
            androidId = "unknown";
        }
        return "android-" + androidId;
    }

    static void replaceDeviceToken(Context context, String token) {
        if (token == null || token.isBlank()) {
            throw new IllegalArgumentException("device token is empty");
        }
        preferences(context).edit().putString(TOKEN_KEY, encrypt(token)).apply();
    }

    static String deviceToken(Context context) {
        String encoded = preferences(context).getString(TOKEN_KEY, "");
        if (encoded == null || encoded.isBlank()) {
            return "";
        }
        try {
            return decrypt(encoded);
        } catch (RuntimeException error) {
            preferences(context).edit().remove(TOKEN_KEY).apply();
            return "";
        }
    }

    static synchronized void addBinding(
            Context context, String phoneNumber, int simSlot, String carrier) {
        List<Binding> bindings = bindings(context);
        bindings.removeIf(item -> item.simSlot == simSlot);
        bindings.add(new Binding(phoneNumber, simSlot, carrier));
        JSONArray array = new JSONArray();
        for (Binding binding : bindings) {
            JSONObject object = new JSONObject();
            try {
                object.put("phone_number", binding.phoneNumber);
                object.put("sim_slot", binding.simSlot);
                object.put("carrier", binding.carrier);
            } catch (JSONException error) {
                throw new IllegalStateException("cannot store binding", error);
            }
            array.put(object);
        }
        preferences(context).edit().putString(BINDINGS_KEY, array.toString()).apply();
    }

    static synchronized List<Binding> bindings(Context context) {
        List<Binding> result = new ArrayList<>();
        String raw = preferences(context).getString(BINDINGS_KEY, "[]");
        try {
            JSONArray array = new JSONArray(raw == null ? "[]" : raw);
            for (int index = 0; index < array.length(); index++) {
                JSONObject object = array.getJSONObject(index);
                int slot = object.optInt("sim_slot", 0);
                if (slot == 1 || slot == 2) {
                    result.add(new Binding(
                            object.optString("phone_number", ""),
                            slot,
                            object.optString("carrier", "")));
                }
            }
        } catch (JSONException ignored) {
            preferences(context).edit().remove(BINDINGS_KEY).apply();
        }
        return result;
    }

    static boolean isSlotBound(Context context, int simSlot) {
        for (Binding binding : bindings(context)) {
            if (binding.simSlot == simSlot) {
                return true;
            }
        }
        return false;
    }

    static int onlyBoundSlot(Context context) {
        List<Binding> bindings = bindings(context);
        return bindings.size() == 1 ? bindings.get(0).simSlot : 0;
    }

    static void recordUpload(Context context, String value) {
        preferences(context).edit().putString(LAST_UPLOAD_KEY, value).apply();
    }

    static String lastUpload(Context context) {
        return preferences(context).getString(LAST_UPLOAD_KEY, "从未") ;
    }

    private static SharedPreferences preferences(Context context) {
        return context.getSharedPreferences(PREFS, Context.MODE_PRIVATE);
    }

    private static SecretKey secretKey() throws Exception {
        KeyStore keyStore = KeyStore.getInstance(KEYSTORE);
        keyStore.load(null);
        if (keyStore.containsAlias(KEY_ALIAS)) {
            return ((KeyStore.SecretKeyEntry) keyStore.getEntry(KEY_ALIAS, null)).getSecretKey();
        }
        KeyGenerator generator = KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, KEYSTORE);
        generator.init(new KeyGenParameterSpec.Builder(
                KEY_ALIAS,
                KeyProperties.PURPOSE_ENCRYPT | KeyProperties.PURPOSE_DECRYPT)
                .setBlockModes(KeyProperties.BLOCK_MODE_GCM)
                .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
                .setRandomizedEncryptionRequired(true)
                .build());
        return generator.generateKey();
    }

    private static String encrypt(String value) {
        try {
            Cipher cipher = Cipher.getInstance("AES/GCM/NoPadding");
            cipher.init(Cipher.ENCRYPT_MODE, secretKey());
            byte[] ciphertext = cipher.doFinal(value.getBytes(StandardCharsets.UTF_8));
            return Base64.encodeToString(cipher.getIV(), Base64.NO_WRAP)
                    + ":" + Base64.encodeToString(ciphertext, Base64.NO_WRAP);
        } catch (Exception error) {
            throw new IllegalStateException("cannot encrypt device token", error);
        }
    }

    private static String decrypt(String encoded) {
        try {
            String[] parts = encoded.split(":", 2);
            if (parts.length != 2) {
                throw new IllegalArgumentException("invalid token envelope");
            }
            Cipher cipher = Cipher.getInstance("AES/GCM/NoPadding");
            cipher.init(
                    Cipher.DECRYPT_MODE,
                    secretKey(),
                    new GCMParameterSpec(128, Base64.decode(parts[0], Base64.NO_WRAP)));
            return new String(
                    cipher.doFinal(Base64.decode(parts[1], Base64.NO_WRAP)),
                    StandardCharsets.UTF_8);
        } catch (Exception error) {
            throw new IllegalStateException("cannot decrypt device token", error);
        }
    }
}
