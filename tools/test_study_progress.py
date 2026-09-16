import copy
from datetime import datetime, date, timezone
from pathlib import Path
import tempfile
import unittest

from study_progress import ensure_today, local_day, summarize


class ProgressIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / 'sample.md').write_text('### 01 · 老师\nmodel\n### 02 · 我\nresponse\n')
        self.catalog = {'items': [{'id': 'one', 'kind': 'word', 'events': [
            {'id': 'e1', 'date': '2026-09-12', 'file': 'sample.md', 'turn': 1,
             'quote': 'model', 'kind': 'exposure'}]}]}

    def test_timezone_rolls_over_before_utc(self):
        now = datetime(2026, 9, 14, 17, tzinfo=timezone.utc)
        self.assertEqual(local_day('Asia/Singapore', now), date(2026, 9, 15))

    def test_existing_user_page_is_never_replaced(self):
        p = ensure_today(self.root, date(2026, 9, 14))
        p.write_text('unsummarized original response')
        ensure_today(self.root, date(2026, 9, 14))
        self.assertEqual(p.read_text(), 'unsummarized original response')

    def test_duplicate_event_cannot_inflate_counts(self):
        self.catalog['items'][0]['events'] *= 2
        with self.assertRaises(ValueError):
            summarize(self.root, self.catalog, date(2026, 9, 14))

    def test_teacher_example_is_not_user_practice(self):
        self.catalog['items'][0]['events'][0]['kind'] = 'supported-correct'
        with self.assertRaises(ValueError):
            summarize(self.root, self.catalog, date(2026, 9, 14))

    def test_review_with_visible_hint_is_not_verified(self):
        e = dict(id='e2', date='2026-09-13', file='sample.md', turn=2,
                 quote='response', kind='review-verified', support='visible', assessment='correct')
        self.catalog['items'][0]['events'].append(e)
        with self.assertRaises(ValueError):
            summarize(self.root, self.catalog, date(2026, 9, 14))
        e['support'] = 'none'
        self.assertTrue(summarize(self.root, self.catalog, date(2026, 9, 14))[0]['verified'])

    def test_repeated_read_is_idempotent(self):
        before = copy.deepcopy(self.catalog)
        a = summarize(self.root, self.catalog, date(2026, 9, 14))
        b = summarize(self.root, self.catalog, date(2026, 9, 14))
        self.assertEqual(a, b)
        self.assertEqual(before, self.catalog)


if __name__ == '__main__':
    unittest.main()
