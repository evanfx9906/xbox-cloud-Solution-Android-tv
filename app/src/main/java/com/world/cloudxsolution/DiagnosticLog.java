package com.world.cloudxsolution;

import android.content.ContentResolver;
import android.content.ContentValues;
import android.content.Context;
import android.net.Uri;
import android.os.Build;
import android.os.Environment;
import android.provider.MediaStore;
import android.util.DisplayMetrics;
import android.util.Log;

import org.json.JSONObject;

import java.io.OutputStream;
import java.text.SimpleDateFormat;
import java.util.Date;
import java.util.Locale;

/**
 * Surgical addition: a write-only diagnostic logger for tracking down the
 * aspect-ratio / freeze issues without needing logcat access.
 *
 * Design rules:
 *  - Every method here is wrapped in try/catch and NEVER throws, and NEVER
 *    touches any rendering, layout, or streaming logic. It only observes and
 *    appends lines to a file. If this class is completely broken, the app
 *    around it must behave exactly as if it didn't exist.
 *  - Every single log line is opened, written, flushed, and closed
 *    immediately -- nothing is buffered in memory waiting for a "finalize"
 *    step, so whatever's on disk at the instant of a crash/freeze is
 *    complete up to that point. No button or export step is required for
 *    the data to survive.
 *  - The log lives in the public Downloads/CloudXDiagnostics folder via
 *    MediaStore, so it's visible in any normal file manager app with no
 *    special permission and no need to reopen CloudX after a crash.
 *
 * Each process (main app process and the ":stream" process) gets its own
 * file, since Android gives each process its own static state anyway.
 */
public class DiagnosticLog {

    private static final String SUBFOLDER = "CloudXDiagnostics";
    private static volatile Uri logUri;
    private static volatile ContentResolver resolver;
    private static final Object LOCK = new Object();
    private static final SimpleDateFormat TIME_FMT =
            new SimpleDateFormat("HH:mm:ss.SSS", Locale.US);

    public static void init(Context context, String process) {
        try {
            resolver = context.getApplicationContext().getContentResolver();
            String fileName = "cloudx_diag_" + process + ".jsonl";

            ContentValues values = new ContentValues();
            values.put(MediaStore.Downloads.DISPLAY_NAME, fileName);
            values.put(MediaStore.Downloads.MIME_TYPE, "application/json");
            values.put(MediaStore.Downloads.RELATIVE_PATH,
                    Environment.DIRECTORY_DOWNLOADS + "/" + SUBFOLDER);

            logUri = resolver.insert(MediaStore.Downloads.EXTERNAL_CONTENT_URI, values);
            log(process, "session", "log initialized, writing to Downloads/" + SUBFOLDER + "/" + fileName);
        } catch (Throwable ignored) {
            // Logging must never affect the app itself.
        }
    }

    public static void installUncaughtExceptionHandler(String process) {
        try {
            final Thread.UncaughtExceptionHandler defaultHandler =
                    Thread.getDefaultUncaughtExceptionHandler();
            Thread.setDefaultUncaughtExceptionHandler((thread, throwable) -> {
                try {
                    log(process, "FATAL_on_" + thread.getName(), Log.getStackTraceString(throwable));
                } catch (Throwable ignored) {
                }
                if (defaultHandler != null) {
                    defaultHandler.uncaughtException(thread, throwable);
                }
            });
        } catch (Throwable ignored) {
        }
    }

    public static void log(String process, String tag, String message) {
        try {
            synchronized (LOCK) {
                if (logUri == null || resolver == null) return;
                JSONObject entry = new JSONObject();
                entry.put("t", TIME_FMT.format(new Date()));
                entry.put("ms", System.currentTimeMillis());
                entry.put("process", process);
                entry.put("tag", tag);
                entry.put("msg", message);
                try (OutputStream os = resolver.openOutputStream(logUri, "wa")) {
                    if (os != null) {
                        os.write((entry.toString() + "\n").getBytes());
                        os.flush();
                    }
                }
            }
        } catch (Throwable ignored) {
        }
    }

    public static void logException(String process, String tag, Throwable t) {
        try {
            log(process, tag, Log.getStackTraceString(t));
        } catch (Throwable ignored) {
        }
    }

    public static void logDeviceInfo(Context context, String process) {
        try {
            DisplayMetrics dm = context.getResources().getDisplayMetrics();
            JSONObject info = new JSONObject();
            info.put("widthPx", dm.widthPixels);
            info.put("heightPx", dm.heightPixels);
            info.put("density", dm.density);
            info.put("densityDpi", dm.densityDpi);
            info.put("sdkInt", Build.VERSION.SDK_INT);
            info.put("model", Build.MODEL);
            info.put("manufacturer", Build.MANUFACTURER);
            log(process, "device_info", info.toString());
        } catch (Throwable ignored) {
        }
    }

    public static void logMemory(String process) {
        try {
            Runtime rt = Runtime.getRuntime();
            JSONObject mem = new JSONObject();
            mem.put("freeMB", rt.freeMemory() / (1024 * 1024));
            mem.put("totalMB", rt.totalMemory() / (1024 * 1024));
            mem.put("maxMB", rt.maxMemory() / (1024 * 1024));
            log(process, "memory", mem.toString());
        } catch (Throwable ignored) {
        }
    }
}
