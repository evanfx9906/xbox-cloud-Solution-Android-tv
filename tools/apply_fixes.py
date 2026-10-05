#!/usr/bin/env python3
"""
Edits for the CloudX fork (FINAL version, v8).

Base = commit 72dc66f (your fork on Oct 3, before any script ran).
Run with --reset (the workflow does) and the OWNED files below are first restored
to that base, then every edit is applied. Result: always the same, never stacks.
If you add an edit to a new file, add that file to OWNED.

Safety rules:
  * Each edit needs exact text. Already changed -> skipped.
  * Original text not found exactly once -> STOP with an error, never guess.
"""
import pathlib
import subprocess
import sys

BASE = "72dc66f"

ROOT = pathlib.Path(__file__).resolve().parent.parent
JAVA_DIR = "app/src/main/java/com/world/cloudxsolution/"
JAVA = JAVA_DIR + "MainActivity.java"
DIAGLOG = JAVA_DIR + "DiagnosticLog.java"
SERVICE = JAVA_DIR + "StreamingService.java"
ASSET_JS = "app/src/main/assets/index.js"
WEBRTC = JAVA_DIR + "WebRtcReceiver.java"
OLD_WATCHDOG = JAVA_DIR + "StallWatchdog.java"   # debug helper from earlier builds: deleted
BOUNDED = JAVA_DIR + "BoundedCall.java"          # new file, written by this script
LAYOUT = "app/src/main/res/layout/"
MANIFEST = "app/src/main/AndroidManifest.xml"
GRADLE = "app/build.gradle.kts"
STRINGS = "app/src/main/res/values/strings.xml"

OWNED = [
    MANIFEST, JAVA, DIAGLOG, SERVICE, WEBRTC, ASSET_JS, GRADLE, STRINGS,
    LAYOUT + "dialog_app_settings.xml",
    LAYOUT + "dialog_streaming_menu.xml",
    LAYOUT + "dialog_intro_help.xml",
]

if "--reset" in sys.argv:
    subprocess.run(["git", "checkout", BASE, "--"] + OWNED, cwd=ROOT, check=True)
    print(f"reset {len(OWNED)} files to base {BASE}")

changed = []


def edit(rel, old, new, label):
    if rel not in OWNED:
        sys.exit(f"ERROR [{label}]: {rel} is not listed in OWNED")
    p = ROOT / rel
    text = p.read_text(encoding="utf-8")
    if new in text:
        print(f"skip (already applied): {label}")
        return
    n = text.count(old)
    if n != 1:
        sys.exit(f"ERROR [{label}] in {rel}: expected exactly 1 match, found {n}")
    p.write_text(text.replace(old, new, 1), encoding="utf-8")
    changed.append(label)
    print(f"applied: {label}")


# ---- 1. Language: the Xbox page URL was hard-coded to French (verified working) ----
edit(JAVA,
     'webView.loadUrl("https://www.xbox.com/fr-FR/play");',
     'webView.loadUrl("https://www.xbox.com/en-US/play");',
     "Xbox page language fr-FR -> en-US")

# ---- 2. Rotation (verified working) -------------------------------------------------
edit(MANIFEST,
     'android:screenOrientation="landscape"',
     'android:screenOrientation="sensor"',
     "screen orientation landscape -> sensor")

# ---- 3. Scrollable dialogs (verified working) ---------------------------------------
OLD_HEAD = '''<LinearLayout xmlns:android="http://schemas.android.com/apk/res/android"
    android:layout_width="340dp"
    android:layout_height="wrap_content"
    android:orientation="vertical"
    android:background="@drawable/bg_dialog_xbox"
    android:padding="20dp">
'''
NEW_HEAD = '''<ScrollView xmlns:android="http://schemas.android.com/apk/res/android"
    android:layout_width="340dp"
    android:layout_height="wrap_content"
    android:background="@drawable/bg_dialog_xbox"
    android:overScrollMode="ifContentScrolls">

<LinearLayout
    android:layout_width="match_parent"
    android:layout_height="wrap_content"
    android:orientation="vertical"
    android:padding="20dp">
'''


