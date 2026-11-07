# What the analysis does

## Inputs and preparation

`data/sources.json` freezes the public archive URLs and their published MD5 hashes. The selected runs are D0 (SRR7588938), D4 (SRR7588942), D8 (SRR7588945) and the extraction blank (SRR10898399), all under SRP155048. The blank's archive run title explicitly labels it as a negative control. The paper describes a serial dilution of a defined bacterial community. It is a process benchmark, not an ecological survey.

`python scripts/prepare.py --pairs 12000` downloads each complete compressed mate, verifies its archive MD5, validates matching FASTQ IDs and retains the first matching pairs. It saves the subset SHA-256 hashes and the number actually retained. This cap keeps a laptop run manageable. Archive order is deterministic but is not random sampling; the saved demonstration cannot reproduce the paper's full-study estimates. There is no fallback to invented data.

The deposited reads begin within the V4 marker sequence. I inspected their starts before choosing preprocessing. I discard the first 15 positions as in the paper, retain forward reads through position 230 and cut reverse reads at position 140, where the measured reverse quality profile begins to fall sharply. The reverse cut is more conservative than the paper's preprocessing. These leave enough overlap in this dataset. When using another primer pair or read length, inspect quality and primer presence and change these parameters. The pipeline does not claim to remove arbitrary primers.

## Quality, variants and names

The script records mean quality and the fraction of bases at Phred 30 or higher at each cycle for both mates of every sample. It also plots the first sample's quality profiles. DADA2 filters reads with ambiguous bases, PhiX matches, early quality truncation or more than 2.5 expected errors in either mate. Read pairs must survive together. Separate forward and reverse error models are learned from all surviving input subsets; no canned error model is substituted for a small fixture. The fitted models, diagnostic plots and read survival at each stage are saved.

DADA2 infers amplicon sequence variants (ASVs), merges mates with at least 12 bases of exact overlap and removes chimeras by consensus. A chimera is a mixed sequence produced during amplification. Samples with no surviving reads remain in the count table and decision table. A run with no surviving ASVs fails with an explanation instead of producing an empty success report.

Taxonomy uses the full RDP trainset 18, release 11.5, with DADA2's naive Bayesian classifier, reverse-complement checking, a fixed seed and a minimum bootstrap support of 80. Bootstrap values are written for every rank; unsupported assignments remain NA. This does not establish species identity. ASVs are sorted by sequence to make their IDs stable within the run.

## Controls

For each ASV, `contamination.tsv` records mean relative abundance and prevalence in nonempty controls and samples. The warning requires mean blank abundance of at least 0.01 and at least five times mean sample abundance. This is a transparent, deliberately simple review rule, not a replacement for a replicated-control statistical method. A single blank is weak evidence: true organisms, carryover and reagent contaminants may overlap. Variants are flagged, never automatically removed, and reported diversity retains them. Check the screen before interpreting apparent differences.

Controls with no non-chimeric reads are not treated as evidence of clean samples. Missing controls and empty controls have distinct unavailable statuses. Negative controls never enter diversity comparisons. The code accepts additional controls in the sample sheet, but this dataset subset has only one.

## Depth and diversity

The minimum comparison depth is explicit, not chosen after looking for a desired result. `make analyze DEPTH=5000` excludes every biological sample below that retained non-chimeric read count. It does not replace a shallow sample with zeros or silently lower the depth. Negative controls are always excluded. If no samples qualify, alpha and beta outputs are unavailable; with one eligible sample only alpha diversity is produced.

Rarefaction curves use exact hypergeometric expected richness without replacement via `vegan::rarefy`. Each curve stops at its sample's actual depth. A tail-gain warning identifies curves whose final tenth of sequencing adds more than five percent of the observed richness. This heuristic is not a statistical test or proof of adequate coverage.

Eligible samples are subsampled once to equal depth using `vegan::rrarefy` and seed 104729. The actual subsampled count table is saved. Observed richness, Shannon entropy and Simpson diversity describe each sample; Bray-Curtis distances compare their compositions. PCoA uses a Cailliez additive correction where needed for plotting; the exported distance matrix remains the original Bray-Curtis matrix. No taxon filtering is applied after rarefaction. Low counts, sampling variability and reference coverage all limit interpretation. The dilution samples are not independent biological replicates, so no group significance test is appropriate.

## Reproducibility and tests

`environment.yml` pins the main tools. The explicit platform locks freeze all resolved conda packages with archive hashes. `sessionInfo.txt` records the executed versions. The workflow runs single-threaded to limit laptop use and avoid parallel random-number differences. Exact floating-point results can vary slightly across CPU architectures; the actual raw-read hashes and saved output provenance make the run auditable.

The CI fixture is derived from the same verified public raw files with `python scripts/make_fixture.py`. It keeps the first 2000 pairs from D0, D4 and Blank, and the first 80 from D8 to exercise shallow-sample exclusion. That reduction is an engineering stress case, not evidence that the archived D8 sample is intrinsically shallow. The fixture includes real qualities and sequencing errors. CI runs actual error learning, inference, merging, chimera removal and taxonomy, then checks stage counts, ASV uniqueness, nonempty taxonomy, read depth, control exclusion, symmetric distances and the standalone report.

For offline CI only, the reference retains every hundredth entry plus up to 20 entries per expected mock-community genus from RDP trainset 18. This restricted reference tests classifier execution, not annotation completeness. The saved demonstration uses the full reference. `tests/fixture/sha256.json` detects accidental fixture edits. Unit tests also exercise mismatched mates, malformed FASTQ, checksum failures, absent and empty controls, analytical rarefaction values, known Shannon values, extreme Bray-Curtis distances and deterministic subsampling.

## Sources

- Caruso, Song, Asquith and Karstens (2019), [Performance of Microbiome Sequence Inference Methods in Environments with Varying Biomass](https://doi.org/10.1128/mSystems.00163-18), open access under CC BY 4.0.
- [SRA study SRP155048](https://www.ncbi.nlm.nih.gov/sra/?term=SRP155048) and [ENA's public file report](https://www.ebi.ac.uk/ena/portal/api/filereport?accession=SRP155048&result=read_run&fields=run_accession,sample_alias,fastq_ftp,fastq_md5&format=tsv). The deposited reads are public research data; the fixture retains their original sequences and quality values.
- [Negative-control run SRR10898399](https://www.ebi.ac.uk/ena/browser/view/SRR10898399).
- [DADA2 tutorial](https://benjjneb.github.io/dada2/tutorial.html), [DADA2 paper](https://doi.org/10.1038/nmeth.3869) and [reference database format](https://benjjneb.github.io/dada2/training.html).
- [RDP trainset 18 / release 11.5, formatted for DADA2](https://doi.org/10.5281/zenodo.4310151), Callahan (2020), CC BY 4.0; the offline fixture is an explicitly reduced copy. [RDP classifier paper](https://doi.org/10.1128/AEM.00062-07).
- [vegan reference documentation](https://vegandevs.github.io/vegan/reference/index.html).
