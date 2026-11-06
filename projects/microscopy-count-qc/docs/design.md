# Design and evaluation

This project counts fluorescent nuclei as a proxy for cells. It does not identify cell boundaries, viability, or cell type.

I use BBBC039's published train/validation/test filename lists. Calibration uses only training images: median nucleus diameter, minimum object size, a low focus cutoff, and a large-object cutoff. Validation remains unused. Both methods process full resolution test images. No patch splitting or model fitting occurs.

A threshold plus distance-transform watershed provides an inspectable baseline. The second method is Cellpose 3's frozen nuclei model on CPU. A newer large model would cost more memory; a custom trained network would make this comparison harder to reproduce. The saved run records dependencies, archive and model hashes, parameters and split membership.

At each IoU threshold, maximum-cardinality one-to-one matching counts true positives, false positives and misses. IoU is the overlapping area divided by the combined area. Micro F1 pools those counts over images; macro F1 averages image scores. Count error includes signed difference, absolute error and relative error when the reference count is nonzero.

Focus is variance of the Laplacian after robust intensity normalization. Its training fifth percentile is a review cutoff, not a validated diagnosis. Objects exceeding the training area cutoff or containing separated distance peaks are flagged as possible merges. QC uses images and predicted masks only at inference. Ground truth is used separately for evaluation and error overlays. Synthetic blur is a sensitivity check, not evidence of real focus defects.

Cellpose may have seen related public microscopy data during pretraining. BBBC039 partly overlaps BBBC038. Whole-image holdout prevents this project's tuning leakage but cannot establish independence from upstream pretraining. Results describe this dataset and these settings, not general biological accuracy.
