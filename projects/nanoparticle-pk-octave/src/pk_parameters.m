function p = pk_parameters(n)
%PK_PARAMETERS Create assumed example parameters for 1, 2 or 3 compartments.
% P=PK_PARAMETERS(N) returns dose (mg), V (L), CL and Q (L/h), infusion (h).
% These defaults are illustrative, not estimates from a publication. Set
% infusion=0 for a bolus. V(1) is central; Q(j) links central to V(j+1).
  if ~isscalar(n) || ~isreal(n) || ~ismember(n,[1 2 3])
    error('pk:parameters','Compartment count must be 1, 2 or 3');
  end
  volumes=[2 1 0.5]; exchanges=[0.01 0.003];
  p=struct('n',n,'dose',50,'V',volumes(1:n),'CL',0.02, ...
           'Q',exchanges(1:n-1),'infusion',0);
end
