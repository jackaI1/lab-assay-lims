# Downstream decisions are kept separate so their edge cases can be tested directly.
validate_metadata <- function(meta) {
  required <- c('sample', 'type', 'run', 'forward', 'reverse')
  if (!all(required %in% names(meta)) || nrow(meta) < 1L) stop('Invalid sample sheet')
  if (anyNA(meta) || anyDuplicated(meta$sample) || any(!grepl('^[A-Za-z0-9_-]+$', meta$sample))) stop('Invalid or duplicate sample names')
  if (any(!meta$type %in% c('sample', 'negative'))) stop('type must be sample or negative')
  if (!any(meta$type == 'sample')) stop('Need a biological sample')
  if (!all(file.exists(c(meta$forward, meta$reverse)))) stop('Missing FASTQ files')
  invisible(TRUE)
}

control_screen <- function(counts, types) {
  totals <- rowSums(counts)
  relative <- counts / pmax(totals, 1)
  negative <- types == 'negative' & totals > 0
  biological <- types == 'sample' & totals > 0
  status <- if (!any(types == 'negative')) 'unavailable: no negative controls' else if (!any(negative)) 'unavailable: controls have no retained reads' else 'screened: heuristic only, no automatic removal'
  blank_mean <- if (any(negative)) colMeans(relative[negative, , drop=FALSE]) else rep(NA_real_, ncol(counts))
  sample_mean <- if (any(biological)) colMeans(relative[biological, , drop=FALSE]) else rep(NA_real_, ncol(counts))
  flag <- !is.na(blank_mean) & !is.na(sample_mean) & blank_mean >= 0.01 & blank_mean >= 5 * sample_mean
  list(status=status, table=data.frame(asv=colnames(counts), blank_mean=blank_mean,
       sample_mean=sample_mean, blank_prevalence=if (any(negative)) colMeans(counts[negative,,drop=FALSE]>0) else NA_real_,
       sample_prevalence=if (any(biological)) colMeans(counts[biological,,drop=FALSE]>0) else NA_real_, flag=flag))
}

assess_depth <- function(counts, types, depth) {
  if (length(depth) != 1 || !is.finite(depth) || depth < 1 || depth != floor(depth)) stop('depth must be a positive integer')
  n <- rowSums(counts)
  status <- ifelse(types == 'negative', 'CONTROL: excluded from diversity',
                   ifelse(n < depth, 'TOO SHALLOW: excluded from comparison', 'ELIGIBLE at requested depth'))
  data.frame(sample=rownames(counts), retained=n, eligible=types == 'sample' & n >= depth, status=status)
}

rarefaction_table <- function(counts, points=15L) {
  rows <- lapply(seq_len(nrow(counts)), function(i) {
    n <- sum(counts[i,])
    if (!n) return(data.frame(sample=rownames(counts)[i], depth=0, expected_asvs=0))
    depths <- unique(pmax(1, round(seq(1, n, length.out=points))))
    data.frame(sample=rownames(counts)[i], depth=depths,
               expected_asvs=vapply(depths, function(d) as.numeric(vegan::rarefy(counts[i,,drop=FALSE], d)), 0.0))
  })
  do.call(rbind, rows)
}

ordinate_bray <- function(distance) {
  n <- nrow(distance)
  if (n < 2) stop('Need two samples to ordinate')
  if (max(distance) == 0) return(matrix(0, nrow=n, ncol=2))
  fit <- cmdscale(as.dist(distance), k=min(2,n-1), eig=TRUE, add=TRUE)
  points <- as.matrix(fit$points)
  if (ncol(points) < 2) points <- cbind(points, matrix(0,nrow=n,ncol=2-ncol(points)))
  points
}
