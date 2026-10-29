#!/usr/bin/env python3
"""Date-aware daily page creation and evidence-based learning index rendering."""
import argparse
from datetime import datetime, date, timedelta
import json
import os
from pathlib import Path
import re
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]


def local_day(zone, now=None):
    return (now or datetime.now(ZoneInfo(zone))).astimezone(ZoneInfo(zone)).date()


def ensure_today(root, day):
    folder = root / '日常练习'
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / f'{day.isoformat()}.md'
    try:
        with target.open('x', encoding='utf-8') as f:
            f.write(f'# 日语练习 · {day:%m.%d}\n\n{day.isoformat()} · 今天的对话\n\n---\n\n### 01 · 老师\n\n')
    except FileExistsError:
        pass
    return target


def turn(root, evidence):
    path = (root / evidence['file']).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError('Evidence must stay inside the project')
    text = path.read_text(encoding='utf-8')
    sections = re.split(r'^### (\d+) · ([^\n]+)\n', text, flags=re.M)
    for i in range(1, len(sections), 3):
        if int(sections[i]) == evidence['turn']:
            if evidence['quote'] not in sections[i + 2]:
                raise ValueError(f'Evidence quote missing: {evidence["id"]}')
            return sections[i + 1]
    raise ValueError(f'Evidence turn missing: {evidence["id"]}')


def summarize(root, catalog, day):
    rows, ids, event_ids = [], set(), set()
    for item in catalog['items']:
        if item['id'] in ids:
            raise ValueError('Duplicate item ID')
        ids.add(item['id'])
        events = item['events']
        if not events:
            raise ValueError('A learned item needs evidence')
        for event in events:
            if event['id'] in event_ids:
                raise ValueError('Duplicate event ID')
            event_ids.add(event['id'])
            role = turn(root, event)
            if date.fromisoformat(event['date']) > day:
                raise ValueError('Future evidence date')
            if event['kind'] not in {'exposure', 'attempt', 'supported-correct', 'review-verified'}:
                raise ValueError('Unknown evidence kind')
            if event['kind'] != 'exposure' and not role.startswith('我'):
                raise ValueError('Practice evidence must be a user turn')
        first = min(date.fromisoformat(e['date']) for e in events)
        last = max(date.fromisoformat(e['date']) for e in events)
        reviews = [e for e in events if e['kind'] == 'review-verified']
        for e in reviews:
            if e.get('support') != 'none' or date.fromisoformat(e['date']) <= first or not e.get('assessment'):
                raise ValueError('Review verification requires later unsupported response and assessment')
        practiced = any(e['kind'] != 'exposure' for e in events)
        interval = [1, 3, 7][min(len(reviews), 2)]
        rows.append(dict(item=item, first=first, last=last,
                         practiced=practiced, verified=bool(reviews),
                         due=last + timedelta(days=interval)))
    return rows


def render(root, rows, day):
    words = sum(r['item']['kind'] == 'word' for r in rows)
    lines = ['# 学习进度', '', f'更新日期：{day.isoformat()}', '',
             '“学过”表示已有教学接触记录，不代表掌握。词条、表达和语法分开计数；不是 N3 完成百分比。', '',
             f'- 已接触：{len(rows)} 项（词条 {words}，表达/语法 {len(rows)-words}）。',
             f'- 有输出练习记录：{sum(r["practiced"] for r in rows)} 项，包含看提示后的尝试。',
             f'- 有隔日无提示复习验证：{sum(r["verified"] for r in rows)} 项；不等于永久掌握。',
             f'- 日期页：{len(list((root / "日常练习").glob("????-??-??.md")))} 页；不换算学习时长或连续打卡。', '',
             '| 学过的项目 | 罗马音 | 意思 | 类型 | 当前证据 | 首次/最近记录 | 原始记录 |',
             '| --- | --- | --- | --- | --- | --- | --- |']
    for r in rows:
        i = r['item']
        e = i['events'][-1]
        link = Path(e['file']).name
        target = os.path.relpath((root / e['file']).resolve(), (root / '日常练习').resolve())
        state = '复习验证过' if r['verified'] else '练习过（有提示）' if r['practiced'] else '接触过'
        kind = {'word': '词条', 'expression': '表达', 'grammar': '语法'}[i['kind']]
        lines.append(f'| {i["japanese"]} | {i["romaji"]} | {i["meaning"]} | {kind} | {state} | {r["first"]} / {r["last"]} | [{link} · 第 {e["turn"]} 轮]({target}) |')
    lines += ['', '## 下次可自然重遇', '',
              '这是教师选材候选，不是欠下的作业。每次最多选 1–2 项，用户要换主题时可以跳过。', '']
    candidates = sorted((r for r in rows if r['due'] <= day), key=lambda r: (r['due'], r['item']['id']))[:2]
    for r in candidates:
        i = r['item']
        lines.append(f'- {i["japanese"]}（{i["romaji"]}）：{i["meaning"]}。换一个小场景重遇。')
    if not candidates:
        lines.append('目前没有按试行间隔到期的项目；可以继续当前场景。')
    lines += ['', '## 统计边界', '',
              '只收录教师确认真正教过的目标，不把故事里的每个字、资料库里的词或规划中的词算成已学。',
              '历史日期按当时已知记录整理；不根据文件修改时间推断作答时间。旧页中跨日的纠正按标注日期记录。',
              '正确性仍由教师判断，程序只核对来源、回合和状态条件。当前没有真实听力测验或学习时长统计。',
              '本页由学习索引生成；修订证据须保留原始日常对话。任务状态仍以任务包 TASK-META.json 为准。', '']
    return '\n'.join(lines)


