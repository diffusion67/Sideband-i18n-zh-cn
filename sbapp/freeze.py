"""Native desktop bundles: python sbapp/freeze.py bdist_appimage|bdist_dmg.

Run on the target OS/architecture. Desktop CI pins the cx_Freeze version;
the Android and Windows build routes remain separate.
"""

import importlib.machinery
import importlib.util
from pathlib import Path
import platform
import re
import sys

import cx_Freeze


APP = Path(__file__).resolve().parent
ROOT = APP.parent
source = (APP / "main.py").read_text(encoding="utf-8")
version = re.search(r'^__version__ = [\'"]([^\'"]+)[\'"]$', source, re.M)
if version is None:
    raise ValueError("Unable to find the Sideband source version")
version = version.group(1)

if sys.platform not in ("linux", "darwin"):
    raise RuntimeError("Use winbuild.bat for Windows desktop packages")

plyer_platform = "macosx" if sys.platform == "darwin" else "linux"
excludes = [
    "tkinter", "pytest", "kivy.tests", "kivy.tools", "kivymd.tools",
    "sbapp.freeze", "sbapp.service", "sbapp.build", "sbapp.dist",
    "sbapp.plyer.platforms.android", "sbapp.plyer.platforms.ios",
    "sbapp.plyer.platforms.win", "LXST.Platforms.android", "LXST.Platforms.windows",
    "LXST.Codecs.libs.pyogg.libs.win32", "LXST.Codecs.libs.pyogg.libs.win_amd64",
]
if sys.platform == "linux":
    excludes += ["sbapp.plyer.platforms.macosx", "LXST.Platforms.darwin",
                 "LXST.Codecs.libs.pyogg.libs.macos"]
else:
    excludes += ["sbapp.plyer.platforms.linux", "LXST.Platforms.linux"]

# LXST distributes several Python/CPU-specific filter libraries together.
# Do not ask the native linker to process binaries for another platform.
bin_excludes = []
lxst = importlib.util.find_spec("LXST")
if lxst is not None:
    lxst_path = Path(lxst.origin).parent
    native = importlib.machinery.PathFinder.find_spec("LXST.filterlib", [str(lxst_path)])
    if native is None:
        raise RuntimeError("LXST has no native filter library for this Python/platform")
    bin_excludes = [p.name for p in lxst_path.glob("filterlib*")
                    if p != Path(native.origin)]

build_options = {
    "path": [str(ROOT), str(APP), *sys.path],
    "packages": ["kivy", "kivymd", "mapview", "RNS", "LXMF", "LXST",
                 "sbapp.plyer.platforms." + plyer_platform],
    "includes": ["LXST.filterlib", "mistune", "bs4", "pycodec2"],
    "excludes": excludes,
    "bin_excludes": bin_excludes,
    # These are filesystem resources, including dynamically loaded KV files
    # and the CJK font. Keep package files out of library.zip as well.
    "include_files": [
        (str(APP / "assets"), "lib/sbapp/assets"),
        (str(APP / "kivymd"), "lib/kivymd"),
        (str(APP / "mapview"), "lib/mapview"),
    ],
    "zip_exclude_packages": ["*"],
}
options = {"build_exe": build_options}
if sys.platform == "linux":
    # Kivy opens this by soname through ctypes; dependency analysis cannot
    # discover that load. CI installs libmtdev1, then bundles it for users.
    mtdev = Path("/usr/lib") / (platform.machine() + "-linux-gnu") / "libmtdev.so.1"
    build_options["include_files"].append((str(mtdev), "lib/libmtdev.so.1"))
    # Override cx_Freeze's default exclusion of system-library directories.
    build_options["bin_includes"] = ["libmtdev.so"]
    options["bdist_appimage"] = {"target_name": "Sideband-zh-CN", "target_version": version}
else:
    options["bdist_mac"] = {
        "bundle_name": "Sideband",
        "iconfile": str(APP / "assets/icon.icns"),
        "plist_items": [
            ("CFBundleIdentifier", "io.unsigned.sideband"),
            ("CFBundleShortVersionString", version),
            ("NSMicrophoneUsageDescription", "Sideband 需要使用麦克风进行语音通话和录制语音消息。"),
        ],
    }
    options["bdist_dmg"] = {"volume_label": "Sideband-zh-CN-" + version,
                            "applications_shortcut": True}

cx_Freeze.setup(
    name="Sideband", version=version, author="Mark Qvist",
    url="https://unsigned.io/sideband",
    executables=[cx_Freeze.Executable(
        script=str(ROOT / "main.py"), base="console", target_name="Sideband",
        icon=str(APP / "assets/icon.png"),
        copyright="Copyright (c) Mark Qvist and contributors",
    )],
    options=options,
)
