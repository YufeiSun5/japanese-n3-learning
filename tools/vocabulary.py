#!/usr/bin/env python3
"""Build, verify and query the local reference lexicon without network access."""
from __future__ import annotations
import argparse
import csv
from collections import Counter
from datetime import datetime
import hashlib
import json
from pathlib import Path
import shutil
import unicodedata

ROOT = Path(__file__).resolve().parents[1]
PACK = ROOT / '2026-Winter-Exam/tasks/002-vocabulary-library'
RAW = PACK / 'assets/upstream'
LIBRARY = ROOT / '2026-Winter-Exam/vocabulary'


def read_json(path):
    return json.loads(path.read_text(encoding='utf-8'))


def dump(data):
    return json.dumps(data, ensure_ascii=False, indent=2) + '\n'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def normalize(value):
    return unicodedata.normalize('NFKC', value).strip()


def cell(value):
    return str(value).replace('|', '\\|').replace('\n', ' ')


def compile_data():
    retrieval = read_json(RAW / 'retrieval.json')
    for item in retrieval['files']:
        if digest(RAW / item['path']) != item['sha256']:
            raise ValueError('Changed upstream snapshot: ' + item['path'])
    records = {}
    row_counts = {}
    empty_gloss_rows = []
    for level in ['N3', 'N4', 'N5']:
        source = f'original_data__{level.lower()}.csv'
        with (RAW / source).open(encoding='utf-8', newline='') as stream:
            reader = csv.DictReader(stream)
            if reader.fieldnames != ['jmdict_seq', 'kana', 'kanji', 'waller_definition']:
                raise ValueError('Unexpected source fields: ' + source)
            count = 0
            for line, row in enumerate(reader, 2):
                count += 1
                seq = row['jmdict_seq']
                if not seq.isdigit() or not row['kana']:
                    raise ValueError(f'Invalid ID/reading: {source}:{line}')
                vid = 'jmdict-' + seq
                record = records.setdefault(vid, {'id': vid, 'jmdictSeqFromSource': seq,
                    'forms': [], 'referenceLevels': [], 'originalEnglishGlosses': [],
                    'sourceRows': [], 'curated': None, 'priorityTags': [], 'officialEvidence': []})
                form = {'word': normalize(row['kanji'] or row['kana']), 'reading': normalize(row['kana'])}
                if form not in record['forms']:
                    record['forms'].append(form)
                if level not in record['referenceLevels']:
                    record['referenceLevels'].append(level)
                gloss = row['waller_definition'].strip()
                if gloss and gloss not in record['originalEnglishGlosses']:
                    record['originalEnglishGlosses'].append(gloss)
                if not gloss:
                    empty_gloss_rows.append({'source': source, 'row': line, 'word': form['word']})
                record['sourceRows'].append({'source': source, 'row': line, 'level': level,
                                             'original': row})
            row_counts[level] = count

    source_ids = set(records)
    curated_input = read_json(PACK / 'assets/curated-input.json')
    linked = []
    for entry in curated_input['entries']:
        signature = (normalize(entry['word']), normalize(entry['reading']))
        candidates = [r for r in records.values() if any(
            (f['word'], f['reading']) == signature for f in r['forms'])]
        if len(candidates) > 1:
            raise ValueError('Ambiguous spelling/reading requires explicit resolution: ' + entry['word'])
        if candidates:
            record = candidates[0]
        else:
            vid = 'local-' + hashlib.sha256(('\0'.join(signature)).encode()).hexdigest()[:16]
            if vid in records:
                raise ValueError('Local ID collision: ' + vid)
            record = {'id': vid, 'jmdictSeqFromSource': None,
                      'forms': [{'word': signature[0], 'reading': signature[1]}],
                      'referenceLevels': [], 'originalEnglishGlosses': [], 'sourceRows': [],
                      'curated': None, 'priorityTags': [], 'officialEvidence': []}
            records[vid] = record
        if record['curated'] is not None:
            raise ValueError('Multiple curated entries on one source ID require manual merging')
        record['curated'] = {k: entry[k] for k in ['word', 'reading', 'zh', 'simpleEn', 'note', 'glossProvenance']}
        record['priorityTags'] = entry['tags']
        record['officialEvidence'] = entry['officialEvidence']
        linked.append(record)

    for record in records.values():
        record['forms'].sort(key=lambda f: (f['reading'], f['word']))
        record['referenceLevels'].sort()
        record['qualityFlags'] = []
        if record['sourceRows']:
            record['qualityFlags'].append('reference-level-is-nonofficial')
            if not record['curated']:
                record['qualityFlags'].append('source-gloss-and-spelling-not-individually-reviewed')
            if not record['originalEnglishGlosses']:
                record['qualityFlags'].append('missing-original-english')
        else:
            record['qualityFlags'].append('supplement-outside-selected-reference-lists')
        record['preferredForm'] = ({'word': record['curated']['word'], 'reading': record['curated']['reading']}
                                   if record['curated'] else record['forms'][0])
    entries = sorted(records.values(), key=lambda r: (r['preferredForm']['reading'], r['id']))
    official = [r for r in linked if r['officialEvidence']]
    report = {'sourceRows': row_counts, 'sourceRowsTotal': sum(row_counts.values()),
              'sourceUniqueEntryIds': len(source_ids),
              'sourceUniqueEntryIdsByLevel': {n: sum(n in r['referenceLevels'] for r in entries) for n in row_counts},
              'duplicateOrVariantRowsConsolidated': sum(row_counts.values()) - len(source_ids),
              'totalLibraryEntries': len(entries), 'trilingualPriorityEntries': len(linked),
              'officialSampleTargetEntries': len(official),
              'officialTargetsOutsideSelectedReferenceLists': sum(not r['sourceRows'] for r in official),
              'totalSupplementEntries': len(entries) - len(source_ids),
              'missingOriginalEnglishRows': empty_gloss_rows,
              'entriesWithoutChineseTeachingGloss': sum(r['curated'] is None for r in entries),
              'warnings': ['No complete official JLPT vocabulary inventory exists.',
                           '48 selected targets cover only sections 1/2/4/5 of two vocabulary workbooks.',
                           'Priority tags are source evidence or tutor selection, not exam-frequency estimates.',
                           'Reference spellings and English definitions can be dated, incomplete or misleading.',
                           'No learner mastery, listening or retention evidence has been collected.']}
    payload = {'schemaVersion': '1.0', 'sourceCommit': retrieval['commit'],
               'retrievedAt': retrieval['retrievedAt'],
               'curationSha256': digest(PACK / 'assets/curated-input.json'),
               'license': 'CC-BY-SA-4.0; see SOURCES.md for attribution and evidence boundaries',
               'coverage': 'Complete import of the chosen N3/N4/N5 source files, not all possible N3 words.',
               'entries': entries}
    return payload, report, linked


