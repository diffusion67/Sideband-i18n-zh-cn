from pathlib import Path
import unittest


WORKFLOWS_DIR = Path(__file__).resolve().parents[1] / ".github" / "workflows"


def read_workflow(filename):
    return (WORKFLOWS_DIR / filename).read_text(encoding="utf-8")


class GitHubWorkflowContractTests(unittest.TestCase):
    def test_android_workflow_contract(self):
        workflow = read_workflow("build-android-apk.yml")

        for fragment in (
            "workflow_dispatch:",
            "runs-on: ubuntu-22.04",
            "make apk",
            "path: dist/*.apk",
            "Reticulum",
            "LXMF",
            "LXST",
        ):
            with self.subTest(fragment=fragment):
                self.assertIn(fragment, workflow)
        self.assertNotIn("push:", workflow)

    def test_windows_workflow_contract(self):
        workflow = read_workflow("build-windows-zip.yml")

        for fragment in (
            "workflow_dispatch:",
            "runs-on: windows-2022",
            "winbuild.bat",
            "path: Sideband_*.zip",
            "Reticulum",
            "LXMF",
            "LXST",
        ):
            with self.subTest(fragment=fragment):
                self.assertIn(fragment, workflow)
        self.assertNotIn("push:", workflow)


if __name__ == "__main__":
    unittest.main()
