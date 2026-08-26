import glob
import re
import unittest

from sbapp.i18n import ZH_CN, localize_kv, translate


class ChineseLocalizationTests(unittest.TestCase):
    def test_translates_kivy_text_and_hint_properties(self):
        layout = '''
MDLabel:
    text: "Conversations"
MDTextField:
    hint_text: "Write message"
'''

        self.assertEqual(
            localize_kv(layout),
            '''
MDLabel:
    text: "会话"
MDTextField:
    hint_text: "输入消息"
''',
        )

    def test_keeps_unknown_text_unchanged(self):
        self.assertEqual(translate("LXMF Propagation Node"), "LXMF 传播节点")
        self.assertEqual(translate("A value supplied by a peer"), "A value supplied by a peer")

    def test_translates_a_property_with_an_inline_comment(self):
        self.assertEqual(
            localize_kv('MDLabel:\n    text: "Send"  # primary action\n'),
            'MDLabel:\n    text: "发送"  # primary action\n',
        )

    def test_translates_all_literal_user_facing_kivy_properties(self):
        property_pattern = re.compile(
            r'''^\s*(?:text|title|hint_text|helper_text)\s*:\s*(?P<quote>["'])(?P<value>.*?)(?P=quote)\s*(?:#.*)?$'''
        )
        untranslated = []

        for path in glob.glob("sbapp/ui/*.py"):
            with open(path, encoding="utf-8") as source:
                for line_number, line in enumerate(source, start=1):
                    match = property_pattern.match(line)
                    if match:
                        value = match.group("value").replace("\\\\", "\\")
                        if value.strip() and value not in ZH_CN:
                            untranslated.append(f"{path}:{line_number}: {value}")

        self.assertEqual(untranslated, [])


if __name__ == "__main__":
    unittest.main()
