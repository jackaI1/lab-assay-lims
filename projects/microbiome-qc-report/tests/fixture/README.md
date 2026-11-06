# Public-read test fixture

These are unmodified sequence and quality records from SRA study [SRP155048](https://www.ncbi.nlm.nih.gov/sra/?term=SRP155048), downloaded through the public ENA mirror. The fixture is a small technical subset, not a separate experiment.

`python scripts/make_fixture.py` creates the files after `make prepare` has verified the full downloaded mates against the original MD5 hashes. It retains the first 2000 matching pairs from D0 (SRR7588938), D4 (SRR7588942) and the extraction blank (SRR10898399), plus the first 80 pairs from D8 (SRR7588945). The deliberately shallow D8 subset tests exclusion at a requested depth of 800; it says nothing about the original run's depth. `provenance.json` identifies every source and subset hash. `sha256.json` locks the committed fixture bytes.

CI uses real FASTQ quality scores to learn error models and runs DADA2 inference, paired-read merging, chimera removal and taxonomic classification. It does not load a precomputed count table or replace denoising with a mock.

The taxonomy fixture is an explicitly reduced derivative of Callahan's [RDP trainset 18 / release 11.5, formatted for DADA2](https://doi.org/10.5281/zenodo.4310151) (2020), licensed under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). The generation command keeps every hundredth reference entry and up to 20 entries per expected mock-community genus. This is a restricted classifier-execution test. The saved public demonstration uses the full reference, not this subset. The source reference MD5 is frozen in `data/sources.json`.

The study and its data description are Caruso, Song, Asquith and Karstens (2019), [Performance of Microbiome Sequence Inference Methods in Environments with Varying Biomass](https://doi.org/10.1128/mSystems.00163-18), open access under CC BY 4.0. The study's public reads retain their source attribution; this repository's MIT license applies to the code.

Run `make fixture-test` inside the pinned environment. No read or taxonomy downloads are needed for that test. The generated report is saved as `results/fixture/report.html`, with a [checked-in example](../../reports/fixture/report.md).
