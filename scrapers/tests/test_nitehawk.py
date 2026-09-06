"""Nitehawk publishes one page per day; the adapter must read a card off each."""
import sys, unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bs4 import BeautifulSoup
import refresh

PAGE = """
<ul class="thumbnails-container">
  <li class="show-container thumbnail">
    <div class="show-thumbnail" style="background-image: url(https://example.test/still.jpg)">
      <div class="show-title">Forbidden Planet, 35mm</div>
    </div>
    <div class="short-description">A starship crew investigates a silent colony.</div>
    <a class="overlay-link" href="/prospectpark/movies/forbidden-planet/?date=today"></a>
    <div class="showtimes-container">
      <ul class="showtime-button-row">
        <li><a class="showtime" href="/prospectpark/purchase/1/">2:30 pm</a></li>
        <li><a class="showtime" href="/prospectpark/purchase/2/">8:15 pm</a></li>
      </ul>
    </div>
  </li>
  <li class="show-container thumbnail">
    <div class="show-title">Sold Out Show</div>
    <a class="overlay-link" href="/prospectpark/movies/sold-out/"></a>
    <div class="showtimes-container"><ul class="showtime-button-row"></ul></div>
  </li>
</ul>
"""

VENUE = {'id': 'nitehawk', 'sourceUrl': 'https://nitehawkcinema.com/prospectpark/'}


class Nitehawk(unittest.TestCase):
    def rows(self, page=PAGE, days=1):
        def one(url, key=None):
            return BeautifulSoup(page if url.endswith('/0/') else '', 'html.parser')
        with patch.object(refresh, 'soup', side_effect=one), \
             patch.object(refresh, 'concurrent') as pool:
            pool.futures.ThreadPoolExecutor.return_value.__enter__.return_value.map = \
                lambda fn, rng: [fn(i) for i in rng]
            return refresh.nitehawk(VENUE)

    def test_reads_title_times_image_and_description(self):
        rows = self.rows()
        self.assertEqual(len(rows), 1)
        r = rows[0]
        self.assertEqual(r['title'], 'Forbidden Planet, 35mm')
        self.assertEqual(r['showtimes'], ['14:30', '20:15'])
        self.assertEqual(r['format'], '35mm')
        self.assertEqual(r['imageUrl'], 'https://example.test/still.jpg')
        self.assertTrue(r['description'].startswith('A starship crew'))
        self.assertTrue(r['ticketUrl'].startswith('https://nitehawkcinema.com/'))
        self.assertEqual(r['date'], refresh.TODAY.isoformat())

    def test_a_card_with_no_showtimes_is_skipped(self):
        self.assertEqual([r['title'] for r in self.rows()], ['Forbidden Planet, 35mm'])

    def test_a_day_that_fails_to_load_does_not_sink_the_venue(self):
        def one(url, key=None):
            if url.endswith('/0/'):
                raise ValueError('502')
            return BeautifulSoup(PAGE, 'html.parser')
        with patch.object(refresh, 'soup', side_effect=one), \
             patch.object(refresh, 'concurrent') as pool:
            pool.futures.ThreadPoolExecutor.return_value.__enter__.return_value.map = \
                lambda fn, rng: [fn(i) for i in rng]
            rows = refresh.nitehawk(VENUE)
        dates = {r['date'] for r in rows}
        self.assertNotIn(refresh.TODAY.isoformat(), dates)   # the broken day is simply absent
        self.assertEqual(len(rows), 20)                      # the other twenty still arrive


if __name__ == '__main__':
    unittest.main()
