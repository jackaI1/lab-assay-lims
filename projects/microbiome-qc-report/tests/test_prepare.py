import gzip
import hashlib
from pathlib import Path
import tempfile
import unittest
from scripts.prepare import digest, download, subset_pair, records


class ReadPreparationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)

    def fastq(self, name, text):
        p=self.root/name
        with gzip.open(p,'wt') as f: f.write(text)
        return p

    def test_subset_keeps_pairs_and_is_deterministic(self):
        f=self.fastq('f.gz','@one/1\nACGT\n+\nIIII\n@two/1\nAAAA\n+\nIIII\n')
        r=self.fastq('r.gz','@one/2\nTGCA\n+\nIIII\n@two/2\nTTTT\n+\nIIII\n')
        out=[self.root/'a.gz',self.root/'b.gz']
        self.assertEqual(subset_pair(f,r,out,1),1)
        first=[digest(p) for p in out]
        subset_pair(f,r,out,1)
        self.assertEqual(first,[digest(p) for p in out])
        self.assertEqual(len(list(records(out[0]))),1)

    def test_mismatched_mate_rejected(self):
        f=self.fastq('f.gz','@a\nAC\n+\nII\n')
        r=self.fastq('r.gz','@b\nAC\n+\nII\n')
        with self.assertRaisesRegex(ValueError,'mates'):
            subset_pair(f,r,[self.root/'a.gz',self.root/'b.gz'],2)

    def test_unequal_pair_length_rejected(self):
        f=self.fastq('f.gz','@a\nAC\n+\nII\n')
        r=self.fastq('r.gz','@a\nAC\n+\nII\n@b\nAC\n+\nII\n')
        with self.assertRaisesRegex(ValueError,'mates'):
            subset_pair(f,r,[self.root/'a.gz',self.root/'b.gz'],5)

    def test_malformed_quality_rejected(self):
        f=self.fastq('bad.gz','@a\nAC\n+\nI\n')
        with self.assertRaisesRegex(ValueError,'Malformed'):
            list(records(f))

    def test_download_validates_checksum_and_cleans_partial(self):
        source=self.root/'source'; source.write_bytes(b'public fixture')
        target=self.root/'target'
        with self.assertRaisesRegex(ValueError,'Checksum'):
            download(source.as_uri(),target,'0'*32)
        self.assertFalse(target.exists())
        self.assertFalse((self.root/'target.part').exists())
        download(source.as_uri(),target,hashlib.md5(source.read_bytes()).hexdigest())
        self.assertEqual(source.read_bytes(),target.read_bytes())
