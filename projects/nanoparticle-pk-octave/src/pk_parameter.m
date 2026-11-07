function [value, updated] = pk_parameter(p, name, replacement)
%PK_PARAMETER Read or replace CL, V1..Vn, or Q1..Q(n-1).
% [VALUE,UPDATED]=PK_PARAMETER(P,NAME,REPLACEMENT) copies P and changes one
% parameter. This helper provides a shared naming scheme for all analyses.
  updated=p;
  if strcmp(name,'CL')
    value=p.CL;
    if nargin==3, updated.CL=replacement; end
  elseif ischar(name) && numel(name)==2 && ismember(name(1),'VQ') && ismember(name(2),'123')
    j=str2double(name(2));
    if (name(1)=='V' && j<=p.n) || (name(1)=='Q' && j<p.n)
      entries=p.(name(1)); value=entries(j);
      if nargin==3, entries(j)=replacement; updated.(name(1))=entries; end
    else, error('pk:parameter','Unknown parameter for this compartment count'); end
  else, error('pk:parameter','Unknown parameter name'); end
end
