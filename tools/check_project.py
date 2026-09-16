#!/usr/bin/env python3
"""Read-only project validation, with an optional explicitly selected JSON report."""
from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path
import re
import sys
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]
TASKS = ROOT / '2026-Winter-Exam/tasks'
STATUSES = {'draft', 'ready', 'active', 'blocked', 'review', 'closed'}
ACCEPTANCE = {'not-started', 'partial', 'passed', 'failed', 'blocked'}
TYPES = {'baseline', 'learning-unit', 'exam-practice', 'project-setup', 'resource-build'}
CORE = ['TASK-META.json', 'README.md', '学习目标与计划.md', '练习.md',
        '作答与反馈.md', '验收与证据.md', '接续与变更.md', '教法探索.md']


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', help='Write a JSON report inside the project.')
    args = parser.parse_args()
    failures: list[str] = []
    checks = 0

    def check(condition: bool, message: str) -> None:
        nonlocal checks
        checks += 1
        if not condition:
            failures.append(message)

    def inside(path: Path) -> bool:
        return path.resolve().is_relative_to(ROOT)

    def load_json(path: Path):
        try:
            return json.loads(path.read_text(encoding='utf-8'))
        except (OSError, ValueError) as exc:
            check(False, f'{path.relative_to(ROOT)}: {exc}')
            return None

    required = ['README.md', 'AGENTS.md', 'MEMORY.md', 'AI-INTERACTION-PANEL.md',
                '.ai/agents/tutor.md', '.ai/instructions/teaching.md',
                '.ai/instructions/adaptive-tutoring.md', '.ai/docs/task-policy.md',
                '.ai/interactions/INDEX.md', '2026-Winter-Exam/README.md',
                '2026-Winter-Exam/exam-brief.md', '2026-Winter-Exam/resources.md',
                'tools/initialization-manifest.json']
    for name in required:
        check((ROOT / name).is_file(), f'Missing required file: {name}')
    for name in ['agents', 'instructions', 'docs', 'skills', 'interactions']:
        check((ROOT / '.ai' / name / 'README.md').is_file(), f'Missing .ai/{name}/README.md')

    documents = [p for p in ROOT.rglob('*.md')
                 if not any(s in p.relative_to(ROOT).parts for s in ('backups', '.git', '.local'))]
    local_links = 0
    for path in documents:
        content = path.read_text(encoding='utf-8')
        # This project uses simple inline Markdown links, without nested parentheses.
        content = re.sub(r'```.*?```', '', content, flags=re.S)
        for match in re.finditer(r'!?\[[^\]\n]*\]\(([^)\n]+)\)', content):
            target = match.group(1).strip().strip('<>')
            if re.match(r'^[a-zA-Z][a-zA-Z0-9+.-]*:', target) or target.startswith('#'):
                continue
            target = unquote(target.split('#', 1)[0])
            dest = (path.parent / target).resolve()
            local_links += 1
            check(inside(dest) and dest.exists(), f'Broken/outside link in {path.relative_to(ROOT)}: {target}')

    metadata = {}
    folders = [p for p in TASKS.iterdir() if p.is_dir()] if TASKS.exists() else []
    check(bool(folders), 'No task packages found')
    required_keys = {'schemaVersion', 'taskId', 'taskType', 'title', 'deliveryUnit', 'scope',
                     'status', 'currentStage', 'owner', 'dependencies', 'skills', 'instructions',
                     'deliverables', 'acceptanceStatus', 'acceptedExceptions', 'activeChange',
                     'createdAt', 'updatedAt'}
    for folder in folders:
        for name in CORE:
            check((folder / name).is_file(), f'{folder.name}: missing {name}')
        meta = load_json(folder / 'TASK-META.json')
        if not isinstance(meta, dict):
            continue
        label = folder.name
        check(required_keys <= meta.keys(), f'{label}: missing metadata fields')
        task_id = meta.get('taskId')
        check(isinstance(task_id, str) and bool(re.fullmatch(r'JP-N3-\d{3}', task_id)), f'{label}: invalid task ID')
        check(task_id not in metadata, f'{label}: duplicate task ID')
        metadata[task_id] = meta
        check(meta.get('schemaVersion') == '1.0', f'{label}: unknown schema version')
        check(meta.get('status') in STATUSES, f'{label}: invalid status')
        check(meta.get('taskType') in TYPES, f'{label}: invalid task type')
        check(meta.get('acceptanceStatus') in ACCEPTANCE, f'{label}: invalid acceptance status')
        for key in ['title', 'deliveryUnit', 'owner', 'currentStage']:
            value = meta.get(key)
            check(isinstance(value, str) and bool(value.strip()), f'{label}: empty {key}')
        scope = meta.get('scope', {})
        check(isinstance(scope, dict) and all(isinstance(scope.get(k), list) and scope[k] for k in ['in', 'out']),
              f'{label}: scope must contain nonempty in/out lists')
        for key in ['dependencies', 'skills', 'instructions', 'deliverables', 'acceptedExceptions']:
            check(isinstance(meta.get(key), list), f'{label}: {key} must be a list')
        for key in ['createdAt', 'updatedAt']:
            try:
                timestamp = datetime.fromisoformat(meta.get(key, ''))
                check(timestamp.tzinfo is not None, f'{label}: {key} needs timezone')
            except (ValueError, TypeError):
                check(False, f'{label}: invalid {key}')
        check('REPLACE-' not in json.dumps(meta), f'{label}: unresolved template metadata')
        for key in ['skills', 'instructions']:
            for name in meta.get(key, []):
                dest = ROOT / name
                check(inside(dest) and dest.is_file(), f'{label}: missing {key} path {name}')
        for name in meta.get('deliverables', []):
            dest = ROOT / name
            check(inside(dest), f'{label}: deliverable outside project')
            if meta.get('status') == 'closed':
                check(dest.is_file(), f'{label}: closed task missing deliverable {name}')
        if meta.get('status') == 'closed':
            check(meta.get('acceptanceStatus') == 'passed' or
                  (meta.get('acceptanceStatus') == 'partial' and bool(meta.get('acceptedExceptions'))),
                  f'{label}: closed task lacks passed acceptance or documented exceptions')

    for task_id, meta in metadata.items():
        for dependency in meta.get('dependencies', []):
            check(dependency in metadata and dependency != task_id, f'{task_id}: invalid dependency {dependency}')

    entry = ROOT / '2026-Winter-Exam/README.md'
    if entry.exists():
        pointers = re.findall(r'\]\((tasks/[^/]+/README\.md)\)', entry.read_text(encoding='utf-8'))
        learning_pointers = []
        for pointer in pointers:
            data = load_json(entry.parent / Path(pointer).parent / 'TASK-META.json')
            if isinstance(data, dict) and data.get('taskType') != 'project-setup':
                learning_pointers.append(data)
        check(len(learning_pointers) == 1, 'Exam entry must have one current learning pointer')
        if learning_pointers:
            check(learning_pointers[0].get('status') != 'closed', 'Current learning pointer targets a closed package')

    for name in CORE:
        check((ROOT / '2026-Winter-Exam/templates/learning-task' / name).is_file(), f'Template missing {name}')
    template = load_json(ROOT / '2026-Winter-Exam/templates/learning-task/TASK-META.json')
    check(isinstance(template, dict) and template.get('status') == 'draft', 'Template must remain draft')

    manifest = load_json(ROOT / 'tools/initialization-manifest.json')
    if isinstance(manifest, dict):
        check(manifest.get('preexistingDirectories') == ['2026-Winter-Exam'], 'Manifest must preserve preexisting directory')
        entries = manifest.get('files', [])
        check(bool(entries), 'Manifest must list created files')
        for item in entries:
            dest = ROOT / item.get('path', '')
            check(inside(dest) and dest.is_file(), f'Manifest file missing/outside: {item.get("path")}')
            check(bool(re.fullmatch(r'[0-9a-f]{64}', item.get('sha256', ''))), 'Invalid manifest hash')
        # Hashes are a creation snapshot, not a requirement that future work remain unchanged.

    result = {'checkedAt': datetime.now().astimezone().isoformat(timespec='seconds'),
              'status': 'passed' if not failures else 'failed', 'checks': checks,
              'markdownFiles': len(documents), 'localLinks': local_links,
              'taskPackages': len(folders), 'failures': failures,
              'limits': ['No external link/audio availability check', 'No Japanese content or learning-outcome verification',
                         'No proof that all future edits follow governance; manual review remains necessary']}
    if args.report:
        target = (ROOT / args.report).resolve()
        if not inside(target) or target.suffix != '.json':
            parser.error('Report must be a .json file inside this project')
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 1 if failures else 0


if __name__ == '__main__':
    sys.exit(main())
