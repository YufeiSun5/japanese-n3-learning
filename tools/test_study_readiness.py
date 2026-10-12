"""Regression checks for claiming a blank daily page is ready."""
import unittest
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory

from study_progress import lesson_ready


class ReadinessTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.day = date(2026, 10, 12)
        self.page = self.root / '日常练习/2026-10-12.md'
        self.page.parent.mkdir()
        self.catalog = {'sessions': [{'date': str(self.day),
                        'source': '日常练习/2026-10-12.md',
                        'reviewPlan': {'targets': [{'itemId': 'old-word'}]}}]}
        self.material = ('### 02 · 老师\n\n- 原文：結果は？\n'
                         '- 假名：けっか は？\n- 罗马音（拼读）：Kekka wa?\n'
                         '- 输入法按键：`kekka ha`\n\n### 03 · 我\n\n')

    def test_created_blank_page_is_not_ready(self):
        self.page.write_text('# 今日\n\n### 01 · 老师\n', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'teaching turn'):
            lesson_ready(self.root, self.catalog, self.day)

    def test_empty_pronunciation_field_is_not_ready(self):
        self.page.write_text(self.material.replace('Kekka wa?', ''), encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'nonempty'):
            lesson_ready(self.root, self.catalog, self.day)

    def test_material_without_reply_location_is_not_ready(self):
        self.page.write_text(self.material.split('### 03')[0], encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'reply turn'):
            lesson_ready(self.root, self.catalog, self.day)

    def test_material_without_opening_plan_is_not_ready(self):
        self.page.write_text(self.material, encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'review plan'):
            lesson_ready(self.root, {'sessions': []}, self.day)

    def test_ready_check_reports_actual_turns_without_editing(self):
        self.page.write_text(self.material, encoding='utf-8')
        before = self.page.read_bytes()
        result = lesson_ready(self.root, self.catalog, self.day)
        self.assertTrue(result['ready'])
        self.assertEqual((result['teacherTurn'], result['replyTurn']), (2, 3))
        self.assertEqual(self.page.read_bytes(), before)
        with self.assertRaises(ValueError):
            lesson_ready(self.root, self.catalog, self.day, 39, 40)


if __name__ == '__main__':
    unittest.main()
