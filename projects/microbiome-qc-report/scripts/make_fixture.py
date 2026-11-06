#!/usr/bin/env python3
"""Create the small, public-read fixture from already verified demo inputs."""
import csv
import gzip
import json
from pathlib import Path
from prepare import digest, subset_pair

root=Path('tests/fixture');root.mkdir(parents=True,exist_ok=True)
source=json.loads(Path('data/raw/provenance.json').read_text())
provenance=[]
rows=[]
for s in source['samples']:
    name=s['sample']
    targets=[root/f'{name}_R{i}.fastq.gz' for i in (1,2)]
    # Deliberately shallow technical subset exercises exclusion, not a new sample.
    limit=80 if name=='D8' else 2000
    count=subset_pair(Path(f'data/raw/{name}_R1.fastq.gz'),Path(f'data/raw/{name}_R2.fastq.gz'),targets,limit)
    provenance.append({**s,'pairs_retained':count,'subset_sha256':[digest(p) for p in targets]})
    rows.append([name,s['type'],s['run'],*(str(p) for p in targets)])
with (root/'samples.tsv').open('w') as f:
    w=csv.writer(f,delimiter='\t',lineterminator='\n')
    w.writerow(['sample','type','run','forward','reverse']);w.writerows(rows)
(root/'provenance.json').write_text(json.dumps({'study':source['study'],'samples':provenance},indent=2)+'\n')
# Keep sparse decoys across the full database, and a few examples of known mock
# genera. CI checks real classification, not the completeness of this reference.
wanted={'Pseudomonas','Escherichia/Shigella','Escherichia','Salmonella','Lactobacillus','Enterococcus','Listeria','Bacillus'}
seen={}; kept=[]
with gzip.open('data/reference/rdp_train_set_18.fa.gz','rt') as f:
    content=f.read().split('>')[1:]
for i,entry in enumerate(content):
    genus=entry.splitlines()[0].rstrip(';').split(';')[-1]
    if i%100==0 or (genus in wanted and seen.get(genus,0)<20):
        kept.append('>'+entry)
        seen[genus]=seen.get(genus,0)+1
with open(root/'taxonomy.fa.gz','wb') as raw:
    with gzip.GzipFile(filename='',mode='wb',fileobj=raw,mtime=0) as f:
        f.write(''.join(kept).encode())
checksums={p.name:digest(p) for p in sorted(root.glob('*')) if p.is_file() and p.name!='sha256.json'}
(root/'sha256.json').write_text(json.dumps(checksums,indent=2)+'\n')
print(f'Fixture: {sum(s["pairs_retained"] for s in provenance)} public pairs, {len(kept)} restricted reference entries')
