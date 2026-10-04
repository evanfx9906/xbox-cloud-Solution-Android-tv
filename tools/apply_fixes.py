#!/usr/bin/env python3
"""
Edits for the CloudX fork (version v3). Written against the CURRENT source of
evanfx9906/xbox-cloud-Solution-Android-tv, which already contains the earlier
fullscreen / cutout / keep-awake code, so none of that is touched here.

Safety rules:
  * Each edit needs exact text. Already changed -> skipped.
  * Original text not found exactly once -> the script STOPS with an error.
  * Running it twice changes nothing the second time.
"""
import pathlib
import sys

BUILD_STAMP = "v3"

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


# ---- 1. Language: the Xbox page URL is hard-coded to French -------------------
edit(JAVA,
     'webView.loadUrl("https://www.xbox.com/fr-FR/play");',
     'webView.loadUrl("https://www.xbox.com/en-US/play");',
     "Xbox page language fr-FR -> en-US")

# ---- 2. Rotation: the manifest locks the screen to landscape ------------------
# "sensor" follows the phone's orientation sensor. Use "fullUser" instead if you
# want it to obey the phone's auto-rotate toggle.
edit("app/src/main/AndroidManifest.xml",
     'android:screenOrientation="landscape"',
     'android:screenOrientation="sensor"',
     "screen orientation landscape -> sensor")

# ---- 3. Landscape: make three dialogs scrollable ------------------------------
OLD_HEAD = '''<LinearLayout xmlns:android="http://schemas.android.com/apk/res/android"
    android:layout_width="340dp"
    android:layout_height="wrap_content"
    android:orientation="vertical"
    android:background="@drawable/bg_dialog_xbox"
    android:padding="20dp">
'''


def new_head(with_id):
    id_line = '    android:id="@+id/dialog_scroll"\n' if with_id else ""
    return ('<ScrollView xmlns:android="http://schemas.android.com/apk/res/android"\n'
            + id_line +
            '    android:layout_width="340dp"\n'
            '    android:layout_height="wrap_content"\n'
            '    android:background="@drawable/bg_dialog_xbox"\n'
            '    android:overScrollMode="ifContentScrolls">\n'
            '\n'
            '<LinearLayout\n'
            '    android:layout_width="match_parent"\n'
            '    android:layout_height="wrap_content"\n'
            '    android:orientation="vertical"\n'
            '    android:padding="20dp">\n')


def wrap_in_scroll(name, with_id=False):
    p = ROOT / (LAYOUT + name)
    text = p.read_text(encoding="utf-8")
    if "<ScrollView xmlns:android" in text:
        print(f"skip (already applied): scroll wrapper {name}")
        return
    if text.count(OLD_HEAD) != 1:
        sys.exit(f"ERROR [scroll {name}]: root tag not found exactly once")
    body = text.replace(OLD_HEAD, new_head(with_id), 1).rstrip()
    if not body.endswith("</LinearLayout>"):
        sys.exit(f"ERROR [scroll {name}]: file does not end with </LinearLayout>")
    p.write_text(body + "\n</ScrollView>\n", encoding="utf-8")
    changed.append(f"scroll wrapper {name}")
    print(f"applied: scroll wrapper {name}")


wrap_in_scroll("dialog_app_settings.xml", with_id=True)
wrap_in_scroll("dialog_streaming_menu.xml")
wrap_in_scroll("dialog_intro_help.xml")

# ---- 4. Install next to your current app instead of replacing it --------------
edit("app/build.gradle.kts",
     "    buildTypes {\n        release {\n",
     "    buildTypes {\n        debug {\n            applicationIdSuffix = \".fixed\"\n        }\n        release {\n",
     "debug build installs as a separate app (.fixed)")
edit("app/src/main/res/values/strings.xml",
     '<string name="app_name">cloudxSolution</string>',
     '<string name="app_name">cloudxSolution Fixed</string>',
     "app label 'cloudxSolution Fixed'")

# ---- 5. TEMPORARY read-only diagnostics (change no behaviour) -----------------
DIAG_HELPERS = '''    // ---- Temporary diagnostics (added by apply_fixes.py) ----
    private int diagPageCount = 0;
    private boolean diagSettingsShown = false;

    private void showDiagnostic(String title, String raw) {
        String msg = raw == null ? "null" : raw.replaceAll("^\\"|\\"$", "").replace(" | ", "\\n");
        new androidx.appcompat.app.AlertDialog.Builder(this)
                .setTitle(title)
                .setMessage(msg)
                .setPositiveButton("OK", null)
                .show();
    }

'''
edit(JAVA,
     "private boolean debug=false;\n    public void showCustomToast",
     DIAG_HELPERS + "private boolean debug=false;\n    public void showCustomToast",
     "diagnostic helper")

DIAG_PAGE = '''super.onPageFinished(view, url);
                if (diagPageCount < 2 && url != null && url.contains("xbox.com")) {
                    diagPageCount++;
                    view.evaluateJavascript(
                            "(function(){return 'URL: ' + location.href + ' | navigator.language: ' + navigator.language + ' | page lang attribute: ' + document.documentElement.lang;})()",
                            value -> showDiagnostic("Build ''' + BUILD_STAMP + ''' - language check " + diagPageCount + "/2", value));
                }
'''
edit(JAVA,
     "super.onPageFinished(view, url);\n",
     DIAG_PAGE,
     "language diagnostic on page load")

edit(JAVA,
     "        dialog.show();\n        btnApply.requestFocus();\n",
     "        dialog.show();\n        btnApply.requestFocus();\n"
     "        if (!diagSettingsShown) {\n"
     "            diagSettingsShown = true;\n"
     "            dialog.getWindow().getDecorView().postDelayed(() -> {\n"
     "                View sv = dialog.findViewById(R.id.dialog_scroll);\n"
     "                if (sv == null) return;\n"
     "                View child = ((ViewGroup) sv).getChildAt(0);\n"
     "                showDiagnostic(\"Build " + BUILD_STAMP + " - settings dialog\",\n"
     "                        \"screen height px: \" + getResources().getDisplayMetrics().heightPixels\n"
     "                        + \" | window height px: \" + dialog.getWindow().getDecorView().getHeight()\n"
     "                        + \" | scroll area height px: \" + sv.getHeight()\n"
     "                        + \" | content height px: \" + (child == null ? -1 : child.getHeight())\n"
     "                        + \" | can scroll down: \" + sv.canScrollVertically(1)\n"
     "                        + \" | can scroll up: \" + sv.canScrollVertically(-1)\n"
     "                        + \" | orientation (1=portrait, 2=landscape): \" + getResources().getConfiguration().orientation);\n"
     "            }, 500);\n"
     "        }\n",
     "settings dialog scroll diagnostic")

print("\nDone." if changed else "\nNothing to change.")
