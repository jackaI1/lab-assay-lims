#!/usr/bin/env Rscript
suppressPackageStartupMessages({library(dada2); library(vegan); library(ShortRead)})
source('scripts/lib.R')
args <- commandArgs(trailingOnly=TRUE)
if (length(args) != 4) stop('Usage: Rscript scripts/pipeline.R samples.tsv taxonomy.fa.gz output depth')
meta <- read.delim(args[1], stringsAsFactors=FALSE, check.names=FALSE)
validate_metadata(meta)
if (!file.exists(args[2])) stop('Taxonomy reference missing')
out <- args[3]; depth <- as.numeric(args[4]); seed <- 104729L
# Validate the depth before spending time denoising.
invisible(assess_depth(matrix(0, nrow(meta), 1, dimnames=list(meta$sample, 'placeholder')), meta$type, depth))
dir.create(out, recursive=TRUE, showWarnings=FALSE)
if (file.exists(file.path(out, 'counts.tsv'))) stop('Output already contains a run; use a new directory')
write_tsv <- function(x, name) write.table(x, file.path(out, name), sep='\t', row.names=FALSE, quote=FALSE, na='NA')
set.seed(seed)
quality_rows <- list()
for (i in seq_len(nrow(meta))) for (mate in c('forward', 'reverse')) {
  reads <- readFastq(meta[[mate]][i]); q <- as(quality(reads), 'matrix')
  quality_rows[[length(quality_rows)+1L]] <- data.frame(sample=meta$sample[i], mate=mate, cycle=seq_len(ncol(q)),
    mean_quality=colMeans(q, na.rm=TRUE), fraction_q30=colMeans(q>=30, na.rm=TRUE))
  rm(reads, q)
}
write_tsv(do.call(rbind, quality_rows), 'read_quality.tsv')
for (mate in c('forward', 'reverse')) {
  png(file.path(out, paste0('quality_',mate,'.png')), width=1100, height=700)
  print(plotQualityProfile(meta[[mate]][1], n=50000)); dev.off()
}
filter_dir <- file.path(out, 'filtered'); dir.create(filter_dir)
f <- file.path(filter_dir, paste0(meta$sample, '_F.fastq.gz'))
r <- file.path(filter_dir, paste0(meta$sample, '_R.fastq.gz'))
# Deposited reads start in the V4 sequence, not in the primer. The first 15 bases
# are trimmed following the study's preprocessing; tails are selected from QC.
filtered <- filterAndTrim(meta$forward, f, meta$reverse, r, trimLeft=c(15,15),
  truncLen=c(230,140), maxN=0, maxEE=c(2.5,2.5), truncQ=2,
  rm.phix=TRUE, compress=TRUE, multithread=FALSE, matchIDs=TRUE, id.sep=" ", id.field=1)
active <- filtered[, 'reads.out'] > 0
if (!any(active)) stop('No reads survived QC')
set.seed(seed)
ef <- learnErrors(f[active], nbases=1e8, multithread=FALSE, randomize=FALSE)
er <- learnErrors(r[active], nbases=1e8, multithread=FALSE, randomize=FALSE)
saveRDS(list(forward=ef, reverse=er), file.path(out,'error_models.rds'))
for (direction in c('forward','reverse')) {
  png(file.path(out, paste0('errors_',direction,'.png')), width=1000, height=800)
  print(plotErrors(if (direction=='forward') ef else er, nominalQ=TRUE)); dev.off()
}
derep_f <- lapply(f[active], derepFastq)
derep_r <- lapply(r[active], derepFastq)
df <- dada(derep_f, err=ef, multithread=FALSE, pool=FALSE)
dr <- dada(derep_r, err=er, multithread=FALSE, pool=FALSE)
if (inherits(df, "dada")) df <- list(df)
if (inherits(dr, "dada")) dr <- list(dr)
merged <- mergePairs(df, derep_f, dr, derep_r, minOverlap=12, maxMismatch=0, verbose=TRUE)
seqtab <- makeSequenceTable(merged)
rownames(seqtab) <- meta$sample[active]
nonchim <- removeBimeraDenovo(seqtab, method='consensus', multithread=FALSE)
if (!ncol(nonchim) || sum(nonchim)==0) stop('No non-chimeric ASVs remain')
# Restore zero-read samples, then use sequence order for stable identifiers.
sequences <- sort(colnames(nonchim))
counts <- matrix(0L, nrow(meta), length(sequences), dimnames=list(meta$sample, sequences))
counts[rownames(nonchim),] <- nonchim[,sequences,drop=FALSE]
asvs <- sprintf('ASV%04d', seq_along(sequences)); colnames(counts) <- asvs
set.seed(seed)
tax <- assignTaxonomy(sequences, args[2], minBoot=80, outputBootstraps=TRUE, multithread=FALSE, tryRC=TRUE)
write_tsv(data.frame(asv=asvs, sequence=sequences, tax$tax, check.names=FALSE), 'taxonomy.tsv')
write_tsv(data.frame(asv=asvs, tax$boot, check.names=FALSE), 'taxonomy_bootstraps.tsv')
writeLines(as.vector(rbind(paste0('>',asvs), sequences)), file.path(out, 'asvs.fasta'))
write_tsv(data.frame(sample=rownames(counts), counts, check.names=FALSE), 'counts.tsv')
getN <- function(x) sum(getUniques(x))
track <- data.frame(sample=meta$sample, type=meta$type, run=meta$run,
 raw_pairs=filtered[,'reads.in'], filtered_pairs=filtered[,'reads.out'], denoised_forward=0L, denoised_reverse=0L, merged=0L, nonchimeric=rowSums(counts))
