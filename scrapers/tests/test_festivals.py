"""Series come from several venues; one failing source must not empty the strip."""
import sys, unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import refresh

# the shape Film at Lincoln Center ships: markup escaped inside a JSON payload
FLC = r'''
<div>{"content":"<article><a href=\"/nyff2026/\"><h3>64th New York Film Festival</h3></a>
<p>Produced by Film at Lincoln Center, the 64th edition runs September 25 through October 12, 2026.</p></article>
<article><a href=\"/series/new-releases/\"><h3>New Releases</h3></a><p>September 13 only</p></article>
<article><a href=\"/series/the-met-live-in-hd/\"><h3>The Met: Live in HD</h3></a><p>October 3 through October 12</p></article>"}</div>
'''


class Aggregate(unittest.TestCase):
    def test_lincoln_reads_titles_and_spans_and_skips_house_labels(self):
        with patch.object(refresh, 'fetch', return_value=FLC):
            rows = refresh.lincoln_series()
        titles = [r['title'] for r in rows]
        self.assertIn('64TH NEW YORK FILM FESTIVAL', titles)
        self.assertIn('THE MET: LIVE IN HD', titles)
        self.assertNotIn('NEW RELEASES', titles)          # a house label, not a series
        nyff = next(r for r in rows if r['title'].startswith('64TH'))
        self.assertEqual(nyff['venueId'], 'lincoln')
        self.assertEqual(nyff['dates'], 'SEPTEMBER 25 THROUGH OCTOBER 12')
        self.assertTrue(nyff['url'].startswith('https://www.filmlinc.org/'))

    def test_a_failed_source_keeps_its_previous_entries(self):
        previous = [{'title': 'OLD METROGRAPH SERIES', 'venue': 'METROGRAPH', 'venueId': 'metrograph',
                     'dates': 'FROM AUGUST 1', 'startDate': '2026-08-01', 'url': 'x', 'fetchedAt': 'y'},
                    {'title': 'OLD FLC', 'venue': 'FILM AT LINCOLN CENTER', 'venueId': 'lincoln',
                     'dates': 'FROM AUGUST 2', 'startDate': '2026-08-02', 'url': 'x', 'fetchedAt': 'y'}]
        def boom(): raise ValueError('503')
        good = [{'title': 'NEW FLC', 'venue': 'FILM AT LINCOLN CENTER', 'venueId': 'lincoln',
                 'dates': 'FROM SEPTEMBER 1', 'startDate': '2026-09-01', 'url': 'x', 'fetchedAt': 'y'}]
        with patch.object(refresh, 'SERIES_SOURCES', [('metrograph', boom), ('lincoln', lambda: good)]):
            out = refresh.festivals(previous)
        titles = [f['title'] for f in out]
        self.assertEqual(titles, ['OLD METROGRAPH SERIES', 'NEW FLC'])   # stale kept, fresh added, sorted

    def test_every_source_failing_with_no_history_is_an_error(self):
        def boom(): raise ValueError('503')
        with patch.object(refresh, 'SERIES_SOURCES', [('metrograph', boom)]):
            with self.assertRaises(ValueError):
                refresh.festivals([])


if __name__ == '__main__':
    unittest.main()
