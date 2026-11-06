# Public ontology snapshot

This project uses the Human Phenotype Ontology, release `2026-09-01`, maintained by the Human Phenotype Ontology Consortium. `hp.obo` is an unmodified copy of the [official release asset](https://github.com/obophenotype/human-phenotype-ontology/releases/download/v2026-09-01/hp.obo). Its source URL, version and SHA-256 are saved in [manifest.json](manifest.json). No substitute ontology was used.

The upstream [LICENSE.md](https://github.com/obophenotype/human-phenotype-ontology/blob/v2026-09-01/LICENSE.md) is copied as [HPO-LICENSE.md](HPO-LICENSE.md). It links to the HPO website's license page, which returned HTTP 404 during this build. The [HPO project's older license explanation](https://human-phenotype-ontology.github.io/license.html) remains readable: it asks for acknowledgement, version information and preservation of the ontology's content and relationships. This repository preserves the downloaded ontology bytes; cleaned subject lists do not modify the ontology. Consult the upstream terms for reuse.

Reference: Köhler and colleagues, [The Human Phenotype Ontology in 2021](https://doi.org/10.1093/nar/gkaa1043). HPO is a public vocabulary; no disease annotations, gene files, patient records or private systems were used here.
