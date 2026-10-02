"""Offline freezer regressions and native CI smoke checks."""

import contextlib
import os
from pathlib import Path
import re
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
                 "mapview/icons/marker.png", "LXST/Filters.h", "pycparser/c_parser.pyc"):
        path = lib / name
        assert path.is_file() and path.stat().st_size > 0, f"Missing packaged resource: {name}"
    assert list((lib / "LXST").glob("filterlib*.so")), "Missing native LXST filter library"
    assert list((lib / "pycodec2").glob("*.so")), "Missing native Codec2 extension"
    if sys.platform == "linux":
        assert (lib / "libmtdev.so.1").is_file(), "Missing native multitouch library libmtdev.so.1"
    elif sys.platform == "darwin":
        for name in ("libogg.0.dylib", "libopus.0.dylib", "libopusfile.0.dylib"):
            assert (lib / "LXST/Codecs/libs/pyogg/libs/macos" / name).is_file(), f"Missing native audio library {name}"


class MacGraphicsUnavailable(AssertionError):
    """The observed hosted-macOS accelerated OpenGL constraint, not a pass."""


def known_mac_graphics_failure(text):
    if "sdl2 - RuntimeError: b'Failed creating OpenGL pixel format'" not in text:
        return False
    if "Unable to get a Window, abort." not in text:
        return False
    if any(marker in text for marker in ("Traceback (most recent call last)",
                                        "falling back to Python filters",
                                        "Could not load pre-compiled LXST filters library")):
        return False
    errors = [line for line in text.splitlines() if re.search(r"\[(?:ERROR|CRITICAL)\s*\]", line, re.I)]
    allowed = ("Unable to find any valuable Window provider.", "Unable to get a Window, abort.")
    return bool(errors) and all(any(message in line for message in allowed) for line in errors)


def smoke(executable, timeout=90, daemon=False, log_path=None):
    """Require real GUI/core startup with isolated state and no source cwd."""
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
            command = [str(executable), "-v", "--config", str(home / "sideband"), "--rnsconfig", str(rns)]
            master = slave = None
            if daemon:
                command.append("--daemon")
            # The frozen interpreter ignores PYTHONUNBUFFERED. A PTY makes
            # readiness and native-filter diagnostics immediately observable.
            import pty
            master, slave = pty.openpty()
            os.set_blocking(master, False)
            try:
                process = subprocess.Popen(
                    command, cwd=home, env=env,
                    stdout=slave if slave is not None else log, stderr=subprocess.STDOUT,
                )
            except BaseException:
                if master is not None:
                    os.close(master)
                if slave is not None:
                    os.close(slave)
                raise
            # Keep our slave open until after the final read. On macOS, the
            # last slave close flushes unread output, including late errors.

            def drain_daemon_output():
                if master is not None:
                    while True:
                        try:
                            chunk = os.read(master, 65536)
                            if not chunk:
                                break
                            log.write(chunk)
                        except BlockingIOError:
                            break
                        except OSError as error:
                            if error.errno != 5:  # PTY EOF after process exit
                                raise
                            break
                    log.flush()
            startup_verified = False
            try:
                deadline = time.monotonic() + timeout
                ready_since = None
                while time.monotonic() < deadline:
                    drain_daemon_output()
                    text = output.read_text(errors="replace")
                    assert "Traceback (most recent call last)" not in text, text
                    assert "falling back to Python filters" not in text, f"Native filter acceleration unavailable:\n{text}"
                    assert "Could not load pre-compiled LXST filters library" not in text, text
                    if process.poll() is not None:
                        # poll() can observe exit after the previous PTY read.
                        # Classify all final output, including any late exception.
                        drain_daemon_output()
                        text = output.read_text(errors="replace")
                        known_graphics = not daemon and sys.platform == "darwin" and known_mac_graphics_failure(text)
                        if known_graphics:
                            raise MacGraphicsUnavailable(text)
                        raise AssertionError(f"Sideband exited before {'daemon' if daemon else 'GUI'} startup:\n{text}")
                    # Diagnostics can arrive in fragments. Classify generic
                    # errors only after exit/full drain or before readiness;
                    # never terminate a still-incomplete macOS diagnostic.
                    config = home / "sideband/app_storage"
                    if daemon:
                        ready = bool(re.search(r"Sideband Core .+started", text)) and all(
                            (config / name).is_file() for name in ("sideband_config", "sideband.db", "primary_identity"))
                    else:
                        ready = "Start application main loop" in text and (config / "sideband_config").is_file()
                    if ready:
                        assert not re.search(r"\[(?:ERROR|CRITICAL)\s*\]", text, re.I), text
                        if ready_since is None:
                            ready_since = time.monotonic()
                        if time.monotonic() - ready_since >= 3:
                            startup_verified = True
                            print(f"Native {'daemon' if daemon else 'GUI'} startup and isolated configuration verified")
                            return text
                    time.sleep(0.25)
                raise AssertionError(f"{'Daemon' if daemon else 'GUI'} did not become ready in {timeout}s:\n{output.read_text(errors='replace')}")
            finally:
                try:
                    if process.poll() is None:
                        process.terminate()
                        try:
                            process.wait(timeout=10)
                        except subprocess.TimeoutExpired:
                            process.kill()
                            process.wait()
                    drain_daemon_output()
                finally:
                    if slave is not None:
                        os.close(slave)
                    if master is not None:
                        os.close(master)
                if log_path is not None:
                    log.flush()
                    Path(log_path).write_bytes(output.read_bytes())
                final_text = output.read_text(errors="replace")
                assert "Traceback (most recent call last)" not in final_text, final_text
                allowed_graphics = not startup_verified and not daemon and sys.platform == "darwin" and known_mac_graphics_failure(final_text)
                assert allowed_graphics or not re.search(r"\[(?:ERROR|CRITICAL)\s*\]", final_text, re.I), final_text
                assert "falling back to Python filters" not in final_text, f"Native filter acceleration unavailable:\n{final_text}"
                assert "Could not load pre-compiled LXST filters library" not in final_text, final_text


