#!/usr/bin/env python3
"""
Applies a fixed list of edits to the CloudX Android source.

Safety rules (zero assumptions):
  * Every edit looks for exact text. If the text is already changed, it is skipped.
  * If the original text is not found exactly once, the script STOPS with an error
    instead of guessing. Nothing is half-applied silently.
  * Running it twice changes nothing the second time.
"""
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
JAVA = "app/src/main/java/com/world/cloudxsolution/MainActivity.java"
LAYOUT = "app/src/main/res/layout/"
changed = []


def edit(rel, old, new, label):
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


# ---- 1. Site language: French -> English -------------------------------------
edit(JAVA,
     'webView.loadUrl("https://www.xbox.com/fr-FR/play");',
     'webView.loadUrl("https://www.xbox.com/en-US/play");',
     "Xbox site language fr-FR -> en-US")

# ---- 2. Fullscreen, camera cutout, keep screen on ----------------------------
edit(JAVA,
     "import androidx.core.content.ContextCompat;\n",
     "import androidx.core.content.ContextCompat;\n"
     "import androidx.core.view.WindowCompat;\n"
     "import androidx.core.view.WindowInsetsCompat;\n"
     "import androidx.core.view.WindowInsetsControllerCompat;\n",
     "imports for immersive mode")

edit(JAVA,
     "        setContentView(R.layout.activity_main);\n",
     "        setContentView(R.layout.activity_main);\n"
     "        applyImmersiveMode(getWindow());\n",
     "call immersive mode in onCreate")

HELPERS = '''    // ---- Fullscreen helpers (added by apply_fixes.py) ----
    private static void hideSystemBars(android.view.Window window) {
        if (window == null) return;
        WindowInsetsControllerCompat controller =
                WindowCompat.getInsetsController(window, window.getDecorView());
        controller.setSystemBarsBehavior(
                WindowInsetsControllerCompat.BEHAVIOR_SHOW_TRANSIENT_BARS_BY_SWIPE);
        controller.hide(WindowInsetsCompat.Type.systemBars());
    }

    private static void applyImmersiveMode(android.view.Window window) {
        if (window == null) return;
        // Keep the screen awake for as long as this window is shown.
        window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
        // Draw edge to edge, including behind the camera cutout, in both orientations.
        WindowCompat.setDecorFitsSystemWindows(window, false);
        WindowManager.LayoutParams lp = window.getAttributes();
        lp.layoutInDisplayCutoutMode =
                WindowManager.LayoutParams.LAYOUT_IN_DISPLAY_CUTOUT_MODE_SHORT_EDGES;
        window.setAttributes(lp);
        hideSystemBars(window);
    }

    @Override
    public void onWindowFocusChanged(boolean hasFocus) {
        super.onWindowFocusChanged(hasFocus);
        if (hasFocus) hideSystemBars(getWindow());
    }

'''
edit(JAVA,
     "    private void pushSurfaceIfReady() {\n",
     HELPERS + "    private void pushSurfaceIfReady() {\n",
     "fullscreen helper methods")

# Dialogs are separate windows, so they need the same bar-hiding call.
edit(JAVA,
     "        dialog.show();\n        btnOk.requestFocus();\n",
     "        hideSystemBars(dialog.getWindow());\n        dialog.show();\n        btnOk.requestFocus();\n",
     "hide bars on intro dialog")
edit(JAVA,
     "        dialog.show();\n        btnSubmit.requestFocus();\n",
     "        hideSystemBars(dialog.getWindow());\n        dialog.show();\n        btnSubmit.requestFocus();\n",
     "hide bars on keyboard dialog")
edit(JAVA,
     "        dialog.show();\n        btnExit.requestFocus();\n",
     "        hideSystemBars(dialog.getWindow());\n        dialog.show();\n        btnExit.requestFocus();\n",
     "hide bars on in-game menu")
edit(JAVA,
     "        dialog.show();\n        btnApply.requestFocus();\n",
     "        hideSystemBars(dialog.getWindow());\n        dialog.show();\n        btnApply.requestFocus();\n",
     "hide bars on app settings dialog")
edit(JAVA,
     "        CXdialoge dialog = new CXdialoge(this);\n        dialog.show();\n",
     "        CXdialoge dialog = new CXdialoge(this);\n        dialog.show();\n        hideSystemBars(dialog.getWindow());\n",
     "hide bars on controller settings dialog")

# ---- 3. Landscape: make three dialogs scrollable -----------------------------
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
    p = ROOT / rel
    text = p.read_text(encoding="utf-8")
    if "<ScrollView xmlns:android" in text:
        print(f"skip (already applied): scroll wrapper {name}")
        return
    if text.count(OLD_HEAD) != 1:
        sys.exit(f"ERROR [scroll {name}]: root tag not found exactly once")
    body = text.replace(OLD_HEAD, NEW_HEAD, 1)
    stripped = body.rstrip()
    if not stripped.endswith("</LinearLayout>"):
        sys.exit(f"ERROR [scroll {name}]: file does not end with </LinearLayout>")
    body = stripped + "\n</ScrollView>\n"
    p.write_text(body, encoding="utf-8")
    changed.append(f"scroll wrapper {name}")
    print(f"applied: scroll wrapper {name}")


for layout in ("dialog_app_settings.xml", "dialog_streaming_menu.xml", "dialog_intro_help.xml"):
    wrap_in_scroll(layout)

# ---- 4. Install next to the original app instead of replacing it -------------
edit("app/build.gradle.kts",
     "    buildTypes {\n        release {\n",
     "    buildTypes {\n        debug {\n            applicationIdSuffix = \".fixed\"\n        }\n        release {\n",
     "debug build installs as a separate app (.fixed)")
edit("app/src/main/res/values/strings.xml",
     '<string name="app_name">cloudxSolution</string>',
     '<string name="app_name">cloudxSolution Fixed</string>',
     "app label 'cloudxSolution Fixed'")

print("\nDone." if changed else "\nNothing to change.")