track$denoised_forward[active] <- vapply(df,getN,0.0)
track$denoised_reverse[active] <- vapply(dr,getN,0.0)
track$merged[active] <- rowSums(seqtab)
write_tsv(track, 'read_tracking.tsv')
screen <- control_screen(counts, meta$type)
write_tsv(screen$table, 'contamination.tsv')
decisions <- assess_depth(counts, meta$type, depth)
curves <- rarefaction_table(counts); write_tsv(curves, 'rarefaction.tsv')
# Expected new ASVs in the final 10% of retained reads, divided by total richness.
gain <- vapply(seq_len(nrow(counts)), function(i) {
 n <- sum(counts[i,]); if (!n) return(NA_real_)
 (sum(counts[i,]>0)-as.numeric(rarefy(counts[i,,drop=FALSE],max(1,floor(0.9*n)))))/sum(counts[i,]>0)
}, 0.0)
decisions$tail_gain_fraction <- gain
decisions$rarefaction_warning <- ifelse(is.na(gain), 'NO RETAINED READS', ifelse(gain>0.05,'STILL RISING: depth may miss rare variants','small final gain; not proof of complete coverage'))
write_tsv(decisions, 'sample_decisions.tsv')
selected <- counts[decisions$eligible,,drop=FALSE]
if (nrow(selected)>0) {
 set.seed(seed); rare <- rrarefy(selected, sample=depth)
 alpha <- data.frame(sample=rownames(rare), depth=depth, observed_asvs=rowSums(rare>0), shannon=diversity(rare,index='shannon'), simpson=diversity(rare,index='simpson'))
 write_tsv(alpha, 'alpha_diversity.tsv')
 write_tsv(data.frame(sample=rownames(rare),rare,check.names=FALSE),'rarefied_counts.tsv')
 if (nrow(rare)>1) {
  beta <- as.matrix(vegdist(rare, method='bray'))
  write_tsv(data.frame(sample=rownames(beta),beta,check.names=FALSE),'beta_bray_curtis.tsv')
  coordinates <- ordinate_bray(beta)
  write_tsv(data.frame(sample=rownames(beta), axis1=coordinates[,1],axis2=coordinates[,2]),'pcoa.tsv')
  png(file.path(out,'beta_pcoa.png'),width=1000,height=700)
  plot(coordinates[,1],coordinates[,2],pch=19,xlab='PCoA axis 1',ylab='PCoA axis 2',main='Bray-Curtis, Cailliez correction for ordination')
  text(coordinates[,1],coordinates[,2],labels=rownames(beta),pos=3); dev.off()
 }
}
png(file.path(out,'rarefaction.png'),width=1000,height=700)
plot(NA,xlim=c(0,max(curves$depth,depth)),ylim=c(0,max(1,curves$expected_asvs)),xlab='Retained read pairs sampled',ylab='Expected sequence variants',main='Rarefaction: is more sequencing still finding variants?')
colors <- seq_len(nrow(meta))
for(i in seq_len(nrow(meta))) { z<-curves[curves$sample==meta$sample[i],]; lines(z$depth,z$expected_asvs,col=colors[i],lwd=2) }
abline(v=depth,lty=2); legend('bottomright',legend=meta$sample,col=colors,lty=1);dev.off()
write_tsv(data.frame(parameter=c('seed','depth','trimLeft_F','trimLeft_R','truncLen_F','truncLen_R','maxEE_F','maxEE_R','taxonomy_min_bootstrap','taxonomy_reference','taxonomy_reference_md5','dada2_version','control_screen'),
 value=c(seed,depth,15,15,230,140,2.5,2.5,80,basename(args[2]),unname(tools::md5sum(args[2])),as.character(packageVersion("dada2")),screen$status)),'parameters.tsv')
writeLines(trimws(capture.output(sessionInfo()),which='right'),file.path(out,'sessionInfo.txt'))
message('Completed ', nrow(counts),' samples, ',ncol(counts),' ASVs; ',sum(decisions$eligible),' eligible for diversity')
