"""Fail publication for corrupt data; report source coverage without deleting it."""
import json, re
from pathlib import Path
from datetime import date, datetime

root = Path(__file__).resolve().parents[1]
data = json.loads((root / 'dist/data/screenings.json').read_text())
venues = {v['id'] for v in json.loads((root / 'dist/data/theaters.json').read_text())}
venues -= {'lincoln','moma','angelika','paris','momi','spectacle'}
assert len(venues) == 8
assert set(data['venues']) == venues
if data.get('updatedAt'): datetime.fromisoformat(data['updatedAt'])
keys = set()
for r in data['screenings']:
    assert r['venue'] in venues
    date.fromisoformat(r['date'])
    assert r['title'].strip() and r['ticketUrl'].startswith(('https://', 'http://'))
    assert r.get('description','').strip() and len(r['description']) <= 240
    assert r['showtimes'] == sorted(set(r['showtimes']))
    assert all(re.fullmatch(r'(?:[01]\d|2[0-3]):[0-5]\d', t) for t in r['showtimes'])
    assert r.get('format') in (None, '', '16mm', '35mm', '70mm')
    key = (r['venue'], r['date'], r['title'].casefold(), r.get('format') or '')
    assert key not in keys, f'Duplicate: {key}'
    keys.add(key)
for v, status in data['venues'].items():
    print(f"{v}: {status['status']}")
print(f"Validated {len(keys)} unique film / theater / date / format entries.")
