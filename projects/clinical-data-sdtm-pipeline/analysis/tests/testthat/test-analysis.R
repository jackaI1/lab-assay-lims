# Hand-computed endpoints catch censoring, join and model-population mistakes.
source(file.path(Sys.getenv('PROJECT_ROOT'), 'analysis', 'functions.R'))
fixture <- function() {
  list(dm = tibble::tibble(USUBJID=c('s1','s2','s3','s4'), ARM=c('ACTIVE','PLACEBO','ACTIVE','PLACEBO'),
    AGE=c('40','50','60','70'), SEX=c('F','M','F','M'), RFSTDTC=rep('2025-01-01',4),
    RFENDTC=c('2025-01-11','2025-01-21','2025-01-31','2025-02-10'),
    DTHFL=c('Y','','Y',''), DTHDTC=c('2025-01-11','','2025-01-31','')),
    ds=tibble::tibble(USUBJID=c('s1','s2','s3','s4'),DSDECOD=c('DEATH','COMPLETED','DEATH','COMPLETED'),
      DSSTDTC=c('2025-01-11','2025-01-21','2025-01-31','2025-02-10')))
}

testthat::test_that('endpoint follows elapsed days and right censoring', {
  f <- fixture()
  pop <- analysis_population(f$dm,f$ds)
  testthat::expect_equal(pop$time,c(10,20,30,40))
  testthat::expect_equal(pop$event,c(1L,0L,1L,0L))
  testthat::expect_equal(as.character(pop$arm),c('ACTIVE','PLACEBO','ACTIVE','PLACEBO'))
})

testthat::test_that('Kaplan-Meier uses censored subjects in the risk set', {
  f <- fixture(); pop <- analysis_population(f$dm,f$ds)
  fit <- survival::survfit(survival::Surv(time,event) ~ 1, data=pop)
  testthat::expect_equal(as.numeric(summary(fit,times=c(10,30))$surv),c(0.75,0.375))
})

testthat::test_that('missing or duplicate dispositions never silently drop subjects', {
  f <- fixture()
  testthat::expect_error(analysis_population(f$dm,f$ds[-1,]),'exactly one')
  testthat::expect_error(analysis_population(f$dm,dplyr::bind_rows(f$ds,f$ds[1,])),'exactly one')
})

testthat::test_that('invalid dates and reversed follow-up stop analysis', {
  f <- fixture(); f$dm$RFSTDTC[1] <- '2025-02-30'
  testthat::expect_error(analysis_population(f$dm,f$ds),'date')
  f <- fixture(); f$dm$RFSTDTC[1] <- '2025-02-01'
  testthat::expect_error(analysis_population(f$dm,f$ds),'follow-up')
})

testthat::test_that('endpoint status and date must agree with demographics', {
  f <- fixture(); f$ds$DSDECOD[1] <- 'COMPLETED'
  testthat::expect_error(analysis_population(f$dm,f$ds),'agree')
  f <- fixture(); f$ds$DSSTDTC[1] <- '2025-01-12'
  testthat::expect_error(analysis_population(f$dm,f$ds),'agree')
})

testthat::test_that('duplicate subjects and nonnumeric covariates stop analysis', {
  f <- fixture()
  testthat::expect_error(analysis_population(dplyr::bind_rows(f$dm,f$dm[1,]),f$ds),'unique')
  f$dm$AGE[1] <- 'NaN'
  testthat::expect_error(analysis_population(f$dm,f$ds),'covariates')
})

testthat::test_that('demographics use all eligible subjects and explicit denominators', {
  f <- fixture(); tab <- demographics(analysis_population(f$dm,f$ds))
  testthat::expect_equal(tab$n,c(2L,2L))
  testthat::expect_equal(tab$age_median,c(60,50)) # PLACEBO then ACTIVE
  testthat::expect_equal(tab$deaths,c(0L,2L))
})

testthat::test_that('real pipeline produces finite Cox estimates and report inputs', {
  input <- Sys.getenv('SDTM_DIR','build/demo/output/sdtm')
  out <- tempfile('clinical-analysis-')
  on.exit(unlink(out,recursive=TRUE),add=TRUE)
  result <- run_analysis(input,out)
  testthat::expect_equal(nrow(result$population),119L)
  testthat::expect_equal(nrow(result$cox),3L)
  testthat::expect_equal(result$cox$term,c('armACTIVE','age','sexM'))
  testthat::expect_equal(result$model$nevent,80)
  testthat::expect_equal(result$cox$hazard_ratio[1],0.666705,tolerance=1e-5)
  testthat::expect_true(all(is.finite(result$cox$hazard_ratio)))
  testthat::expect_true(all(result$cox$lower_95 <= result$cox$hazard_ratio))
  testthat::expect_true(all(result$cox$upper_95 >= result$cox$hazard_ratio))
  testthat::expect_equal(sum(result$demographics$n),119L)
  testthat::expect_true(file.exists(file.path(out,'km.png')))
  testthat::expect_true('GLOBAL' %in% result$ph$term)
})

testthat::test_that('absent columns and missing covariates cannot produce a model', {
  f <- fixture(); f$dm$DTHDTC <- NULL
  testthat::expect_error(analysis_population(f$dm,f$ds),'columns')
  f <- fixture(); f$dm$SEX[1] <- NA_character_
  testthat::expect_error(analysis_population(f$dm,f$ds),'covariates')
})
