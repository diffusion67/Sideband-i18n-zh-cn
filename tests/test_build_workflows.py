"""Offline regressions for package collection and CI safety contracts."""

from pathlib import Path
import os
import shutil
import subprocess
import tempfile
import unittest
import zipfile


ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"


def step_script(workflow, name):
    text = (WORKFLOWS / workflow).read_text()
    step = text.split("      - name: " + name + "\n", 1)[1]
    step = step.split("\n      - ", 1)[0]
    script = step.split("        run: |\n", 1)[1]
    return "\n".join(line[10:] for line in script.splitlines())


class BuildWorkflowTests(unittest.TestCase):
    def test_fetchapk_collects_signed_and_unsigned_release_names(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            shutil.copy(ROOT / "Makefile", root)
            (root / "environment").touch()
            (root / "sbapp/bin").mkdir(parents=True)
            (root / "dist").mkdir()
            names = ["sideband-1.9.2-arm64-v8a-release.apk",
                     "sideband-1.9.2-arm64-v8a-release-unsigned.apk"]
            for name in names:
                (root / "sbapp/bin" / name).write_bytes(b"apk")
            subprocess.run(["make", "fetchapk"], cwd=root, check=True,
                           capture_output=True)
            self.assertEqual(sorted(p.name for p in (root / "dist").iterdir()),
                             sorted(names))

    def test_build_permissions_and_triggers(self):
        for filename in ("build-android-apk.yml", "build-windows-zip.yml"):
            text = (WORKFLOWS / filename).read_text()
            with self.subTest(workflow=filename):
                self.assertIn("  contents: read", text)
                self.assertNotIn("contents: write", text)
                self.assertIn("  workflow_dispatch:", text)
                self.assertIn("  pull_request:", text)
                self.assertIn("  push:", text)
                self.assertIn("    branches: [main]", text)
                self.assertIn("if-no-files-found: error", text)
                self.assertNotIn("if: always()", text)

    def test_signing_title_prefix_exits_before_creating_a_key(self):
        script = step_script("build-android-apk.yml", "Test-sign the approved Android release")
        env = dict(os.environ, RELEASE_COMMIT_MESSAGE=
                   "Release Sideband 1.9.2 Chinese test build (2026-10-02) extra")
        with tempfile.TemporaryDirectory() as tmp:
            env["RUNNER_TEMP"] = tmp
            subprocess.run(["bash", "-e", "-c", script], cwd=tmp, env=env,
                           capture_output=True, check=True)
            self.assertEqual(list(Path(tmp).iterdir()), [])

    def test_test_signing_is_limited_to_approved_release_merge(self):
        text = (WORKFLOWS / "build-android-apk.yml").read_text()
        self.assertIn("Release Sideband 1.9.2 Chinese test build (2026-10-02)", text)
        self.assertIn("github.event_name == 'push'", text)
        self.assertIn("github.ref == 'refs/heads/main'", text)
        self.assertIn('trap cleanup EXIT', text)
        self.assertIn('--print-certs', text)
        self.assertIn('not retained', text)

    def test_android_pins_toolchain_compatible_with_local_python_recipe(self):
        spec = (ROOT / "sbapp/buildozer.spec").read_text()
        self.assertIn("p4a.commit = 7593f9d62439b5864f7e6204fe382c424e11ad57", spec)
        self.assertIn("version = '3.11.5'", (ROOT / "recipes/python3/__init__.py").read_text())

    def test_android_setup_avoids_retired_tools_package(self):
        text = (WORKFLOWS / "build-android-apk.yml").read_text()
        self.assertIn("packages: platform-tools", text)

    def test_android_installs_patchelf_and_pins_observed_tool_versions(self):
        text = (WORKFLOWS / "build-android-apk.yml").read_text()
        self.assertIn("patchelf", text)
        self.assertIn("buildozer==1.6.0", text)
        self.assertIn("cython==0.29.37", text)

    def test_opusfile_uses_real_libogg_build_directory(self):
        text = (ROOT / "recipes/opusfile/__init__.py").read_text()
        self.assertIn("-L{}/src/.libs -logg", text)

    def test_android_unsigned_apk_is_labelled_not_installable(self):
        self.assertIn("      - name: Verify APK", (WORKFLOWS / "build-android-apk.yml").read_text())
        script = step_script("build-android-apk.yml", "Verify APK")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "dist").mkdir()
            apk = root / "dist/sideband-1.9.2-arm64-v8a-release-unsigned.apk"
            with zipfile.ZipFile(apk, "w") as archive:
                archive.writestr("AndroidManifest.xml", b"manifest")
                archive.writestr("classes.dex", b"dex")
                archive.writestr("lib/arm64-v8a/libpython3.11.so", b"lib")
            tools = root / "sdk/build-tools/33.0.2"
            tools.mkdir(parents=True)
            signer = tools / "apksigner"
            signer.write_text("#!/bin/sh\nexit 1\n")
            signer.chmod(0o755)
            env = dict(os.environ, ANDROID_SDK_ROOT=str(root / "sdk"))
            subprocess.run(["bash", "-e", "-c", script], cwd=root, env=env,
                           check=True, capture_output=True)
            self.assertIn("not installable", (root / "dist/APK-SIGNATURE.txt").read_text())
            self.assertIn(apk.name, (root / "dist/SHA256SUMS").read_text())

    def test_android_verifier_rejects_invalid_apk(self):
        self.assertIn("      - name: Verify APK", (WORKFLOWS / "build-android-apk.yml").read_text())
        script = step_script("build-android-apk.yml", "Verify APK")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "dist").mkdir()
            with zipfile.ZipFile(root / "dist/invalid-release-unsigned.apk", "w") as archive:
                archive.writestr("unrelated.txt", "not an Android app")
            result = subprocess.run(["bash", "-e", "-c", script], cwd=root,
                                    capture_output=True)
            self.assertNotEqual(result.returncode, 0)

    def test_android_verifier_requires_signature_tool(self):
        script = step_script("build-android-apk.yml", "Verify APK")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "dist").mkdir()
            with zipfile.ZipFile(root / "dist/sideband-test-release-unsigned.apk", "w") as archive:
                archive.writestr("AndroidManifest.xml", b"manifest")
                archive.writestr("classes.dex", b"dex")
                archive.writestr("lib/arm64-v8a/libpython3.11.so", b"lib")
            env = dict(os.environ, ANDROID_SDK_ROOT=str(root / "missing-sdk"))
            result = subprocess.run(["bash", "-e", "-c", script], cwd=root,
                                    env=env, capture_output=True)
            self.assertNotEqual(result.returncode, 0)

    def test_windows_archive_validation_checks_executable(self):
        script = step_script("build-windows-zip.yml", "Verify Windows ZIP")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "dist").mkdir()
            package = root / "dist/Sideband_windows_x86_64.zip"
            with zipfile.ZipFile(package, "w") as archive:
                archive.writestr("Sideband_1.9.2/Sideband.exe", b"executable")
            subprocess.run(["bash", "-e", "-c", script], cwd=root,
                           check=True, capture_output=True)
            with zipfile.ZipFile(package, "w") as archive:
                archive.writestr("README.txt", "missing executable")
            result = subprocess.run(["bash", "-e", "-c", script], cwd=root,
                                    capture_output=True)
            self.assertNotEqual(result.returncode, 0)

    def test_windows_ci_bundles_real_angle_backend_for_headless_runner(self):
        spec = (ROOT / "sideband.spec").read_text()
        workflow = (WORKFLOWS / "build-windows-zip.yml").read_text()
        self.assertIn('angle.dep_bins', spec)
        self.assertIn('kivy-deps.angle', workflow)
        self.assertIn('KIVY_GL_BACKEND: angle_sdl2', workflow)

    def test_windows_performs_runtime_startup_check(self):
        text = (WORKFLOWS / "build-windows-zip.yml").read_text()
        self.assertIn('name: Smoke test Windows executable', text)
        self.assertIn('HasExited', text)
        self.assertIn('--config', text)

    def test_windows_creates_real_zip_and_checks_build_failures(self):
        text = (ROOT / "winbuild.bat").read_text()
        self.assertIn("Compress-Archive", text)
        self.assertIn("if errorlevel 1 exit /b", text)
        self.assertIn("Sideband.exe", text)
        workflow = (WORKFLOWS / "build-windows-zip.yml").read_text()
        self.assertIn("path: dist/*.zip", workflow)
        self.assertIn("      - name: Verify Windows ZIP", workflow)


if __name__ == "__main__":
    unittest.main()