def lesson_ready(root, catalog, day, teacher_turn=2, reply_turn=3):
    """Verify written material and reply location; never create a page."""
    page = root / '日常练习' / f'{day.isoformat()}.md'
    if not page.is_file():
        raise ValueError('Today\'s learning page does not exist')
    sections = re.split(r'^### (\d+) · ([^\n]+)\n',
                        page.read_text(encoding='utf-8'), flags=re.M)
    turns = {}
    for pos in range(1, len(sections), 3):
        number = int(sections[pos])
        if number in turns:
            raise ValueError('Duplicate turn numbers in learning page')
        turns[number] = (sections[pos + 1], sections[pos + 2])
    role, body = turns.get(teacher_turn, ('', ''))
    if not role.startswith('老师'):
        raise ValueError('Requested teaching turn is missing')
    fields = {}
    for field in ['原文', '分块辅助', '假名', '罗马音（拼读）', '输入法按键']:
        match = re.search(r'^- ' + re.escape(field) + r'：([^\n]+)', body, re.M)
        if not match or not match[1].strip(' *`'):
            raise ValueError(f'Teaching material needs a nonempty {field} field')
        fields[field] = match[1].strip(' *`')
    if re.sub(r'\s+', '', fields['原文']) != re.sub(r'\s+', '', fields['分块辅助']):
        raise ValueError('Grouped reading must preserve the original Japanese text')
    if reply_turn <= teacher_turn or not turns.get(reply_turn, ('', ''))[0].startswith('我'):
        raise ValueError('A subsequent user reply turn is missing')
    relative = page.relative_to(root).as_posix()
    sessions = [s for s in catalog.get('sessions', [])
                if s.get('date') == str(day) and s.get('source') == relative]
    if not any(s.get('reviewPlan', {}).get('targets') for s in sessions):
        raise ValueError('Current session has no recorded review plan')
    return {'ready': True, 'today': str(day), 'page': str(page),
            'teacherTurn': teacher_turn, 'replyTurn': reply_turn}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['sync', 'check', 'ready'])
    parser.add_argument('--teacher-turn', type=int, default=2)
    parser.add_argument('--reply-turn', type=int, default=3)
    args = parser.parse_args()
    catalog = json.loads((ROOT / '日常练习/学习索引.json').read_text(encoding='utf-8'))
    day = local_day(catalog['timezone'])
    if args.command == 'ready':
        try:
            result = lesson_ready(ROOT, catalog, day, args.teacher_turn, args.reply_turn)
        except ValueError as exc:
            parser.exit(2, f'Not ready: {exc}\n')
        print(json.dumps(result, ensure_ascii=False))
        return
    rows = summarize(ROOT, catalog, day)
    if args.command == 'sync':
        page = ensure_today(ROOT, day)
        output = ROOT / '日常练习/学习进度.md'
        rendered = render(ROOT, rows, day)
        if not output.exists() or output.read_text(encoding='utf-8') != rendered:
            output.write_text(rendered, encoding='utf-8')
        print(json.dumps({'today': str(day), 'page': str(page), 'learnedItems': len(rows)}, ensure_ascii=False))
    else:
        print(f'OK: {len(rows)} items, evidence checked')


if __name__ == '__main__':
    main()
