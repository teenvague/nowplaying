"""Author the two-line hover captions for films that do not have one yet.

Captions are cached in dist/data/film-summaries.json and committed, so a title is
paid for once and can be edited by hand afterwards; an existing entry is never
overwritten. Without ANTHROPIC_API_KEY the step is skipped and those films simply
show the still with no caption.
"""
from __future__ import annotations
import json, os, re, urllib.error, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / 'dist/data/film-summaries.json'
ISSUES = ROOT / 'dist/data/caption-issues.json'
API = 'https://api.anthropic.com/v1/messages'
MODEL = os.environ.get('SUMMARY_MODEL') or 'claude-sonnet-5'
BATCH = 12
MAX_TOKENS = 2048
LINE = 30

BRIEF = (
    "You write one-line captions for a New York repertory cinema calendar. "
    "They sit under a film still, set in two lines of Courier.\n\n"
    "Describe THE FILM, never the screening. The notes below are scraped from "
    "theater listings and are often promotional: ignore anything about "
    "restorations, new prints, formats, anniversaries, guest appearances, "
    "series titles, ticketing or the venue. None of that belongs in a caption.\n\n"
    "Where you know the film, write from what the film is about. Where you do "
    "not, use whatever the notes say about its story. If neither gives you an "
    "actual premise, omit the title rather than guessing or padding.\n\n"
    "For each film return ONE sentence that:\n"
    "- gives the premise, not a plot summary and not an assessment\n"
    "- is at most 58 characters including spaces, and splits at a word boundary "
    f"into two lines of at most {LINE} characters each\n"
    "- is present tense and opens on an indefinite article where it reads "
    "naturally (\"A poet crosses into the realm of death in pursuit of love.\")\n"
    "- never repeats the film's title and never evaluates it\n\n"
    "Reply with a JSON object mapping each title to its sentence and nothing else. "
    "Omit any title you cannot caption within the limit."
)


def fits(caption, limit=LINE):
    """True when the caption can be split at a word boundary into two short lines."""
    words = caption.split()
    if len(words) < 2:
        return len(caption) <= limit
    return min(max(len(' '.join(words[:i])), len(' '.join(words[i:])))
               for i in range(1, len(words))) <= limit


def key(title):
    return re.sub(r'[^a-z0-9]', '', (title or '').casefold())


def acceptable(title, caption):
    """Return (caption, '') when usable, or ('', reason) so the refusal is reportable."""
    caption = re.sub(r'\s+', ' ', (caption or '')).strip().strip('"\u201c\u201d')
    if not caption:
        return '', 'no_reply'
    if len(caption) > 58:
        return '', 'too_long_%d' % len(caption)
    if len(re.findall(r'[.!?]', caption)) > 1:
        return '', 'multiple_sentences'
    if title.split(':')[0].casefold() in caption.casefold():
        return '', 'echoes_title'
    if not fits(caption):
        return '', 'will_not_split_in_two'
    return caption, ''


def call(payload):
    request = urllib.request.Request(
        API,
        data=json.dumps(payload).encode(),
        headers={'content-type': 'application/json',
                 'anthropic-version': '2023-06-01',
                 'x-api-key': os.environ['ANTHROPIC_API_KEY']})
    with urllib.request.urlopen(request, timeout=60) as response:
        body = json.load(response)
    return ''.join(part.get('text', '') for part in body.get('content', []))


def ask(films):
    listing = '\n'.join(
        f"- {f['title']}"
        + (f" ({f['year']})" if f.get('year') else '')
        + (f", directed by {f['director']}" if f.get('director') else '')
        + (f"\n  Notes: {f['description']}" if f.get('description') else '')
        for f in films)
    text = call({'model': MODEL, 'max_tokens': MAX_TOKENS,
                 'messages': [{'role': 'user', 'content': BRIEF + '\n\n' + listing}]})
    match = re.search(r'\{.*\}', text, re.S)
    return json.loads(match.group(0)) if match else {}


def write_summaries(data, limit=None):
    summaries = json.loads(PATH.read_text()) if PATH.exists() else {}
    if not os.environ.get('ANTHROPIC_API_KEY'):
        missing = len({r['title'] for r in data['screenings'] if r['title'] not in summaries})
        if missing:
            print(f'Captions: {missing} films without one; ANTHROPIC_API_KEY not configured.', flush=True)
        return summaries
    seen, wanted = set(), []
    for row in data['screenings']:
        if row['title'] in summaries or row['title'] in seen:
            continue
        seen.add(row['title'])
        wanted.append(row)
    cap = limit if limit is not None else int(os.environ.get('SUMMARY_LIMIT', '60'))
    wanted = wanted[:cap]
    written, issues = 0, []
    for start in range(0, len(wanted), BATCH):
        group = wanted[start:start + BATCH]
        try:
            replies = ask(group)
        except Exception as error:                  # an outage must not fail the build
            print('Captions: batch skipped -', str(error)[:160], flush=True)
            for film in group:
                issues.append({'title': film['title'], 'reason': 'request_failed',
                               'detail': str(error)[:160]})
            continue
        bykey = {key(k): v for k, v in replies.items()}
        for film in group:
            raw = replies.get(film['title']) or bykey.get(key(film['title'])) or ''
            caption, why = acceptable(film['title'], raw)
            if caption:
                summaries[film['title']] = caption
                written += 1
            else:
                issues.append({'title': film['title'], 'reason': why, 'candidate': str(raw)[:120]})
    if written:
        PATH.write_text(json.dumps(dict(sorted(summaries.items())), ensure_ascii=False, indent=2) + '\n')
    ISSUES.write_text(json.dumps(issues, ensure_ascii=False, indent=2) + '\n')
    print(f'Captions: {written} written, {len(issues)} unresolved; see caption-issues.json', flush=True)
    return summaries


if __name__ == '__main__':
    write_summaries(json.loads((ROOT / 'dist/data/screenings.json').read_text()))
