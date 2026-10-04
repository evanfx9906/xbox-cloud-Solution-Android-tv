#!/usr/bin/env python3
"""
Edits for the CloudX fork (version v5).

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

BUILD_STAMP = "v5"
BASE = "72dc66f"

ROOT = pathlib.Path(__file__).resolve().parent.parent
JAVA_DIR = "app/src/main/java/com/world/cloudxsolution/"
JAVA = JAVA_DIR + "MainActivity.java"
DIAGLOG = JAVA_DIR + "DiagnosticLog.java"
SERVICE = JAVA_DIR + "StreamingService.java"
WATCHDOG = JAVA_DIR + "StallWatchdog.java"   # new file, written by this script
LAYOUT = "app/src/main/res/layout/"
MANIFEST = "app/src/main/AndroidManifest.xml"
GRADLE = "app/build.gradle.kts"
STRINGS = "app/src/main/res/values/strings.xml"

OWNED = [
    MANIFEST, JAVA, DIAGLOG, SERVICE, GRADLE, STRINGS,
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

# ---- 5. CRASH DIAGNOSTICS (read-only, except one safety net, see 5c) ----------------
# 5a. Popup at startup: why did each app process last stop? (Android 11+)
DIAG_HELPERS = '''    // ---- Crash diagnostics (added by apply_fixes.py) ----
    private void showDiagnostic(String title, String text) {
        new androidx.appcompat.app.AlertDialog.Builder(this)
                .setTitle(title)
                .setMessage(text)
                .setPositiveButton("OK", null)
                .show();
    }

    private void diagShowLastExits() {
        if (Build.VERSION.SDK_INT < 30) return;
        try {
            android.app.ActivityManager am =
                    (android.app.ActivityManager) getSystemService(Context.ACTIVITY_SERVICE);
            java.util.List<android.app.ApplicationExitInfo> exits =
                    am.getHistoricalProcessExitReasons(null, 0, 5);
            if (exits == null || exits.isEmpty()) return;
            long now = System.currentTimeMillis();
            StringBuilder sb = new StringBuilder();
            for (android.app.ApplicationExitInfo e : exits) {
                String reason;
                switch (e.getReason()) {
                    case android.app.ApplicationExitInfo.REASON_CRASH: reason = "CRASH (Java exception)"; break;
                    case android.app.ApplicationExitInfo.REASON_CRASH_NATIVE: reason = "CRASH_NATIVE"; break;
                    case android.app.ApplicationExitInfo.REASON_ANR: reason = "ANR (not responding)"; break;
                    case android.app.ApplicationExitInfo.REASON_LOW_MEMORY: reason = "LOW_MEMORY (killed by system)"; break;
                    case android.app.ApplicationExitInfo.REASON_SIGNALED: reason = "SIGNALED (killed)"; break;
                    case android.app.ApplicationExitInfo.REASON_EXCESSIVE_RESOURCE_USAGE: reason = "EXCESSIVE_RESOURCE_USAGE"; break;
                    case android.app.ApplicationExitInfo.REASON_USER_REQUESTED: reason = "USER_REQUESTED"; break;
                    case android.app.ApplicationExitInfo.REASON_USER_STOPPED: reason = "USER_STOPPED"; break;
                    case android.app.ApplicationExitInfo.REASON_EXIT_SELF: reason = "EXIT_SELF"; break;
                    case android.app.ApplicationExitInfo.REASON_DEPENDENCY_DIED: reason = "DEPENDENCY_DIED"; break;
                    case android.app.ApplicationExitInfo.REASON_PERMISSION_CHANGE: reason = "PERMISSION_CHANGE"; break;
                    case android.app.ApplicationExitInfo.REASON_INITIALIZATION_FAILURE: reason = "INITIALIZATION_FAILURE"; break;
                    case android.app.ApplicationExitInfo.REASON_OTHER: reason = "OTHER"; break;
                    default: reason = "code " + e.getReason();
                }
                sb.append(e.getProcessName()).append(" - ").append(reason)
                        .append("\\n   ").append((now - e.getTimestamp()) / 60000).append(" min ago")
                        .append(", status ").append(e.getStatus())
                        .append(", rss ").append(e.getRss() / 1024).append(" MB")
                        .append("\\n   ").append(e.getDescription()).append("\\n\\n");
            }
            String text = sb.toString().trim();
            DiagnosticLog.log("main", "previous_exits", text);
            showDiagnostic("Build ''' + BUILD_STAMP + ''' - how the app last stopped", text);
        } catch (Throwable t) {
            DiagnosticLog.logException("main", "exit_info_fail", t);
        }
    }

    @Override
    public void onTrimMemory(int level) {
        super.onTrimMemory(level);
        DiagnosticLog.log("main", "onTrimMemory", "level=" + level);
    }

'''
edit(JAVA,
     "private boolean debug=false;\n    public void showCustomToast",
     DIAG_HELPERS + "private boolean debug=false;\n    public void showCustomToast",
     "crash diagnostics helpers")

edit(JAVA,
     "        setContentView(R.layout.activity_main);\n",
     "        setContentView(R.layout.activity_main);\n"
     "        new Handler(Looper.getMainLooper()).postDelayed(this::diagShowLastExits, 2000);\n"
     "        StallWatchdog.startMainThreadWatch(\"main\");\n",
     "show how the app last stopped, at startup")

# 5b. Memory telemetry in BOTH processes (the 3-second snapshot already exists)
edit(DIAGLOG,
     '            mem.put("maxMB", rt.maxMemory() / (1024 * 1024));\n',
     '            mem.put("maxMB", rt.maxMemory() / (1024 * 1024));\n'
     '            try {\n'
     '                mem.put("pssMB", android.os.Debug.getPss() / 1024);\n'
     '                mem.put("nativeHeapMB", android.os.Debug.getNativeHeapAllocatedSize() / (1024 * 1024));\n'
     '                String[] fds = new java.io.File("/proc/self/fd").list();\n'
     '                mem.put("openFds", fds == null ? -1 : fds.length);\n'
     '                try (java.io.BufferedReader br = new java.io.BufferedReader(new java.io.FileReader("/proc/self/status"))) {\n'
     '                    String line;\n'
     '                    while ((line = br.readLine()) != null) {\n'
     '                        if (line.startsWith("Threads:")) mem.put("threads", line.substring(8).trim());\n'
     '                    }\n'
     '                }\n'
     '            } catch (Throwable ignored) {\n'
     '            }\n',
     "memory telemetry: PSS, native heap, open files, threads")

# 5c. The one behaviour change: if the WebView's renderer process dies, keep the app
# alive instead of letting Android close it (per Android's WebView termination docs).
edit(JAVA,
     "        webView.setWebViewClient(new WebViewClient() {\n",
     "        webView.setWebViewClient(new WebViewClient() {\n"
     "            @Override\n"
     "            public boolean onRenderProcessGone(WebView view, android.webkit.RenderProcessGoneDetail detail) {\n"
     "                final String info = \"didCrash=\" + detail.didCrash()\n"
     "                        + \" (false = killed by the system, usually low memory)\";\n"
     "                DiagnosticLog.log(\"main\", \"RENDER_PROCESS_GONE\", info);\n"
     "                runOnUiThread(() -> showDiagnostic(\"Build " + BUILD_STAMP + " - WebView process died\", info));\n"
     "                return true;\n"
     "            }\n\n",
     "survive a WebView renderer death and report it")


# ---- 6. HANG DIAGNOSIS + SAFEGUARD (your "Exit game" freeze) ------------------------
# Evidence (from your logs): Exit game calls closeSession() on the UI thread, a blocking
# cross-process call. In the failing run the service logged the start of the call but never
# the "ICE CLOSED" that a normal exit logs, and the app's own heartbeat stopped. So the
# call did not return. These edits (a) record exactly where it is stuck and (b) stop one
# stuck step from freezing the UI thread, by waiting at most a few seconds for it.
WATCHDOG_SOURCE = '''package com.world.cloudxsolution;

import android.os.Handler;
import android.os.Looper;
import android.os.SystemClock;

import java.util.Map;
import java.util.concurrent.atomic.AtomicLong;

/**
 * Diagnostics helper (written by tools/apply_fixes.py).
 *  - startMainThreadWatch: logs a stack dump if the main thread stops responding.
 *  - runBounded: runs a call that might hang on a helper thread and waits at most
 *    timeoutMs, so one stuck step cannot freeze the caller (an ANR).
 *  - flow counters: video frames received and input messages sent.
 */
final class StallWatchdog {
    static final AtomicLong framesIn = new AtomicLong();
    static final AtomicLong inputSends = new AtomicLong();
    private static long lastFrames;
    private static long lastInputs;
    private static volatile long lastBeat = SystemClock.uptimeMillis();
    private static boolean started;

    private StallWatchdog() {
    }

    static synchronized String flowSnapshot() {
        long f = framesIn.get();
        long i = inputSends.get();
        String s = "framesIn +" + (f - lastFrames) + " (total " + f + ") | inputSends +" + (i - lastInputs) + " (total " + i + ")";
        lastFrames = f;
        lastInputs = i;
        return s;
    }

    static synchronized void startMainThreadWatch(final String process) {
        if (started) return;
        started = true;
        final Handler main = new Handler(Looper.getMainLooper());
        main.post(new Runnable() {
            @Override
            public void run() {
                lastBeat = SystemClock.uptimeMillis();
                main.postDelayed(this, 1000);
            }
        });
        Thread t = new Thread(new Runnable() {
            @Override
            public void run() {
                boolean reported = false;
                while (true) {
                    try {
                        Thread.sleep(1000);
                    } catch (InterruptedException e) {
                        return;
                    }
                    long stalled = SystemClock.uptimeMillis() - lastBeat;
                    if (stalled > 3000 && !reported) {
                        reported = true;
                        DiagnosticLog.log(process, "MAIN_THREAD_STALLED", "main thread not responding for " + stalled + " ms");
                        dumpAll(process, "main_thread_stalled");
                    } else if (stalled < 1500) {
                        reported = false;
                    }
                }
            }
        }, "stall-watchdog");
        t.setDaemon(true);
        t.start();
    }

    static boolean runBounded(final String process, final String label, long timeoutMs, final Runnable work) {
        final long start = SystemClock.uptimeMillis();
        Thread t = new Thread(new Runnable() {
            @Override
            public void run() {
                try {
                    work.run();
                } catch (Throwable e) {
                    DiagnosticLog.logException(process, "bounded_" + label + "_EXCEPTION", e);
                }
            }
        }, "bounded-" + label);
        t.setDaemon(true);
        t.start();
        try {
            t.join(timeoutMs);
        } catch (InterruptedException ignored) {
        }
        long took = SystemClock.uptimeMillis() - start;
        if (t.isAlive()) {
            DiagnosticLog.log(process, "BOUNDED_TIMEOUT_" + label, "still running after " + took + " ms; continuing without waiting");
            dumpAll(process, label);
            return false;
        }
        if (took > 300) {
            DiagnosticLog.log(process, "bounded_slow_" + label, "took " + took + " ms");
        }
        return true;
    }

    static void dumpAll(String process, String reason) {
        try {
            StringBuilder sb = new StringBuilder("stack dump (" + reason + ")\\n");
            for (Map.Entry<Thread, StackTraceElement[]> e : Thread.getAllStackTraces().entrySet()) {
                StackTraceElement[] st = e.getValue();
                if (st.length == 0) continue;
                String name = e.getKey().getName();
                if (name.contains("Daemon") || name.contains("Signal Catcher") || name.contains("Jit")
                        || name.contains("ReferenceQueue") || name.contains("perfetto") || name.contains("Profile Saver")) continue;
                if (st[0].getMethodName().equals("nativePollOnce")) continue;
                sb.append("[").append(name).append("] ").append(e.getKey().getState()).append('\\n');
                for (int i = 0; i < Math.min(st.length, 12); i++) {
                    sb.append("   at ").append(st[i]).append('\\n');
                }
                if (sb.length() > 40000) {
                    sb.append("...truncated\\n");
                    break;
                }
            }
            DiagnosticLog.log(process, "STACK_DUMP_" + reason, sb.toString());
        } catch (Throwable ignored) {
            // diagnostics must never crash the app
        }
    }
}
'''

wp = ROOT / WATCHDOG
if wp.exists() and wp.read_text(encoding="utf-8") == WATCHDOG_SOURCE:
    print("skip (already applied): StallWatchdog.java")
else:
    wp.write_text(WATCHDOG_SOURCE, encoding="utf-8")
    changed.append("StallWatchdog.java")
    print("applied: StallWatchdog.java (new file)")

# 6a. Bound the two steps that can block: releasing the video renderer, and closing WebRTC.
edit(SERVICE,
     "                eglRenderer.release();\n                eglRenderer = null;\n            }\n"
     "            if (serviceEglBase != null) {\n                serviceEglBase.release();\n                serviceEglBase = null;\n            }\n",
     "                final org.webrtc.EglRenderer rendererToRelease = eglRenderer;\n"
     "                eglRenderer = null;\n"
     "                final EglBase eglBaseToRelease = serviceEglBase;\n"
     "                serviceEglBase = null;\n"
     "                StallWatchdog.runBounded(\"stream\", \"egl_release\", 1200, () -> {\n"
     "                    rendererToRelease.release();\n"
     "                    if (eglBaseToRelease != null) eglBaseToRelease.release();\n"
     "                });\n"
     "            }\n"
     "            if (serviceEglBase != null) {\n"
     "                final EglBase eglBaseOnly = serviceEglBase;\n"
     "                serviceEglBase = null;\n"
     "                StallWatchdog.runBounded(\"stream\", \"egl_base_release\", 1200, () -> eglBaseOnly.release());\n"
     "            }\n",
     "bounded wait when releasing the video renderer")

edit(SERVICE,
     "        public void closeSession() {\n            clearRenderSurface();\n            webRtcReceiver.closeSession();\n        }\n",
     "        public void closeSession() {\n"
     "            DiagnosticLog.log(\"stream\", \"closeSession_begin\", \"thread=\" + Thread.currentThread().getName());\n"
     "            clearRenderSurface();\n"
     "            StallWatchdog.runBounded(\"stream\", \"webrtc_closeSession\", 1800, () -> webRtcReceiver.closeSession());\n"
     "            DiagnosticLog.log(\"stream\", \"closeSession_end\", \"\");\n"
     "        }\n",
     "bounded wait when closing the WebRTC session")

# 6b. Flow counters: are video frames arriving, are controller inputs being sent?
edit(SERVICE,
     "                    if (eglRenderer != null) {\n                        eglRenderer.onFrame(frame);\n                    }\n",
     "                    StallWatchdog.framesIn.incrementAndGet();\n"
     "                    if (eglRenderer != null) {\n                        eglRenderer.onFrame(frame);\n                    }\n",
     "count video frames received")
edit(SERVICE,
     "        public void onDataChannelSend(String label, byte[] binary, String data, boolean isBinary) {\n            if (binary != null) {\n",
     "        public void onDataChannelSend(String label, byte[] binary, String data, boolean isBinary) {\n"
     "            StallWatchdog.inputSends.incrementAndGet();\n"
     "            if (binary != null) {\n",
     "count controller messages sent")
edit(SERVICE,
     "                DiagnosticLog.logMemory(\"stream\");\n                callbackHandler.postDelayed(this, 3000);\n",
     "                DiagnosticLog.logMemory(\"stream\");\n"
     "                DiagnosticLog.log(\"stream\", \"flow\", StallWatchdog.flowSnapshot());\n"
     "                callbackHandler.postDelayed(this, 3000);\n",
     "log frame/input flow every 3 s")
edit(SERVICE,
     "    public void onDataChannelStateChanged(String label, String state) {\n"
     "        broadcast(cb -> safe(() -> cb.onDataChannelStateChanged(label, state)));\n",
     "    public void onDataChannelStateChanged(String label, String state) {\n"
     "        DiagnosticLog.log(\"stream\", \"datachannel_state\", label + \" = \" + state);\n"
     "        broadcast(cb -> safe(() -> cb.onDataChannelStateChanged(label, state)));\n",
     "log data channel (controller input) state")

print("\nDone." if changed else "\nNothing to change.")
