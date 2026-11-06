import shutil
import tempfile
import unittest
from pathlib import Path
from scripts.check_io import ROOT, check
class CheckIO(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory(); self.root=Path(self.tmp.name); shutil.copytree(ROOT/'design',self.root/'design')
 def tearDown(self): self.tmp.cleanup()
 def test_valid(self): self.assertEqual(check(self.root),[])
 def test_missing_net_connection(self):
  p=self.root/'design/03_inputs.xml'; p.write_text(p.read_text().replace('ref="X101" pin="1"','ref="X999" pin="1"'))
  self.assertTrue(any('Start: wire' in e for e in check(self.root)))
 def test_duplicate_terminal(self):
  p=self.root/'design/io.csv'; p.write_text(p.read_text().replace('X102','X101'))
  self.assertIn('duplicate terminal',check(self.root))
 def test_missing_source_tag(self):
  p=self.root/'design/source-line.st'; p.write_text(p.read_text().replace('    Start : BOOL;',''))
  self.assertIn('I/O list differs from source interface',check(self.root))
if __name__=='__main__': unittest.main()
