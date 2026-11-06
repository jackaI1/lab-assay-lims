#!/usr/bin/env python3
"""Render saved outputs as GitHub-readable Markdown and a portable, offline HTML."""
import argparse
import base64
import csv
import html
import json
from pathlib import Path


def rows(folder, name):
    p = folder / name
    if not p.exists():
        return []
    with p.open() as f:
        return list(csv.DictReader(f, delimiter='\t'))


def table(data, columns=None):
    if not data:
        return '_Not available for this run._'
    columns = columns or list(data[0])
    clean = lambda v: str(v).replace('|', '\\|').replace('\n', ' ')
    return '\n'.join(['| ' + ' | '.join(columns) + ' |', '| ' + ' | '.join(['---']*len(columns)) + ' |'] +
                     ['| ' + ' | '.join(clean(r[c]) for c in columns) + ' |' for r in data])


def build(folder, provenance=None, label='Public SRA demonstration'):
    folder = Path(folder)
    tracking = rows(folder, 'read_tracking.tsv')
    decisions = rows(folder, 'sample_decisions.tsv')
    taxonomy = rows(folder, 'taxonomy.tsv')
    screen = rows(folder, 'contamination.tsv')
    params = {r['parameter']: r['value'] for r in rows(folder, 'parameters.tsv')}
    flagged = [r for r in screen if r['flag'] == 'TRUE']
    summary = {'samples': len(tracking), 'raw_pairs': sum(int(r['raw_pairs']) for r in tracking),
               'nonchimeric_pairs': sum(int(r['nonchimeric']) for r in tracking), 'asvs': len(taxonomy),
               'eligible_samples': sum(r['eligible']=='TRUE' for r in decisions),
               'too_shallow_samples': sum(r['type']=='sample' and d['eligible']=='FALSE' for r,d in zip(tracking, decisions)),
               'flagged_asvs': len(flagged), 'depth': int(params['depth'])}
    (folder/'summary.json').write_text(json.dumps(summary, indent=2)+'\n')
    blocks = [f'# {label}',
      'This report follows public bacterial marker-gene reads from quality checks through sequence inference, organism names and diversity. '
      'The samples are a mock-community dilution series, not independent environmental communities. Differences are descriptive; no population or health conclusions follow.',
      '## Run summary', table([summary]),
      'ASVs are distinct DNA sequence variants inferred after modelling sequencing errors. Counts are read pairs, not numbers of cells. '
      'The depth is a user-selected comparison threshold, not a universal quality standard.',
      '## Read survival', table(tracking),
      'Raw reads were already separated by sample in the archive. The pipeline trims the first bases and low-quality tails, filters expected errors, '
      'learns separate forward/reverse error models with DADA2, infers variants, merges overlapping pairs and removes consensus chimeras (artificial mixed sequences).',
      '## Which samples can be compared?', table(decisions),
      'Controls are always excluded from diversity. Samples below the requested depth are explicitly excluded. '
      'The last-column warning checks the expected gain in variants over the final tenth of sequencing. A small gain does not guarantee complete coverage.',
      '## Rarefaction', 'Rarefaction asks how many variants I would expect to see at a smaller read count. The dashed line marks the requested comparison depth.',
      '![Rarefaction curves](rarefaction.png)',
      '## Diversity within each eligible sample', table(rows(folder,'alpha_diversity.tsv')),
      'Each eligible sample is randomly subsampled without replacement to the same depth with a fixed seed. Observed ASVs counts variants; '
      'Shannon diversity reflects richness and evenness; Simpson diversity is one minus the probability of drawing the same variant twice (using relative abundances). '
      'One subsample is a reproducible illustration and has sampling uncertainty.',
      '## Diversity between eligible samples', table(rows(folder,'beta_bray_curtis.tsv')),
      'Bray-Curtis distance runs from identical composition (zero) to no shared variants (one). '
      'The plot is a principal-coordinate view of those distances with a Cailliez correction if needed. There are no replicate groups and no significance tests.']
    if (folder/'beta_pcoa.png').exists():
        blocks.append('![Between-sample distances](beta_pcoa.png)')
    blocks += ['## Negative-control check', params['control_screen'],
       'The extraction blank is a real archived negative control. The screen flags a variant when its mean relative abundance in nonempty blanks is at least '
       'one percent and at least five times its mean in nonempty biological samples. This is a review heuristic, not a validated contaminant classifier. '
       'With one blank, prevalence evidence is weak. Carryover, extraction contaminants and true shared organisms can look alike. '
       'Nothing is automatically deleted; diversity uses all non-chimeric variants. Empty or missing controls are reported as unavailable.',
       table(flagged),
       'All variants, including unflagged ones, have control/sample prevalence and abundance recorded in `contamination.tsv`.',
       '## Taxonomy',
       'Organism names are assigned by the DADA2 naive Bayesian classifier using the named reference and a minimum bootstrap support threshold. '
       'Uncertain ranks remain NA. These are genus-level annotations, not proof of species identity. Bootstrap support for every rank is saved separately.',
       table(taxonomy, [k for k in taxonomy[0] if k != 'sequence']) if taxonomy else '_No taxonomy._',
       '## Read quality and fitted errors',
       'These quality-profile images show the first biological sample. `read_quality.tsv` records mean quality and the fraction of bases with Phred score '
       'at least 30 for every cycle and mate of every sample. Phred scores describe the chance of a sequencing error. '
       'The error plots compare observed error rates with the learned models; inspect them before trusting results on a new dataset.',
       '![Forward read quality](quality_forward.png)', '![Reverse read quality](quality_reverse.png)',
       '![Forward error model](errors_forward.png)', '![Reverse error model](errors_reverse.png)',
       '## Parameters and provenance', table(rows(folder,'parameters.tsv')),
       'The environment locks, source manifest, sample sheet and commands are in the repository. `sessionInfo.txt` records the executed R package versions. '
       'The saved count table, ASV FASTA, taxonomy, bootstrap support, read survival, rarefaction, control screen, rarefied counts and distance matrix allow the report to be checked.']
    if provenance:
        p = json.loads(Path(provenance).read_text())
        blocks += [f"Study: {p['study']}. This run retains the first matching read pairs in archive order; it is a technical subset, not the complete study. "
                   'Positional subsetting can be biased. The original archive files were verified by their published MD5 checksums before subsetting.',
                   table([{'sample':r['sample'],'run':r['run'],'pairs':r['pairs_retained'],
                           'forward_sha256':r['subset_sha256'][0],'reverse_sha256':r['subset_sha256'][1]} for r in p['samples']])]
        (folder/'provenance.json').write_text(json.dumps(p,indent=2)+'\n')
    md = '\n\n'.join(blocks)+'\n'
    (folder/'report.md').write_text(md)
    # Minimal renderer for generated blocks only, escaping all external text.
    rendered=[]
    for block in blocks:
        if block.startswith('!['):
            alt, filename = block[2:].split('](')
            filename=filename.rstrip(')')
            if not (folder/filename).exists():
                rendered.append('<p>Plot unavailable for this run.</p>')
                continue
            encoded=base64.b64encode((folder/filename).read_bytes()).decode()
            rendered.append(f'<img alt="{html.escape(alt)}" src="data:image/png;base64,{encoded}">')
        elif block.startswith('| '):
            lines=block.splitlines()
            cells=lambda line: [html.escape(c.strip()) for c in line.strip('|').split('|')]
            head='<tr>'+''.join(f'<th>{c}</th>' for c in cells(lines[0]))+'</tr>'
            body=''.join('<tr>'+''.join(f'<td>{c}</td>' for c in cells(line))+'</tr>' for line in lines[2:])
            rendered.append(f'<div class="scroll"><table><thead>{head}</thead><tbody>{body}</tbody></table></div>')
        elif block.startswith('#'):
            level=len(block)-len(block.lstrip('#'))
            rendered.append(f'<h{level}>{html.escape(block[level:].strip())}</h{level}>')
        else:
            rendered.append('<p>'+html.escape(block)+'</p>')
    (folder/'report.html').write_text('<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
        '<title>Microbiome QC report</title><style>body{max-width:1100px;margin:3rem auto;padding:0 1rem;font:17px/1.6 system-ui;color:#19313a;background:#fafbf9}'
        'h1,h2{line-height:1.2}h2{margin-top:2.5rem}table{border-collapse:collapse;font-size:14px}td,th{border:1px solid #b9c9ca;padding:.4rem;text-align:left}'
        'th{background:#dfedeb}.scroll{overflow:auto}img{max-width:100%;height:auto}</style><main>'+'\n'.join(rendered)+'</main></html>')
    print(json.dumps(summary))
    return summary


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('folder')
    parser.add_argument('--provenance')
    parser.add_argument('--label',default='Public SRA demonstration')
    a=parser.parse_args()
    build(a.folder,a.provenance,a.label)
