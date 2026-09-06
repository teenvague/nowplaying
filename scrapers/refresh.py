"""Daily, source-attributed cinema snapshots. Never replace a failed source with [] ."""
from __future__ import annotations
import argparse, concurrent.futures, hashlib, html, json, re, urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urljoin, urlencode
from zoneinfo import ZoneInfo
from bs4 import BeautifulSoup, Comment
from titles import title_case
from cache_images import cache_images
from descriptions import enrich_descriptions, clean
from summaries import write_summaries

ROOT = Path(__file__).resolve().parents[1]
NY = ZoneInfo('America/New_York')
TODAY = datetime.now(NY).date()
STAMP = datetime.now(timezone.utc).isoformat()
CACHE = None
URL_CACHE = {}

def text(node):
    return re.sub(r'\s+', ' ', node.get_text(' ', strip=True)).strip() if node else ''

def fetch(url, key=None):
    if CACHE and key and (CACHE / (key + '.html')).exists():
        return (CACHE / (key + '.html')).read_text()
    if url not in URL_CACHE:
        req = urllib.request.Request(url, headers={'User-Agent': 'PlayingInNewYork/1.0 (cinema calendar index)'})
        with urllib.request.urlopen(req, timeout=30) as r:
            if r.status != 200:
                raise ValueError(f'HTTP {r.status}')
            URL_CACHE[url] = r.read().decode('utf-8-sig', errors='replace')
    return URL_CACHE[url]

def soup(url, key=None):
    return BeautifulSoup(fetch(url, key), 'html.parser')

def nearest_date(month, day):
    candidates = []
    for year in [TODAY.year - 1, TODAY.year, TODAY.year + 1]:
        try: candidates.append(date(year, month, day))
        except ValueError: pass
    return min(candidates, key=lambda d: abs((d - TODAY).days)).isoformat()

def short_date(value):
    m = re.search(r'([A-Za-z]+)\s+(\d{1,2})', value)
    if not m: raise ValueError(f'No date: {value}')
    month = datetime.strptime(m[1][:3], '%b').month
    return nearest_date(month, int(m[2]))

def clock(value, pm_default=False):
    m = re.search(r'(\d{1,2})(?:[:.](\d{2}))?\s*(AM|PM)?', value, re.I)
    if not m: raise ValueError(f'No time: {value}')
    h, minute = int(m[1]), int(m[2] or 0)
    suffix = (m[3] or '').upper()
    if suffix: h = h % 12 + (12 if suffix == 'PM' else 0)
    elif pm_default and h < 10: h += 12
    elif not pm_default: raise ValueError(f'Ambiguous meridiem: {value}')
    if h > 23 or minute > 59: raise ValueError('Invalid time')
    return f'{h:02}:{minute:02}'

def physical(value):
    m = re.search(r'\b(16|35|70)\s*mm\b', value, re.I)
    return m[1] + 'mm' if m else None

def year_in(value):
    m = re.search(r'\b(18\d{2}|19\d{2}|20\d{2})\b', value)
    return int(m[1]) if m else None

def image_url(node, base):
    if not node: return None
    value = node.get("src") or node.get("content")
    return urljoin(base, value) if value else None

def row(venue, title, day, times, url, **metadata):
    return dict(venue=venue, title=html.unescape(title).strip(), date=day,
                showtimes=times, ticketUrl=url, sourceUrl=url, fetchedAt=STAMP, **metadata)

def metadata(url, venue):
    """Read only film-specific metadata, never infer credits from review prose."""
    s = soup(url)
    out = {}
    image = image_url(s.select_one('meta[property="og:image"]'), url)
    if image: out['imageUrl'] = image
    for node in s.select('.synopsis, .film-text-content.synopsis, .detailed-screening__copy, .film-notes p, .copy > p, .entry-content p'):
        description = clean(text(node))
        if len(description) >= 45:
            out['description'] = description
            break
    if venue == 'ifc':
        h = s.select_one('h1.title')
        if h:
            for li in h.parent.select('li'):
                strong = li.find('strong', recursive=False)
                if strong and text(strong) in ['Director', 'Year']:
                    value = text(li)[len(text(strong)):].strip()
                    out['director' if text(strong) == 'Director' else 'year'] = value
    elif venue == 'quad':
        h = s.select_one('h1.film-title')
        if h:
            info = text(h.find_next_sibling('p'))
            out.update(year=year_in(info), format=physical(info))
        for credit in s.select('.credit-item'):
            if text(credit.select_one('.credit-label')) == 'A film by':
                out['director'] = text(credit.select_one('.credit-name'))
    elif venue == 'film-forum':
        h = s.select_one('h2.main-title')
        if h:
            section = h.parent
            urgent = section.select_one('.urgent')
            if urgent:
                lines = urgent.get_text('\n', strip=True).splitlines()
                for line in lines:
                    m = re.match(r'DIRECTED BY\s+(.+)', line, re.I)
                    if m: out['director'] = m[1].title()
            for p in section.select('.copy > p, .details'):
                value = text(p)
                if re.match(r'^(19\d{2}|20\d{2})\s', value):
                    out.update(year=year_in(value), format=physical(value))
                    break
    return out

