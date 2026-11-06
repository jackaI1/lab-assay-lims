function out = pk_monte_carlo(p,time,names,cv,count,seed)
%PK_MONTE_CARLO Independent lognormal parameter variability, not confidence.
% M=PK_MONTE_CARLO(P,T,NAMES,CV,COUNT,SEED) treats P values as medians and
% CV as an assumed coefficient of variation (scalar or one per name).
% Returns concentration (time by draw), draws (draw by parameter), 5th/50th/
% 95th percentile curves, and auc (mg*h/L over T only). Restores caller RNG.
  pk_simulate(p,time);
  if ~isnumeric(cv) || ~isreal(cv) || any(~isfinite(cv(:))) || any(cv(:)<0) || ...
     ~(isscalar(cv) || numel(cv)==numel(names))
    error('pk:montecarlo','CV must be nonnegative and scalar or one per parameter');
  end
  if ~isscalar(count) || ~isfinite(count) || count<2 || count~=fix(count)
    error('pk:montecarlo','Draw count must be an integer at least 2');
  end
  if ~isscalar(seed) || ~isreal(seed) || ~isfinite(seed) || seed<0 || seed~=fix(seed)
    error('pk:montecarlo','Seed must be a nonnegative integer');
  end
  if ~iscellstr(names) || isempty(names) || numel(unique(names))~=numel(names)
    error('pk:montecarlo','Use distinct parameter names');
  end
  values=zeros(1,numel(names));
  for j=1:numel(names)
    values(j)=pk_parameter(p,names{j});
    if values(j)<=0, error('pk:montecarlo','Varied parameters must be positive'); end
  end
  if isscalar(cv), cv=repmat(cv,1,numel(names)); else, cv=cv(:)'; end
  old=rng; cleanup=onCleanup(@() rng(old));
  rng(seed,'twister');
  sigma=sqrt(log(1+cv.^2));
  draws=exp(bsxfun(@plus,log(values),bsxfun(@times,randn(count,numel(names)),sigma)));
  concentration=zeros(numel(time),count);
  for i=1:count
    sample=p;
    for j=1:numel(names), [~,sample]=pk_parameter(sample,names{j},draws(i,j)); end
    s=pk_simulate(sample,time); concentration(:,i)=s.concentration;
  end
  sorted=sort(concentration,2); bands=zeros(numel(time),3);
  probabilities=[0.05 0.5 0.95];
  for j=1:3
    rank=1+(count-1)*probabilities(j); lo=floor(rank); hi=ceil(rank);
    bands(:,j)=sorted(:,lo)+(rank-lo)*(sorted(:,hi)-sorted(:,lo));
  end
  out=struct('time',time(:),'names',{names},'draws',draws,'concentration',concentration, ...
             'lower',bands(:,1),'median',bands(:,2),'upper',bands(:,3), ...
             'auc',trapz(time(:),concentration,1),'cv',cv,'seed',seed);
end
