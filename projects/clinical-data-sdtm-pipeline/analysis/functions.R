suppressPackageStartupMessages(library(tidyverse))
suppressPackageStartupMessages(library(survival))

read_domain <- function(folder, domain) {
  readr::read_csv(file.path(folder,paste0(domain,'.csv')),col_types=cols(.default=col_character()),
                  na=character(),show_col_types=FALSE)
}

strict_date <- function(x) {
  result <- suppressWarnings(as.Date(x,format='%Y-%m-%d'))
  bad <- is.na(result) | format(result,'%Y-%m-%d') != x | !grepl('^[0-9]{4}-[0-9]{2}-[0-9]{2}$',x)
  if (any(bad)) stop('Invalid complete date in analysis input')
  result
}

analysis_population <- function(dm, ds) {
  dm_columns <- c('USUBJID','ARM','AGE','SEX','RFSTDTC','RFENDTC','DTHFL','DTHDTC')
  ds_columns <- c('USUBJID','DSDECOD','DSSTDTC')
  if (!all(dm_columns %in% names(dm)) || !all(ds_columns %in% names(ds))) stop('Missing required analysis columns')
  if (anyNA(dm[c('ARM','AGE','SEX')])) stop('Missing analysis covariates')
  if (anyNA(dm[setdiff(dm_columns,c('ARM','AGE','SEX'))]) || anyNA(ds[ds_columns])) stop('Missing endpoint dates or identities')
  if (nrow(dm)==0 || anyDuplicated(dm$USUBJID) || any(dm$USUBJID=='')) {
    stop('Demographic subjects must be nonempty and unique')
  }
  if (anyDuplicated(ds$USUBJID) || nrow(ds)!=nrow(dm) || !setequal(dm$USUBJID,ds$USUBJID)) {
    stop('Each subject must have exactly one terminal disposition')
  }
  joined <- dplyr::left_join(dm,ds,by='USUBJID',relationship='one-to-one')
  start <- strict_date(joined$RFSTDTC)
  end <- strict_date(joined$DSSTDTC)
  reference_end <- strict_date(joined$RFENDTC)
  event <- as.integer(joined$DSDECOD=='DEATH')
  if (any(!joined$DSDECOD %in% c('DEATH','COMPLETED')) ||
      any(!joined$DTHFL %in% c('Y','')) || any((joined$DTHFL=='Y')!=(event==1L)) ||
      any(end!=reference_end) || any(joined$DTHDTC[event==1L]!=joined$DSSTDTC[event==1L]) ||
      any(joined$DTHDTC[event==0L]!='')) {
    stop('Disposition and demographic endpoints must agree')
  }
  time <- as.numeric(end-start)
  if (any(!is.finite(time) | time<=0)) stop('Nonpositive follow-up is not eligible')
  age <- suppressWarnings(as.numeric(joined$AGE))
  if (any(!is.finite(age) | age<18 | age>90) || any(!joined$SEX %in% c('F','M','U')) ||
      any(!joined$ARM %in% c('ACTIVE','PLACEBO'))) stop('Invalid analysis covariates')
  tibble(USUBJID=joined$USUBJID,arm=factor(joined$ARM,levels=c('PLACEBO','ACTIVE')),
         age=age,sex=factor(joined$SEX),time=time,event=event)
}

demographics <- function(population) {
  population %>% group_by(arm,.drop=FALSE) %>% summarise(
    n=n(),age_median=median(age),age_q1=quantile(age,.25),age_q3=quantile(age,.75),
    female=sum(sex=='F'),male=sum(sex=='M'),unknown_sex=sum(sex=='U'),
    deaths=sum(event),censored=sum(event==0),.groups='drop')
}

run_analysis <- function(sdtm_dir, output_dir) {
  population <- analysis_population(read_domain(sdtm_dir,'DM'),read_domain(sdtm_dir,'DS'))
  if (nrow(population)<20 || any(table(population$arm)==0) || sum(population$event)<5 || nlevels(population$sex)<2) {
    stop('Insufficient subjects, arms, sex categories or events for the demonstration model')
  }
  dir.create(output_dir,recursive=TRUE,showWarnings=FALSE)
  tab <- demographics(population)
  km <- survfit(Surv(time,event) ~ arm,data=population,conf.type='log-log')
  model <- coxph(Surv(time,event) ~ arm + age + sex,data=population,ties='efron',x=TRUE)
  if (any(!is.finite(coef(model)))) stop('Cox model produced nonfinite estimates')
  estimates <- summary(model)
  cox <- tibble(term=rownames(estimates$coefficients),hazard_ratio=as.numeric(estimates$conf.int[,'exp(coef)']),
                lower_95=as.numeric(estimates$conf.int[,'lower .95']),upper_95=as.numeric(estimates$conf.int[,'upper .95']),
                p_value=as.numeric(estimates$coefficients[,'Pr(>|z|)']))
  zph <- cox.zph(model)
  ph <- as.data.frame(zph$table) %>% rownames_to_column('term') %>% as_tibble()
  info <- summary(km,censored=TRUE)
  curve <- tibble(time=info$time,survival=info$surv,lower=info$lower,upper=info$upper,
                  censored=info$n.censor,arm=sub('arm=','',as.character(info$strata)))
  curve <- bind_rows(tibble(time=0,survival=1,lower=1,upper=1,censored=0,arm=c('PLACEBO','ACTIVE')),curve) %>% arrange(arm,time)
  chart <- ggplot(curve,aes(time,survival,color=arm)) +
    geom_step(linewidth=.9) + geom_step(aes(y=lower),linetype='dotted',alpha=.6) +
    geom_step(aes(y=upper),linetype='dotted',alpha=.6) +
    geom_point(data=filter(curve,censored>0),shape=3,size=2) +
    scale_color_manual(values=c(ACTIVE='#176b73',PLACEBO='#9a4228')) +
    scale_y_continuous(limits=c(0,1),labels=scales::label_percent()) +
    labs(title='Survival in a fictional trial',subtitle='Dotted lines: 95% confidence limits. Crosses: censoring.',
         x='Days since randomization',y='Estimated survival',color='Assigned arm') + theme_minimal(base_size=13)
  ggsave(file.path(output_dir,'km.png'),chart,width=8,height=5,dpi=150)
  risk <- summary(km,times=c(0,90,180,270,365),extend=FALSE)
  at_risk <- tibble(arm=sub('arm=','',as.character(risk$strata)),day=risk$time,n_at_risk=risk$n.risk)
  write_csv(population,file.path(output_dir,'analysis_population.csv'))
  write_csv(tab,file.path(output_dir,'demographics.csv'))
  write_csv(cox,file.path(output_dir,'cox.csv'))
  write_csv(ph,file.path(output_dir,'ph_test.csv'))
  write_csv(at_risk,file.path(output_dir,'km_at_risk.csv'))
  capture.output(sessionInfo(),file=file.path(output_dir,'session-info.txt'))
  list(population=population,demographics=tab,km=km,cox=cox,ph=ph,at_risk=at_risk,model=model)
}
