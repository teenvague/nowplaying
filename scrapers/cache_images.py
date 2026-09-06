"""Preserve good cached stills; automatically source missing or poor images."""
from pathlib import Path
from urllib.parse import quote
import concurrent.futures, hashlib, io, json, re, urllib.request
from PIL import Image
from image_fallback import candidates
import os
ROOT = Path(__file__).resolve().parents[1]

def cache_images(data):
    path = ROOT / 'dist/data/film-images.json'
    catalog = json.loads(path.read_text()) if path.exists() else {'sources': {}}
    rows = data['screenings']
    catalog.setdefault('sources', {})
    def usable(url):
        if not url or not url.startswith('stills/'): return False
        try:
            dest = (ROOT/'dist'/url).resolve()
            if not dest.is_relative_to((ROOT/'dist/stills').resolve()): return False
            with Image.open(dest) as im:
                im.load()
                return im.width >= 500 and im.height >= 250
        except Exception: return False
    def one(url):
        try:
            source = url
            if 'bam.org/' in url: source = url.split('?')[0]
            if 'ifccenter.com/' in url: source = re.sub(r'-80x40(?=\.)', '', url)
            name = 'stills/' + hashlib.sha256(source.encode()).hexdigest()[:16] + '.jpg'
            dest = ROOT / 'dist' / name
            if not usable(name):
                req = urllib.request.Request(quote(source, safe=':/?&=%+#'), headers={'User-Agent':'Mozilla/5.0'})
                with urllib.request.urlopen(req, timeout=25) as response: raw = response.read()
                with Image.open(io.BytesIO(raw)) as image:
                    image.load()
                    if image.width < 500 or image.height < 250: return url, None
                    image = image.convert('RGB'); image.thumbnail((1200,1200))
                    dest.parent.mkdir(exist_ok=True)
                    image.save(dest, 'JPEG', quality=90, optimize=True)
            return url, {'url':name, 'sourceUrl':source}
        except Exception:
            return url, None
    for row in rows:
        saved = catalog['sources'].get(row['ticketUrl'], {})
        if usable(saved.get('url')):
            row['imageUrl'] = saved['url']
            row['imageSourceUrl'] = saved.get('sourceUrl', '')
    urls = set(r['imageUrl'] for r in rows if r.get('imageUrl','').startswith('http'))
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
        found = dict(pool.map(one, urls))
    for row in rows:
        image = found.get(row.get('imageUrl'))
        if image:
            row['imageUrl'] = image['url']; row['imageSourceUrl'] = image['sourceUrl']
            catalog['sources'][row['ticketUrl']] = dict(image, sourcePage=row['ticketUrl'])
    path.write_text(json.dumps(catalog, ensure_ascii=False, indent=2))
    # Resolve each identity once per refresh; never replace a good existing still.
    resolved = {}
    issues = []
    for row in rows:
        if usable(row.get('imageUrl')): continue
        saved = catalog['sources'].get(row['ticketUrl'], {})
        if usable(saved.get('url')):
            row['imageUrl'] = saved['url']
            row['imageSourceUrl'] = saved.get('sourceUrl', '')
            continue
        key = (row['title'], str(row.get('year','')), row.get('director',''))
        if key not in resolved:
            resolved[key] = None
            try:
                for candidate in candidates(row):
                    _, image = one(candidate['sourceUrl'])
                    if image:
                        resolved[key] = dict(image, **{k:v for k,v in candidate.items() if k!='sourceUrl'})
                        break
            except Exception:
                pass  # API outages cannot discard existing listings or images.
        image = resolved[key]
        if image:
            row['imageUrl'] = image['url']
            row['imageSourceUrl'] = image['sourceUrl']
            catalog['sources'][row['ticketUrl']] = image
        else:
            reason = 'no_verified_still' if os.environ.get('TMDB_READ_TOKEN') else 'tmdb_token_not_configured'
            issue = {'title':row['title'], 'ticketUrl':row['ticketUrl'], 'reason':reason}
            if issue not in issues: issues.append(issue)
    path.write_text(json.dumps(catalog, ensure_ascii=False, indent=2))
    (ROOT/'dist/data/image-issues.json').write_text(json.dumps(issues, ensure_ascii=False, indent=2))
    if issues: print(f'Image sourcing: {len(issues)} unresolved screening pages; see image-issues.json')
    return data

if __name__ == '__main__':
    path = ROOT/'dist/data/screenings.json'
    data = cache_images(json.loads(path.read_text()))
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2))