def wrap_in_scroll(name):
    rel = LAYOUT + name
    if rel not in OWNED:
        sys.exit(f"ERROR: {rel} is not listed in OWNED")
    p = ROOT / rel
    text = p.read_text(encoding="utf-8")
    if "<ScrollView xmlns:android" in text:
        print(f"skip (already applied): scroll wrapper {name}")
        return
    if text.count(OLD_HEAD) != 1:
        sys.exit(f"ERROR [scroll {name}]: root tag not found exactly once")
    body = text.replace(OLD_HEAD, NEW_HEAD, 1).rstrip()
    if not body.endswith("</LinearLayout>"):
        sys.exit(f"ERROR [scroll {name}]: file does not end with </LinearLayout>")
    p.write_text(body + "\n</ScrollView>\n", encoding="utf-8")
    changed.append(f"scroll wrapper {name}")
    print(f"applied: scroll wrapper {name}")


for layout in ("dialog_app_settings.xml", "dialog_streaming_menu.xml", "dialog_intro_help.xml"):
    wrap_in_scroll(layout)

# ---- 4. Install next to your current app ------------------------------------------
edit(GRADLE,
     "    buildTypes {\n        release {\n",
     "    buildTypes {\n        debug {\n            applicationIdSuffix = \".fixed\"\n        }\n        release {\n",
     "debug build installs as a separate app (.fixed)")
edit(STRINGS,
     '<string name="app_name">cloudxSolution</string>',
     '<string name="app_name">cloudxSolution Fixed</string>',
     "app label 'cloudxSolution Fixed'")

# ---- 5. SAFEGUARDS (quiet, no popups) ---------------------------------------------------
# Verified from your phone's logs and stack traces: the freeze came from a WebRTC statistics
# call made on the video render thread; "Exit game" then hung waiting on that stuck video
# pipeline. These two edits are the fix, and the bounded waits are the safety net.

# 5a. Remove the debug helper that earlier builds added (no longer needed).
old_wd = ROOT / OLD_WATCHDOG
if old_wd.exists():
    old_wd.unlink()
    changed.append("removed StallWatchdog.java")
    print("applied: removed StallWatchdog.java (debug helper)")

# 5b. Small helper: run a call that might hang on a helper thread, wait at most timeoutMs.
BOUNDED_SOURCE = """package com.world.cloudxsolution;

/**
 * Written by tools/apply_fixes.py.
 * Runs a call that might hang on a helper thread and waits at most timeoutMs, so one stuck
 * step cannot freeze the caller (which would show as "app isn't responding").
 */
final class BoundedCall {
    private BoundedCall() {
    }

    static boolean run(final String process, final String label, long timeoutMs, final Runnable work) {
        Thread t = new Thread(new Runnable() {
            @Override
            public void run() {
                try {
                    work.run();
                } catch (Throwable e) {
                    DiagnosticLog.logException(process, "bounded_" + label, e);
                }
            }
        }, "bounded-" + label);
        t.setDaemon(true);
        t.start();
        try {
            t.join(timeoutMs);
        } catch (InterruptedException ignored) {
        }
        if (t.isAlive()) {
            DiagnosticLog.log(process, "bounded_timeout_" + label, "still running after " + timeoutMs + " ms; continuing");
            return false;
        }
        return true;
    }
}
"""
bp = ROOT / BOUNDED
if bp.exists() and bp.read_text(encoding="utf-8") == BOUNDED_SOURCE:
    print("skip (already applied): BoundedCall.java")
else:
    bp.write_text(BOUNDED_SOURCE, encoding="utf-8")
    changed.append("BoundedCall.java")
    print("applied: BoundedCall.java (new file)")

