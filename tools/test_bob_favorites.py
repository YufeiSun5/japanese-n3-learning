"""Verify read-only enforcement using disposable databases, never Bob's data."""
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from bob_favorites import open_readonly, query


class BobFavoritesTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'fixture.sqlite'
        with sqlite3.connect(self.path) as db:
            db.execute('CREATE TABLE translate_translate_favorite '
                       '(localId INTEGER PRIMARY KEY, queryText TEXT, resultTuple0 TEXT, favoriteTime TEXT)')
            db.execute('CREATE TABLE service_snapshot (identifier TEXT, name TEXT)')
            db.execute('CREATE TABLE translate_translate_history (queryText TEXT)')
            db.execute("INSERT INTO service_snapshot VALUES ('fixture-service', 'Fixture')")
            result = json.dumps({'overview': {'identifier': 'fixture-service'},
                                 'result': {'content': {'text': 'a little rest'}}})
            db.execute('INSERT INTO translate_translate_favorite VALUES (1, ?, ?, ?)',
                       ("it's a phrase", result, 'raw-time'))
            db.execute("INSERT INTO translate_translate_favorite VALUES (2, 'other', 'invalid JSON', NULL)")
        self.connection = open_readonly(self.path)
        self.addCleanup(self.connection.close)

    def test_writes_and_history_access_denied(self):
        before = self.path.read_bytes()
        for sql in ["UPDATE translate_translate_favorite SET queryText='changed'",
                    'DROP TABLE translate_translate_favorite',
                    'CREATE TABLE unwanted (value TEXT)',
                    'PRAGMA query_only=OFF',
                    "ATTACH DATABASE ':memory:' AS unwanted",
                    'SELECT * FROM translate_translate_history']:
            with self.subTest(sql=sql), self.assertRaises(sqlite3.DatabaseError):
                self.connection.execute(sql)
        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual(query(self.connection, 'stats')['totalFavorites'], 2)

    def test_literal_search_in_original_and_translation(self):
        for text in ["it's", 'LITTLE']:
            found = query(self.connection, 'search', text)
            self.assertEqual(found['totalMatches'], 1)
            self.assertEqual(found['entries'][0]['firstServiceName'], 'Fixture')
        self.assertEqual(query(self.connection, 'search', "' OR 1=1 --")['totalMatches'], 0)

    def test_missing_translation_is_not_fabricated(self):
        found = query(self.connection, 'recent', limit=1)
        self.assertEqual(found['showing'], 1)
        self.assertEqual(found['entries'][0]['localId'], 2)
        self.assertIsNone(found['entries'][0]['firstServiceTranslation'])
        self.assertEqual(found['entries'][0]['warning'], 'invalid-first-service-result')

    def test_missing_path_does_not_create_database(self):
        missing = self.path.parent / 'missing.sqlite'
        with self.assertRaises(FileNotFoundError):
            open_readonly(missing)
        self.assertFalse(missing.exists())


if __name__ == '__main__':
    unittest.main()
