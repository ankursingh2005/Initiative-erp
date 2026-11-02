"""Resolve uploaded incentive periods without falling back to today's month."""
import re
from datetime import date, datetime


def detect_incentive_month(value):
    if isinstance(value, (date, datetime)):
        return value.strftime('%Y-%m')
    text = str(value or '').lower().replace('_', ' ')
    years = set(re.findall(r'\b(?:19|20)\d{2}\b', text))
    if len(years) != 1:
        return ''
    year = next(iter(years))
    names = [r'jan(?:uary)?', r'feb(?:ruary)?', r'mar(?:ch)?', r'apr(?:il)?', r'may',
             r'jun(?:e)?', r'jul(?:y)?', r'aug(?:ust)?', r'sep(?:t(?:ember)?)?',
             r'oct(?:ober)?', r'nov(?:ember)?', r'dec(?:ember)?']
    months = [i + 1 for i, name in enumerate(names) if re.search(r'\b' + name + r'\b', text)]
    if len(months) == 1:
        return f'{year}-{months[0]:02d}'
    if months:
        return ''
    match = re.search(r'\b((?:19|20)\d{2})[- /]+(0?[1-9]|1[0-2])\b', text)
    if match:
        return f'{match[1]}-{int(match[2]):02d}'
    match = re.search(r'\b(0?[1-9]|1[0-2])[- /]+((?:19|20)\d{2})\b', text)
    return f'{match[2]}-{int(match[1]):02d}' if match else ''
