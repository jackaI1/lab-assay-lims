function M = pk_matrix(p)
%PK_MATRIX Validate parameters and return the amount-transfer matrix (1/h).
% dA/dt=M*A+input. Loss is only from central; Q gives reversible exchange.
% Volumes must be positive. Clearance, dose and infusion may be zero.
  if ~isstruct(p) || ~all(isfield(p,{'n','dose','V','CL','Q','infusion'}))
    error('pk:parameters','Missing model parameter fields');
  end
  if ~isscalar(p.n) || ~isreal(p.n) || ~ismember(p.n,[1 2 3])
    error('pk:parameters','Compartment count must be 1, 2 or 3');
  end
  if ~isreal(p.V) || numel(p.V)~=p.n || any(~isfinite(p.V(:))) || any(p.V(:)<=0)
    error('pk:volume','Each compartment needs a positive finite volume');
  end
  if ~isreal(p.CL) || ~isscalar(p.CL) || ~isfinite(p.CL) || p.CL<0 || ...
     ~isreal(p.Q) || numel(p.Q)~=p.n-1 || any(~isfinite(p.Q(:))) || any(p.Q(:)<0)
    error('pk:clearance','All clearance values must be finite and nonnegative');
  end
  if ~isscalar(p.dose) || ~isreal(p.dose) || ~isfinite(p.dose) || p.dose<0
    error('pk:dose','The dose must be finite and nonnegative');
  end
  if ~isscalar(p.infusion) || ~isreal(p.infusion) || ~isfinite(p.infusion) || p.infusion<0
    error('pk:infusion','The infusion duration must be finite and nonnegative');
  end
  M=zeros(p.n); M(1,1)=-p.CL/p.V(1);
  for j=2:p.n
    q=p.Q(j-1);
    M(1,1)=M(1,1)-q/p.V(1); M(j,1)=q/p.V(1);
    M(1,j)=q/p.V(j); M(j,j)=-q/p.V(j);
  end
end
