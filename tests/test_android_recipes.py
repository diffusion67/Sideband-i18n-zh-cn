"""Offline regressions for the legacy CPython Android cross-build toolchain."""

import configparser
import importlib.util
import os
from pathlib import Path
import shutil
import subprocess
import sys
import sysconfig
import tempfile
import textwrap
import unittest


ROOT = Path(__file__).resolve().parents[1]
CONSTRAINTS = ROOT / "recipes/android-build-constraints.txt"


class AndroidRecipeTests(unittest.TestCase):
    def test_build_frontend_constraint_preserves_cross_compile_pythonpath(self):
        self.assertTrue(CONSTRAINTS.is_file(), "Missing Android build compatibility constraints")
        requirements = [line.split("#", 1)[0].strip()
                        for line in CONSTRAINTS.read_text().splitlines()]
        self.assertIn("build==1.4.2", requirements)

    def test_numpy_uses_fixed_upstream_tag_required_by_lxst(self):
        spec = configparser.ConfigParser(interpolation=None)
        spec.read(ROOT / "sbapp/buildozer.spec")
        requirements = spec["app"]["requirements"].split(",")
        numpy = [item.strip() for item in requirements
                 if item.strip().split("==", 1)[0] == "numpy"]
        # p4a passes this exact value to git checkout, so retain the v prefix.
        # 2.3.4 fixes unique.cpp's missing <unordered_map> and meets LXST's floor.
        self.assertEqual(numpy, ["numpy==v2.3.4"])
        self.assertEqual(spec["app"]["android.ndk"], "25b")

    @unittest.skipUnless(importlib.util.find_spec("build"),
                         "Install build with recipes/android-build-constraints.txt")
    @unittest.skipUnless(sys.platform == "linux" and shutil.which("cc"),
                         "Native extension probe needs a Linux C compiler")
    def test_isolated_backend_can_import_host_native_extension(self):
        # p4a copies hostpython into the target tree and uses PYTHONPATH to
        # expose native-build/build/lib.*. A backend process must retain that
        # entry even though its Python package dependencies are isolated.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            native = root / "host-native-extensions"
            native.mkdir()
            source = root / "host_probe.c"
            source.write_text(textwrap.dedent('''\
                #include <Python.h>
                static struct PyModuleDef probe = {
                    PyModuleDef_HEAD_INIT, "_sideband_host_probe", NULL, -1, NULL
                };
                PyMODINIT_FUNC PyInit__sideband_host_probe(void) {
                    return PyModule_Create(&probe);
                }
            '''))
            subprocess.run([
                "cc", "-shared", "-fPIC", "-I" + sysconfig.get_paths()["include"],
                str(source), "-o",
                str(native / ("_sideband_host_probe" + sysconfig.get_config_var("EXT_SUFFIX"))),
            ], check=True, capture_output=True, text=True)
            project = root / "project"
            project.mkdir()
            (project / "pyproject.toml").write_text(textwrap.dedent('''\
                [build-system]
                requires = []
                build-backend = "backend"
                backend-path = ["."]
            '''))
            (project / "backend.py").write_text(textwrap.dedent('''\
                import os
                import _sideband_host_probe

                def get_requires_for_build_wheel(config_settings=None):
                    return []

                def build_wheel(wheel_directory, config_settings=None, metadata_directory=None):
                    filename = "host_path_probe-1.0-py3-none-any.whl"
                    with open(os.path.join(wheel_directory, filename), "wb") as output:
                        output.write(b"backend imported native extension successfully")
                    return filename
            '''))
            env = dict(os.environ)
            env["PYTHONPATH"] = os.pathsep.join(
                [str(native), *filter(None, env.get("PYTHONPATH", "").split(os.pathsep))])
            result = subprocess.run(
                [sys.executable, "-m", "build", "--wheel", str(project)],
                env=env, capture_output=True, text=True,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertTrue((project / "dist/host_path_probe-1.0-py3-none-any.whl").is_file())


if __name__ == "__main__":
    unittest.main()
