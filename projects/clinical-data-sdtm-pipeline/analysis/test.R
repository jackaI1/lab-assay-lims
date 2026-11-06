required <- c('tidyverse','survival','testthat')
missing <- required[!vapply(required,requireNamespace,logical(1),quietly=TRUE)]
if (length(missing)) stop('Missing R packages: ',paste(missing,collapse=', '))
Sys.setenv(PROJECT_ROOT=normalizePath('.'), SDTM_DIR=normalizePath('build/demo/output/sdtm',mustWork=TRUE))
# Run from the repository root. Stop on any failed expectation.
results <- testthat::test_dir('analysis/tests/testthat',reporter='summary',stop_on_failure=TRUE,
                  env=new.env(parent=globalenv()),load_helpers=FALSE)

counts <- as.data.frame(results)
if (any(counts$skipped) || any(counts$warning)) stop('R tests must not skip or warn')
cat(nrow(counts), 'R tests,',sum(counts$passed), 'passing expectations\n')
