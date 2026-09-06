"""Captions must fit two Courier lines and never overwrite an authored one."""
import json, sys, unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import summaries as s

FILMS = {'screenings': [
    {'title': 'Orpheus', 'year': 1950, 'director': 'Jean Cocteau', 'description': 'A poet follows death.'},
    {'title': 'Orpheus', 'year': 1950, 'director': 'Jean Cocteau', 'description': 'A poet follows death.'},
    {'title': 'Playtime', 'year': 1967, 'director': 'Jacques Tati', 'description': 'A visitor in Paris.'},
]}

class Constraint(unittest.TestCase):
    def test_two_short_lines_required(self):
        self.assertTrue(s.fits('A poet crosses into the realm of death in pursuit of love.'))
        self.assertFalse(s.fits('A woman who has spent her whole life waiting departs at last today.'))

    def test_rejects_title_echo_and_overlong(self):
        self.assertEqual(s.acceptable('Playtime', 'Playtime follows a lost visitor.'), '')
        self.assertEqual(s.acceptable('Orpheus', 'A ' + 'very ' * 20 + 'long line.'), '')

    def test_rejects_multiple_sentences(self):
        self.assertEqual(s.acceptable('Orpheus', 'A poet descends. He returns.'), '')

class Writing(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(self.id() + '.json')
        self.patch = patch.object(s, 'PATH', self.tmp)
        self.patch.start()

    def tearDown(self):
        self.patch.stop()
        self.tmp.unlink(missing_ok=True)

    def test_writes_only_valid_captions_once_per_title(self):
        self.tmp.write_text(json.dumps({'Playtime': 'A bemused visitor loses his way in Paris.'}))
        seen = []
        def ask(group):
            seen.append([f['title'] for f in group])
            return {'Orpheus': 'A poet crosses into death in pursuit of love.'}
        with patch.dict('os.environ', {'ANTHROPIC_API_KEY': 'x'}), patch.object(s, 'ask', ask):
            out = s.write_summaries(FILMS)
        self.assertEqual(seen, [['Orpheus']])                      # deduped, Playtime skipped
        self.assertEqual(out['Playtime'], 'A bemused visitor loses his way in Paris.')  # not overwritten
        self.assertIn('Orpheus', json.loads(self.tmp.read_text()))

    def test_api_failure_leaves_the_file_alone(self):
        self.tmp.write_text(json.dumps({'Playtime': 'A bemused visitor loses his way in Paris.'}))
        with patch.dict('os.environ', {'ANTHROPIC_API_KEY': 'x'}), \
             patch.object(s, 'ask', side_effect=RuntimeError('503')):
            out = s.write_summaries(FILMS)
        self.assertEqual(json.loads(self.tmp.read_text()), {'Playtime': 'A bemused visitor loses his way in Paris.'})
        self.assertNotIn('Orpheus', out)

    def test_no_key_is_a_no_op(self):
        self.tmp.write_text(json.dumps({}))
        with patch.dict('os.environ', {}, clear=True):
            self.assertEqual(s.write_summaries(FILMS), {})

if __name__ == '__main__':
    unittest.main()
