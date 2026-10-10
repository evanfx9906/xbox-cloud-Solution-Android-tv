#!/usr/bin/env python3
"""
Edits for the CloudX fork, LAB BRANCH copy of the final v8 script.
Only difference from the main-branch script: the app installs as a SEPARATE app
(package suffix .lab, label "Xbox Lab") so it never touches the working app (.fixed).

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
     "    buildTypes {\n        debug {\n            applicationIdSuffix = \".lab\"\n        }\n        release {\n",
     "debug build installs as a separate app (.lab)")
edit(STRINGS,
     '<string name="app_name">cloudxSolution</string>',
     '<string name="app_name">Xbox Lab</string>',
     "app label 'Xbox Lab'")

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


# ---- 8. LAB ONLY (probe v5): probe + market experiment + offering analysis for the new Xbox site (play.xbox.com) -----------------------------
# Purpose: find out what the new site does inside this app, WITHOUT streaming through it yet.
# The old site script (index.js) is switched off in this lab app. A small diagnostics script
# (assets/probe.js) runs at document start and records addresses (host + path only), request
# kinds and statuses, workers, WebRTC use, page replacement, and a few yes/no page hints.
# It never records cookies, header values (except the market), bodies, tokens, page text or account names.
# EXPERIMENT: the market the page sends (GR) is rewritten to the app's Server Region setting.
PROBE_JS = r'''/* Xbox Lab probe v5 (diagnostics + market experiment + offering analysis). Runs at document start on play.xbox.com / www.xbox.com.
 * Records WHAT the page does, never what it contains: no cookies, headers, bodies, tokens, query
 * strings, fragments, page text or account names. Addresses are reduced to host + path with
 * id-like path pieces masked. Output goes to console.log("[LABPROBE] ...") and the app writes it
 * to its debug log.
 * EXPERIMENT (v3): rewrites the market the page sends (market=GR, locale=xx-GR, x-xbl-market header) to
 * the market chosen in the app's Server Region setting, to test whether the server trusts it. */
(function () {
  try {
    if (window.__labProbe) return;
    window.__labProbe = true;

    var T0 = Date.now();
    var isTop = (window === window.top);
    var buf = [];
    var counts = {};
    var sent = 0;
    var MAX_EVENTS = 500;

    function maskPiece(s) {
      s = String(s);
      s = s.replace(/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/ig, '{guid}');
      s = s.replace(/[0-9a-f]{16,}/ig, '{hex}');
      s = s.replace(/[0-9]{6,}/g, '{num}');
      if (s.length > 40) return '{long}';
      return s;
    }
    function maskPath(p) {
      return String(p || '').split('/').map(maskPiece).join('/');
    }

    function safeUrl(u) {
      try {
        var s = String(u);
        if (/^blob:/i.test(s)) return 'blob:';
        if (/^data:/i.test(s)) return 'data:';
        var a = new URL(s, location.href);
        return a.protocol + '//' + a.host + maskPath(a.pathname);
      } catch (e) {
        return 'unparsable';
      }
    }

    var VALUE_PARAMS = /^(market|mkt|locale|language|languages|lang|country|countrycode|region|culture|geo|clientlocale|clientcountry|clientlanguage|offering|offerings|offeringid)$/i;
    var seenReq = {};
    function reqDetail(u, init, input) {
      try {
        var s = String(u);
        if (/^(blob|data):/i.test(s)) return null;
        var a = new URL(s, location.href);
        if (!/(xboxservices\.com|xboxlive\.com|gamepass\.com|xbox\.com)$/i.test(a.hostname)) return null;
        var names = [];
        a.searchParams.forEach(function (v, k) {
          if (VALUE_PARAMS.test(k) && /^[A-Za-z0-9_,\-]{1,14}$/.test(v)) names.push(k + '=' + v);
          else names.push(k);
        });
        var hdrs = [];
        var h = (init && init.headers) || (input && input.headers);
        if (h) {
          if (typeof h.forEach === 'function' && !Array.isArray(h)) h.forEach(function (v, k) { hdrs.push(String(k).toLowerCase()); });
          else if (Array.isArray(h)) h.forEach(function (p) { hdrs.push(String(p[0]).toLowerCase()); });
          else Object.keys(h).forEach(function (k) { hdrs.push(k.toLowerCase()); });
        }
        var key = a.hostname + maskPath(a.pathname);
        if (seenReq[key]) return null;
        seenReq[key] = 1;
        return 'params[' + names.join(',') + '] headers[' + hdrs.join(',') + ']';
      } catch (e) { return null; }
    }

    var OK_KEYS = /^(id|offering|offerings|offeringid|offeringids|hasaccess|access|allowed|isavailable|tier|subscription|type|name|kind|state|status|market|region|regions|country|countrycode|locale|culture|language|lang|code|availability|reason|message|action|actions|platform|platforms|cloud|isxcloud|xcloud|supported|enabled|available|iscloud|offeringsettings|allowregionselection|isdefaultregion)$/i;
    function maskKey(k) { return maskPiece(k); }
    function scrubValue(v) {
      var t = String(v);
      if (/^https?:\/\//i.test(t)) { try { return new URL(t).host; } catch (e) { return 'url'; } }
      return maskPiece(scrub(t).replace(/[^\s@"]+@[^\s@"]+/g, '{email}')).slice(0, 60);
    }
    function shape(v, depth, key) {
      if (v === null) return 'null';
      var t = typeof v;
      if (t === 'string') return OK_KEYS.test(key || '') ? JSON.stringify(scrubValue(v)) : 'str';
      if (t === 'number' || t === 'boolean') return OK_KEYS.test(key || '') ? String(v) : t;
      if (Array.isArray(v)) {
        var kinds = '';
        if (v.length && /^(actions|sections|layouts|rows|tiles|offerings|items|results|data|value|values)$/i.test(key || '')) {
          kinds = ' kinds=[' + v.slice(0, 12).map(function (e) {
            var x = e && (e.type || e.actionType || e.kind || e.name || e.id || e.offeringId || e.offering);
            return typeof x === 'string' ? scrubValue(x).slice(0, 30) : '?';
          }).join('|') + ']';
        }
        return 'arr[' + v.length + ']' + kinds + ((v.length && depth <= 3) ? '<' + shape(v[0], depth + 1, key) + '>' : '');
      }
      if (t === 'object') {
        if (depth > 3) return '{..}';
        var ks = Object.keys(v);
        return '{' + ks.slice(0, 30).map(function (k) { return maskKey(k) + ':' + shape(v[k], depth + 1, k); }).join(',') + (ks.length > 30 ? ',..' + ks.length : '') + '}';
      }
      return t;
    }
    var SHAPE_URLS = /(xCloudWebHome|\/api\/details\/[^\/]+\/actions|catalog\.gamepass\.com\/sigls\/v3|contentaccess\.exp\.xboxservices\.com\/all\/v1|title\.mgt\.xboxlive\.com\/titles\/default\/endpoints)/;
    var shapeCount = {};
    var OFFER_URL = /contentaccess\.exp\.xboxservices\.com\/all\/v1/;
    function captureOffering(tag, urlStr, r, input, init) {
      try {
        if (!OFFER_URL.test(urlStr)) return false;
        var hsrc = (init && init.headers) ? init.headers : ((typeof Request === 'function' && input instanceof Request) ? input.headers : null);
        var ct = r.headers && r.headers.get ? r.headers.get('content-type') : '';
        r.clone().arrayBuffer().then(function (buf) {
          var u8 = new Uint8Array(buf);
          emit('offer_baseline', r.status + ' ct=' + scrub(ct) + ' ' + describeBinary(u8, true));
          offeringTests(urlStr, hsrc, u8);
        }, function () { });
        return true;
      } catch (e) { return false; }
    }
    function captureShape(tag, urlStr, r) {
      try {
        if (!SHAPE_URLS.test(urlStr)) return;
        var k = tag.replace(/\{[a-z]+\}/g, '');
        shapeCount[k] = (shapeCount[k] || 0) + 1;
        if (shapeCount[k] > 4) return;
        r.clone().json().then(function (j) {
          emit('shape', tag.split(' ')[1].replace(/^https?:\/\//, '') + ' => ' + shape(j, 0, '').slice(0, 1800));
        }, function () { });
      } catch (e) { }
    }

    function scrub(text) {
      return String(text == null ? '' : text).replace(/https?:\/\/\S+/g, '{url}').slice(0, 120);
    }

    function emit(kind, detail) {
      try {
        var key = kind + '|' + detail;
        counts[key] = (counts[key] || 0) + 1;
        if (counts[key] > 1) return;
        if (sent >= MAX_EVENTS) return;
        sent++;
        buf.push({ t: Date.now() - T0, top: isTop, k: kind, d: detail });
      } catch (e) { }
    }

    function flush() {
      try {
        if (!buf.length) return;
        var out = buf.splice(0, buf.length);
        console.log('[LABPROBE] ' + JSON.stringify(out));
      } catch (e) { }
    }

    function summary() {
      try {
        var rows = [];
        Object.keys(counts).forEach(function (k) { if (counts[k] > 2) rows.push([k, counts[k]]); });
        rows.sort(function (a, b) { return b[1] - a[1]; });
        if (rows.length) {
          emit('summary', rows.slice(0, 12).map(function (r) { return r[1] + 'x ' + r[0]; }).join(' ;; ') + ' @' + Math.round((Date.now() - T0) / 1000) + 's');
        }
      } catch (e) { }
    }

    setInterval(flush, 2000);
    setInterval(summary, 30000);
    window.addEventListener('pagehide', function () { summary(); flush(); });

    if (isTop) { emit('market_target', targetMarket() + ' bridge=' + (window.LabBridge ? 'yes' : 'no')); }

    var ref = '';
    try { ref = document.referrer ? new URL(document.referrer).host : ''; } catch (e) { }
    emit('doc_start', location.host + maskPath(location.pathname) + ' referrer=' + ref);

    if (isTop) {
      var brands = '';
      try {
        brands = (navigator.userAgentData && navigator.userAgentData.brands || [])
          .map(function (b) { return b.brand + ' ' + b.version; }).join(',');
      } catch (e) { }
      emit('env', JSON.stringify({
        ua: navigator.userAgent, brands: brands,
        mobile: navigator.userAgentData ? navigator.userAgentData.mobile : null,
        w: window.innerWidth, h: window.innerHeight, dpr: window.devicePixelRatio,
        serviceWorkerApi: !!navigator.serviceWorker,
        lang: navigator.language, langs: (navigator.languages || []).join(','),
        tz: (function () { try { return Intl.DateTimeFormat().resolvedOptions().timeZone; } catch (e) { return ''; } })()
      }));
    }

    // ---- offering analysis (v5) ----
    var BYPASS_IPS = { US: '143.244.47.65', BR: '169.150.198.66', KR: '121.125.60.151', JP: '138.199.21.239',
                       PL: '45.134.212.66', ES: '80.58.61.250', GB: '62.24.134.1', FR: '212.27.40.240' };
    function fnv(u8) {
      var h = 0x811c9dc5;
      for (var i = 0; i < u8.length; i++) { h ^= u8[i]; h = Math.imul(h, 0x01000193); }
      return (h >>> 0).toString(16);
    }
    function findBytes(u8, str) {
      var n = str.length, codes = [];
      for (var k = 0; k < n; k++) codes.push(str.charCodeAt(k));
      for (var i = 0; i + n <= u8.length; i++) {
        var ok = true;
        for (var j = 0; j < n; j++) { if (u8[i + j] !== codes[j]) { ok = false; break; } }
        if (ok) return i;
      }
      return -1;
    }
    function upperTokens(u8) {
      var out = {}, cur = '';
      for (var i = 0; i <= u8.length; i++) {
        var c = i < u8.length ? u8[i] : 0;
        if ((c >= 65 && c <= 90) || (c >= 48 && c <= 57) || c === 95) cur += String.fromCharCode(c);
        else {
          if (cur.length >= 6 && cur.length <= 40 && /[A-Z]/.test(cur) && /^[A-Z]/.test(cur)) out[cur] = (out[cur] || 0) + 1;
          cur = '';
        }
      }
      return out;
    }
    function readVarint(u8, p) {
      var r = 0, mul = 1, b;
      do {
        if (p >= u8.length || mul > 4e15) return null;
        b = u8[p++]; r += (b & 0x7f) * mul; mul *= 128;
      } while (b & 0x80);
      return [r, p];
    }
    function parseMsg(u8, start, end) {
      var fields = [], p = start;
      while (p < end) {
        var t = readVarint(u8, p); if (!t) return null; p = t[1];
        var f = Math.floor(t[0] / 8), wt = t[0] % 8;
        if (f < 1 || f > 100000) return null;
        if (wt === 0) { var v = readVarint(u8, p); if (!v) return null; fields.push({ f: f, wt: 0, v: v[0] }); p = v[1]; }
        else if (wt === 1) { if (p + 8 > end) return null; fields.push({ f: f, wt: 1 }); p += 8; }
        else if (wt === 5) { if (p + 4 > end) return null; fields.push({ f: f, wt: 5 }); p += 4; }
        else if (wt === 2) {
          var l = readVarint(u8, p); if (!l) return null; p = l[1];
          if (p + l[0] > end) return null;
          fields.push({ f: f, wt: 2, s: p, e: p + l[0] }); p += l[0];
        } else return null;
      }
      return p === end ? fields : null;
    }
    function printableText(u8, s, e) {
      if (e - s === 0) return '';
      var n = 0;
      for (var i = s; i < e; i++) { var c = u8[i]; if (c >= 32 && c < 127) n++; }
      if (n / (e - s) < 0.95) return null;
      var t = '';
      for (var j = s; j < Math.min(e, s + 80); j++) t += String.fromCharCode(u8[j]);
      return t;
    }
    // render a length-delimited field: nested message, text, or bytes
    function renderField(u8, fd, depth) {
      var txt = printableText(u8, fd.s, fd.e);
      var nested = (depth < 7 && fd.e - fd.s > 1) ? parseMsg(u8, fd.s, fd.e) : null;
      if (nested && nested.length && (txt === null || fd.e - fd.s > 80 && nested.length > 1)) return renderMsg(u8, nested, depth + 1);
      if (txt !== null) return JSON.stringify(scrubValue(txt));
      return 'bytes[' + (fd.e - fd.s) + ']';
    }
    function renderMsg(u8, fields, depth) {
      var parts = [];
      for (var i = 0; i < fields.length && i < 24; i++) {
        var fd = fields[i];
        if (fd.wt === 0) parts.push(fd.f + ':' + fd.v);
        else if (fd.wt === 2) parts.push(fd.f + ':' + renderField(u8, fd, depth));
        else parts.push(fd.f + ':fixed');
      }
      if (fields.length > 24) parts.push('..+' + (fields.length - 24));
      return '{' + parts.join(' ') + '}';
    }
    // find the message that directly contains the needle string and render it, plus the path of field numbers leading to it
    function describeAround(u8, needle) {
      var idx = findBytes(u8, needle);
      if (idx < 0) return 'needle-not-found';
      var s = 0, e = u8.length, path = [], best = null;
      for (var depth = 0; depth < 10; depth++) {
        var fields = parseMsg(u8, s, e);
        if (!fields) break;
        var hit = null;
        for (var i = 0; i < fields.length; i++) { if (fields[i].wt === 2 && fields[i].s <= idx && idx < fields[i].e) { hit = fields[i]; break; } }
        if (!hit) break;
        path.push(hit.f);
        var child = parseMsg(u8, hit.s, hit.e);
        if (child && child.length > 1) { best = { s: hit.s, e: hit.e, fields: child }; s = hit.s; e = hit.e; }
        else break;
      }
      if (!best) return 'could-not-decode (needle at byte ' + idx + ')';
      return 'path=' + path.join('>') + ' ' + renderMsg(u8, best.fields, 0).slice(0, 1600);
    }
    function describeBinary(u8, withTree) {
      var toks = upperTokens(u8), names = Object.keys(toks).sort();
      var shown = names.slice(0, 50).map(function (t) { return maskPiece(t); }).join('|');
      var cloud = findBytes(u8, 'CLOUDGAMING') >= 0;
      var out = 'bin len=' + u8.length + ' fnv=' + fnv(u8) + ' hasCLOUDGAMING=' + cloud + ' upperTokens=' + names.length + (withTree ? ' [' + shown + ']' : '');
      if (withTree) {
        var rootF = parseMsg(u8, 0, u8.length);
        if (rootF) {
          var counts = {};
          rootF.forEach(function (f) { counts[f.f] = (counts[f.f] || 0) + 1; });
          out += ' rootFields=' + JSON.stringify(counts);
        } else out += ' rootNotProtobuf';
        if (cloud) out += ' AROUND_CLOUDGAMING: ' + describeAround(u8, 'CLOUDGAMING');
      }
      return out;
    }
    function diffSummary(a, b) {
      if (a.length !== b.length) return 'lengthDiffers(' + a.length + ' vs ' + b.length + ')';
      var n = 0, first = -1, last = -1;
      for (var i = 0; i < a.length; i++) { if (a[i] !== b[i]) { n++; if (first < 0) first = i; last = i; } }
      return n + ' bytes differ' + (n ? ' (first ' + first + ', last ' + last + ')' : '');
    }
    function describeBody(t) {   // text bodies (kept for the JSON endpoints)
      try { return 'json ' + shape(JSON.parse(t), 0, '').slice(0, 1500); } catch (e) { }
      return 'non-json text len=' + String(t).length;
    }
    var offerTestsDone = false;
    function offeringTests(urlStr, headersSrc, baseU8) {
      if (offerTestsDone) return;
      offerTestsDone = true;
      var M = '';
      try { M = (window.LabBridge && window.LabBridge.market && window.LabBridge.market()) || ''; } catch (e) { }
      var ip = BYPASS_IPS[M] || BYPASS_IPS.US;
      var real = realMarket || 'GR';
      var tests = [
        ['repeat of the page request', null, null],
        ['market=' + real + ' (your real one)', real, null],
        ['market=ES', 'ES', null], ['market=GB', 'GB', null], ['market=PL', 'PL', null],
        ['x-forwarded-for=' + ip, M || 'US', ['x-forwarded-for', ip]],
        ['forwarded=for=' + ip, M || 'US', ['forwarded', 'for=' + ip]],
        ['clientip=' + ip, M || 'US', ['clientip', ip]]
      ];
      function one(t) {
        var a = new URL(urlStr);
        if (t[1]) a.searchParams.set('market', t[1]);
        var h = new Headers(headersSrc || undefined);
        if (t[2]) h.set(t[2][0], t[2][1]);
        return ofetch.call(window, a.toString(), { method: 'GET', headers: h, mode: 'cors' }).then(function (r) {
          return r.arrayBuffer().then(function (buf) {
            var u8 = new Uint8Array(buf);
            emit('offer_test', t[0] + ' -> ' + r.status + ' ' + describeBinary(u8, false) + ' diffVsPage: ' + diffSummary(baseU8, u8));
          });
        }, function (e) { emit('offer_test', t[0] + ' -> blocked or failed: ' + scrub(e && e.name)); });
      }
      tests.reduce(function (p, t) { return p.then(function () { return one(t); }); }, Promise.resolve());
    }

    // ---- market experiment ----
    var realMarket = null;
    var REWRITE_HOSTS = /(xboxservices\.com|xboxlive\.com|gamepass\.com)$/i;
    var SKIP_HOSTS = /^(user|xsts|device|title)\.auth\.xboxlive\.com$|^login\./i;
    var MARKET_PARAMS = /^(market|mkt|country|countrycode|clientcountry)$/i;
    var LOCALE_PARAMS = /^(locale|clientlocale)$/i;

    function targetMarket() {
      try {
        var m = window.LabBridge && window.LabBridge.market && window.LabBridge.market();
        if (m && /^[A-Z]{2}$/.test(m)) return m;
      } catch (e) { }
      return 'ES';
    }

    function rewritableHost(urlStr) {
      try {
        var h = new URL(String(urlStr), location.href).hostname;
        return REWRITE_HOSTS.test(h) && !SKIP_HOSTS.test(h);
      } catch (e) { return false; }
    }

    function rewriteUrlString(s, M) {
      var out = { url: s, changed: false, note: '' };
      try {
        var a = new URL(String(s), location.href);
        if (!REWRITE_HOSTS.test(a.hostname) || SKIP_HOSTS.test(a.hostname)) return out;
        var pairs = [];
        a.searchParams.forEach(function (v, k) { pairs.push([k, v]); });
        pairs.forEach(function (kv) {                       // pass 1: learn the real market
          if (MARKET_PARAMS.test(kv[0]) && /^[A-Za-z]{2}$/.test(kv[1]) && !realMarket) realMarket = kv[1].toUpperCase();
        });
        var notes = [];
        pairs.forEach(function (kv) {                       // pass 2: rewrite
          var k = kv[0], v = kv[1];
          if (MARKET_PARAMS.test(k) && /^[A-Za-z]{2}$/.test(v)) {
            if (v.toUpperCase() !== M) { a.searchParams.set(k, M); notes.push(k + ':' + v.toUpperCase() + '>' + M); }
          } else if (LOCALE_PARAMS.test(k)) {
            var mm = /^([A-Za-z]{2,3})-([A-Za-z]{2})$/.exec(v);
            if (mm && realMarket && realMarket !== M && mm[2].toUpperCase() === realMarket) {
              var nv = mm[1].toLowerCase() + '-' + M;
              a.searchParams.set(k, nv); notes.push(k + ':' + v + '>' + nv);
            }
          }
        });
        if (notes.length) { out.url = a.toString(); out.changed = true; out.note = notes.join(','); }
      } catch (e) { }
      return out;
    }

    function rewriteHeaders(src, M) {
      try {
        var hh = new Headers(src || undefined);
        var cur = hh.get('x-xbl-market');
        if (cur === null) return null;
        if (!realMarket && /^[A-Za-z]{2}$/.test(cur)) realMarket = cur.toUpperCase();
        if (cur.toUpperCase() === M) return null;
        hh.set('x-xbl-market', M);
        return { headers: hh, note: 'x-xbl-market:' + cur.toUpperCase() + '>' + M };
      } catch (e) { return null; }
    }

    // returns null (nothing to change) or { promise } resolving to [input, init]
    function planRewrite(input, init) {
      var M = targetMarket();
      var isReq = (typeof Request === 'function') && (input instanceof Request);
      var urlStr = isReq ? input.url : String(input);
      if (!rewritableHost(urlStr)) return null;
      var u = rewriteUrlString(urlStr, M);
      var hdrSrc = (init && init.headers) ? init.headers : (isReq ? input.headers : null);
      var h = rewriteHeaders(hdrSrc, M);
      if (!u.changed && !h) return null;
      var note = [u.note, h && h.note].filter(Boolean).join(' ');
      var host = '';
      try { host = new URL(urlStr, location.href).hostname + maskPath(new URL(urlStr, location.href).pathname); } catch (e) { }
      emit('rewrite', host + ' ' + note + (isReq ? ' (Request object)' : ''));
      if (!isReq) {
        var ni = Object.assign({}, init || {});
        if (h) ni.headers = h.headers;
        return { promise: Promise.resolve([u.changed ? u.url : input, ni]) };
      }
      var method = String(input.method || 'GET').toUpperCase();
      var bodyP = (method === 'GET' || method === 'HEAD') ? Promise.resolve(undefined) : input.clone().arrayBuffer();
      return {
        promise: bodyP.then(function (buf) {
          var base = { method: input.method, headers: input.headers, body: buf, mode: input.mode, credentials: input.credentials,
                       cache: input.cache, redirect: input.redirect, referrer: input.referrer, referrerPolicy: input.referrerPolicy,
                       integrity: input.integrity, keepalive: input.keepalive, signal: input.signal };
          var merged = Object.assign(base, init || {});
          if (h) merged.headers = h.headers;
          return [new Request(u.changed ? u.url : input.url, merged), undefined];
        })
      };
    }

    var ofetch = window.fetch;
    var loggedFetch = null;
    if (ofetch) {
      loggedFetch = function (input, init) {
        var tag = 'GET ?';
        var rawUrl = '';
        try {
          var url = (typeof input === 'string') ? input : (input && input.url);
          var method = (init && init.method) || (input && input.method) || 'GET';
          tag = method + ' ' + safeUrl(url);
          emit('fetch', tag);
          var rd = reqDetail(url, init, (typeof input === 'string') ? null : input);
          if (rd) emit('fetch_request', tag + ' ' + rd);
          rawUrl = String(url);
        } catch (e) { }
        var p = ofetch.apply(this, arguments);
        try {
          p.then(function (r) { emit('fetch_status', tag + ' -> ' + r.status); captureShape(tag, rawUrl || '', r); captureOffering(tag, rawUrl || '', r, input, init); },
                 function (e) { emit('fetch_fail', tag + ' ' + scrub(e && e.name)); });
        } catch (e) { }
        return p;
      };
    }
    if (loggedFetch) {
      window.fetch = function (input, init) {
        var self = this;
        var plan = null;
        try { plan = planRewrite(input, init); } catch (e) { plan = null; }
        if (!plan) return loggedFetch.call(self, input, init);
        return plan.promise.then(
          function (args) { return loggedFetch.call(self, args[0], args[1]); },
          function (err) { emit('rewrite_failed', scrub(err && err.name)); return loggedFetch.call(self, input, init); }
        );
      };
    }

    var oopen = window.XMLHttpRequest && XMLHttpRequest.prototype.open;
    if (oopen) {
      XMLHttpRequest.prototype.open = function (m, u) {
        try { emit('xhr', m + ' ' + safeUrl(u)); } catch (e) { }
        return oopen.apply(this, arguments);
      };
    }

    if (window.RTCPeerConnection && RTCPeerConnection.prototype.setRemoteDescription) {
      var osrd = RTCPeerConnection.prototype.setRemoteDescription;
      RTCPeerConnection.prototype.setRemoteDescription = function (d) {
        try { emit('rtc_remote_description', d && d.type); } catch (e) { }
        return osrd.apply(this, arguments);
      };
    }

    function wrapCtor(name, describe) {
      try {
        var C = window[name];
        if (!C || typeof Proxy !== 'function') return;
        window[name] = new Proxy(C, {
          construct: function (target, args, newTarget) {
            try { emit(name, describe(args)); } catch (e) { }
            return Reflect.construct(target, args, newTarget);
          }
        });
      } catch (e) { }
    }
    wrapCtor('WebSocket', function (a) { return safeUrl(a[0]); });
    wrapCtor('Worker', function (a) { return safeUrl(a[0]); });
    wrapCtor('SharedWorker', function (a) { return safeUrl(a[0]); });
    wrapCtor('RTCPeerConnection', function () { return 'created'; });

    ['pushState', 'replaceState'].forEach(function (m) {
      try {
        var o = history[m];
        history[m] = function (s, t, u) {
          try { emit('history.' + m, u == null ? '' : safeUrl(u)); } catch (e) { }
          return o.apply(this, arguments);
        };
      } catch (e) { }
    });

    try {
      var odo = document.open;
      document.open = function () {
        try { emit('document.open', location.host + maskPath(location.pathname)); } catch (e) { }
        return odo.apply(this, arguments);
      };
    } catch (e) { }

    if (isTop && navigator.serviceWorker) {
      try {
        var oreg = navigator.serviceWorker.register;
        if (oreg) {
          navigator.serviceWorker.register = function (u) {
            try { emit('sw_register', safeUrl(u)); } catch (e) { }
            return oreg.apply(this, arguments);
          };
        }
        setTimeout(function () {
          try {
            navigator.serviceWorker.getRegistrations().then(function (rs) {
              emit('service_workers', rs.length + ' registered ' + rs.map(function (r) { return safeUrl(r.scope); }).join(','));
            }, function () { });
          } catch (e) { }
        }, 6000);
      } catch (e) { }
    }

    window.addEventListener('error', function (e) { emit('js_error', scrub(e && e.message)); }, true);
    window.addEventListener('unhandledrejection', function (e) {
      var r = e && e.reason;
      emit('rejection', scrub((r && (r.message || r.name)) || r));
    });

    function scan() {
      try {
        var t = ((document.body && document.body.innerText) || '').toLowerCase();
        var keys = ["not available in your region", "isn't available in your region", 'unsupported', 'not supported',
                    'browser', 'sign in', 'preview', 'game pass', 'install', 'something went wrong'];
        var hits = keys.filter(function (k) { return t.indexOf(k) >= 0; });
        emit('page_hints', JSON.stringify({ title: scrub(document.title).slice(0, 60), hits: hits, textLength: t.length }));
      } catch (e) { }
    }
    if (isTop) {
      setTimeout(scan, 8000);
      setTimeout(scan, 25000);
    }
  } catch (e) { }
})();
'''

pp = ROOT / "app/src/main/assets/probe.js"
if pp.exists() and pp.read_text(encoding="utf-8") == PROBE_JS:
    print("skip (already applied): assets/probe.js")
else:
    pp.write_text(PROBE_JS, encoding="utf-8")
    changed.append("assets/probe.js")
    print("applied: assets/probe.js (new file)")

LAB_HELPERS = """    // ---- LAB probe helpers (added by apply_fixes.py, lab branch only) ----
    private static final boolean LAB_INJECT_OLD_SCRIPT = false;

    private String labReadAsset(String name) {
        StringBuilder sb = new StringBuilder();
        try (InputStream is = getAssets().open(name);
             BufferedReader reader = new BufferedReader(new InputStreamReader(is, StandardCharsets.UTF_8))) {
            String line;
            while ((line = reader.readLine()) != null) sb.append(line).append('\\n');
        } catch (IOException ignored) {
        }
        return sb.toString();
    }

    private String labSafeUrl(String url) {
        try {
            android.net.Uri u = android.net.Uri.parse(url);
            String path = u.getPath() == null ? "" : u.getPath().replaceAll(
                    "[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}", "{guid}")
                    .replaceAll("[0-9a-fA-F]{16,}", "{hex}").replaceAll("[0-9]{6,}", "{num}");
            return u.getScheme() + "://" + u.getHost() + path;
        } catch (Throwable t) {
            return "unparsable";
        }
    }

    private class LabBridge {
        @android.webkit.JavascriptInterface
        public String market() {
            String r = getSharedPreferences(PREFS_NAME, MODE_PRIVATE).getString(KEY_REGION, "us");
            if (r == null) return "";
            if (r.equals("uk")) return "GB";
            return r.toUpperCase(java.util.Locale.ROOT);
        }
    }

    private void labInstallProbe() {
        try {
            webView.addJavascriptInterface(new LabBridge(), "LabBridge");
            if (androidx.webkit.WebViewFeature.isFeatureSupported(androidx.webkit.WebViewFeature.DOCUMENT_START_SCRIPT)) {
                java.util.Set<String> origins = new java.util.HashSet<>();
                origins.add("https://play.xbox.com");
                origins.add("https://www.xbox.com");
                androidx.webkit.WebViewCompat.addDocumentStartJavaScript(webView, labReadAsset("probe.js"), origins);
                DiagnosticLog.log("main", "probe_installed", "document-start script registered");
            } else {
                DiagnosticLog.log("main", "probe_unsupported", "this WebView cannot run document-start scripts");
            }
        } catch (Throwable t) {
            DiagnosticLog.logException("main", "probe_install_failed", t);
        }
    }

