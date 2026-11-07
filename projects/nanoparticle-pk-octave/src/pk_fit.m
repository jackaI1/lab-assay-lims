function fit = pk_fit(time, observed, initial, names)
%PK_FIT Fit selected positive parameters by log-concentration least squares.
% F=PK_FIT(T,C,P,{'CL','V1'}) uses fminsearch on log parameters, three
% deterministic starts, and ode45 predictions. Other fields of P stay fixed.
% Returns params, predicted, residual (log units), sse, initial_sse, rmse
% (concentration units), exitflag and names. Positive observations required.
% Assumed exchange parameters and data limitations must be reported by caller.
  pk_simulate(initial,time); % Validate model and time before optimization.
  time=time(:); observed=observed(:);
  if numel(time)~=numel(observed), error('pk:fit','Time and observations need the same length'); end
  if ~isreal(observed) || any(~isfinite(observed)) || any(observed<=0)
    error('pk:fit','Observed concentrations must be finite and positive');
  end
  if ~iscellstr(names) || isempty(names) || numel(unique(names))~=numel(names)
    error('pk:fit','Use distinct parameter names in a cell array');
  end
  if numel(time)<=numel(names), error('pk:fit','Need at least one more observation than fitted parameters'); end
  x0=zeros(1,numel(names));
  for j=1:numel(names)
    v=pk_parameter(initial,names{j});
    if v<=0, error('pk:fit','Fitted parameter initial values must be positive'); end
    x0(j)=log(v);
  end
  objective=@(x) score(x,time,observed,initial,names);
  initial_sse=objective(x0); best=Inf; bestflag=0;
  opts=optimset('Display','off','MaxIter',350,'MaxFunEvals',700,'TolX',1e-6,'TolFun',1e-9);
  for shift=[0 -0.5 0.5]
    [x,sse,flag]=fminsearch(objective,x0+shift,opts);
    if sse<best, best=sse; bestx=x; bestflag=flag; end
  end
  if best>=1e90, error('pk:fit','No finite model fit found'); end
  params=unpack(initial,names,bestx); s=pk_simulate(params,time);
  residual=log(s.concentration)-log(observed);
  fit=struct('params',params,'predicted',s.concentration,'residual',residual, ...
             'sse',sum(residual.^2),'initial_sse',initial_sse, ...
             'rmse',sqrt(mean((s.concentration-observed).^2)), ...
             'exitflag',bestflag,'names',{names});
end

function p = unpack(p,names,x)
  for j=1:numel(names), [~,p]=pk_parameter(p,names{j},exp(x(j))); end
end

function value = score(x,time,observed,p,names)
  % Broad numerical guard, not a physiological prior or clinical bound.
  if any(~isfinite(x)) || any(abs(x)>20), value=1e100; return; end
  try
    p=unpack(p,names,x); s=pk_simulate(p,time);
    if any(~isfinite(s.concentration)) || any(s.concentration<=0)
      value=1e100;
    else, value=sum((log(s.concentration)-log(observed)).^2); end
  catch
    value=1e100;
  end
end