# 5c. THE FIX: the statistics request no longer runs on the video render thread.
OLD_LOG_CALLBACK = """    @Override
    public void onLogMessage(String message, Logging.Severity severity, String tag) {

        if (showStats && message != null && message.startsWith("stream-rendererDuration:") && peerConnection != null) {
            try {
                peerConnection.getStats(report -> {
                    String stats = buildLiveNetworkStatsString(report);
                    if (signalingListener != null) {
                        signalingListener.onPerformanceStatsReceived(stats);
                    }
                });
            } catch (Exception e) {
                Log.e(TAG, "Failed to collect live stats", e);
                DiagnosticLog.logException("stream", "getStats_fail", e);
            }
        }
    }
"""
NEW_LOG_CALLBACK = """    private final java.util.concurrent.atomic.AtomicBoolean statsInFlight =
            new java.util.concurrent.atomic.AtomicBoolean(false);
    private final java.util.concurrent.ExecutorService statsExecutor =
            java.util.concurrent.Executors.newSingleThreadExecutor(r -> {
                Thread t = new Thread(r, "stats-collector");
                t.setDaemon(true);
                return t;
            });

    @Override
    public void onLogMessage(String message, Logging.Severity severity, String tag) {
        // This callback runs on the video render thread while it holds a lock that frame
        // delivery needs. A blocking WebRTC call here can freeze the video, so the stats
        // request is handed to a helper thread, one at a time (skipped while one is pending).
        if (showStats && message != null && message.startsWith("stream-rendererDuration:") && peerConnection != null) {
            final PeerConnection pcForStats = peerConnection;
            if (statsInFlight.compareAndSet(false, true)) {
                statsExecutor.execute(() -> {
                    try {
                        if (pcForStats != peerConnection) {
                            statsInFlight.set(false);
                            return;
                        }
                        pcForStats.getStats(report -> {
                            try {
                                String stats = buildLiveNetworkStatsString(report);
                                if (signalingListener != null) {
                                    signalingListener.onPerformanceStatsReceived(stats);
                                }
                            } finally {
                                statsInFlight.set(false);
                            }
                        });
                    } catch (Exception e) {
                        statsInFlight.set(false);
                        Log.e(TAG, "Failed to collect live stats", e);
                        DiagnosticLog.logException("stream", "getStats_fail", e);
                    }
                });
            }
        }
    }
"""
edit(WEBRTC, OLD_LOG_CALLBACK, NEW_LOG_CALLBACK,
     "move the stats request off the video render thread (the freeze fix)")

# 5d. Safety net: Exit game / surface teardown can no longer hang the whole app.
edit(SERVICE,
     "                    remoteTrack.removeSink(webRtcReceiver.getPendingRenderTarget());\n",
     "                    final VideoTrack trackToDetach = remoteTrack;\n"
     "                    BoundedCall.run(\"stream\", \"remove_sink\", 800,\n"
     "                            () -> trackToDetach.removeSink(webRtcReceiver.getPendingRenderTarget()));\n",
     "bounded wait when detaching the video sink")

edit(SERVICE,
     "                eglRenderer.release();\n                eglRenderer = null;\n            }\n"
     "            if (serviceEglBase != null) {\n                serviceEglBase.release();\n                serviceEglBase = null;\n            }\n",
     "                final org.webrtc.EglRenderer rendererToRelease = eglRenderer;\n"
     "                eglRenderer = null;\n"
     "                final EglBase eglBaseToRelease = serviceEglBase;\n"
     "                serviceEglBase = null;\n"
     "                BoundedCall.run(\"stream\", \"egl_release\", 800, () -> {\n"
     "                    rendererToRelease.release();\n"
     "                    if (eglBaseToRelease != null) eglBaseToRelease.release();\n"
     "                });\n"
     "            }\n"
     "            if (serviceEglBase != null) {\n"
     "                final EglBase eglBaseOnly = serviceEglBase;\n"
     "                serviceEglBase = null;\n"
     "                BoundedCall.run(\"stream\", \"egl_base_release\", 800, () -> eglBaseOnly.release());\n"
     "            }\n",
     "bounded wait when releasing the video renderer")

edit(SERVICE,
     "        public void closeSession() {\n            clearRenderSurface();\n            webRtcReceiver.closeSession();\n        }\n",
     "        public void closeSession() {\n"
     "            clearRenderSurface();\n"
     "            BoundedCall.run(\"stream\", \"webrtc_closeSession\", 1200, () -> webRtcReceiver.closeSession());\n"
     "        }\n",
     "bounded wait when closing the WebRTC session")

# ---- 6. THE SMALL LEAK: the 3-second logger loop was never stopped -----------------------
edit(SERVICE,
     "    private volatile boolean nativeGamepadEnabledMirror = false;\n",
     "    private volatile boolean nativeGamepadEnabledMirror = false;\n    private Runnable memSnapshotRunnable;\n",
     "leak fix (service): keep a handle on the logger loop")
