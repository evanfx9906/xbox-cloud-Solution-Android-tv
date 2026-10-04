package com.world.cloudxsolution;

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
            StringBuilder sb = new StringBuilder("stack dump (" + reason + ")\n");
            for (Map.Entry<Thread, StackTraceElement[]> e : Thread.getAllStackTraces().entrySet()) {
                StackTraceElement[] st = e.getValue();
                if (st.length == 0) continue;
                String name = e.getKey().getName();
                if (name.contains("Daemon") || name.contains("Signal Catcher") || name.contains("Jit")
                        || name.contains("ReferenceQueue") || name.contains("perfetto") || name.contains("Profile Saver")) continue;
                if (st[0].getMethodName().equals("nativePollOnce")) continue;
                sb.append("[").append(name).append("] ").append(e.getKey().getState()).append('\n');
                for (int i = 0; i < Math.min(st.length, 12); i++) {
                    sb.append("   at ").append(st[i]).append('\n');
                }
                if (sb.length() > 40000) {
                    sb.append("...truncated\n");
                    break;
                }
            }
            DiagnosticLog.log(process, "STACK_DUMP_" + reason, sb.toString());
        } catch (Throwable ignored) {
            // diagnostics must never crash the app
        }
    }
}
