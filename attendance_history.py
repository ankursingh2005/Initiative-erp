"""Keep attendance scheduling changes effective from their change date."""
import json
from datetime import datetime, timedelta, timezone


def weekoff_history(user):
    return json.loads(getattr(user, 'weekoff_history', None) or '[]')


def weekoff_on(user, day):
    value = user.weekoff_day
    for entry in weekoff_history(user):
        if entry['from'] > day.isoformat():
            break
        value = entry['day']
    return value


def change_weekoff(user, day, effective_date=None):
    if weekoff_on(user, effective_date or datetime.now(timezone(timedelta(hours=5, minutes=30))).date()) == day:
        return
    effective_date = effective_date or datetime.now(timezone(timedelta(hours=5, minutes=30))).date()
    history = weekoff_history(user)
    if not history:
        history = [{'from': '0001-01-01', 'day': user.weekoff_day}]
    key = effective_date.isoformat()
    history = [entry for entry in history if entry['from'] != key]
    history.append({'from': key, 'day': day})
    user.weekoff_history = json.dumps(sorted(history, key=lambda entry: entry['from']))
    user.weekoff_day = (day[0] if day else None) if isinstance(day, list) else day


def daily_attendance_status(user, day, today, present=False, leave=False):
    """Shared daily status priority for live attendance and salary summaries."""
    if day > today:
        return 'upcoming'
    if present:
        return 'present'
    if leave:
        return 'leave'
    return 'weekoff' if is_weekoff(user, day) else 'absent'


def is_weekoff(user, day):
    value = weekoff_on(user, day)
    return day.strftime('%A') in (value if isinstance(value, list) else [value])