edit(SERVICE,
     "        final Runnable memSnapshot = new Runnable() {\n",
     "        memSnapshotRunnable = new Runnable() {\n",
     "leak fix (service): loop becomes a field")
edit(SERVICE,
     "        callbackHandler.postDelayed(memSnapshot, 3000);\n",
     "        callbackHandler.postDelayed(memSnapshotRunnable, 3000);\n",
     "leak fix (service): start the field loop")
edit(SERVICE,
     "        callbacks.kill();\n        super.onDestroy();\n",
     "        if (callbackHandler != null && memSnapshotRunnable != null) callbackHandler.removeCallbacks(memSnapshotRunnable);\n"
     "        callbacks.kill();\n        super.onDestroy();\n",
     "leak fix (service): stop the loop when the service stops")

edit(JAVA,
     "        final Handler diagHandler = new Handler(Looper.getMainLooper());\n        final Runnable memSnapshot = new Runnable() {\n",
     "        diagHandler = new Handler(Looper.getMainLooper());\n        memSnapshotRunnable = new Runnable() {\n",
     "leak fix (app): logger loop becomes a field")
edit(JAVA,
     "        diagHandler.postDelayed(memSnapshot, 3000);\n",
     "        diagHandler.postDelayed(memSnapshotRunnable, 3000);\n",
     "leak fix (app): start the field loop")
edit(JAVA,
     "        super.onDestroy();\n",
     "        if (diagHandler != null && memSnapshotRunnable != null) diagHandler.removeCallbacks(memSnapshotRunnable);\n"
     "        super.onDestroy();\n",
     "leak fix (app): stop the loop when the screen is destroyed")

# ---- 7. ASPECT RATIO BUTTON in the in-game menu ----------------------------------------
# Verified in your logs: the stream arrives as 1920x1080 (16:9) and the app draws it onto the
# full 2400x1080 phone surface, which is the stretch you see. This button changes only the size
# of the video box on your phone (client side): 16:9, 18:9, or Stretch (full screen = as before).
edit(JAVA,
     '    private static final String KEY_USE_UNRELIABLE_INPUT = "use_unreliable_input";\n',
     '    private static final String KEY_USE_UNRELIABLE_INPUT = "use_unreliable_input";\n'
     '    private static final String KEY_ASPECT_MODE = "aspect_mode";\n',
     "aspect ratio: preference key")

ASPECT_CODE = """    // ---- Aspect ratio + small helpers (added by apply_fixes.py) ----
    private Handler diagHandler;
    private Runnable memSnapshotRunnable;
    private int aspectMode = 0; // 0 = Stretch (full screen, the original look), 1 = 16:9, 2 = 18:9

    private String aspectModeLabel() {
        switch (aspectMode) {
            case 1:
                return "Aspect ratio: 16:9";
            case 2:
                return "Aspect ratio: 18:9";
            default:
                return "Aspect ratio: Stretch (full screen)";
        }
    }

    private void cycleAspectMode() {
        aspectMode = (aspectMode + 1) % 3;
        getSharedPreferences(PREFS_NAME, MODE_PRIVATE).edit().putInt(KEY_ASPECT_MODE, aspectMode).apply();
        applyAspectMode();
    }

    /** Sizes the video box: fit inside the screen at the chosen ratio, centred; black elsewhere. */
    private void applyAspectMode() {
        if (rootLayout == null || surfaceView == null) return;
        int w = rootLayout.getWidth();
        int h = rootLayout.getHeight();
        if (w <= 0 || h <= 0) return;
        float target = aspectMode == 1 ? 16f / 9f : (aspectMode == 2 ? 2f : 0f);
        int newW = ViewGroup.LayoutParams.MATCH_PARENT;
        int newH = ViewGroup.LayoutParams.MATCH_PARENT;
        if (target > 0f) {
            if ((float) w / (float) h >= target) {
                newH = h;
                newW = Math.round(h * target);
            } else {
                newW = w;
                newH = Math.round(w / target);
            }
        }
        FrameLayout.LayoutParams lp = (FrameLayout.LayoutParams) surfaceView.getLayoutParams();
        if (lp.width != newW || lp.height != newH) {
            lp.width = newW;
            lp.height = newH;
            lp.gravity = android.view.Gravity.CENTER;
            surfaceView.setLayoutParams(lp);
        }
    }

    /** Quietly records how the app's previous processes ended (Android 11+), to the debug log only. */
    private void logPreviousExits() {
        if (Build.VERSION.SDK_INT < 30) return;
        try {
            android.app.ActivityManager am =
                    (android.app.ActivityManager) getSystemService(Context.ACTIVITY_SERVICE);
            java.util.List<android.app.ApplicationExitInfo> exits = am.getHistoricalProcessExitReasons(null, 0, 3);
            if (exits == null || exits.isEmpty()) return;
            StringBuilder sb = new StringBuilder();
            for (android.app.ApplicationExitInfo e : exits) {
                sb.append(e.getProcessName()).append(" reason=").append(e.getReason())
                        .append(" (").append(e.getDescription()).append(") ")
                        .append((System.currentTimeMillis() - e.getTimestamp()) / 60000).append(" min ago\\n");
            }
            DiagnosticLog.log("main", "previous_exits", sb.toString().trim());
        } catch (Throwable ignored) {
        }
    }

"""
edit(JAVA,
     "    private void pushSurfaceIfReady() {\n",
     ASPECT_CODE + "    private void pushSurfaceIfReady() {\n",
     "aspect ratio: logic")

