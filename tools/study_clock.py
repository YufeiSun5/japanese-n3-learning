#!/usr/bin/env python3
"""Read the live clock in Pacific time and the learning-record timezone."""
from datetime import date, datetime, timezone
import argparse
import json
from zoneinfo import ZoneInfo


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--exam-date', type=date.fromisoformat)
    args = parser.parse_args()
    now = datetime.now(timezone.utc)
    local = now.astimezone(ZoneInfo('Asia/Singapore'))
    pacific = now.astimezone(ZoneInfo('America/Los_Angeles'))
    result = {
        'utc': now.isoformat(timespec='seconds'),
        'pacificTimezone': 'America/Los_Angeles',
        'pacific': pacific.isoformat(timespec='seconds'),
        'pacificAbbreviation': pacific.tzname(),
        'learningTimezone': 'Asia/Singapore',
        'learningTime': local.isoformat(timespec='seconds'),
        'learningDate': local.date().isoformat(),
    }
    if args.exam_date:
        result['examDate'] = args.exam_date.isoformat()
        result['calendarDaysUntilExam'] = (args.exam_date - local.date()).days
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
