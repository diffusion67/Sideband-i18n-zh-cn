# GitHub APK and Windows Build Design

## Goal

Provide manual GitHub Actions builds in the mirror repository for the Chinese-localized Sideband source. Each successful run must expose a downloadable Android APK or Windows ZIP without creating a release.

## Scope

Two independent workflows will be added under `.github/workflows/`:

- `build-android-apk.yml` runs only through `workflow_dispatch` on Ubuntu and uploads the generated release APK as an artifact.
- `build-windows-zip.yml` runs only through `workflow_dispatch` on Windows and uploads the generated ZIP as an artifact.

Neither workflow runs on pushes or pull requests, publishes packages, creates releases, signs artifacts, or changes Sideband source code.

## Android workflow

The Android job checks out the selected branch and the required Reticulum, LXMF, and LXST repositories into sibling directories expected by `sbapp/Makefile`. It installs the JDK, Android command-line tooling, Buildozer, and Python dependencies needed by the existing `make apk` target. The job invokes that target, then uploads `dist/*.apk` even when a later diagnostic step fails.

The artifact name includes the run number. APK signing is intentionally out of scope: the workflow produces a build artifact, not an official release.

## Windows workflow

The Windows job checks out Sideband and the three required dependency repositories. It assembles the source layout consumed by the repository's existing `winbuild.bat`, installs Python build dependencies and PyInstaller, then invokes the batch script. The resulting `Sideband_*.zip` file is uploaded as a build artifact.

The Windows workflow does not package an installer and does not code-sign the executable. Any missing or incompatible upstream dependency is a visible build failure with preserved logs.

## Failure handling and verification

Both workflows pin no secrets and use only public checkout and setup actions. Each has a final artifact-upload step guarded with `if: always()` so build logs and any partial artifact can be retrieved. YAML validation will be covered by a lightweight repository test that asserts both workflow names, manual trigger, runner, expected build command, and artifact upload path.

## Acceptance criteria

- A maintainer can select either workflow from the GitHub Actions tab and run it manually on `i18n/zh-cn`.
- Android builds execute `make apk` after dependency checkout and publish an APK artifact when produced.
- Windows builds execute `winbuild.bat` after dependency checkout and publish a ZIP artifact when produced.
- No push, PR, release, signing, or credential-based automation is introduced.
