from pathlib import Path
import unittest


WORKFLOWS_DIR = Path(__file__).resolve().parents[1] / ".github" / "workflows"


def read_workflow(filename):
    return (WORKFLOWS_DIR / filename).read_text(encoding="utf-8")


class GitHubWorkflowContractTests(unittest.TestCase):
    def assert_manual_dispatch_only(self, workflow):
        self.assertIn("workflow_dispatch:", workflow)
        for trigger in ("push:", "pull_request:", "schedule:", "workflow_call:"):
            with self.subTest(trigger=trigger):
                self.assertNotIn(trigger, workflow)

        for prohibited in ("release", "signing", "secrets"):
            with self.subTest(prohibited=prohibited):
                self.assertNotIn(prohibited, workflow.lower())

    def test_android_workflow_contract(self):
        workflow = read_workflow("build-android-apk.yml")

        self.assert_manual_dispatch_only(workflow)
        for fragment in (
            "runs-on: ubuntu-22.04",
            "make apk",
            "path: dist/*.apk",
            "Reticulum",
            "LXMF",
            "LXST",
        ):
            with self.subTest(fragment=fragment):
                self.assertIn(fragment, workflow)
    def test_windows_workflow_contract(self):
        workflow = read_workflow("build-windows-zip.yml")

        self.assert_manual_dispatch_only(workflow)
        for fragment in (
            "runs-on: windows-2022",
            "winbuild.bat",
            "path: Sideband_*.zip",
            "Reticulum",
            "LXMF",
            "LXST",
        ):
            with self.subTest(fragment=fragment):
                self.assertIn(fragment, workflow)

if __name__ == "__main__":
    unittest.main()
