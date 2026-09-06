import sys, unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import image_fallback as f
class Matching(unittest.TestCase):
    def test_remake_rejected(self):
        with patch.object(f,'api',return_value={'results':[{'id':1,'title':'Suspiria','release_date':'2018-01-01'}]}):
            self.assertEqual(f.candidates({'title':'Suspiria','year':1977}),[])
    def test_ambiguous_rejected(self):
        with patch.object(f,'api',return_value={'results':[{'id':i,'title':'Film','release_date':'2000-01-01'} for i in [1,2]]}):
            self.assertEqual(f.candidates({'title':'Film','year':2000}),[])
    def test_verified_backdrop_only(self):
        def api(path,**kwargs):
            if path=='search/movie':return {'results':[{'id':1,'title':'Persona','release_date':'1966-01-01'}]}
            if path.endswith('credits'):return {'crew':[{'job':'Director','name':'Ingmar Bergman'}]}
            return {'backdrops':[{'width':1280,'height':720,'iso_639_1':None,'file_path':'/good.jpg'}, {'width':100,'height':50,'file_path':'/bad.jpg'}]}
        with patch.object(f,'api',side_effect=api):
            result=f.candidates({'title':'Persona','year':1966,'director':'Ingmar Bergman'})
            self.assertEqual(len(result),1)
            self.assertTrue(result[0]['sourceUrl'].endswith('/good.jpg'))
    def test_no_identity_rejected(self):
        with patch.object(f,'api',return_value={'results':[{'id':1,'title':'Film'}]}):
            self.assertEqual(f.candidates({'title':'Film'}),[])
if __name__=='__main__':unittest.main()
