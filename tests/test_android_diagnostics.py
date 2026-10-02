import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class AndroidDiagnosticTests(unittest.TestCase):
    def test_error_excerpt_omits_environment_and_secret_like_lines(self):
        path = ROOT / '.github/scripts/collect_android_error.py'
        self.assertTrue(path.is_file())
        spec = importlib.util.spec_from_file_location('android_diagnostics', path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        log = ('Traceback (most recent call last):\nModuleNotFoundError: missing\n'
               'AUTHORIZATION=example-private-token\n'
               'index https://example-user:example-pass@packages.invalid/simple\n'
               '-----BEGIN PRIVATE KEY-----\nexample-secret-body\n-----END PRIVATE KEY-----\n'
               '# ENVIRONMENT:\nGITHUB_TOKEN=example-secret\nOTHER=private-environment\n')
        result = module.excerpt(log)
        self.assertIn('ModuleNotFoundError: missing', result)
        for secret in ('example-private-token', 'example-user', 'example-pass',
                       'example-secret-body', 'example-secret', 'private-environment'):
            self.assertNotIn(secret, result)

    def test_terminal_controls_are_removed_before_diagnostic_upload(self):
        path = ROOT / '.github/scripts/collect_android_error.py'
        spec = importlib.util.spec_from_file_location('android_diagnostics', path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        result = module.excerpt('\x1b]52;c;example-clipboard-control\x07\x1b[31mCompiler error\x1b[0m\x00\n')
        self.assertEqual(result, 'Compiler error\n')

    def test_android_failure_diagnostic_does_not_change_pipeline_exit_status(self):
        workflow = (ROOT / '.github/workflows/build-android-apk.yml').read_text()
        self.assertIn('set -o pipefail', workflow)
        self.assertIn('collect_android_error.py', workflow)
        self.assertIn('if: failure()', workflow)
