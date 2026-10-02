"""Run with python -m unittest discover -s tests -v (no GUI required)."""
import ast
import importlib.util
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
from sbapp import i18n


class LocalizationTests(unittest.TestCase):
    def test_runtime_dialog_and_status_phrases(self):
        for source in ('Announce Sent', 'Service restarted successfully!', 'Requesting path...',
                       'Backup done', 'Could not send the message', 'No active conversation'):
            with self.subTest(source=source):
                self.assertRegex(i18n.translate(source), r'[\u3400-\u9fff]')

    def test_unknown_content_is_never_rewritten(self):
        for text in ('Alice: Call ended', 'My Preferences', '[b]Conversations[/b] from a peer',
                     'lxm://012345abcdef', 'Announce Sent to Alice'):
            self.assertEqual(i18n.translate(text), text)

    def test_kv_expression_is_not_replaced_as_a_literal(self):
        layout = 'Label:\n    text: "Conversations" if root.active else "Voice"\n'
        self.assertEqual(i18n.localize_kv(layout), layout)

    def test_kv_quoted_translation_remains_valid(self):
        layout = 'Label:\n    text: "Cancel" # comment\n'
        self.assertEqual(i18n.localize_kv(layout), 'Label:\n    text: "取消" # comment\n')

    def test_existing_catalog_preserves_markup(self):
        for source, target in i18n.ZH_CN.items():
            with self.subTest(source=source[:70]):
                self.assertEqual(re.findall(r'\[/?(?:b|i|u|s|color|size|font|ref)(?:=[^\]]*)?\]', source),
                                 re.findall(r'\[/?(?:b|i|u|s|color|size|font|ref)(?:=[^\]]*)?\]', target))


if __name__ == '__main__':
    unittest.main()

class TemplateTests(unittest.TestCase):
    def test_translate_formats_template_without_translating_values(self):
        self.assertEqual(i18n.translate('Call from {dn}', dn='Cancel {raw}'), '来自 Cancel {raw} 的通话')

    def test_named_placeholder_contract(self):
        import string
        for source, target in i18n.ZH_CN.items():
            fields = lambda text: sorted((f, spec, conversion) for _, f, spec, conversion in string.Formatter().parse(text) if f is not None)
            with self.subTest(source=source[:50]):
                self.assertEqual(fields(source), fields(target))

class MainWindowCoverageTests(unittest.TestCase):
    def test_message_hint_and_validation_callsites_are_localized(self):
        tree = ast.parse((ROOT / 'sbapp/main.py').read_text())
        keys = {n.args[0].value for n in ast.walk(tree)
                if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                and n.func.id == 'tr' and n.args and isinstance(n.args[0], ast.Constant)}
        expected = {'Paper message', 'Send command or request',
                    'Message for direct delivery', 'Message for propagation',
                    'Invalid address, check your input', 'Invalid scale factor, check your input',
                    'The repository server is running at the following addresses:\n\n'}
        self.assertTrue(expected <= keys, expected - keys)

    def test_clipboard_action_words_are_localized(self):
        for action in ('tap', 'click'):
            rendered = i18n.translate('Field copied, double-{action} any empty field to paste',
                                      action=i18n.translate(action))
            self.assertNotIn(action, rendered)
