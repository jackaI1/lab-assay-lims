function out = pk_sensitivity(p,time,names,step)
%PK_SENSITIVITY Local dimensionless d(log C)/d(log parameter) by differences.
% S=PK_SENSITIVITY(P,T,NAMES,STEP) perturbs each named positive parameter by
% +/-STEP (default 0.01). Zero central concentration gives NaN elasticity.
% Returned fields: time, names, elasticity (time by parameter), baseline.
  if nargin<4, step=0.01; end
  if ~isscalar(step) || ~isreal(step) || ~isfinite(step) || step<=0 || step>=1
    error('pk:sensitivity','The step must be between zero and one');
  end
  base=pk_simulate(p,time); elasticity=NaN(numel(time),numel(names));
  for j=1:numel(names)
    v=pk_parameter(p,names{j});
    if v<=0, error('pk:sensitivity','Sensitivity parameter must be positive'); end
    [~,lo]=pk_parameter(p,names{j},v*(1-step));
    [~,hi]=pk_parameter(p,names{j},v*(1+step));
    a=pk_simulate(lo,time); b=pk_simulate(hi,time);
    valid=a.concentration>0 & b.concentration>0;
    elasticity(valid,j)=(log(b.concentration(valid))-log(a.concentration(valid))) ...
                       /(log(1+step)-log(1-step));
  end
  out=struct('time',base.time,'names',{names},'elasticity',elasticity, ...
             'baseline',base.concentration);
end
