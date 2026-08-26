# GitHub APK and Windows Builds Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add manually triggered GitHub Actions workflows that build downloadable Android APK and Windows ZIP artifacts.

**Architecture:** Two independent workflow files run on their native GitHub-hosted operating systems. Both retrieve Sideband's three sibling-source dependencies, invoke the repository's existing build entry point, and upload only its produced artifact. A Python standard-library test validates the workflow contracts without requiring a local GitHub runner.

**Tech Stack:** GitHub Actions, Ubuntu, Windows, Buildozer, Java 17, Python, PyInstaller, `unittest`.

**Spec:** `docs/superpowers/specs/2026-08-26-github-builds-design.md`

## Global Constraints

- Workflows trigger only with `workflow_dispatch`; they must not add `push`, `pull_request`, release, signing, or secrets.
- Android runs `make apk` and uploads `dist/*.apk`.
- Windows runs `winbuild.bat` and uploads `Sideband_*.zip`.
- Dependencies are checked out as sibling directories named `Reticulum`, `LXMF`, and `LXST`.
- Artifact uploads use `if: always()` and retain artifacts for 14 days.

---

### Task 1: Add workflow contract tests

**Files:**
- Create: `tests/test_github_workflows.py`

**Interfaces:**
- Consumes: `.github/workflows/build-android-apk.yml` and `.github/workflows/build-windows-zip.yml` as UTF-8 text.
- Produces: regression checks for dispatch-only triggers, expected runner, build command, dependency names, and artifact paths.

- [ ] **Step 1: Write the failing test**

```python
def test_android_workflow_is_manual_and_uploads_apk(self):
    workflow = self.read_workflow("build-android-apk.yml")
    self.assertIn("workflow_dispatch:", workflow)
    self.assertNotIn("push:", workflow)
    self.assertIn("runs-on: ubuntu-22.04", workflow)
    self.assertIn("make apk", workflow)
    self.assertIn("path: dist/*.apk", workflow)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_github_workflows -v`

Expected: failure because neither workflow file exists.

- [ ] **Step 3: Add the equivalent Windows contract test**

```python
def test_windows_workflow_is_manual_and_uploads_zip(self):
    workflow = self.read_workflow("build-windows-zip.yml")
    self.assertIn("workflow_dispatch:", workflow)
    self.assertNotIn("push:", workflow)
    self.assertIn("runs-on: windows-2022", workflow)
    self.assertIn("winbuild.bat", workflow)
    self.assertIn("path: Sideband_*.zip", workflow)
```

- [ ] **Step 4: Commit the failing tests**

```bash
git add tests/test_github_workflows.py
git commit -m "test: define build workflow contracts"
```

### Task 2: Add Android APK workflow

**Files:**
- Create: `.github/workflows/build-android-apk.yml`
- Modify: `tests/test_github_workflows.py`

**Interfaces:**
- Consumes: a manual Actions dispatch and public source repositories `markqvist/Reticulum`, `markqvist/LXMF`, and `markqvist/LXST`.
- Produces: a `sideband-android-apk-${{ github.run_number }}` Actions artifact from `dist/*.apk`.

- [ ] **Step 1: Write the minimal workflow**

```yaml
name: Build Android APK
on:
  workflow_dispatch:
jobs:
  build:
    runs-on: ubuntu-22.04
    steps:
      - uses: actions/checkout@v4
      - uses: actions/checkout@v4
        with:
          repository: markqvist/Reticulum
          path: Reticulum
      - uses: actions/checkout@v4
        with:
          repository: markqvist/LXMF
          path: LXMF
      - uses: actions/checkout@v4
        with:
          repository: markqvist/LXST
          path: LXST
      - run: make apk
      - if: always()
        uses: actions/upload-artifact@v4
        with:
          path: dist/*.apk
```

- [ ] **Step 2: Add toolchain setup before `make apk`**

Install Python 3.11, Temurin Java 17, Android command-line tools, NDK 25b, Buildozer, and the packages required by `sbapp/Makefile`. Export `ANDROIDSDK`, `ANDROID_HOME`, and `ANDROID_NDK_HOME` through `GITHUB_ENV` so `make apk` uses the runner-installed toolchain.

- [ ] **Step 3: Complete artifact metadata**

Set the artifact name to `sideband-android-apk-${{ github.run_number }}` and `retention-days: 14`; leave `if-no-files-found: warn` so diagnostics remain available after failed builds.

- [ ] **Step 4: Run the contract tests**

Run: `python -m unittest tests.test_github_workflows -v`

Expected: both Android and Windows tests fail until Task 3 adds the Windows workflow; Android-specific assertions pass.

- [ ] **Step 5: Commit the Android workflow**

```bash
git add .github/workflows/build-android-apk.yml tests/test_github_workflows.py
git commit -m "ci: add manual Android APK build"
```

### Task 3: Add Windows ZIP workflow

**Files:**
- Create: `.github/workflows/build-windows-zip.yml`
- Modify: `tests/test_github_workflows.py`

**Interfaces:**
- Consumes: a manual Actions dispatch and public source repositories `markqvist/Reticulum`, `markqvist/LXMF`, and `markqvist/LXST`.
- Produces: a `sideband-windows-zip-${{ github.run_number }}` Actions artifact from `Sideband_*.zip`.

- [ ] **Step 1: Add a Windows workflow with dependency checkout**

```yaml
name: Build Windows ZIP
on:
  workflow_dispatch:
jobs:
  build:
    runs-on: windows-2022
    steps:
      - uses: actions/checkout@v4
      - uses: actions/checkout@v4
        with:
          repository: markqvist/Reticulum
          path: Reticulum
      - uses: actions/checkout@v4
        with:
          repository: markqvist/LXMF
          path: LXMF
      - uses: actions/checkout@v4
        with:
          repository: markqvist/LXST
          path: LXST
      - shell: cmd
        run: winbuild.bat
```

- [ ] **Step 2: Add the Windows Python and package setup**

Use `actions/setup-python@v5` with Python 3.11. Install the requirements used by `winbuild.bat`, including PyInstaller and Sideband's package dependencies, before invoking the batch file. Keep all paths relative to `GITHUB_WORKSPACE` so the script finds `sideband_sources`.

- [ ] **Step 3: Upload the ZIP even if build diagnostics fail**

```yaml
- if: always()
  uses: actions/upload-artifact@v4
  with:
    name: sideband-windows-zip-${{ github.run_number }}
    path: Sideband_*.zip
    if-no-files-found: warn
    retention-days: 14
```

- [ ] **Step 4: Run all repository checks**

Run: `python -m unittest discover -s tests -v && python -m py_compile sbapp/i18n.py sbapp/main.py && git diff --check`

Expected: all localization and workflow contract tests pass; no Python compile errors or whitespace failures.

- [ ] **Step 5: Commit and push**

```bash
git add .github/workflows/build-windows-zip.yml tests/test_github_workflows.py
git commit -m "ci: add manual Windows ZIP build"
git push
```
