"""A non-time chip in Quad's showtimes list must not abort the venue."""
import sys, unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bs4 import BeautifulSoup
import refresh

PAGE = """
<div class="day-wrap"><div class="grid-item">
  <h4><a href="https://quadcinema.com/film/le-samourai/">Le Samourai</a></h4>
  <div class="showtimes-list">
    <a href="/tickets?date=2026-09-06&t=1">1:00 PM</a>
    <a href="/tickets?date=2026-09-06&t=2">7:15 PM</a>
    <a href="/format">35mm</a>
  </div>
</div></div>
"""

VENUE = {'id': 'quad', 'sourceUrl': 'https://quadcinema.com/'}

class QuadShowtimes(unittest.TestCase):
    def rows(self, page):
        with patch.object(refresh, 'soup', return_value=BeautifulSoup(page, 'html.parser')), \
             patch.object(refresh, 'enrich', side_effect=lambda rows, venue: rows):
            return refresh.quad(VENUE)

    def test_format_chip_does_not_abort_the_venue(self):
        rows = self.rows(PAGE)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['showtimes'], ['13:00', '19:15'])
        self.assertEqual(rows[0]['date'], '2026-09-06')

    def test_entry_without_any_showtime_is_skipped(self):
        rows = self.rows(PAGE.replace('>1:00 PM<', '>35mm<').replace('>7:15 PM<', '>DCP<'))
        self.assertEqual(rows, [])

    def test_date_read_from_a_showtime_not_a_chip(self):
        shuffled = PAGE.replace(
            '<a href="/tickets?date=2026-09-06&t=1">1:00 PM</a>',
            '<a href="/format?date=1999-01-01">35mm</a><a href="/tickets?date=2026-09-06&t=1">1:00 PM</a>')
        self.assertEqual(self.rows(shuffled)[0]['date'], '2026-09-06')

if __name__ == '__main__':
    unittest.main()
