"""Integration invariants: actual denoising, classification and comparable diversity."""
import argparse
import csv
import json
from pathlib import Path


def check(folder, shallow=None):
    def rows(name):
        with (folder/name).open() as f: return list(csv.DictReader(f,delimiter='\t'))
    track=rows('read_tracking.tsv')
    assert len(track)==4
    for r in track:
        assert 0<=int(r['nonchimeric'])<=int(r['merged'])<=min(int(r['denoised_forward']),int(r['denoised_reverse']))<=int(r['filtered_pairs'])<=int(r['raw_pairs'])
    assert any(r['sample']=='Blank' and int(r['nonchimeric'])>0 for r in track)
    if shallow:
        decision=next(r for r in rows('sample_decisions.tsv') if r['sample']==shallow)
        assert decision['eligible']=='FALSE' and 'TOO SHALLOW' in decision['status']
    counts=rows('counts.tsv')
    assert [r['sample'] for r in counts]==[r['sample'] for r in track]
    assert all(sum(int(v) for k,v in c.items() if k!='sample')==int(t['nonchimeric']) for c,t in zip(counts,track))
    taxonomy=rows('taxonomy.tsv')
    assert len(taxonomy)>1
    assert len({r['sequence'] for r in taxonomy})==len(taxonomy)
    assert any(r.get('Genus','NA')!='NA' for r in taxonomy)
    alpha=rows('alpha_diversity.tsv')
    assert len(alpha)>=2
    assert 'Blank' not in [r['sample'] for r in alpha]
    depths={r['sample']:int(r['depth']) for r in alpha}
    assert all(sum(int(v) for k,v in r.items() if k!='sample')==depths[r['sample']] for r in rows('rarefied_counts.tsv'))
    beta=rows('beta_bray_curtis.tsv')
    assert len(beta)==len(alpha)
    for i,r in enumerate(beta):
        assert float(r[r['sample']])==0
        for j,s in enumerate(beta):
            assert 0<=float(r[s['sample']])<=1
            assert abs(float(r[s['sample']])-float(s[r['sample']]))<1e-10
    assert len(rows('read_quality.tsv'))>100
    assert (folder/'error_models.rds').stat().st_size>100
    html=(folder/'report.html').read_text()
    assert 'data:image/png;base64,' in html and '<html lang="en">' in html
    assert 'https://' not in html # report has no remote dependencies
    print(f'Integration passed: {len(track)} samples, {len(taxonomy)} ASVs, {len(alpha)} comparable samples')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('folder',type=Path);p.add_argument('--expect-shallow')
    a=p.parse_args();check(a.folder,a.expect_shallow)
