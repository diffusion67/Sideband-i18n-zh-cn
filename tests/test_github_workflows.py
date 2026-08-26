from pathlib import Path
import re
import unittest


WORKFLOWS_DIR = Path(__file__).resolve().parents[1] / ".github" / "workflows"


def read_workflow(filename):
    return (WORKFLOWS_DIR / filename).read_text(encoding="utf-8")


class GitHubWorkflowContractTests(unittest.TestCase):
    def assert_manual_dispatch_only(self, workflow):
        header, separator, _ = workflow.partition("\njobs:")
        self.assertTrue(separator, "workflow must contain a jobs section")

        lines = header.splitlines()
        on_lines = [index for index, line in enumerate(lines) if re.fullmatch(r"on:", line)]
        self.assertEqual(len(on_lines), 1, "workflow must use one block-form on: line")

        event_keys = []
        for line in lines[on_lines[0] + 1 :]:
            if line and not line.startswith((" ", "\t")):
                break
            match = re.fullmatch(r"  ([A-Za-z_][A-Za-z0-9_-]*):\s*", line)
            if match:
                event_keys.append(match.group(1))
        self.assertEqual(event_keys, ["workflow_dispatch"])

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
