# Evaluation choices

I want this project to answer a narrow, reproducible question: can a gate detect controlled damage without discarding too many reference photos, and what does its selection do to a simple classifier's accuracy? I do not treat synthetic damage as expert clinical judgement.

## Sources and separation

The source manifest freezes 180 unique nevus and 180 unique melanoma lesion records from ISIC collection 212. I queried the official API for `diagnosis_3:"Nevus"` and `diagnosis_3:"Melanoma, NOS"`, paged its default order and kept the first eligible unique lesions. This is convenience sampling, not random population sampling. The API's collection membership and diagnoses can change, so the manifest, original file hashes and per-image provenance define this experiment rather than the collection's current image count.

I split the sorted source list with seed 42, stratifying by diagnosis: 60% training, 20% validation and 20% test. I choose one image per lesion, reject repeated lesion IDs and reject repeated exact image hashes. There is no patient identifier in the retained manifest, so patient-level separation is unproven. All generated versions of a source stay in its split.

## Image scale and damage labels

I apply EXIF orientation, convert to RGB and resize the full field to 128 by 128 pixels. I intentionally normalize aspect ratio rather than crop away part of the source. This distorts geometry and limits transfer to other scales, but it makes the focus measurement and synthetic strengths comparable. The gate applies the same processing to a new photo. Input dimensions below 64 pixels are rejected rather than enlarged into apparent detail.

The original and strength-1 variants receive the operational acceptable label. Strengths 2 and 3 receive the operational damaged label. The values in `images.STRENGTHS` are fixed before evaluation. There are five damage families: Gaussian blur, darkening, brightening, horizontal framing loss with black padding, and seeded dark lines representing hair. The complete grid contains the clean original and three strengths of each family. I do not claim the mild level preserves diagnosis information. In particular, a small spatial classifier can fail even on mild framing loss.

## Gate comparison

Both gates consume eight single-image measurements. Focus is the variance of a discrete Laplacian, a measure of local intensity change. Exposure checks count pixels in the bottom and top histogram tails. Coverage is the fraction of nonblack pixels, a field-of-view proxy that cannot measure the lesion itself. A morphological closing operation fills thin dark features; its mean difference from the image provides a hair proxy. Mean brightness, contrast and entropy complete the feature set. The learned gate uses a logarithm of the focus feature to reduce its numeric range.

The simple gate uses validation acceptable examples to choose 2nd-percentile lower bounds for focus and coverage and 98th-percentile upper bounds for both clipping fractions and the hair response. It rejects when any bound is exceeded. The learned gate fits standardized logistic regression to augmented training examples, with balanced class weights and regularization C=1. Its score threshold is the 90th percentile of acceptable validation scores. This is a chosen retention target, not a guarantee about future data. Neither threshold is selected on test performance. A fixed low-contrast guard makes constant images abstain for both methods.

I export means, scales, coefficients and intercepts as JSON, so the report does not require loading executable serialized Python objects. The check command reports raw measurements and either rule failure reasons or the learned damage score and cutoff decision. Its abstaining path returns before computing lesion features or calling the downstream model.

## Downstream baseline

The public baseline implemented in this repository uses normalized RGB histograms with 16 bins per channel and a 4 by 4 RGB spatial grid. It is a standardized logistic regression trained only on clean training sources with the same fixed regularization. This is not a downloaded pretrained lesion model. It predicts the archive's nevus/melanoma labels, not a clinical diagnosis. Its simplicity makes sensitivity to shifts, colour loss and obstruction visible rather than providing a competitive diagnostic benchmark.

The experiment intentionally evaluates the baseline on every held-out version, including rejected ones. This counterfactual scoring is necessary to compare accepted and rejected accuracy and is separate from the abstaining inference command. Counts, correct counts and denominators are reported, along with per-diagnosis results to reveal changing class composition. I also include the ungated and clean-only baseline.

## Evidence and uncertainty

The benchmark saves per-version decisions and measurements, model parameters, source partitions and unrounded metrics. The Markdown report can be read on GitHub; the HTML version embeds all example images and works offline. Examples use the first held-out image alphabetically per class, without inspecting its score. Captions retain the source ID, attribution, licence and the changes made.

For an uncertainty interval on accepted-minus-rejected accuracy, I resample source lesions 500 times with seed 42 and keep every generated version together. Empty accepted or rejected subsets have null accuracy, not zero. These intervals describe variation within this convenience sample and do not correct for the archive's selection or unknown patient relationships. A threshold sweep records kept-image counts and accuracy. Hard abstentions remain rejected at every model threshold.

CI reruns the full frozen experiment and compares counts, rates, individual decisions and numeric models with the checked-in evidence. Counts and individual decisions must match exactly. Rates use a numerical tolerance of 0.0000001; model parameters use 0.0001 because CPU rounding at histogram boundaries and solver precision differ slightly between Mac and Linux. The first cross-platform run produced identical predictions and gate decisions, with a maximum parameter difference of about 0.0000103. Offline tests additionally replace held-out pixels and check that fitted coefficients, calibration limits and the lesion classifier do not change. A source download mismatch fails the run rather than silently dropping a source or producing a partial result.

## Extending the experiment

`uv run image-qc freeze --per-class 180` explicitly creates a new source snapshot. I would review source licences and splits, rerun the experiment and regenerate the README before publishing a changed snapshot. Normal `download` and `reproduce` commands do not change the manifest.

A useful next evaluation would use clinician-rated quality, actual lesion masks for framing, mixed real-world defects, patient-level source groups, broader devices and skin tones, and a stronger independently validated lesion model. None of those is established by this experiment.
