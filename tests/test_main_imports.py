import ast
from pathlib import Path
import unittest


MAIN_PATH = Path(__file__).resolve().parents[1] / "sbapp" / "main.py"


def _android_platform_check(node):
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "is_android"
        and isinstance(node.func.value, ast.Attribute)
        and node.func.value.attr == "platformutils"
        and isinstance(node.func.value.value, ast.Attribute)
        and node.func.value.value.attr == "vendor"
        and isinstance(node.func.value.value.value, ast.Name)
        and node.func.value.value.value.id == "RNS"
    )


def _localize_imports(nodes):
    return {
        (statement.level, statement.module)
        for node in nodes
        for statement in ast.walk(node)
        if isinstance(statement, ast.ImportFrom)
        and any(alias.name == "localize_kv" for alias in statement.names)
    }


class MainImportContractTests(unittest.TestCase):
    def test_localize_kv_import_is_absolute_on_android_and_relative_elsewhere(self):
        tree = ast.parse(MAIN_PATH.read_text(encoding="utf-8"))
        platform_branches = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.If)
            and _android_platform_check(node.test)
            and (
                (0, "i18n") in _localize_imports(node.body)
                or (1, "i18n") in _localize_imports(node.orelse)
            )
        ]

        self.assertEqual(len(platform_branches), 1)
        branch = platform_branches[0]
        self.assertIn((0, "i18n"), _localize_imports(branch.body))
        self.assertIn((1, "i18n"), _localize_imports(branch.orelse))


if __name__ == "__main__":
    unittest.main()