def macos_validation(executable, resources, report, architecture):
    """Keep the known host graphics limit explicit; all other failures abort."""
    assert sys.platform == "darwin", "Experimental graphics classification is macOS-only"
    verify_resources(resources)
    report = Path(report)
    report.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="sideband-macos-validation-") as tmp:
        daemon_log = Path(tmp) / "daemon.log"
        gui_log = Path(tmp) / "gui.log"
        smoke(executable, daemon=True, log_path=daemon_log)
        try:
            smoke(executable, log_path=gui_log)
            gui_status = "PASS: actual GUI event loop and isolated configuration verified"
        except MacGraphicsUnavailable:
            gui_status = ("UNVERIFIED: hosted macOS runner cannot create Kivy/SDL2's required accelerated OpenGL pixel format. "
                          "The GUI was attempted and failed at window creation; this is not a GUI pass.")
        report.write_text(
            f"EXPERIMENTAL macOS {architecture} validation\n"
            f"Commit: {os.environ.get('GITHUB_SHA', 'local build')}\n"
            "DMG integrity: PASS (hdiutil verify in workflow)\n"
            f"Native architectures: PASS (executable and all packaged dylib/so files contain {architecture})\n"
            "Required packaged resources: PASS\n"
            "Daemon startup: PASS (core started; isolated configuration, database and identity created)\n"
            f"GUI startup: {gui_status}\n"
            "Audio runtime: UNVERIFIED (microphone, speaker and voice calls not exercised)\n"
            "Signing: no Developer ID or notarization; only freezer ad-hoc signatures\n"
            "\n--- Actual GUI attempt log ---\n" + gui_log.read_text(errors="replace") +
            "\n--- Actual daemon startup log ---\n" + daemon_log.read_text(errors="replace"), encoding="utf-8")
        print(gui_status)


def freezer_config(platform, machine="x86_64"):
    captured = {}
    freezer = types.ModuleType("cx_Freeze")
    freezer.Executable = lambda **kw: kw
    freezer.setup = lambda **kw: captured.update(kw)
    with tempfile.TemporaryDirectory() as tmp:
        with patch.dict(sys.modules, {"cx_Freeze": freezer, "setuptools": types.ModuleType("setuptools")}), patch.object(sys, "platform", platform), patch("platform.machine", return_value=machine):
            with contextlib.chdir(tmp):
                runpy.run_path(str(ROOT / "sbapp/freeze.py"), run_name="__main__")
    return captured


