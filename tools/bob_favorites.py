#!/usr/bin/env python3
"""Query Bob favorites locally, with no database writes or project exports."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sqlite3

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / '2026-Winter-Exam/vocabulary/bob-source.json'
FAVORITES = 'translate_translate_favorite'


def open_readonly(path: Path) -> sqlite3.Connection:
    path = path.expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError(f'Bob database not found: {path}')
    connection = sqlite3.connect(path.as_uri() + '?mode=ro', uri=True,
                                 isolation_level=None, timeout=5)
    try:
        connection.execute('PRAGMA query_only = ON')

        def authorize(action, table, column, database, trigger):
            if action in (sqlite3.SQLITE_SELECT, sqlite3.SQLITE_FUNCTION):
                return sqlite3.SQLITE_OK
            if action == sqlite3.SQLITE_READ and table in (FAVORITES, 'service_snapshot'):
                return sqlite3.SQLITE_OK
            return sqlite3.SQLITE_DENY

        connection.set_authorizer(authorize)
        # Fail on a changed schema instead of searching unrelated tables.
        connection.execute(f'SELECT localId, queryText, resultTuple0, favoriteTime '
                           f'FROM {FAVORITES} LIMIT 0')
    except Exception:
        connection.close()
        raise
    connection.row_factory = sqlite3.Row
    return connection


def decode_first_service(raw):
    if not raw:
        return None, None, 'missing-first-service-result'
    try:
        data = json.loads(raw)
        identifier = data.get('overview', {}).get('identifier')
        content = data.get('result', {}).get('content', {})
        text = content.get('text')
        if not isinstance(text, str):
            return None, identifier, 'unsupported-first-service-result'
        return text, identifier, None
    except (ValueError, TypeError, AttributeError):
        return None, None, 'invalid-first-service-result'


def query(connection, command, query='', limit=10):
    total = connection.execute(f'SELECT count(*) FROM {FAVORITES}').fetchone()[0]
    result = {'source': 'bob-favorites', 'access': 'read-only', 'totalFavorites': total}
    if command == 'stats':
        return result
    service_names = {row['identifier']: row['name'] for row in
                     connection.execute('SELECT identifier, name FROM service_snapshot')}
    rows = connection.execute(f'SELECT localId, queryText, resultTuple0, favoriteTime '
                              f'FROM {FAVORITES} ORDER BY localId DESC')
    matches = []
    needle = query.casefold()
    try:
        for row in rows:
            translation, service_id, warning = decode_first_service(row['resultTuple0'])
            original = row['queryText'] or ''
            if needle and not any(needle in s.casefold() for s in (original, translation or '')):
                continue
            matches.append({'id': f"bob-favorite-{row['localId']}",
                            'localId': row['localId'], 'original': original,
                            'firstServiceTranslation': translation,
                            'firstServiceName': service_names.get(service_id),
                            'favoriteTimeRaw': row['favoriteTime'], 'warning': warning})
            if command == 'recent' and len(matches) >= limit:
                break
    finally:
        rows.close()
    if command == 'search':
        result['query'] = query
        result['totalMatches'] = len(matches)
    result['showing'] = min(len(matches), limit)
    result['entries'] = matches[:limit]
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database', type=Path, help='Override the local source path; still read-only.')
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('stats')
    recent = sub.add_parser('recent')
    recent.add_argument('--limit', type=int, default=5)
    search = sub.add_parser('search')
    search.add_argument('query')
    search.add_argument('--limit', type=int, default=10)
    args = parser.parse_args()
    limit = getattr(args, 'limit', 10)
    if not 1 <= limit <= 100:
        parser.error('--limit must be between 1 and 100')
    if args.command == 'search' and not args.query.strip():
        parser.error('Search text must not be empty')
    connection = None
    try:
        config = json.loads(CONFIG.read_text(encoding='utf-8'))
        if config['access'] != 'read-only':
            raise ValueError('Source configuration must remain read-only')
        connection = open_readonly(args.database or Path(config['databasePath']))
        result = query(connection, args.command, getattr(args, 'query', ''), limit)
    except (OSError, ValueError, KeyError, sqlite3.Error) as exc:
        parser.exit(1, f'Bob source unavailable: {exc}\n')
    finally:
        if connection is not None:
            connection.close()
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
