args <- commandArgs(trailingOnly=TRUE)
if (length(args)!=2) stop('Usage: Rscript analysis/render.R <sdtm-dir> <report-output-dir>')
root <- normalizePath('.')
input <- normalizePath(args[1],mustWork=TRUE)
dir.create(args[2],recursive=TRUE,showWarnings=FALSE)
output <- normalizePath(args[2])
rmarkdown::render(file.path(root,'analysis','report.Rmd'),output_file='report.html',output_dir=output,
                  output_options=list(pandoc_args=paste0('--resource-path=',output)),
                  params=list(project_root=root,sdtm_dir=input,output_dir=output),
                  envir=new.env(parent=globalenv()),quiet=TRUE)
report_path <- file.path(output,'report.html')
writeLines(sub('[ \t]+$','',readLines(report_path,warn=FALSE)),report_path)
cat('Rendered ',file.path(output,'report.html'),'\n',sep='')
