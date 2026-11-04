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


# ---- 8. LAB ONLY (v12, EXPERIMENT): adds the ported native WebRTC handover on top of v11's proven pieces for the new Xbox site (play.xbox.com) -----------------------------
# Purpose: find out what the new site does inside this app, WITHOUT streaming through it yet.
# The old site script (index.js) is switched off in this lab app. A small diagnostics script
# (assets/probe.js) runs at document start and records addresses (host + path only), request
# kinds and statuses, workers, WebRTC use, page replacement, and a few yes/no page hints.
# It never records cookies, header values (except the market), bodies, tokens, page text or account names.
# EXPERIMENT: the market the page sends (GR) is rewritten to the app's Server Region setting.
PROBE_JS = r'''/* Xbox Lab (lean, v11). Runs at document start on play.xbox.com / www.xbox.com.
 * What it does (all in the page, nothing leaves the phone):
 *  1. Market: rewrites the market the page sends (market=GR, locale=xx-GR, x-xbl-market, JSON body market
 *     fields) to the market chosen in the app's Server Region setting.
 *  2. Streaming servers (*.gssv-play-prod.xboxlive.com) and the page's own client-IP headers get the
 *     chosen region's example client IP (with a safe fallback if the server refuses the extra header).
 *  3. Experiment answer: default offering CLOUDGAMING is changed to XGPUWEB (kept from the working lab build).
 *  4. Aspect ratio on the stream screen (16:9 / 18:9 / Stretch) via a CSS scale on the video element.
 * Logging is minimal: a few short lines (addresses without ids, never tokens or page text). */
(function () {
  try {
    if (window.__labLean) return;
    window.__labLean = true;
    var isTop = (window === window.top);
    var T0 = Date.now(), buf = [], counts = {}, sent = 0, MAX_EVENTS = 80;

    function maskPiece(s) {
      s = String(s);
      s = s.replace(/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/ig, '{guid}');
      s = s.replace(/[0-9a-f]{16,}/ig, '{hex}');
      s = s.replace(/[0-9]{6,}/g, '{num}');
      return s.length > 40 ? '{long}' : s;
    }
    function maskPath(p) { return String(p || '').split('/').map(maskPiece).join('/'); }
    function scrub(t) { return String(t == null ? '' : t).replace(/https?:\/\/\S+/g, '{url}').slice(0, 120); }
    function emit(kind, detail) {
      try {
        var key = kind + '|' + detail;
        counts[key] = (counts[key] || 0) + 1;
        if (counts[key] > 1 || sent >= MAX_EVENTS) return;
        sent++;
        buf.push({ t: Date.now() - T0, k: kind, d: detail });
      } catch (e) { }
    }
    function flush() {
      try { if (buf.length) console.log('[LABPROBE] ' + JSON.stringify(buf.splice(0, buf.length))); } catch (e) { }
    }
    setInterval(flush, 8000);
    window.addEventListener('pagehide', flush);

    // ---------- market / client-IP / streaming-server rewriting ----------
    var BYPASS_IPS = { US: '143.244.47.65', BR: '169.150.198.66', KR: '121.125.60.151', JP: '138.199.21.239',
                       PL: '45.134.212.66', ES: '80.58.61.250', GB: '62.24.134.1', FR: '212.27.40.240' };
    var realMarket = null;
    var REWRITE_HOSTS = /(xboxservices\.com|xboxlive\.com|gamepass\.com)$/i;
    var SKIP_HOSTS = /^(user|xsts|device|title)\.auth\.xboxlive\.com$|^login\./i;
    var MARKET_PARAMS = /^(market|mkt|country|countrycode|clientcountry)$/i;
    var LOCALE_PARAMS = /^(locale|clientlocale)$/i;
    var IP_HEADERS = ['forwarded', 'clientip', 'x-forwarded-for', 'x-client-ip'];

    // ---- callbacks the ported handover expects on window (native app -> page), unchanged ----
// Bridge for Native Android WebRTC
window.handleAnswer = function(sdp) {
    console.log("[BxC] handleAnswer from Java, sdp length: " + (sdp ? sdp.length : 0));
    if (window.pendingAnswerResolver) {
        window.pendingAnswerResolver({ type: 'answer', sdp: sdp });
        window.pendingAnswerResolver = null;
    } else {
        console.warn("[BxC] No pendingAnswerResolver found");
    }
};

window.handleOffer = function(sdp) {
    console.log("[BxC] handleOffer from Java, sdp length: " + (sdp ? sdp.length : 0));
    if (window.pendingOfferResolver) {
        window.pendingOfferResolver({ type: 'offer', sdp: sdp });
        window.pendingOfferResolver = null;
    } else {
        console.warn("[BxC] No pendingOfferResolver found");
    }
};

window.handleIceCandidate = function(sdpMid, sdpMLineIndex, sdp) {
    console.log("[BxC] handleIceCandidate from Java: " + sdpMid + " sdp length: " + (sdp ? sdp.length : 0));
    if (window.peer && window.peer.onicecandidate) {
        window.peer.onicecandidate({
            candidate: {
                candidate: sdp,
                sdpMid: sdpMid,
                sdpMLineIndex: sdpMLineIndex
            }
        });
    } else {
        console.warn("[BxC] handleIceCandidate: peer or onicecandidate missing");
    }
};

window.handleDataChannelMessage = function(label, binaryData, textData, isBinary) {
    console.log("[BxC] handleDataChannelMessage: " + label + " (binary: " + isBinary + ")");
    const dc = window.proxyDataChannels && window.proxyDataChannels[label];
    if (dc) {
        let data;
        if (isBinary) {
            data = window.bxToArrayBuffer(binaryData);
        } else {
            data = textData;
        }

        console.warn("[BxC] recivin data from channel " + label + ", data: " + data);
        if(label=='message'&&data.includes('HandshakeAck')){
        async function CXkeepalive(){

                                                            let CXtoken =  window.BX_EXPOSED.streamSession.gsToken;
                                                            let CXsessionPath=window.BX_EXPOSED.streamSession.sessionPath;
                                                            let CXendPoint=window.BX_EXPOSED.streamSession.domainName;
                                                            if(CXtoken.length&&CXtoken.length>0&&CXsessionPath.length&&CXsessionPath.length>0&&CXendPoint.length&&CXendPoint.length>0)
                                                           {
                                                            let CXurl=CXendPoint+'/'+CXsessionPath+'/keepalive';
                                                            console.log("[BxC] Keepalive URL:", CXurl,' token: ',CXtoken);
                                                             if (window.AndroidBridge && window.AndroidBridge.keepalive) {
                                                                            window.AndroidBridge.keepalive(CXurl,CXtoken);
                                                                        }
                                                                        return;}
                                                                        return setTimeout(CXkeepalive,10);
                                                           }
                                                       setTimeout(CXkeepalive,10);
        }
        // Create a real MessageEvent so the app can access .data
        const event = new MessageEvent('message', {
            data: data,
            origin: window.location.origin
        });
        dc.dispatchEvent(event);
        if (dc.onmessage) dc.onmessage(event);
    }
};

window.handleDataChannelState = function(label, state) {
    console.log("[BxC] handleDataChannelState: " + label + " -> " + state);
    const dc = window.proxyDataChannels && window.proxyDataChannels[label];
    if (dc) {
        dc.readyState = state.toLowerCase();
        if (dc.onopen && dc.readyState === 'open') dc.onopen();
        if (dc.onclose && dc.readyState === 'closed') dc.onclose();
    }
};

window.handleIceConnectionState = function(state) {
    console.log("[BxC] handleIceConnectionState: " + state);
    if (window.peer) {
        window.peer.iceConnectionState = state.toLowerCase();
        if (window.peer.oniceconnectionstatechange) window.peer.oniceconnectionstatechange();
        if (window.peer._listeners['iceconnectionstatechange']) {
            window.peer._listeners['iceconnectionstatechange'].forEach(l => l());
        }
    }
};

window.setControllerSettings = function(deadzone, sensitivity) {
    setPref("controller.deadzone", deadzone);
    setPref("controller.sensitivity", sensitivity);
}

window.setUseUnreliableInput = function(enabled) {
    window.BX_USE_UNRELIABLE_INPUT = enabled;
    BxLogger.info("Settings", "Updated UseUnreliableInput to:", enabled);
}
window.setPref = function lsSet(key, value) {
    localStorage.setItem(key, value);
};

window.getPref=function lsget(key){
return localStorage.getItem(key);
}


    function targetMarket() {
      try {
        var m = window.LabBridge && window.LabBridge.market && window.LabBridge.market();
        if (m && /^[A-Z]{2}$/.test(m)) return m;
      } catch (e) { }
      return 'ES';
    }
    function rewritableHost(urlStr) {
      try { var h = new URL(String(urlStr), location.href).hostname; return REWRITE_HOSTS.test(h) && !SKIP_HOSTS.test(h); }
      catch (e) { return false; }
    }
    function rewriteUrlString(s, M) {
      var out = { url: s, changed: false, note: '' };
      try {
        var a = new URL(String(s), location.href);
        if (!REWRITE_HOSTS.test(a.hostname) || SKIP_HOSTS.test(a.hostname)) return out;
        var pairs = [];
        a.searchParams.forEach(function (v, k) { pairs.push([k, v]); });
        pairs.forEach(function (kv) { if (MARKET_PARAMS.test(kv[0]) && /^[A-Za-z]{2}$/.test(kv[1]) && !realMarket) realMarket = kv[1].toUpperCase(); });
        var notes = [];
        pairs.forEach(function (kv) {
          var k = kv[0], v = kv[1];
          if (MARKET_PARAMS.test(k) && /^[A-Za-z]{2}$/.test(v)) {
            if (v.toUpperCase() !== M) { a.searchParams.set(k, M); notes.push(k + ':' + v.toUpperCase() + '>' + M); }
          } else if (LOCALE_PARAMS.test(k)) {
            var mm = /^([A-Za-z]{2,3})-([A-Za-z]{2})$/.exec(v);
            if (mm && realMarket && realMarket !== M && mm[2].toUpperCase() === realMarket) {
              var nv = mm[1].toLowerCase() + '-' + M; a.searchParams.set(k, nv); notes.push(k + ':' + v + '>' + nv);
            }
          }
        });
        if (notes.length) { out.url = a.toString(); out.changed = true; out.note = notes.join(','); }
      } catch (e) { }
      return out;
    }
    function swapIp(name, value, ip) {
      var v = String(value), v4 = /\b\d{1,3}(\.\d{1,3}){3}\b/;
      if (v4.test(v)) return v.replace(v4, ip);
      if (/:[0-9a-f]*:/i.test(v)) return name === 'forwarded' ? 'for=' + ip : ip;
      return null;
    }
    function rewriteHeaders(src, M, host) {
      try {
        var hh = new Headers(src || undefined), notes = [], changed = false;
        var cur = hh.get('x-xbl-market');
        if (cur !== null) {
          if (!realMarket && /^[A-Za-z]{2}$/.test(cur)) realMarket = cur.toUpperCase();
          if (cur.toUpperCase() !== M) { hh.set('x-xbl-market', M); notes.push('x-xbl-market:' + cur.toUpperCase() + '>' + M); changed = true; }
        }
        var ip = BYPASS_IPS[M] || BYPASS_IPS.US;
        IP_HEADERS.forEach(function (nm) {
          var v = hh.get(nm); if (v === null) return;
          var nv = swapIp(nm, v, ip);
          if (nv !== null && nv !== v) { hh.set(nm, nv); notes.push(nm + ':client-ip>' + M + '-ip'); changed = true; }
        });
        var gssv = !!host && /\.gssv-play-prod\.xboxlive\.com$/i.test(host);
        if (gssv && hh.get('x-forwarded-for') === null) { hh.set('x-forwarded-for', ip); notes.push('gssv:x-forwarded-for added'); changed = true; }
        return changed ? { headers: hh, note: notes.join(','), gssv: gssv } : null;
      } catch (e) { return null; }
    }
    function rewriteBodyMarket(body, M) {
      try {
        if (typeof body !== 'string' || (body.charAt(0) !== '{' && body.charAt(0) !== '[')) return null;
        var obj = JSON.parse(body), notes = [];
        (function walk(o, d) {
          if (!o || typeof o !== 'object' || d > 4) return;
          Object.keys(o).forEach(function (k) {
            var v = o[k];
            if (/^(market|country|countrycode|clientcountry)$/i.test(k) && typeof v === 'string' && /^[A-Za-z]{2}$/.test(v)) {
              if (v.toUpperCase() !== M) { notes.push(k + ':' + v.toUpperCase() + '>' + M); o[k] = (v === v.toLowerCase()) ? M.toLowerCase() : M; }
            } else walk(v, d + 1);
          });
        })(obj, 0);
        return notes.length ? { body: JSON.stringify(obj), note: 'body{' + notes.join(',') + '}' } : null;
      } catch (e) { return null; }
    }
    var EXP_URL = /emerald\.xboxservices\.com\/xboxcomfd\/experimentation/;
    function patchExperimentation(r) {
      try {
        if (!r || !r.ok) return r;
        return r.clone().json().then(function (j) {
          var changes = 0;
          (function walk(o, d) {
            if (!o || typeof o !== 'object' || d > 9) return;
            Object.keys(o).forEach(function (k) {
              var v = o[k];
              if (typeof v === 'string' && v.length < 4000 && /cloudgaming/i.test(v)) {
                o[k] = v.replace(/CLOUDGAMING/g, 'XGPUWEB').replace(/cloudgaming/g, 'xgpuweb').replace(/CloudGaming/g, 'XgpuWeb'); changes++;
              } else if (v && typeof v === 'object') walk(v, d + 1);
            });
          })(j, 0);
          emit('exp_patch', changes ? 'changed ' + changes + ' value(s)' : 'nothing to change');
          if (!changes) return r;
          var hdrs = new Headers(r.headers); hdrs.delete('content-length'); hdrs.delete('content-encoding');
          var nr = new Response(JSON.stringify(j), { status: r.status, statusText: r.statusText, headers: hdrs });
          try { Object.defineProperty(nr, 'url', { value: r.url }); } catch (e) { }
          return nr;
        }, function () { return r; });
      } catch (e) { return r; }
    }
    function planRewrite(input, init) {
      var M = targetMarket();
      var isReq = (typeof Request === 'function') && (input instanceof Request);
      var urlStr = isReq ? input.url : String(input);
      if (!rewritableHost(urlStr)) return null;
      var u = rewriteUrlString(urlStr, M);
      var hostName = '';
      try { hostName = new URL(urlStr, location.href).hostname; } catch (e) { }
      var hdrSrc = (init && init.headers) ? init.headers : (isReq ? input.headers : null);
      var h = rewriteHeaders(hdrSrc, M, hostName);
      var bm = (!isReq && init && typeof init.body === 'string') ? rewriteBodyMarket(init.body, M) : null;
      if (!u.changed && !h && !bm) return null;
      var note = [u.note, h && h.note, bm && bm.note].filter(Boolean).join(' ');
      emit('rewrite', hostName + maskPath(new URL(urlStr, location.href).pathname) + ' ' + note + (isReq ? ' (Request object)' : ''));
      var gssvAdded = !!(h && h.gssv && /gssv:/.test(h.note || ''));
      if (!isReq) {
        var ni = Object.assign({}, init || {});
        if (h && h.headers) ni.headers = h.headers;
        if (bm) ni.body = bm.body;
        return { gssvAdded: gssvAdded, promise: Promise.resolve([u.changed ? u.url : input, ni]) };
      }
      var method = String(input.method || 'GET').toUpperCase();
      var bodyP = (method === 'GET' || method === 'HEAD') ? Promise.resolve(undefined) : input.clone().arrayBuffer();
      return {
        gssvAdded: gssvAdded,
        promise: bodyP.then(function (buf2) {
          var base = { method: input.method, headers: input.headers, body: buf2, mode: input.mode, credentials: input.credentials,
                       cache: input.cache, redirect: input.redirect, referrer: input.referrer, referrerPolicy: input.referrerPolicy,
                       integrity: input.integrity, keepalive: input.keepalive, signal: input.signal };
          var merged = Object.assign(base, init || {});
          if (h) merged.headers = h.headers;
          return [new Request(u.changed ? u.url : input.url, merged), undefined];
        })
      };
    }


    // ---- EXPERIMENT (v12): the native WebRTC handover, ported from the proven working build -------
    // Hands the stream to the native decoder instead of the browser's own WebRTC, and sends the same
    // resolution/bitrate/region spoofing the working app always sent. UNTESTED on the new site: if
    // video never appears within ~15s after pressing Play, this is the part to revert.
    var BxLogger = { info: function () {}, error: function () {} };  // same shape, quiet (was console logging)
    if (!window.BX_EXPOSED) window.BX_EXPOSED = {};
    window.BX_EXPOSED.streamSession = window.BX_EXPOSED.streamSession || { gsToken: '', sessionPath: '', domainName: '' };
const BypassServerIps = {
    us: "143.244.47.65",
    br: "169.150.198.66",
    kr: "121.125.60.151",
    jp: "138.199.21.239",
    pl: "45.134.212.66",
    es: "80.58.61.250",
    uk: "62.24.134.1",
    fr: "212.27.40.240"
};

const ServerRegionMap = {
    us: "westus",
    br: "brazilsouth",
    kr: "koreacentral",
    jp: "japaneast",
    pl: "swedencentral",
    es: "spaincentral",
    uk: "uksouth",
    fr: "francecentral"
};

function getTargetRegion() {
    // Priority: window global > localStorage > default (us)
    return window.BX_TARGET_REGION || localStorage.getItem('BX_TARGET_REGION') || 'es';
}

function getTargetResolution() {
    // Priority: window global > localStorage > default (1080p)
    return window.BX_TARGET_RES || localStorage.getItem('BX_TARGET_RES') || '1080p';
}

function getTargetBitrate() {
    // Priority: window global > localStorage > default (0 - Auto)
    return window.BX_TARGET_BITRATE || parseInt(localStorage.getItem('BX_TARGET_BITRATE')) || 0;
}

function getOsNameFromResolution(resolution) {
    let osName;
    switch (resolution) {
        case "1080HQ":
            osName = "tizen";
            break;
        case "1080":
            osName = "windows";
            break;
        case "720":
            osName = "android";
            break;
        default:
            osName = "tizen";
            break;
    }
    return osName;
}

function generateMsDeviceInfo(osName) {
    return {
        appInfo: {
            env: {
                clientAppId: window.location.host,
                clientAppType: "browser",
                clientAppVersion: "26.1.97",
                clientSdkVersion: "10.3.7",
                httpEnvironment: "prod",
                sdkInstallId: ""
            }
        },
        dev: {
            os: { name: osName, ver: "22631.2715", platform: "desktop" },
            hw: { make: "Microsoft", model: "unknown", sdktype: "web" },
            browser: { browserName: "chrome", browserVersion: "140.0.3485.54" },
            displayInfo: {
                dimensions: { widthInPixels: 4096, heightInPixels: 2160 },
                pixelDensity: { dpiX: 1, dpiY: 1 }
            }
        }
    };
}
class XcloudInterceptor {
    static async handleLogin(request, init) {
        const region = getTargetRegion();
        const ip = BypassServerIps[region] || BypassServerIps.us;

        BxLogger.info("XcloudInterceptor", "Using bypass IP for login:", region, "->", ip);

        request.headers.set("X-Forwarded-For", ip);

        let response;
        try {
            response = await NATIVE_FETCH(request, init);
        } catch (e) {
            BxLogger.error("XcloudInterceptor", "Login interception failed", e);
            throw e;
        }

        if (response.status === 200) {
            const obj = await response.clone().json();

            const targetServerRegion = ServerRegionMap[region];

            if (targetServerRegion && obj.offeringSettings && obj.offeringSettings.regions) {
                BxLogger.info("XcloudInterceptor", "Forcing streaming region to:", targetServerRegion);

                const filteredRegions = obj.offeringSettings.regions.filter(r => r.name.toLowerCase().includes(targetServerRegion));
                if (filteredRegions.length > 0) {
                    filteredRegions[0].isDefault = true;
                    obj.offeringSettings.regions = filteredRegions;
                }
            }

            response.json = () => Promise.resolve(obj);
        }

        return response;
    }

    static async handlePlay(request, init) {
        const res = getTargetResolution();
        const osName = getOsNameFromResolution(res);
        const deviceInfo = generateMsDeviceInfo(osName);

        BxLogger.info("XcloudInterceptor", "Patching play request for resolution:", res, "-> OS:", osName);

        // Inject hardware spoofing header
        request.headers.set("x-ms-device-info", JSON.stringify(deviceInfo));

        let finalRequest = request;
        // Modify body to include spoofed OS name
        try {
            const body = await request.clone().json();
            if (body.settings) {
                body.settings.osName = osName;
                // Surgical addition: force English, mirroring Better xCloud's
                // "preferred game language" override (body.settings.locale) on this
                // exact same session-creation request.
                body.settings.locale = "en-US";
            }
            // Create a new request with the modified body
            finalRequest = new Request(request, {
                body: JSON.stringify(body)
            });
        } catch (e) {
            BxLogger.error("XcloudInterceptor", "Play request body modification failed", e);
        }

        const response = await NATIVE_FETCH(finalRequest, init);

        // Capture session info
        try {
            if (response.status >= 200 && response.status < 300) {
                const respBody = await response.clone().json();
                if (respBody.sessionPath) {
                    window.BX_EXPOSED.streamSession.sessionPath = respBody.sessionPath;
                    try { emit("native_session_captured", "yes"); } catch (e) { }
                }
                const url = typeof request === "string" ? request : request.url;
                // Use URL origin to avoid carrying over query parameters or path segments
                window.BX_EXPOSED.streamSession.domainName = new URL(url).origin;
                BxLogger.info("streamSession", "Captured sessionPath and domainName:", window.BX_EXPOSED.streamSession);
            }
        } catch (e) {
            BxLogger.error("XcloudInterceptor", "Session info capture failed", e);
        }

        return response;
    }

    static async handleConfiguration(request, init) {
        // Extract token from Authorization header
        const authHeader = request.headers.get("Authorization");
        if (authHeader && authHeader.startsWith("Bearer ")) {
            window.BX_EXPOSED.streamSession.gsToken = authHeader.substring(7);
            try { emit("native_token_captured", "yes"); } catch (e) { }
            BxLogger.info("streamSession", "Captured gsToken from configuration request headers");
        }

        let response = await NATIVE_FETCH(request, init);
        let text = await response.clone().text();
        if (!text.length) return response;

        try {
            let obj = JSON.parse(text);
            let overrides = JSON.parse(obj.clientStreamingConfigOverrides || "{}") || {};

            overrides.inputConfiguration = overrides.inputConfiguration || {};
            // Force unreliable input channel (unreliableinput) if enabled
            const useUnreliable = window.BX_USE_UNRELIABLE_INPUT !== false;
            overrides.inputConfiguration.useUnreliableInput = useUnreliable;
            overrides.inputConfiguration.enableVibration = true;

            obj.clientStreamingConfigOverrides = JSON.stringify(overrides);

            BxLogger.info("XcloudInterceptor", "Forcing input configuration - unreliableinput:", useUnreliable);

            // Reconstruct response
            const modifiedResponse = new Response(JSON.stringify(obj), {
                status: response.status,
                statusText: response.statusText,
                headers: response.headers
            });

            return modifiedResponse;
        } catch (e) {
            BxLogger.error("XcloudInterceptor", "Configuration modification failed", e);
        }

        return response;
    }

    static async handle(request, init) {
        const url = typeof request === "string" ? request : request.url;
        if (url.endsWith("/v2/login/user")) {
            return XcloudInterceptor.handleLogin(request, init);
        } else if (url.endsWith("/sessions/cloud/play")) {
            return XcloudInterceptor.handlePlay(request, init);
        } else if (url.endsWith("/configuration")) {
            return XcloudInterceptor.handleConfiguration(request, init);
        }
        return NATIVE_FETCH(request, init);
    }
}
function patchSdpBitrate(sdp, videoBitrate) {
    if (!videoBitrate) return sdp;

    let lines = sdp.split('\r\n');
    let newLines = [];
    let inVideoSection = false;

    for (let line of lines) {
        newLines.push(line);
        if (line.startsWith('m=video')) {
            inVideoSection = true;
        } else if (line.startsWith('m=')) {
            inVideoSection = false;
        }

        if (inVideoSection && line.startsWith('c=IN')) {
            // Inject b=AS line after connection info in video section
            newLines.push('b=AS:' + videoBitrate);
        }
    }
    return newLines.join('\r\n');
}

function patchSdpFps(sdp, fps) {
    let lines = sdp.split('\r\n');
    for (let i = 0; i < lines.length; i++) {
        if (lines[i].startsWith('a=fmtp:')) {
            if (!lines[i].includes('max-fr=')) {
                lines[i] += ';max-fr=' + fps;
            } else {
                lines[i] = lines[i].replace(/max-fr=\d+/, 'max-fr=' + fps);
            }
        }
    }
    return lines.join('\r\n');
}

function patchRtcPeerConnection() {
    let OrgRTCPeerConnection = window.RTCPeerConnection;
window.handleIceCandidate = function(sdpMid, sdpMLineIndex, candidateStr) {
    if (!window.peer) return;

    // If candidateStr is null/empty, WebRTC treats it as the end of candidates
    let candidateObj = candidateStr ? { sdpMid: sdpMid, sdpMLineIndex: sdpMLineIndex, candidate: candidateStr } : null;

    let event = new Event('icecandidate');
    event.candidate = candidateObj;

    if (window.peer.onicecandidate) window.peer.onicecandidate(event);
    if (window.peer._listeners && window.peer._listeners['icecandidate']) {
        window.peer._listeners['icecandidate'].forEach(l => l(event));
    }
};
    // Base64 Helpers
    window.bxToBase64 = function(buffer) {
        let binary = '';
        let bytes = new Uint8Array(buffer);
        for (let i = 0; i < bytes.byteLength; i++) binary += String.fromCharCode(bytes[i]);
        return window.btoa(binary);
    };
    window.bxToArrayBuffer = function(base64) {
        let binary = window.atob(base64);
        let bytes = new Uint8Array(binary.length);
        for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
        return bytes.buffer;
    };


    window.simulateOnTrack = function(kind, id) {
        console.log("[BxC] Simulating ontrack for " + kind);

        let stream;
        let track;

        if (kind === 'video') {
            const canvas = document.createElement('canvas');
            canvas.width = 1920;
            canvas.height = 1080;
            const ctx = canvas.getContext('2d');
            ctx.fillStyle = 'black';
            ctx.fillRect(0, 0, canvas.width, canvas.height);

            ctx.fillStyle = 'white';
            ctx.font = '30px Arial';
            ctx.fillText('Native Bridge Active', 50, 50);

            stream = canvas.captureStream(60);
            track = stream.getVideoTracks()[0];
        } else {

                const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
                const destination = audioCtx.createMediaStreamDestination();
                stream = destination.stream;
                track = stream.getAudioTracks()[0];
            }

        // Construct a real-like Track event
        let event = new Event('track');
        event.track = track;
        event.streams = [stream];
        event.transceiver = { receiver: { track: track } };

        if (window.peer) {
            if (window.peer.ontrack) window.peer.ontrack(event);
            if (window.peer._listeners && window.peer._listeners['track']) {
                window.peer._listeners['track'].forEach(l => l(event));
            }
        }
    };

    window.filterSdp = function(sdp) {
        let lines = sdp.split('\r\n');
        let newLines = [];
        let skipExtmap = [
            'urn:ietf:params:rtp-hdrext:toffset',
                        'urn:ietf:params:rtp-hdrext:sdes:rtp-stream-id',
                        'urn:ietf:params:rtp-hdrext:sdes:repaired-rtp-stream-id',
                        'http://www.webrtc.org/experiments/rtp-hdrext/video-layers-allocation00',
            'http://www.ietf.org/id/draft-holmer-rmcat-transport-wide-cc-extensions-01'
        ];

        for (let line of lines) {
            let skip = false;
            if (line.startsWith('a=extmap:')) {
                 for (let ext of skipExtmap) {
                                      if (line.includes(ext)) {
                                          skip = true;
                                          break;
                                      }
                                  }
            }

            if (!skip) newLines.push(line);
        }
        return newLines.join('\r\n');
    };

    window.RTCPeerConnection = function(config) {
        console.log("[BxC] RTCPeerConnection constructor called", JSON.stringify(config));
        window.__labNativeActive = true;
        try { emit("native_pc_created", "yes"); } catch (e) { }

        if (window.AndroidBridge && config) {
            window.AndroidBridge.onPeerConnectionConfig(JSON.stringify(config));
        }

        const pc = {
            config: config,
            localDescription: null,
            remoteDescription: null,
            connectionState: 'new',
            iceConnectionState: 'new',
            signalingState: 'stable',
            _listeners: {},
            _transceivers: [],

            createDataChannel: function(label, options) {
                console.log("[BxC] Proxy createDataChannel: " + label + " options: " + JSON.stringify(options));
                if (window.AndroidBridge) {
                    window.AndroidBridge.onDataChannelCreate(label);
                }

                const dc = {
                    label: label,
                    id: options ? options.id : null,
                    ordered: options ? options.ordered : true,
                    protocol: options ? (options.protocol || "") : "",
                    readyState: 'connecting',
                    binaryType: 'arraybuffer',
                    onmessage: null,
                    onopen: null,
                    onclose: null,

                   send: function(data) {
                                           if(label=='input'||label=='unreliableinput'||label=='reliableinput')return;
                                           if (window.AndroidBridge) {
                                               if(label=='message'&&!data.includes('Handshake')){return;}
                                               let base64;
                                               let isBinary = typeof data !== 'string';
                                               if (isBinary) {

                                                       window.AndroidBridge.onDataChannelSend(label, new Uint8Array(data), null, true);
                                                       return;

                                               } else {
                                               if(label=='control'&&data.includes('resolutionAlias')){
                                               let overridesData=JSON.parse(data);
                                               overridesData.resolutionAlias=window.BX_TARGET_RES;
                                               data=JSON.stringify(overridesData);
                                               }
                                               console.log('sending data from channel'+label+': '+data);
                                               base64 = window.btoa(unescape(encodeURIComponent(data)));
                                               window.AndroidBridge.onDataChannelSend(label, null, base64, false);

                                           }}
                                       },
                    close: function() {
                        console.log("[BxC] Proxy DataChannel close: " + label);
                    },
                    addEventListener: function(type, listener) {
                        if (!this._listeners) this._listeners = {};
                        if (!this._listeners[type]) this._listeners[type] = [];
                        this._listeners[type].push(listener);
                    },
                    removeEventListener: function(type, listener) {
                        if (this._listeners && this._listeners[type]) {
                            this._listeners[type] = this._listeners[type].filter(l => l !== listener);
                        }
                    },
                    dispatchEvent: function(event) {
                        if (event.type === 'message') {
                            if (this.onmessage) this.onmessage(event);
                            if (this._listeners && this._listeners['message']) {
                                this._listeners['message'].forEach(l => l(event));
                            }
                        }
                    }
                };

                if (!window.proxyDataChannels) window.proxyDataChannels = {};
                window.proxyDataChannels[label] = dc;

                return dc;
            },

            addTransceiver: function(trackOrKind, init) {
                console.log("[BxC] Proxy addTransceiver: " + trackOrKind);
                if (window.AndroidBridge) {
                    window.AndroidBridge.onAddTransceiver(trackOrKind, init ? (init.direction || "recvonly") : "recvonly");
                }
                const transceiver = {
                    mid: null,
                    direction: init ? (init.direction || 'sendrecv') : 'sendrecv',
                    sender: { track: (typeof trackOrKind !== 'string' ? trackOrKind : null) },
                    receiver: { track: { kind: (typeof trackOrKind === 'string' ? trackOrKind : trackOrKind.kind), stop: () => {} } },
                    stop: () => {},
                    setCodecPreferences: function(codecs) { console.log("[BxC] Proxy setCodecPreferences"); }
                };
                this._transceivers.push(transceiver);
                return transceiver;
            },

            addTrack: function(track, ...streams) {
                console.log("[BxC] Proxy addTrack: " + track.kind);
                return { track: track };
            },

            getTransceivers: function() { return this._transceivers || []; },
            getReceivers: function() { return (this._transceivers || []).map(t => t.receiver); },
            getSenders: function() { return (this._transceivers || []).map(t => t.sender); },

            setRemoteDescription: function(description) {
                console.log("[BxC] Proxy setRemoteDescription: " + description.type);
                this.remoteDescription = description;
                if (description && window.AndroidBridge) {
                    if (description.type === 'offer') {
                        window.AndroidBridge.onOfferReceived(description.sdp);
                    } else if (description.type === 'answer') {
                        window.AndroidBridge.onAnswerReceived(description.sdp);
                    }
                }
                return Promise.resolve();
            },

            createAnswer: function() {
                console.log("[BxC] Proxy createAnswer");
                return new Promise((resolve) => {
                    window.pendingAnswerResolver = (answer) => {
                        this.localDescription = answer;
                        resolve(answer);
                    };
                });
            },

            createOffer: function() {
                            console.log("[BxC] Proxy createOffer requested");
                            return new Promise((resolve) => {
                                window.pendingOfferResolver = (offer) => {
                                    const bitrateMbps = getTargetBitrate();
                                    if (bitrateMbps > 0) {
                                        try {
                                            // Convert Mbps to Kbps for SDP (b=AS line)
                                            const bitrateKbps = bitrateMbps * 1000;
                                            offer.sdp = patchSdpBitrate(offer.sdp, bitrateKbps);
                                            BxLogger.info("Patcher", "Applied bitrate patch:", bitrateMbps + " Mbps");
                                        } catch (e) {
                                            BxLogger.error("Patcher", "Bitrate patch failed", e);
                                        }
                                    }

                                    offer.sdp = patchSdpFps(offer.sdp, 60);
                                    this.localDescription = offer;
                                    console.log("[BxC] Sending offer to server, length: " + offer.sdp.length);
                                    resolve(offer);
                                };
                                if (window.AndroidBridge) {
                                    window.AndroidBridge.onOfferRequested();
                                }
                            });
                        },

           setLocalDescription: function(description) {
               console.log("[BxC] Proxy setLocalDescription: " + (description ? description.type : "null"));
               this.localDescription = description;

               // 1. Update the internal state
               this.signalingState = description.type === 'offer' ? 'have-local-offer' : 'stable';

               // 2. Fire the state change event
               let event = new Event('signalingstatechange');
               if (this.onsignalingstatechange) this.onsignalingstatechange(event);
               if (this._listeners && this._listeners['signalingstatechange']) {
                   this._listeners['signalingstatechange'].forEach(l => l(event));
               }

               return Promise.resolve();
           },

            setConfiguration: function(config) {
                console.log("[BxC] Proxy setConfiguration", JSON.stringify(config));
                this.config = config;
                if (window.AndroidBridge && config) {
                    window.AndroidBridge.onPeerConnectionConfig(JSON.stringify(config));
                }
            },

            addIceCandidate: function(candidate) {
                console.log("[BxC] Proxy addIceCandidate");
                if (candidate && window.AndroidBridge) {
                    window.AndroidBridge.onIceCandidateReceived(candidate.sdpMid, candidate.sdpMLineIndex, candidate.candidate || candidate.sdp || "");
                }
                return Promise.resolve();
            },

            addEventListener: function(type, listener) {
                if (!this._listeners[type]) this._listeners[type] = [];
                this._listeners[type].push(listener);
                this['on' + type] = listener;
            },

            getStats: function() {
                return Promise.resolve(new Map());
            },

            close: function() {
                console.log("[BxC] Proxy close");
                if (window.AndroidBridge) {
                    window.AndroidBridge.onPeerConnectionClose();
                }
            }
        };

        window.peer = pc;
        return pc;
    };

    window.RTCPeerConnection.prototype = OrgRTCPeerConnection.prototype;
    if (OrgRTCPeerConnection.generateCertificate) {
        window.RTCPeerConnection.generateCertificate = OrgRTCPeerConnection.generateCertificate.bind(OrgRTCPeerConnection);
    }
}
    try { patchRtcPeerConnection(); } catch (e) { emit('native_shim_failed', scrub(e && e.message)); }

    var ofetch = window.fetch;
    function loggedFetch(input, init) {
      var rawUrl = '';
      try { rawUrl = String((typeof input === 'string') ? input : (input && input.url)); } catch (e) { }
      var p = ofetch.apply(this, arguments);
      if (EXP_URL.test(rawUrl)) return p.then(patchExperimentation);
      return p;
    }
    var INTERCEPTED_SUFFIXES = ['/v2/login/user', '/sessions/cloud/play', '/configuration'];
    function interceptedSuffix(urlStr) {
      try {
        if (!/xboxlive\.com$/i.test(new URL(urlStr, location.href).hostname)) return null;
        var p = new URL(urlStr, location.href).pathname;
        for (var i = 0; i < INTERCEPTED_SUFFIXES.length; i++) { if (p.endsWith(INTERCEPTED_SUFFIXES[i])) return INTERCEPTED_SUFFIXES[i]; }
      } catch (e) { }
      return null;
    }
    var NATIVE_FETCH = ofetch;  // used by the ported interceptor, same meaning as in the proven build
    if (ofetch) {
      window.fetch = function (input, init) {
        var self = this;
        var rawUrl = '';
        try { rawUrl = String((typeof input === 'string') ? input : (input && input.url)); } catch (e) { }
        var suf = interceptedSuffix(rawUrl);
        if (suf) {
          var req = (typeof Request === 'function' && input instanceof Request) ? input : new Request(input, init);
          emit('native_intercept', suf);
          return XcloudInterceptor.handle(req, init).catch(function (e) { emit('native_intercept_failed', suf + ' ' + scrub(e && e.name)); return NATIVE_FETCH(req, init); });
        }
        var plan = null;
        try { plan = planRewrite(input, init); } catch (e) { plan = null; }
        if (!plan) return loggedFetch.call(self, input, init);
        return plan.promise.then(
          function (args) {
            var q = loggedFetch.call(self, args[0], args[1]);
            if (plan.gssvAdded) return q.catch(function (e) { emit('gssv_header_blocked', scrub(e && e.name)); return loggedFetch.call(self, input, init); });
            return q;
          },
          function (err) { emit('rewrite_failed', scrub(err && err.name)); return loggedFetch.call(self, input, init); }
        );
      };
    }
    if (isTop) emit('market_target', targetMarket() + ' bridge=' + (window.LabBridge ? 'yes' : 'no'));

    // ---------- aspect ratio on the stream screen ----------
    // modes: 0 = 16:9 (site default), 1 = 18:9, 2 = Stretch (full screen)
    var LABELS = ['Aspect ratio: 16:9', 'Aspect ratio: 18:9', 'Aspect ratio: Stretch (full screen)'];
    var aspectMode = 0, aspectEl = null;
    try { var sv = parseInt(localStorage.getItem('labAspectMode'), 10); if (sv >= 0 && sv <= 2) aspectMode = sv; } catch (e) { }
    function onStreamScreen() { return /^\/stream\//.test(location.pathname); }
    function biggestMedia() {
      var best = null, area = 0;
      Array.prototype.forEach.call(document.querySelectorAll('video, canvas'), function (el) {
        var r = el.getBoundingClientRect(), a = r.width * r.height;
        if (r.width > 160 && r.height > 90 && a > area) { area = a; best = el; }
      });
      return best;
    }
    function clearAspect(el) { try { if (el) el.style.removeProperty('scale'); } catch (e) { } }
    function applyAspect() {
      try {
        if (!onStreamScreen()) { clearAspect(aspectEl); aspectEl = null; return; }
        var el = biggestMedia();
        if (!el) return;
        if (aspectEl && aspectEl !== el) clearAspect(aspectEl);
        aspectEl = el;
        var W = window.innerWidth, H = window.innerHeight;
        var base = Math.min(W, H * 16 / 9);
        var target = aspectMode === 0 ? base : (aspectMode === 1 ? Math.min(W, H * 2) : W);
        var f = base > 0 ? target / base : 1;
        if (f > 1.001) el.style.setProperty('scale', f.toFixed(4) + ' 1', 'important');
        else el.style.removeProperty('scale');
      } catch (e) { }
    }
    window.__labAspectLabel = function () { return LABELS[aspectMode]; };
    window.__labAspectCycle = function () {
      aspectMode = (aspectMode + 1) % 3;
      try { localStorage.setItem('labAspectMode', String(aspectMode)); } catch (e) { }
      applyAspect();
      return LABELS[aspectMode];
    };
    if (isTop) {
      setInterval(applyAspect, 1000);
      window.addEventListener('resize', applyAspect);
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

    private boolean labWebStreamActive() {
        try {
            String u = webView == null ? null : webView.getUrl();
            return u != null && u.contains("/stream/");
        } catch (Throwable t) {
            return false;
        }
    }

    private void labAspectLabel(final Button b, boolean cycle) {
        // v13 fix: once the native handover has actually taken over the stream (window.__labNativeActive),
        // there is no <video> element left for the JS-side cycler to scale, so the EXISTING native
        // aspect control (the same one the original app uses) must drive the button instead.
        webView.evaluateJavascript("!!window.__labNativeActive", nativeActive -> {
            if ("true".equals(nativeActive)) {
                if (cycle) {
                    cycleAspectMode();
                }
                b.setText(aspectModeLabel());
                return;
            }
            String js = cycle ? "window.__labAspectCycle && window.__labAspectCycle()" : "window.__labAspectLabel && window.__labAspectLabel()";
            webView.evaluateJavascript(js, value -> {
                if (value != null && value.length() > 4) b.setText(value.replaceAll("[^A-Za-z0-9:%() /.-]", "").trim());
            });
        });
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
     "        logPreviousExits();\n        DiagnosticLog.log(\"main\", \"app_variant\", \"lab-probe-v13\");\n",
     "lab: mark this app's debug log as the lab probe build")


# ---- 9. LAB ONLY: the aspect-ratio button also works while the stream runs inside the web page ----
edit(JAVA,
     "        btnAspect.setText(aspectModeLabel());\n"
     "        btnAspect.setOnClickListener(v -> {\n"
     "            cycleAspectMode();\n"
     "            btnAspect.setText(aspectModeLabel());\n"
     "        });\n",
     "        if (labWebStreamActive()) {\n"
     "            labAspectLabel(btnAspect, false);\n"
     "        } else {\n"
     "            btnAspect.setText(aspectModeLabel());\n"
     "        }\n"
     "        btnAspect.setOnClickListener(v -> {\n"
     "            if (labWebStreamActive()) {\n"
     "                labAspectLabel(btnAspect, true);\n"
     "            } else {\n"
     "                cycleAspectMode();\n"
     "                btnAspect.setText(aspectModeLabel());\n"
     "            }\n"
     "        });\n",
     "lab: aspect button controls the web stream")
edit(JAVA,
     "            btnMic.setVisibility(View.GONE);\n            btnAspect.setVisibility(View.GONE);\n",
     "            btnMic.setVisibility(View.GONE);\n            if (!labWebStreamActive()) btnAspect.setVisibility(View.GONE);\n",
     "lab: keep the aspect button visible during a web stream")

print("\nDone." if changed else "\nNothing to change.")