edit(JAVA,
     "        surfaceView = findViewById(R.id.surfaceView);\n",
     "        surfaceView = findViewById(R.id.surfaceView);\n"
     "        aspectMode = getSharedPreferences(PREFS_NAME, MODE_PRIVATE).getInt(KEY_ASPECT_MODE, 0);\n"
     "        rootLayout.setBackgroundColor(android.graphics.Color.BLACK);\n"
     "        rootLayout.addOnLayoutChangeListener((v, left, top, right, bottom, oldLeft, oldTop, oldRight, oldBottom) -> {\n"
     "            if ((right - left) != (oldRight - oldLeft) || (bottom - top) != (oldBottom - oldTop)) {\n"
     "                rootLayout.post(this::applyAspectMode);\n"
     "            }\n"
     "        });\n",
     "aspect ratio: load saved choice and follow screen size changes")

edit(JAVA,
     "        setContentView(R.layout.activity_main);\n",
     "        setContentView(R.layout.activity_main);\n        logPreviousExits();\n",
     "record how the app last stopped (log only)")

edit(JAVA,
     "        btnExportDiagLog.setOnClickListener(v -> exportDiagnosticLog());\n",
     "        btnExportDiagLog.setOnClickListener(v -> exportDiagnosticLog());\n"
     "        Button btnAspect = dialog.findViewById(R.id.btn_aspect_ratio);\n"
     "        btnAspect.setText(aspectModeLabel());\n"
     "        btnAspect.setOnClickListener(v -> {\n"
     "            cycleAspectMode();\n"
     "            btnAspect.setText(aspectModeLabel());\n"
     "        });\n",
     "aspect ratio: button wiring")

edit(JAVA,
     "            btnMic.setVisibility(View.GONE);\n",
     "            btnMic.setVisibility(View.GONE);\n            btnAspect.setVisibility(View.GONE);\n",
     "aspect ratio: hide the button when no game is running")

edit(LAYOUT + "dialog_streaming_menu.xml",
     '    <androidx.appcompat.widget.AppCompatButton\n        android:id="@+id/btn_settings"\n',
     '    <androidx.appcompat.widget.AppCompatButton\n'
     '        android:id="@+id/btn_aspect_ratio"\n'
     '        android:layout_width="match_parent"\n'
     '        android:layout_height="wrap_content"\n'
     '        android:text="Aspect ratio: Stretch (full screen)"\n'
     '        android:textColor="@color/selector_text_xbox"\n'
     '        android:textAllCaps="false"\n'
     '        android:textSize="14sp"\n'
     '        android:gravity="start|center_vertical"\n'
     '        android:paddingStart="16dp"\n'
     '        android:paddingTop="12dp"\n'
     '        android:paddingBottom="12dp"\n'
     '        android:background="@drawable/selector_button_xbox"\n'
     '        android:focusable="true"\n'
     '        android:layout_marginBottom="6dp"/>\n\n'
     '    <androidx.appcompat.widget.AppCompatButton\n        android:id="@+id/btn_settings"\n',
     "aspect ratio: menu button")

print("\nDone." if changed else "\nNothing to change.")
