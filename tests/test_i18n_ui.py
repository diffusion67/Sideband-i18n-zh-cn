"""Runtime UI localization contracts; executable without Kivy or Reticulum."""
import ast
import copy
import importlib.util
from pathlib import Path
import re
from string import Formatter
import unittest

ROOT = Path(__file__).resolve().parents[1]
UI = ROOT / 'sbapp' / 'ui'
CATALOG = ROOT / 'sbapp' / 'i18n_ui.py'


def load_catalog():
    if not CATALOG.exists():
        return {}
    spec = importlib.util.spec_from_file_location('i18n_ui_catalog', CATALOG)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.ZH_CN_UI


class RuntimeUiLocalizationTests(unittest.TestCase):
    def test_runtime_screen_catalog_contains_chinese(self):
        catalog = load_catalog()
        for source in ('Delete announce?', 'Edit Conversation', 'Scanning...',
                       'Creating backup...', 'Message Details', 'Start Live Tracking',
                       'Auto sync to collector', 'Log copied to clipboard', 'Hang up'):
            with self.subTest(source=source):
                self.assertIn(source, catalog)
                self.assertRegex(catalog[source], r'[\u3400-\u9fff]')

    def test_catalog_preserves_markup_urls_and_template_fields(self):
        catalog = load_catalog()
        self.assertTrue(catalog, 'The runtime UI catalog must exist')
        for source, target in catalog.items():
            with self.subTest(source=source[:80]):
                self.assertEqual(re.findall(r'\[/?(?:b|i|u|s|color|size|font|ref)(?:=[^\]]*)?\]', source),
                                 re.findall(r'\[/?(?:b|i|u|s|color|size|font|ref)(?:=[^\]]*)?\]', target))
                self.assertEqual(re.findall(r'https?://[^\s\]]+', source),
                                 re.findall(r'https?://[^\s\]]+', target))
                self.assertEqual({name for _, name, _, _ in Formatter().parse(source) if name},
                                 {name for _, name, _, _ in Formatter().parse(target) if name})

    def test_guide_sections_are_explicitly_localized(self):
        tree = ast.parse((UI / 'guide.py').read_text())
        sections = [n for n in ast.walk(tree) if isinstance(n, ast.Assign)
                    and any(isinstance(t, ast.Name) and t.id.startswith('guide_text') for t in n.targets)]
        self.assertEqual(len(sections), 10)
        for section in sections:
            with self.subTest(section=section.targets[0].id):
                self.assertIsInstance(section.value, ast.Call)
                self.assertEqual(section.value.func.id, 'tr')
                self.assertIn(section.value.args[0].value, load_catalog())

    def test_runtime_translations_use_literal_templates_only(self):
        catalog = load_catalog()
        calls = []
        for path in UI.glob('*.py'):
            for node in ast.walk(ast.parse(path.read_text())):
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == 'tr':
                    calls.append(node)
                    with self.subTest(file=path.name, line=node.lineno):
                        self.assertIsInstance(node.args[0], ast.Constant,
                                              'Never translate user content or an interpolated result')
                        self.assertIsInstance(node.args[0].value, str)
        self.assertGreater(len(calls), 100)

    def test_message_status_and_voice_callsites_are_localized(self):
        samples = {'messages.py': {'Message Details', 'Waiting for path', '\n[b]State[/b] Delivered'},
                   'voice.py': {'Hang up', 'Call', 'Path request timed out'},
                   'keys.py': {'Creating backup...', 'No, go back'}}
        for filename, expected in samples.items():
            tree = ast.parse((UI / filename).read_text())
            localized = {n.args[0].value for n in ast.walk(tree)
                         if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                         and n.func.id == 'tr' and n.args and isinstance(n.args[0], ast.Constant)}
            self.assertTrue(expected <= localized, (filename, expected - localized))

    def test_runtime_template_values_match_fields(self):
        catalog = load_catalog()
        for path in UI.glob('*.py'):
            for node in ast.walk(ast.parse(path.read_text())):
                if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                        and node.func.id == 'tr' and node.args
                        and isinstance(node.args[0], ast.Constant)):
                    continue
                source = node.args[0].value
                with self.subTest(file=path.name, line=node.lineno):
                    self.assertIn(source, catalog)
                    fields = {name for _, name, _, _ in Formatter().parse(source) if name}
                    self.assertEqual(fields, {arg.arg for arg in node.keywords})

    def test_framework_enum_values_are_not_translated(self):
        tree = ast.parse((UI / 'conversations.py').read_text())
        assignment = next(node for node in tree.body if isinstance(node, ast.Assign)
                          and any(isinstance(target, ast.Name)
                                  and target.id == 'theme_text_color_options'
                                  for target in node.targets))
        self.assertEqual(ast.literal_eval(assignment.value),
                         ('Primary', 'Secondary', 'Hint', 'Error', 'Custom',
                          'ContrastParentBackground'))

    def test_sensor_display_names_leave_unknown_data_unchanged(self):
        tree = ast.parse((UI / 'objectdetails.py').read_text())
        functions = [node for node in tree.body if isinstance(node, ast.FunctionDef)
                     and node.name == '_sensor_display_name']
        self.assertEqual(len(functions), 1)
        namespace = {'tr': lambda source: load_catalog().get(source, source)}
        exec(compile(ast.Module(body=functions, type_ignores=[]), '<sensor display>', 'exec'),
             namespace)
        display = namespace['_sensor_display_name']
        self.assertEqual(display('Battery'), '电池')
        self.assertEqual(display('Temperature'), '温度')
        self.assertEqual(display('My custom sensor'), 'My custom sensor')
        self.assertEqual(display('Call ended {raw}'), 'Call ended {raw}')
        comparisons = [node for node in ast.walk(tree) if isinstance(node, ast.Compare)
                       and isinstance(node.left, ast.Name) and node.left.id == 'name']
        self.assertTrue(any(any(isinstance(value, ast.Constant) and value.value == 'Battery'
                                for value in node.comparators) for node in comparisons))

    def test_monospace_utility_text_supports_chinese_glyphs(self):
        tree = ast.parse((UI / 'utilities.py').read_text())
        output_ids = ('rnstatus_output.text', 'config_template.text',
                      'logviewer_output.text', 'slogviewer_output.text')
        assignments = [node for node in ast.walk(tree) if isinstance(node, ast.Assign)
                       and any(ast.unparse(target).endswith(output_ids)
                               for target in node.targets)]
        self.assertEqual(len(assignments), 6)
        for assignment in assignments:
            with self.subTest(line=assignment.lineno):
                self.assertTrue(any(isinstance(node, ast.Call)
                                    and isinstance(node.func, ast.Name)
                                    and node.func.id == 'multilingual_markup'
                                    for node in ast.walk(assignment.value)))

    def test_proximity_status_is_localized_without_changing_its_key(self):
        tree = ast.parse((UI / 'objectdetails.py').read_text())
        branches = [node for node in ast.walk(tree) if isinstance(node, ast.If)
                    and ast.unparse(node.test) == "name == 'Proximity'"]
        self.assertEqual(len(branches), 1)
        body = ast.Module(body=branches[0].body, type_ignores=[])
        for triggered, expected in ((True, '已触发'), (False, '未触发')):
            values = {'triggered': triggered}
            catalog = load_catalog()
            namespace = {'s': {'values': values},
                         'tr': lambda source, **args: catalog.get(source, source).format(**args)}
            exec(compile(body, '<proximity display>', 'exec'), namespace)
            self.assertEqual(namespace['formatted_values'], f'接近传感器 [b]{expected}[/b]')
            self.assertEqual(values, {'triggered': triggered})

    def test_voice_profile_names_are_display_only(self):
        tree = ast.parse((UI / 'voice.py').read_text())
        functions = [node for node in tree.body if isinstance(node, ast.FunctionDef)
                     and node.name == '_profile_display_name']
        self.assertEqual(len(functions), 1)
        namespace = {'tr': lambda source: load_catalog().get(source, source)}
        exec(compile(ast.Module(body=functions, type_ignores=[]), '<profile display>', 'exec'),
             namespace)
        display = namespace['_profile_display_name']
        self.assertEqual(display('Low Bandwidth'), '低带宽')
        self.assertEqual(display('Ultra Low Latency'), '极低延迟')
        self.assertEqual(display('Custom codec'), 'Custom codec')

    def test_duration_conjunction_changes_only_generated_display_text(self):
        calls = []
        for filename in ('telemetry.py', 'voice.py', 'objectdetails.py'):
            tree = ast.parse((UI / filename).read_text())
            for node in ast.walk(tree):
                if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                        and node.func.attr == 'replace' and isinstance(node.func.value, ast.Call)
                        and ast.unparse(node.func.value.func) == 'RNS.prettytime'):
                    calls.append(node)
        self.assertEqual(len(calls), 6)
        # Substitute actual Reticulum-format output at the dependency boundary.
        for node in calls:
            for source, expected in (('1h', '1h'), ('0s', '0s'),
                                     ('1h and 1m', '1h、1m'),
                                     ('-1d and 1h', '-1d、1h')):
                expression = copy.deepcopy(node)
                expression.func.value = ast.Constant(value=source)
                expression = ast.fix_missing_locations(ast.Expression(expression))
                result = eval(compile(expression, '<duration display>', 'eval'),
                              {'tr': lambda text: load_catalog().get(text, text)})
                self.assertEqual(result, expected)


if __name__ == '__main__':
    unittest.main()
