options(timeout=max(600,getOption('timeout')))
packages <- c('tidyverse','survival','testthat','rmarkdown')
missing <- packages[!vapply(packages,requireNamespace,logical(1),quietly=TRUE)]
if (length(missing)) install.packages(missing,repos='https://cloud.r-project.org',Ncpus=2)
if (!rmarkdown::pandoc_available()) stop('Install Pandoc: brew install pandoc (macOS), apt install pandoc (Linux)')
