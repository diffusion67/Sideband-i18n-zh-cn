from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class ReleaseWorkflowTests(unittest.TestCase):
    def test_release_only_publishes_successful_main_builds(self):
        path = ROOT / '.github/workflows/publish-release.yml'
        self.assertTrue(path.exists())
        text = path.read_text()
        for guard in ('workflow_run:', "types: [completed]", "head_branch == 'main'",
                      "event == 'push'", "conclusion == 'success'",
                      'contents: write', 'actions: read', 'head_sha: sha',
                      'build-windows-zip.yml', 'build-android-apk.yml', 'build-desktop.yml',
                      'SHA256SUMS', 'createHash', 'getRef', 'refs/tags/',
                      'const latestMain', 'const tagRef', "asset.state !== 'uploaded'",
                      'uploaded.length !== assets.size'):
            with self.subTest(guard=guard):
                self.assertIn(guard, text)
        self.assertNotIn('actions/checkout', text)
        self.assertNotIn('--clobber', text)
