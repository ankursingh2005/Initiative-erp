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
    if user.weekoff_day == day:
        return
    effective_date = effective_date or datetime.now(timezone(timedelta(hours=5, minutes=30))).date()
    history = weekoff_history(user)
    if not history:
        history = [{'from': '0001-01-01', 'day': user.weekoff_day}]
    key = effective_date.isoformat()
    history = [entry for entry in history if entry['from'] != key]
    history.append({'from': key, 'day': day})
    user.weekoff_history = json.dumps(sorted(history, key=lambda entry: entry['from']))
    user.weekoff_day = day