class DesktopBuildTests(unittest.TestCase):
    def test_smoke_retains_pty_slave_until_exit_and_closes_both_descriptors(self):
        import pty
        real_openpty = pty.openpty
        descriptors = []
        slave_open_at_exit = []
        def recording_openpty():
            pair = real_openpty()
            descriptors.extend(pair)
            return pair
        class ExitingProcess:
            def __init__(self, *args, **kwargs):
                self.slave = kwargs["stdout"]
            def poll(self):
                try:
                    os.fstat(self.slave)
                    slave_open_at_exit.append(True)
                except OSError:
                    slave_open_at_exit.append(False)
                return 1
        with patch("pty.openpty", recording_openpty), patch("subprocess.Popen", ExitingProcess):
            with self.assertRaisesRegex(AssertionError, "exited before"):
                smoke(Path("/fake/Sideband"), timeout=2)
        self.assertTrue(all(slave_open_at_exit), "Closing the last PTY slave can discard final output on macOS")
        for descriptor in descriptors:
            with self.assertRaises(OSError):
                os.fstat(descriptor)

    def test_smoke_closes_pty_descriptors_when_process_cannot_start(self):
        import pty
        real_openpty = pty.openpty
        descriptors = []
        def recording_openpty():
            pair = real_openpty()
            descriptors.extend(pair)
            return pair
        with patch("pty.openpty", recording_openpty):
            with self.assertRaises(FileNotFoundError):
                smoke(Path("/nonexistent-sideband-executable"), timeout=2)
        for descriptor in descriptors:
            with self.assertRaises(OSError):
                os.fstat(descriptor)

    def test_macos_report_preserves_unverified_gui_and_actual_attempt_log(self):
        calls = []
        def fake_smoke(executable, daemon=False, log_path=None):
            calls.append(daemon)
            Path(log_path).write_text("real daemon log" if daemon else "real blocked GUI log")
            if not daemon:
                raise MacGraphicsUnavailable("blocked")
        with tempfile.TemporaryDirectory() as tmp:
            report = Path(tmp) / "PLATFORM-VALIDATION-macos-arm64.txt"
            with patch.object(sys, "platform", "darwin"), patch.dict(globals(), {"smoke": fake_smoke, "verify_resources": lambda p: None}):
                macos_validation(Path(tmp) / "app", Path(tmp), report, "arm64")
            text = report.read_text()
            self.assertEqual(calls, [True, False])
            self.assertIn("GUI startup: UNVERIFIED", text)
            self.assertIn("Audio runtime: UNVERIFIED", text)
            self.assertIn("real blocked GUI log", text)
            self.assertIn("real daemon log", text)

    def test_macos_report_does_not_publish_for_other_runtime_errors(self):
        def fake_smoke(executable, daemon=False, log_path=None):
            Path(log_path).write_text("runtime failed")
            if not daemon:
                raise AssertionError("unexpected missing module")
        with tempfile.TemporaryDirectory() as tmp:
            report = Path(tmp) / "PLATFORM-VALIDATION-macos-arm64.txt"
            with patch.object(sys, "platform", "darwin"), patch.dict(globals(), {"smoke": fake_smoke, "verify_resources": lambda p: None}):
                with self.assertRaisesRegex(AssertionError, "unexpected missing module"):
                    macos_validation(Path(tmp) / "app", Path(tmp), report, "arm64")
            self.assertFalse(report.exists())

    def test_exit_drain_does_not_hide_late_traceback_behind_mac_graphics_error(self):
        log = ("[CRITICAL] [Window] Unable to find any valuable Window provider.\n"
               "sdl2 - RuntimeError: b'Failed creating OpenGL pixel format'\n"
               "[CRITICAL] [App] Unable to get a Window, abort.\n")
        class ExitingProcess:
            def __init__(self, *args, **kwargs):
                self.output = os.dup(kwargs["stdout"])
                self.pending = True
                os.write(self.output, log.encode())
            def poll(self):
                if self.pending:
                    os.write(self.output, b"Traceback (most recent call last): late failure\n")
                    os.close(self.output)
                    self.pending = False
                return 1
        with patch.object(sys, "platform", "darwin"), patch("subprocess.Popen", ExitingProcess):
            with self.assertRaises(AssertionError) as error:
                smoke(Path("/fake/Sideband"), timeout=2)
        self.assertNotIsInstance(error.exception, MacGraphicsUnavailable)
        self.assertIn("late failure", str(error.exception))

    def test_smoke_waits_for_complete_fragmented_mac_graphics_diagnostic(self):
        prefix = ("[CRITICAL] [Window] Unable to find any valuable Window provider.\n"
                  "sdl2 - RuntimeError: b'Failed creating OpenGL pixel format'\n")
        suffix = "[CRITICAL] [App] Unable to get a Window, abort.\n"
        class FragmentedProcess:
            def __init__(self, *args, **kwargs):
                self.output = os.dup(kwargs["stdout"])
                self.polls = 0
                os.write(self.output, prefix.encode())
            def poll(self):
                self.polls += 1
                if self.polls == 1:
                    return None
                if self.polls == 2:
                    os.write(self.output, suffix.encode())
                    os.close(self.output)
                return 1
        with patch.object(sys, "platform", "darwin"), patch("subprocess.Popen", FragmentedProcess):
            with self.assertRaises(MacGraphicsUnavailable) as error:
                smoke(Path("/fake/Sideband"), timeout=2)
        self.assertIn(suffix.strip(), str(error.exception))

    def test_smoke_never_accepts_gui_readiness_with_graphics_errors(self):
        log = ("[CRITICAL] [Window] Unable to find any valuable Window provider.\n"
               "sdl2 - RuntimeError: b'Failed creating OpenGL pixel format'\n"
               "[CRITICAL] [App] Unable to get a Window, abort.\n"
               "Start application main loop\n")
        class RunningProcess:
            def __init__(self, command, **kwargs):
                self.returncode = None
                config = Path(command[command.index("--config") + 1]) / "app_storage"
                config.mkdir(parents=True)
                (config / "sideband_config").write_text("created")
                os.write(kwargs["stdout"], log.encode())
            def poll(self):
                return self.returncode
            def terminate(self):
                self.returncode = -15
            def wait(self, timeout=None):
                return self.returncode
        with patch.object(sys, "platform", "darwin"), patch("subprocess.Popen", RunningProcess):
            with self.assertRaises(AssertionError) as error:
                smoke(Path("/fake/Sideband"), timeout=4)
        self.assertNotIsInstance(error.exception, MacGraphicsUnavailable)

    def test_known_mac_graphics_failure_does_not_hide_other_errors(self):
        log = "[CRITICAL] [Window] Unable to find any valuable Window provider.\n"
        log += "sdl2 - RuntimeError: b'Failed creating OpenGL pixel format'\n"
        log += "[CRITICAL] [App] Unable to get a Window, abort.\n"
        self.assertTrue(known_mac_graphics_failure(log))
        self.assertFalse(known_mac_graphics_failure(log + "[ERROR] missing module\n"))
        self.assertFalse(known_mac_graphics_failure(log + "Traceback (most recent call last):\n"))
        self.assertFalse(known_mac_graphics_failure(log + "falling back to Python filters\n"))

    def test_mac_workflow_publishes_precise_validation_report(self):
        text = (ROOT / ".github/workflows/build-desktop.yml").read_text()
        self.assertIn('--macos-report "dist/PLATFORM-VALIDATION-${{ matrix.platform }}.txt"', text)
        self.assertIn('dist/PLATFORM-VALIDATION-macos*.txt', text)

    def test_resource_verifier_rejects_missing_font(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(AssertionError, "NotoSansSC"):
                verify_resources(Path(tmp))

    def test_macos_resource_verifier_requires_bundled_opus_libraries(self):
        with tempfile.TemporaryDirectory() as tmp:
            for name in ("sbapp/assets/fonts/NotoSansSC-Regular.ttf", "sbapp/assets/icon.png",
                         "sbapp/sideband/core.pyc", "sbapp/i18n.pyc", "kivymd/uix/button/button.kv",
                         "mapview/icons/marker.png", "LXST/Filters.h", "LXST/filterlib.test.so",
                         "pycodec2/pycodec2.test.so", "pycparser/c_parser.pyc"):
                path = Path(tmp) / "lib" / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b"resource")
            with patch.object(sys, "platform", "darwin"):
                with self.assertRaisesRegex(AssertionError, "libogg"):
                    verify_resources(Path(tmp))

    def test_smoke_rejects_executable_that_only_reports_version(self):
        with tempfile.TemporaryDirectory() as tmp:
            executable = Path(tmp) / "fake-sideband"
            executable.write_text("#!/bin/sh\necho 'sideband 1.9.2'\n")
            executable.chmod(0o755)
            with self.assertRaisesRegex(AssertionError, "exited before"):
                smoke(executable, timeout=2)

    def test_smoke_rejects_missing_native_filter_acceleration(self):
        with tempfile.TemporaryDirectory() as tmp:
            executable = Path(tmp) / "fake-sideband"
            executable.write_text("#!/bin/sh\necho 'falling back to Python filters'\nsleep 5\n")
            executable.chmod(0o755)
            with self.assertRaisesRegex(AssertionError, "Native filter acceleration unavailable"):
                smoke(executable, timeout=1)

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

    def test_linux_bundles_mtdev_instead_of_relying_on_host_installation(self):
        options = freezer_config("linux")["options"]["build_exe"]
        destinations = {str(dst) for _, dst in options["include_files"]}
        self.assertIn("lib/libmtdev.so.1", destinations)
        self.assertIn("libmtdev.so", options.get("bin_includes", []))
        text = (ROOT / ".github/workflows/build-desktop.yml").read_text()
        self.assertIn("libmtdev1", text)

    def test_linux_installs_display_resolution_helper_for_real_gui_probe(self):
        text = (ROOT / ".github/workflows/build-desktop.yml").read_text()
        self.assertIn("x11-xserver-utils", text)

    def test_lipo_places_input_before_variadic_architectures(self):
        text = (ROOT / ".github/workflows/build-desktop.yml").read_text()
        self.assertIn('lipo "$app/Contents/MacOS/Sideband" -verify_arch "${{ matrix.arch }}"', text)
        self.assertIn('lipo "$library" -verify_arch "${{ matrix.arch }}"', text)
        self.assertNotIn('lipo -verify_arch', text)

    def test_arm_mac_replaces_intel_only_vendored_audio_libraries(self):
        with patch.dict(os.environ, {"SIDEBAND_MACOS_LIB_DIR": "/native/homebrew/lib"}):
            options = freezer_config("darwin", machine="arm64")["options"]["build_exe"]
        self.assertIn("LXST.Codecs.libs.pyogg.libs.macos", options["excludes"])
        files = dict(options["include_files"])
        for name in ("libogg.0.dylib", "libopus.0.dylib", "libopusfile.0.dylib"):
            self.assertEqual(files.get("/native/homebrew/lib/" + name),
                             "lib/LXST/Codecs/libs/pyogg/libs/macos/" + name)

    def test_architecture_check_reports_offending_library(self):
        text = (ROOT / ".github/workflows/build-desktop.yml").read_text()
        self.assertIn('printf "Checking architecture: %s\\n" "$library"', text)
        self.assertIn('lipo "$library" -archs', text)
        self.assertIn('SIDEBAND_MACOS_LIB_DIR=$(brew --prefix)/lib', text)

    def test_ci_pins_numpy_compatible_with_freezer_hook(self):
        text = (ROOT / ".github/workflows/build-desktop.yml").read_text()
        self.assertIn('"numpy==2.3.4"', text)

    def test_ci_pins_pycparser_with_tables_required_by_freezer(self):
        text = (ROOT / ".github/workflows/build-desktop.yml").read_text()
        self.assertIn('"pycparser==2.23"', text)

    def test_offline_job_installs_android_build_regression_dependency(self):
        text = (ROOT / ".github/workflows/build-desktop.yml").read_text()
        self.assertIn("python -m pip install -c recipes/android-build-constraints.txt build", text)


if __name__ == "__main__":
    if "--smoke" in sys.argv:
        import argparse
        parser = argparse.ArgumentParser()
        parser.add_argument("--smoke", type=Path, required=True)
        parser.add_argument("--resources", type=Path, required=True)
        parser.add_argument("--macos-report", type=Path)
        parser.add_argument("--architecture", choices=("arm64", "x86_64"))
        args = parser.parse_args()
        if args.macos_report:
            if not args.architecture:
                parser.error("--architecture is required with --macos-report")
            macos_validation(args.smoke, args.resources, args.macos_report, args.architecture)
        else:
            verify_resources(args.resources)
            smoke(args.smoke)
    else:
        unittest.main()
