package ai.shareapi.vibesms;

import android.content.ContentValues;
import android.content.Context;
import android.database.Cursor;
import android.database.sqlite.SQLiteDatabase;
import android.database.sqlite.SQLiteOpenHelper;

import java.util.ArrayList;
import java.util.List;

final class QueueDatabase extends SQLiteOpenHelper {
    private static final String DATABASE_NAME = "vibesms-outbox.db";
    private static final int DATABASE_VERSION = 1;

    static final class Item {
        final long id;
        final String eventId;
        final String path;
        final String payload;
        final int attempts;

        Item(long id, String eventId, String path, String payload, int attempts) {
            this.id = id;
            this.eventId = eventId;
            this.path = path;
            this.payload = payload;
            this.attempts = attempts;
        }
    }

    QueueDatabase(Context context) {
        super(context.getApplicationContext(), DATABASE_NAME, null, DATABASE_VERSION);
    }

    @Override
    public void onCreate(SQLiteDatabase database) {
        database.execSQL(
                "CREATE TABLE outbox ("
                        + "id INTEGER PRIMARY KEY AUTOINCREMENT,"
                        + "event_id TEXT NOT NULL UNIQUE,"
                        + "path TEXT NOT NULL,"
                        + "payload TEXT NOT NULL,"
                        + "attempts INTEGER NOT NULL DEFAULT 0,"
                        + "next_attempt_at INTEGER NOT NULL DEFAULT 0,"
                        + "created_at INTEGER NOT NULL,"
                        + "last_error TEXT NOT NULL DEFAULT '')");
        database.execSQL("CREATE INDEX outbox_next_attempt ON outbox(next_attempt_at, id)");
    }

    @Override
    public void onUpgrade(SQLiteDatabase database, int oldVersion, int newVersion) {
        throw new IllegalStateException("unsupported queue database migration");
    }

    synchronized void enqueue(String eventId, String path, String payload) {
        ContentValues values = new ContentValues();
        values.put("event_id", eventId);
        values.put("path", path);
        values.put("payload", payload);
        values.put("created_at", System.currentTimeMillis());
        getWritableDatabase().insertWithOnConflict(
                "outbox", null, values, SQLiteDatabase.CONFLICT_IGNORE);
    }

    synchronized List<Item> pending(int limit) {
        List<Item> result = new ArrayList<>();
        try (Cursor cursor = getReadableDatabase().query(
                "outbox",
                new String[]{"id", "event_id", "path", "payload", "attempts"},
                "next_attempt_at <= ?",
                new String[]{String.valueOf(System.currentTimeMillis())},
                null,
                null,
                "id ASC",
                String.valueOf(Math.max(1, Math.min(limit, 100))))) {
            while (cursor.moveToNext()) {
                result.add(new Item(
                        cursor.getLong(0),
                        cursor.getString(1),
                        cursor.getString(2),
                        cursor.getString(3),
                        cursor.getInt(4)));
            }
        }
        return result;
    }

    synchronized void markSent(long id) {
        getWritableDatabase().delete("outbox", "id = ?", new String[]{String.valueOf(id)});
    }

    synchronized void markFailed(Item item, String error) {
        int attempts = item.attempts + 1;
        long multiplier = 1L << Math.min(attempts - 1, 6);
        long delay = Math.min(15L * 60L * 1000L, 15L * 1000L * multiplier);
        ContentValues values = new ContentValues();
        values.put("attempts", attempts);
        values.put("next_attempt_at", System.currentTimeMillis() + delay);
        values.put("last_error", truncate(error, 500));
        getWritableDatabase().update(
                "outbox", values, "id = ?", new String[]{String.valueOf(item.id)});
    }

    synchronized int count() {
        try (Cursor cursor = getReadableDatabase().rawQuery("SELECT COUNT(*) FROM outbox", null)) {
            return cursor.moveToFirst() ? cursor.getInt(0) : 0;
        }
    }

    private static String truncate(String value, int limit) {
        if (value == null) {
            return "";
        }
        return value.length() <= limit ? value : value.substring(0, limit);
    }
}
