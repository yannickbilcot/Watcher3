import unittest
	
	import sys
	import os
	from string import Template
	
	rootdir = os.path.realpath(os.path.join(os.path.dirname(os.path.realpath(__file__)), '..'))
	sys.path.insert(0, os.path.join(rootdir, 'lib'))
	sys.path.insert(0, rootdir)
	
	os.chdir(rootdir)
	
	import PTN
	
	class TestPTNParse(unittest.TestCase):
	
	    def test_language_values(self):
	        s = Template("[ website.com ] the.movie.title.2017.$lang.1080p.WEB-DL.x264-EXTREME.mkv")
	        language_values = [
	            "rus.eng",
	            "ita.eng",
	            "EN",
	            "ENG",
	            "ENGLISH",
	            "FR",
	            "fr",
	            "FRENCH",
	            "TRUEFrench",
	            "Multi",
	            "VOSTFR",
	            "VOST",
	            "VOSTA",
	            "SUBFRENCH"
	        ]
	        for v in language_values:
	            filename = s.substitute(lang=v)
	            meta_data = PTN.parse(filename)
	            self.assertEqual(meta_data['language    '], v)
	
	    def test_language_empty(self):
	        filename = "[ website.com ] the.movie.title.2017.1080p.WEB-DL.x264-EXTREME.mkv"
	        meta_data = PTN.parse(filename)
	        print(meta_data)
	        self.assertTrue('language' not in meta_data)
	
	    def test_language_trap(self):
	        filename = "[ website.com ] the.english.patient.2017.1080p.WEB-DL.x264-EXTREME.mkv"
	        meta_data = PTN.parse(filename)
	        print(meta_data)
	        self.assertTrue('language' not in meta_data)
	
	
	if __name__ == '__main__':
	    unittest.main() 
