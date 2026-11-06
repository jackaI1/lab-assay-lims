function s = pk_simulate(p, time)
%PK_SIMULATE Integrate an IV bolus or finite infusion using ode45.
% S=PK_SIMULATE(P,TIME) returns time (h), amount (mg, rows=time), central
% concentration (mg/L = ug/mL), eliminated (mg), and delivered (mg).
% TIME is a finite, nonnegative, strictly increasing vector. Integration
% always starts at dosing time zero, even when the first requested time >0.
  M=pk_matrix(p);
  if ~isnumeric(time) || ~isreal(time) || ~isvector(time) || isempty(time) || any(~isfinite(time(:)))
    error('pk:time','Time must be a nonempty finite real vector');
  end
  time=time(:);
  if any(time<0), error('pk:time','Time must be nonnegative'); end
  if any(diff(time)<=0), error('pk:time','Time must be strictly increasing'); end
  n=p.n; B=zeros(n+1); B(1:n,1:n)=M; B(n+1,1)=p.CL/p.V(1);
  y=zeros(n+1,1);
  if p.infusion==0, y(1)=p.dose; end
  cuts=[0;time];
  if p.infusion>0 && p.infusion<time(end), cuts=[cuts;p.infusion]; end
  cuts=unique(cuts);
  values=zeros(numel(cuts),n+1); values(1,:)=y';
  opts=odeset('RelTol',1e-7,'AbsTol',1e-9);
  % Each phase has constant input. Splitting at infusion end avoids a
  % discontinuous RHS; all observation times remain exact output points.
  edges=[0;time(end)];
  if p.infusion>0 && p.infusion<time(end), edges=[0;p.infusion;time(end)]; end
  for k=1:numel(edges)-1
    left=edges(k); right=edges(k+1);
    if right==left, continue; end
    ids=find(cuts>=left & cuts<=right); grid=cuts(ids);
    input=zeros(n+1,1);
    if p.infusion>0 && left<p.infusion, input(1)=p.dose/p.infusion; end
    [tout,sol]=ode45(@(t,a) B*a+input,grid, y,opts);
    % A two-element tspan yields adaptive internal output. Interpolate only
    % to its two endpoints; larger grids are returned directly by ode45.
    if numel(grid)==2, sol=sol([1 end],:); end
    if tout(end)<right, error('pk:integration','Integration ended early'); end
    values(ids,:)=sol; y=sol(end,:)';
  end
  [~,idx]=ismember(time,cuts);
  amount=values(idx,1:n); eliminated=values(idx,n+1);
  if p.infusion==0, delivered=p.dose*ones(size(time));
  else, delivered=p.dose*min(time/p.infusion,1); end
  s=struct('time',time,'amount',amount,'concentration',amount(:,1)/p.V(1), ...
           'eliminated',eliminated,'delivered',delivered);
end