def enrich(rows, venue):
    urls = sorted(set(r['ticketUrl'] for r in rows))
    def one(url):
        try: return url, metadata(url, venue)
        except Exception: return url, {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        details = dict(pool.map(one, urls))
    for r in rows: r.update(details[r['ticketUrl']])
    return rows

def metrograph(v):
    s = soup(v['sourceUrl'], 'metrograph'); rows = []
    for movie in s.select('.homepage-in-theater-movie'):
        title = movie.select_one('.movie_title a')
        if not title: continue
        name = re.sub(r'\s*\[(?:16|35|70)mm\]', '', text(title), flags=re.I)
        director = next((text(h).removeprefix('Director:').strip() for h in movie.select('h5') if text(h).startswith('Director:')), None)
        info = next((text(h) for h in movie.select('h5') if re.match(r'^\d{4}\s*/', text(h))), '')
        for day in movie.select('.film_day'):
            parts = day.get('id', '').split('_')
            date_value = short_date(' '.join(parts[-2:]))
            times = [clock(text(a)) for a in day.select('a') if re.search(r'\d.*[ap]m', text(a), re.I)]
            rows.append(row(v['id'], name, date_value, times, urljoin(v['sourceUrl'], title['href']), director=director, year=year_in(info), format=physical(info), imageUrl=image_url(movie.select_one('img'), v['sourceUrl']), description=clean(text(movie.select_one('.synopsis')))))
    return rows

def film_forum(v):
    s = soup(v['sourceUrl'], 'film-forum'); rows = []
    for tab in s.select('.showtimes-container > div'):
        comment = tab.find(string=lambda t: isinstance(t, Comment) and t.strip().isdigit())
        if not comment: continue
        dom = int(comment.strip())
        candidates = [TODAY + timedelta(days=n) for n in range(-7, 33) if (TODAY + timedelta(days=n)).day == dom]
        if not candidates: continue
        day = min(candidates, key=lambda d: abs((d - TODAY).days)).isoformat()
        for p in tab.find_all('p', recursive=False):
            title = p.select_one('strong a')
            if not title: continue
            times = [clock(text(span), pm_default=True) for span in p.select('span') if re.fullmatch(r'\d{1,2}:\d{2}(?:\s*[AP]M)?', text(span), re.I)]
            if times:
                series = p.find('a', href=re.compile('/series/'))
                rows.append(row(v['id'], text(title), day, times, title['href'], series=text(series) or None))
    return enrich(rows, v['id'])

def ifc(v):
    s = soup(v['sourceUrl'], 'ifc'); rows = []
    for day in s.select('.daily-schedule'):
        heading = day.find('h3', recursive=False)
        if not heading or not re.search(r'\b[A-Z][a-z]{2}\s+\d{1,2}\b', text(heading)): continue
        d = short_date(text(heading).split(' ', 1)[-1])
        for details in day.select('.details'):
            title = details.select_one('h3 a')
            if not title: continue
            times = [clock(text(a)) for a in details.select('.times a')]
            rows.append(row(v['id'], text(title), d, times, title['href']))
    return enrich(rows, v['id'])

def quad(v):
    s = soup(v['sourceUrl'], 'quad'); rows = []
    for item in s.select('.day-wrap .grid-item'):
        title = item.select_one('h4 a'); links = item.select('.showtimes-list a')
        # The list also carries non-time chips (e.g. a 35mm format badge); only parse real showtimes.
        times = [a for a in links if re.search(r'\d{1,2}(?:[:.]\d{2})?\s*(?:AM|PM)\b', text(a), re.I)]
        if not title or not times: continue
        match = re.search(r'date=(\d{4}-\d{2}-\d{2})', times[0]['href'])
        if match: rows.append(row(v['id'], text(title), match[1], [clock(text(a)) for a in times], title['href']))
    return enrich(rows, v['id'])

def roxy(v):
    s = soup(v['sourceUrl'], 'roxy'); rows = []
    for item in s.select('.detailed-screening__card[data-datetime]'):
        name = text(item.select_one('.detailed-screening__title'))
        info = text(item.select_one('.detailed-screening__info'))
        time = datetime.fromisoformat(item['data-datetime']).astimezone(NY)
        link = item.select_one('a.cta--text-link') or item.select_one('a[href]')
        if link:
            title = re.sub(r'\s*-\s*(?:16|35|70)MM', '', name, flags=re.I)
            rows.append(row(v['id'], title, time.date().isoformat(), [time.strftime('%H:%M')], link['href'], year=year_in(info), format=physical(name), imageUrl=image_url(item.select_one('img'), v['sourceUrl']), description=clean(text(item.select_one('.detailed-screening__copy')))))
    return rows

def anthology(v):
    s = soup(v['sourceUrl'] + '?view=list', 'anthology-list'); rows = []
    for item in s.select('.film-showing'):
        heading = item.find_previous('h3', class_='current-day')
        detail = item.select_one('.showing-details'); title = item.select_one('.film-title')
        time = item.find('a', attrs={'name': re.compile('^showing-')})
        if not all([heading, detail, title, time]): continue
        day = short_date(text(heading).split(',', 1)[-1].strip())
        lines = [str(x).strip() for x in detail.contents if isinstance(x, str) and str(x).strip()]
        director = next((x[3:] for x in lines if x.startswith('by ')), None)
        info = ' '.join(x for x in lines if not x.startswith('by '))
        rows.append(row(v['id'], text(title), day, [clock(text(time))], v['sourceUrl'] + '?view=list#' + time['name'], director=director, year=year_in(info), format=physical(info), imageUrl=image_url(item.select_one('img.screening-image'), v['sourceUrl']), description=clean(text(item.select_one('.film-notes p')))))
    return rows

def bam(v):
    query = urlencode({'start': TODAY.strftime('%m/%d/%Y'), 'end': (TODAY + timedelta(days=29)).strftime('%m/%d/%Y')})
    url = 'https://www.bam.org/api/BAMApi/GetCalendarEventsByDayWithOnGoing?' + query
    raw = (CACHE / 'bam-api.json').read_text() if CACHE and (CACHE / 'bam-api.json').exists() else fetch(url)
    records = json.loads(raw); rows = []
    for f in records:
        if f.get('genres') != 'Film': continue
        for when in f.get('performances', []):
            dt = datetime.fromisoformat(when).astimezone(NY)
            rows.append(row(v['id'], html.unescape(f['name']), dt.date().isoformat(), [dt.strftime('%H:%M')], urljoin(v['sourceUrl'], f['moreLink']), imageUrl=urljoin(v['sourceUrl'], f['img']) if f.get('img') else None, description=clean(f.get('desc',''))))
    return rows

def walk(value):
    if isinstance(value, dict):
        yield value
        for child in value.values(): yield from walk(child)
    elif isinstance(value, list):
        for child in value: yield from walk(child)

def paris(v):
    s = soup(v['sourceUrl'], 'paris'); rows = []; tree = None
    decoder = json.JSONDecoder()
    for script in s.find_all('script'):
        raw = script.string or ''
        if not raw.startswith('self.__next_f.push([1,'): continue
        chunk = json.loads(raw[len('self.__next_f.push('):-1])[1]
        if 'a:["$","html"' in chunk:
            start = chunk.index('a:["$","html"') + 2
            tree = decoder.raw_decode(chunk[start:])[0]
    if tree is None: raise ValueError('Paris page structure changed')
    for event in walk(tree):
        if not event.get('EventDate') or not event.get('EventTime') or not event.get('TicketLink'): continue
        films = event.get('films', {}).get('data', [])
        movie = films[0].get('attributes', {}) if len(films) == 1 else {}
        rows.append(row(v['id'], movie.get('FilmName') or event['EventName'], event['EventDate'], [clock(event['EventTime'])], event['TicketLink'], director=movie.get('Director'), year=movie.get('Year'), format=physical(str(movie.get('FilmFormat', ''))), notes=event.get('HeroDetails'), imageUrl=((event.get('HeroImage') or {}).get('data') or {}).get('attributes', {}).get('url')))
    return rows

def nitehawk(v):
    """One page per day: /prospectpark/<date>/<offset>/. Three weeks out is all they post."""
    base = v['sourceUrl'].rstrip('/')
    def day(offset):
        when = (TODAY + timedelta(days=offset)).isoformat()
        try:
            s = soup(f'{base}/{when}/{offset}/', f'nitehawk-{offset}')
        except Exception:
            return []
        found = []
        for card in s.select('li.show-container.thumbnail'):
            title = text(card.select_one('.show-title'))
            link = card.select_one('a.overlay-link')
            times = sorted({clock(text(a)) for a in card.select('.showtime-button-row a.showtime')})
            if not title or not link or not times:
                continue
            still = card.select_one('.show-thumbnail')
            image = re.search(r'url\((.*?)\)', still.get('style', '')) if still else None
            found.append(row(v['id'], title, when, times, urljoin(base, link['href']),
                             description=clean(text(card.select_one('.short-description'))),
                             format=physical(title),
                             imageUrl=image[1].strip('\'"') if image else None))
        return found
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        rows = [r for days in pool.map(day, range(21)) for r in days]
    return rows

def structured_events(v):
    """Standards adapter, pending venue-specific validation for restricted sources."""
    s = soup(v['sourceUrl'], v['id']); rows = []
    for script in s.select('script[type="application/ld+json"]'):
        try: records = json.loads(script.string or '')
        except ValueError: continue
        for event in walk(records):
            if event.get('@type') != 'ScreeningEvent': continue
            when = event.get('startDate', '')
            if 'T' not in when: continue
            dt = datetime.fromisoformat(when.replace('Z', '+00:00'))
            if dt.tzinfo: dt = dt.astimezone(NY)
            work = event.get('workPresented') or {}
            link = event.get('url')
            if not link: continue
            director = work.get('director')
            if isinstance(director, dict): director = director.get('name')
            rows.append(row(v['id'], work.get('name') or event['name'], dt.date().isoformat(), [dt.strftime('%H:%M')], urljoin(v['sourceUrl'], link), director=director))
    if not rows: raise ValueError('No verified screening feed; venue adapter requires setup')
    return rows

ADAPTERS = {'metrograph': metrograph, 'film-forum': film_forum, 'ifc': ifc, 'roxy': roxy,
            'quad': quad, 'anthology': anthology, 'bam': bam, 'paris': paris,
            'nitehawk': nitehawk, 'lincoln': structured_events,
            'moma': structured_events, 'angelika': structured_events,
            'momi': structured_events, 'spectacle': structured_events}

def metrograph_series():
    source = 'https://metrograph.com/series/'
    s = soup(source, 'metrograph-series'); output = []
    for link in s.select('.movie_title a'):
        when = text(link.parent.find_next_sibling('h5'))
        if not link or not when: continue
        try: start = short_date(when.removeprefix('From '))
        except ValueError: continue
        if abs((date.fromisoformat(start) - TODAY).days) > 30: continue
        output.append({'title': text(link).upper(), 'venue': 'METROGRAPH', 'venueId': 'metrograph',
                       'dates': when.upper(), 'startDate': start,
                       'url': urljoin(source, link['href']), 'fetchedAt': STAMP})
    return output


# Film at Lincoln Center hydrates its calendar from a JSON payload that carries the
# markup as an escaped string, so unescape before parsing. Keys on href and heading
# rather than the utility classes around them.
FLC_SKIP = {'new releases', 'get tickets', 'get pre-sale access', 'membership'}
SPAN = re.compile(r'([A-Z][a-z]+ \d{1,2})\s*(?:through|to|–|—|-)\s*([A-Z][a-z]+ \d{1,2})|([A-Z][a-z]+ \d{1,2})\s+only')

def lincoln_series():
    source = 'https://www.filmlinc.org/calendar/'
    raw = fetch(source, 'flc-calendar').replace('\\"', '"').replace('\\u003c', '<').replace('\\u003e', '>')
    s = BeautifulSoup(raw, 'html.parser'); output = []
    for link in s.select('a[href^="/series/"], a[href^="/nyff"]'):
        heading = link.find(['h1', 'h2', 'h3', 'h4'])
        if not heading: continue
        title = text(heading)
        if not title or title.casefold() in FLC_SKIP: continue
        block = link.find_parent(['article', 'section', 'li', 'div']) or link.parent
        match = SPAN.search(text(block)[:900])
        if not match: continue
        first = match[1] or match[3]
        try: start = short_date(first)
        except ValueError: continue
        if abs((date.fromisoformat(start) - TODAY).days) > 60: continue
        when = f'{first} through {match[2]}' if match[2] else f'{first} only'
        output.append({'title': title.upper(), 'venue': 'FILM AT LINCOLN CENTER', 'venueId': 'lincoln',
                       'dates': when.upper(), 'startDate': start,
                       'url': urljoin(source, link['href']), 'fetchedAt': STAMP})
    return output


SERIES_SOURCES = [('metrograph', metrograph_series), ('lincoln', lincoln_series)]

def festivals(previous=None):
    """Aggregate series and festivals across venues; one bad source keeps its last good rows."""
    previous = previous or []
    output, seen = [], set()
    for venue, parser in SERIES_SOURCES:
        try:
            found = parser()
            if not found: raise ValueError('no entries parsed')
        except Exception as error:
            print(f'Series: {venue} unavailable ({str(error)[:70]}); keeping its last snapshot', flush=True)
            found = [f for f in previous if f.get('venueId') == venue]
        for entry in found:
            token = (entry['venueId'], entry['title'])
            if token in seen: continue
            seen.add(token); output.append(entry)
    if not output: raise ValueError('No verified series from any source')
    return sorted(output, key=lambda f: (f['startDate'], f['title']))


def normalize(records):
    grouped = {}
    catalog_path = ROOT / 'dist/data/film-images.json'
    catalog = json.loads(catalog_path.read_text()).get('sources', {}) if catalog_path.exists() else {}
    for r in records:
        r['title'] = title_case(r.get('title', ''))
        saved_image = catalog.get(r['ticketUrl'])
        if saved_image:
            r['imageUrl'] = saved_image['url']
            r['imageSourceUrl'] = saved_image['sourceUrl']
        if not r.get('title') or not r.get('showtimes'): continue
        date.fromisoformat(r['date'])
        if not TODAY.isoformat() <= r['date'] <= (TODAY + timedelta(days=60)).isoformat(): continue
        if not re.match(r'^https?://', r['ticketUrl']): raise ValueError('Invalid source URL')
        if any(not re.fullmatch(r'(?:[01]\d|2[0-3]):[0-5]\d', t) for t in r['showtimes']): raise ValueError('Invalid showtime')
        key = (r['venue'], r['date'], r['title'].casefold(), r.get('format') or '')
        if key in grouped: grouped[key]['showtimes'] += r['showtimes']
        else: grouped[key] = dict(r, showtimes=list(r['showtimes']))
    for key, r in grouped.items():
        r['showtimes'] = sorted(set(r['showtimes']))
        r['id'] = hashlib.sha256('|'.join(key).encode()).hexdigest()[:16]
    return sorted(grouped.values(), key=lambda r: (r['date'], r['showtimes'][0], r['title']))

def refresh():
    path = ROOT / 'dist/data/screenings.json'
    old = json.loads(path.read_text()) if path.exists() else {'screenings': [], 'venues': {}, 'festivals': []}
    venues = [v for v in json.loads((ROOT / 'dist/data/theaters.json').read_text()) if v['id'] not in {'lincoln','moma','angelika','paris','momi','spectacle'}]
    def one(v):
        try:
            raw = ADAPTERS[v['id']](v)
            if not raw: raise ValueError('No listings parsed; preserving last successful data')
            rows = normalize(raw)
            if raw and not rows: raise ValueError('Source has no current listings; preserving last successful data')
            status = 'partial' if v['id'] == 'paris' else 'ok'
            return v['id'], rows, {'status': status, 'lastSuccessfulFetch': STAMP, 'sourceUrl': v['sourceUrl'], 'note': 'Special events only; regular showtimes feed not connected.' if status == 'partial' else None}
        except Exception as e:
            previous = [r for r in old['screenings'] if r['venue'] == v['id'] and r['date'] >= TODAY.isoformat()]
            status = dict(old.get('venues', {}).get(v['id'], {}), status='stale' if previous else 'unavailable', lastAttempt=STAMP, error=str(e), sourceUrl=v['sourceUrl'])
            return v['id'], previous, status
    data = {'updatedAt': old.get('updatedAt'), 'attemptedAt': STAMP, 'screenings': [], 'venues': {}, 'festivals': old.get('festivals', [])}
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
        for name, rows, status in pool.map(one, venues):
            print(f'{name}: {status["status"]}, {len(rows)} film/day entries', flush=True)
            data['screenings'].extend(rows); data['venues'][name] = status
            if status['status'] in ['ok', 'partial']: data['updatedAt'] = STAMP
    try: data['festivals'] = festivals(old.get('festivals'))
    except Exception as e: print('Series refresh retained last snapshot:', str(e), flush=True)
    data = cache_images(data)
    data = enrich_descriptions(data)
    write_summaries(data)
    tmp = path.with_suffix('.tmp'); tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2)); tmp.replace(path)
    return data

if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('--source-dir', type=Path)
    args = parser.parse_args(); CACHE = args.source_dir
    refresh()
