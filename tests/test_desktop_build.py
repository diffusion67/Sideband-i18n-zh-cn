"""Offline freezer regressions and native CI smoke checks."""

import contextlib
import os
from pathlib import Path
import runpy
import subprocess
import sys
import tempfile
import time
import types
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]


def verify_resources(resource_root):
    """Inspect extracted/mounted output, never files in the source checkout."""
    lib = Path(resource_root).resolve() / "lib"
    for name in ("sbapp/assets/fonts/NotoSansSC-Regular.ttf",
                 "sbapp/assets/icon.png", "sbapp/sideband/core.pyc",
                 "sbapp/i18n.pyc", "kivymd/uix/button/button.kv",
                 "mapview/icons/marker.png", "LXST/Filters.h"):
        path = lib / name
        assert path.is_file() and path.stat().st_size > 0, f"Missing packaged resource: {name}"
    assert list((lib / "LXST").glob("filterlib*.so")), "Missing native LXST filter library"
    assert list((lib / "pycodec2").glob("*.so")), "Missing native Codec2 extension"


def smoke(executable, timeout=90):
    """Require real GUI startup with isolated user state and no source cwd."""
    executable = Path(executable).resolve()
    with tempfile.TemporaryDirectory(prefix="sideband-smoke-") as tmp:
        home = Path(tmp)
        rns = home / "reticulum"
        rns.mkdir()
        (rns / "config").write_text("[reticulum]\n  enable_transport = No\n  share_instance = No\n[interfaces]\n")
        env = dict(os.environ, HOME=tmp, KIVY_HOME=str(home / "kivy"),
                   KIVY_NO_ARGS="1", PYTHONUNBUFFERED="1")
        env.pop("PYTHONPATH", None)
        env.pop("PYTHONHOME", None)
        output = home / "startup.log"
        with output.open("wb") as log:
            process = subprocess.Popen(
                [str(executable), "-v", "--config", str(home / "sideband"),
                 "--rnsconfig", str(rns)], cwd=home, env=env,
                stdout=log, stderr=subprocess.STDOUT,
            )
            try:
                deadline = time.monotonic() + timeout
                ready_since = None
                while time.monotonic() < deadline:
                    text = output.read_text(errors="replace")
                    assert process.poll() is None, f"Sideband exited before GUI startup:\n{text}"
                    assert "Traceback (most recent call last)" not in text, text
                    ready = "Start application main loop" in text and (
                        home / "sideband/app_storage/sideband_config").is_file()
                    if ready:
                        if ready_since is None:
                            ready_since = time.monotonic()
                        if time.monotonic() - ready_since >= 3:
                            print("Native GUI startup and isolated configuration verified")
                            return
                    time.sleep(0.25)
                raise AssertionError(f"GUI did not become ready in {timeout}s:\n{output.read_text(errors='replace')}")
            finally:
                if process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait()


def freezer_config(platform):
    captured = {}
    freezer = types.ModuleType("cx_Freeze")
    freezer.Executable = lambda **kw: kw
    freezer.setup = lambda **kw: captured.update(kw)
    with tempfile.TemporaryDirectory() as tmp:
        with patch.dict(sys.modules, {"cx_Freeze": freezer, "setuptools": types.ModuleType("setuptools")}), patch.object(sys, "platform", platform):
            with contextlib.chdir(tmp):
                runpy.run_path(str(ROOT / "sbapp/freeze.py"), run_name="__main__")
    return captured


class DesktopBuildTests(unittest.TestCase):
    def test_resource_verifier_rejects_missing_font(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(AssertionError, "NotoSansSC"):
                verify_resources(Path(tmp))

    def test_smoke_rejects_executable_that_only_reports_version(self):
        with tempfile.TemporaryDirectory() as tmp:
            executable = Path(tmp) / "fake-sideband"
            executable.write_text("#!/bin/sh\necho 'sideband 1.9.2'\n")
            executable.chmod(0o755)
            with self.assertRaisesRegex(AssertionError, "exited before"):
                smoke(executable, timeout=2)

    def test_linux_uses_supported_commands_and_package_launcher(self):
        config = freezer_config("linux")
        self.assertIn("build_exe", config["options"])
        self.assertIn("bdist_appimage", config["options"])
        self.assertNotIn("build_appimage", config["options"])
        executable = config["executables"][0]
        self.assertEqual(Path(executable["script"]), ROOT / "main.py")
        self.assertTrue(Path(executable["icon"]).is_file())

    def test_native_resources_and_dynamic_packages_are_collected(self):
        options = freezer_config("linux")["options"].get("build_exe", {})
        self.assertIn(str(ROOT / "sbapp"), options.get("path", []))
        destinations = {str(dst) for _, dst in options.get("include_files", [])}
        self.assertIn("lib/sbapp/assets", destinations)
        self.assertIn("lib/kivymd", destinations)
        self.assertIn("lib/mapview", destinations)
        self.assertIn("sbapp.plyer.platforms.linux", options.get("packages", []))
        self.assertIn("LXST.filterlib", options.get("includes", []))
        self.assertIn("*", options.get("zip_exclude_packages", []))

    def test_mac_dmg_has_bundle_icon_microphone_permission_and_no_identity(self):
        options = freezer_config("darwin")["options"]
        self.assertIn("bdist_mac", options)
        self.assertIn("bdist_dmg", options)
        mac = options["bdist_mac"]
        self.assertTrue(Path(mac["iconfile"]).is_file())
        self.assertIn("NSMicrophoneUsageDescription", dict(mac["plist_items"]))
        self.assertIn("语音", dict(mac["plist_items"])["NSMicrophoneUsageDescription"])
        self.assertNotIn("codesign_identity", mac)
        self.assertIn("sbapp.plyer.platforms.macosx", options["build_exe"]["packages"])

    def test_ci_builds_native_artifacts_and_checks_runtime(self):
        path = ROOT / ".github/workflows/build-desktop.yml"
        self.assertTrue(path.is_file(), "Desktop build workflow is missing")
        text = path.read_text()
        for expected in ("contents: read", "ubuntu-22.04", "macos-14", "macos-15-intel",
                         "bdist_appimage", "bdist_dmg", "--appimage-extract",
                         "hdiutil verify", "--smoke", "--resources", "if-no-files-found: error"):
            self.assertIn(expected, text)
        self.assertNotIn("contents: write", text)
        self.assertNotIn("continue-on-error", text)
        self.assertIn("lipo -verify_arch", text)

    def test_ci_pins_numpy_compatible_with_freezer_hook(self):
        text = (ROOT / ".github/workflows/build-desktop.yml").read_text()
        self.assertIn('"numpy==2.3.4"', text)


if __name__ == "__main__":
    if "--smoke" in sys.argv:
        import argparse
        parser = argparse.ArgumentParser()
        parser.add_argument("--smoke", type=Path, required=True)
        parser.add_argument("--resources", type=Path, required=True)
        args = parser.parse_args()
        verify_resources(args.resources)
        smoke(args.smoke)
    else:
        unittest.main()
