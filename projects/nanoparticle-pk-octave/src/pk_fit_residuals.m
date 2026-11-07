function rows = pk_fit_residuals(time, observed, fit)
%PK_FIT_RESIDUALS Tabulate each observation and its fitted error.
% ROWS has columns time, observed, predicted, predicted minus observed,
% and the same error as a percentage of the observed concentration.
% These are in-sample diagnostics, not a test of predictive performance.
  time=time(:); observed=observed(:); predicted=fit.predicted(:);
  if numel(time)~=numel(observed) || numel(time)~=numel(predicted)
    error('pk:diagnostics','Time, observations and predictions need the same length');
  end
  if any(~isfinite(observed)) || any(observed<=0)
    error('pk:diagnostics','Observations must be finite and positive');
  end
  if any(~isfinite(time)) || any(time<0) || any(~isfinite(predicted)) || any(predicted<0)
    error('pk:diagnostics','Times and predictions must be finite and nonnegative');
  end
  error_amount=predicted-observed;
  rows=[time observed predicted error_amount 100*error_amount./observed];
end