def render_views(payload, report, priority):
    reference = ['# N3 参考词表', '',
                 '这是选定来源标为 N3 的完整去重视图，不是官方范围，也不是今日作业。N4/N5 基础另在总库中保留。', '',
                 f'原表 {report["sourceRows"]["N3"]} 行，按来源词条 ID 整理为 {report["sourceUniqueEntryIdsByLevel"]["N3"]} 个词条。', '',
                 '英文是原表释义，可能过简或陈旧；中文只对已整理重点补充，其余明确留待逐词讲解。',
                 '同一词条的字形/读法组合保留；没有逐条进行独立词典校审。来源和许可见 [SOURCES.md](SOURCES.md)。', '',
                 '| 词条 ID | 日语与读法 | 原表英文（未全量校审） | 中文学习释义 |',
                 '| --- | --- | --- | --- |']
    for r in payload['entries']:
        if 'N3' not in r['referenceLevels']:
            continue
        forms = '；'.join(f'{f["word"]}（{f["reading"]}）' for f in r['forms'])
        gloss = ' / '.join(r['originalEnglishGlosses']) or '原表缺失'
        zh = r['curated']['zh'] if r['curated'] else '待按场景补充'
        reference.append('| ' + ' | '.join(map(cell, [r['id'], forms, gloss, zh])) + ' |')
    focus = ['# 有依据的重点词与表达', '',
             f'共 {len(priority)} 条三语学习释义。不是必考清单或背诵任务，也不声称它们是全体词汇中频率最高的一组。', '',
             '重点分为“官方样题目标”与“教师按含义、工作和兴趣选择”。原表级别是参考标签；“补充”表示不在本次 N3/N4/N5 原表，不能推断正式级别。', '',
             '中文及简单英语是教师整理，不是官方译文；释义可能需要随具体场景展开。来源与处理边界见 [SOURCES.md](SOURCES.md)。', '']
    for official_group in [True, False]:
        subset = [r for r in priority if bool(r['officialEvidence']) == official_group]
        focus.extend(['## ' + ('官方练习册已核对目标' if official_group else '含义理解、软件与兴趣优先'), '',
                      '| 日语 | 读音 | 中文 | 简单英语 | 参考表标签 | 依据与用法提醒 |',
                      '| --- | --- | --- | --- | --- | --- |'])
        for r in subset:
            c = r['curated']
            evidence = '; '.join(f'{e["sourceId"]} Q{e["question"]}，PDF第{e["pdfPage"]}页' for e in r['officialEvidence'])
            reason = (evidence if evidence else '教师选择：' + ', '.join(r['priorityTags'])) + '；' + c['note']
            focus.append('| ' + ' | '.join(map(cell, [c['word'], c['reading'], c['zh'], c['simpleEn'],
                                                     ', '.join(r['referenceLevels']) or '补充', reason])) + ' |')
        focus.append('')
    return {'lexicon.json': dump(payload), 'quality-report.json': dump(report),
            'N3参考词表.md': '\n'.join(reference) + '\n', '重点词.md': '\n'.join(focus) + '\n'}