"""
edit(JAVA,
     "    private String loadScriptFromAssets() {\n",
     LAB_HELPERS + "    private String loadScriptFromAssets() {\n",
     "lab: probe helpers")

edit(JAVA,
     'webView.loadUrl("https://www.xbox.com/en-US/play");',
     'webView.loadUrl("https://play.xbox.com/");',
     "lab: start page is the new Xbox site")

edit(JAVA,
     '            if (newProgress > 30 && !isScriptInjected && view.getUrl() != null && view.getUrl().contains("play")) {\n',
     '            if (newProgress > 30 && !isScriptInjected && view.getUrl() != null && view.getUrl().contains("play") && LAB_INJECT_OLD_SCRIPT) {\n',
     "lab: old site script switched off")

edit(JAVA,
     "        webView.setWebChromeClient(new CustomWebChromeClient());\n",
     "        webView.setWebChromeClient(new CustomWebChromeClient());\n        labInstallProbe();\n",
     "lab: register the probe for every new WebView")

edit(JAVA,
     '            Log.d(TAG, "WebView Console: " + consoleMessage.message());\n',
     '            Log.d(TAG, "WebView Console: " + consoleMessage.message());\n'
     '            String labMsg = consoleMessage.message();\n'
     '            if (labMsg != null && labMsg.startsWith("[LABPROBE] ")) {\n'
     '                DiagnosticLog.log("main", "probe", labMsg.substring(11));\n'
     '            }\n',
     "lab: copy probe output into the debug log")

edit(JAVA,
     '                Log.i(TAG, "Page started: " + url);\n',
     '                Log.i(TAG, "Page started: " + url);\n'
     '                DiagnosticLog.log("main", "page_started", labSafeUrl(url));\n',
     "lab: log page starts (host + path only)")

edit(JAVA,
     "                super.onPageFinished(view, url);\n                setWebviewVisible();\n",
     "                super.onPageFinished(view, url);\n"
     "                DiagnosticLog.log(\"main\", \"page_finished\", labSafeUrl(url) + \" | ua=\" + view.getSettings().getUserAgentString());\n"
     "                setWebviewVisible();\n",
     "lab: log page finishes (host + path only)")

edit(JAVA,
     "        logPreviousExits();\n",
     "        logPreviousExits();\n        DiagnosticLog.log(\"main\", \"app_variant\", \"lab-probe-v5\");\n",
     "lab: mark this app's debug log as the lab probe build")

print("\nDone." if changed else "\nNothing to change.")