def build():
    payload, report, priority = compile_data()
    outputs = render_views(payload, report, priority)
    stamp = datetime.now().strftime('%Y%m%d-%H%M%S-%f')
    for name, value in outputs.items():
        dest = LIBRARY / name
        if dest.exists() and dest.read_text(encoding='utf-8') != value:
            backup = PACK / 'backups' / stamp / name
            backup.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(dest, backup)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(value, encoding='utf-8')
    print(dump(report))


def verify():
    payload, report, priority = compile_data()
    expected = render_views(payload, report, priority)
    for name, value in expected.items():
        if (LIBRARY / name).read_text(encoding='utf-8') != value:
            raise ValueError('Generated output differs from current inputs: ' + name)
    entries = read_json(LIBRARY / 'lexicon.json')['entries']
    ids = [r['id'] for r in entries]
    assert len(ids) == len(set(ids)), 'Duplicate IDs'
    row_keys = [(x['source'], x['row']) for r in entries for x in r['sourceRows']]
    assert len(row_keys) == len(set(row_keys)) == report['sourceRowsTotal'], 'Lost or repeated source rows'
    for n, count in report['sourceRows'].items():
        assert {line for name, line in row_keys if name == f'original_data__{n.lower()}.csv'} == set(range(2, count + 2))
    source_records = [r for r in entries if r['sourceRows']]
    assert all(len({x['original']['jmdict_seq'] for x in r['sourceRows']}) == 1 for r in source_records)
    assert len({r['id'] for r in entries if any(f['reading'] == 'せい' for f in r['forms'])}) >= 5, 'Homophones collapsed'
    assert all(c['curated']['zh'] and c['curated']['simpleEn'] for c in priority), 'Missing priority translations'
    evidence = [e for r in entries for e in r['officialEvidence']]
    assert len(evidence) == 48
    assert len({(e['sourceId'], e['question']) for e in evidence}) == 48
    for year in [2012, 2018]:
        questions = {e['question'] for e in evidence if str(year) in e['sourceId']}
        tail = range(24, 34) if year == 2012 else range(26, 36)
        assert questions == set(range(1, 15)) | set(tail)
    for word, operator in [('以上', '>=10'), ('以下', '<=10')]:
        item = next(r for r in priority if r['curated']['word'] == word)
        assert operator in item['curated']['note'], 'Boundary explanation missing'
        assert item['originalEnglishGlosses'], 'Original evidence must remain'
    assert all('examFrequency' not in r and 'mastered' not in r for r in entries)
    print(dump({'status': 'passed', 'sourceRowsPreserved': len(row_keys), 'uniqueEntries': len(entries),
                'trilingualPriorityEntries': len(priority), 'officialTargetReferences': len(evidence),
                'checked': ['upstream checksums', 'reproducible generated views', 'source row coverage',
                            'homophone separation', 'priority translations and official question references',
                            'numerical boundary corrections', 'no invented frequency or mastery'],
                'limits': ['No full dictionary audit', 'No complete official exam inventory', 'No learner performance test']}))


def search(args):
    data = read_json(LIBRARY / 'lexicon.json')
    query = normalize(args.query).casefold()
    results = []
    for r in data['entries']:
        if args.level and args.level not in r['referenceLevels']:
            continue
        if args.tag and args.tag not in r['priorityTags']:
            continue
        if args.priority and not r['curated']:
            continue
        searchable = json.dumps([r['forms'], r['originalEnglishGlosses'], r['curated']], ensure_ascii=False).casefold()
        if query and query not in searchable:
            continue
        results.append({'id': r['id'], 'form': r['preferredForm'], 'referenceLevels': r['referenceLevels'],
                        'originalEnglish': r['originalEnglishGlosses'], 'teaching': r['curated'],
                        'priorityTags': r['priorityTags'], 'officialEvidence': r['officialEvidence'],
                        'qualityFlags': r['qualityFlags']})
    print(dump({'totalMatches': len(results), 'showing': min(len(results), args.limit), 'entries': results[:args.limit]}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('build')
    sub.add_parser('check')
    p = sub.add_parser('search')
    p.add_argument('query', nargs='?', default='')
    p.add_argument('--level', choices=['N3', 'N4', 'N5'])
    p.add_argument('--tag')
    p.add_argument('--priority', action='store_true')
    p.add_argument('--limit', type=int, default=10)
    args = parser.parse_args()
    if args.command == 'build':
        build()
    elif args.command == 'check':
        verify()
    else:
        if args.limit < 1:
            parser.error('--limit must be positive')
        search(args)


if __name__ == '__main__':
    main()
