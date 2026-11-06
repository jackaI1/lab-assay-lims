% Octave BIST: independent analytical and mass-balance checks.

%!test
%! p=pk_parameters(1); p.V=2; p.CL=0.4; p.dose=10;
%! s=pk_simulate(p,[0 1 4 10]);
%! assert(s.concentration,5*exp(-0.2*[0;1;4;10]),2e-6);

%!test
%! for n=2:3
%!   p=pk_parameters(n); t=[0 0.5 3 12]; s=pk_simulate(p,t);
%!   M=pk_matrix(p); a=zeros(n,1); a(1)=p.dose;
%!   for i=1:numel(t)
%!     assert(s.amount(i,:)',expm(M*t(i))*a,2e-5);
%!   end
%! end

%!test
%! for n=1:3
%!   p=pk_parameters(n); s=pk_simulate(p,linspace(0,300,60));
%!   assert(sum(s.amount,2)+s.eliminated,p.dose*ones(60,1),1e-7);
%!   assert(min(s.amount(:))>=-1e-7);
%! end

%!test
%! p=pk_parameters(3); p.CL=0; s=pk_simulate(p,[0 1 10 100]);
%! assert(sum(s.amount,2),p.dose*ones(4,1),1e-7);

%!test
%! p=pk_parameters(1); p.infusion=1.5; p.V=2; p.CL=0.4; p.dose=10;
%! t=[0;0.25;1.5;2;10]; s=pk_simulate(p,t);
%! during=10/1.5/0.4*(1-exp(-0.2*min(t,1.5)));
%! expected=during.*exp(-0.2*max(t-1.5,0));
%! assert(s.concentration,expected,2e-6);
%! assert(sum(s.amount,2)+s.eliminated,10*min(t/1.5,1),1e-7);

%!test
%! p=pk_parameters(2); p.infusion=1.5;
%! full=pk_simulate(p,[0 1 1.5 2 9]); late=pk_simulate(p,[2 9]);
%! assert(late.concentration,full.concentration([4 5]),2e-6);

%!error <strictly increasing> pk_simulate(pk_parameters(1),[1 0])
%!error <strictly increasing> pk_simulate(pk_parameters(1),[0 0 1])
%!error <nonnegative> pk_simulate(pk_parameters(1),[-1 2])
%!error <finite> pk_simulate(pk_parameters(1),[0 NaN])
%!error <1, 2 or 3> pk_parameters(4)
%!error <volume> p=pk_parameters(1); p.V=0; pk_simulate(p,[0 1]);
%!error <clearance> p=pk_parameters(2); p.Q=-1; pk_simulate(p,[0 1]);
%!error <dose> p=pk_parameters(1); p.dose=-1; pk_simulate(p,[0 1]);
%!error <infusion> p=pk_parameters(1); p.infusion=-1; pk_simulate(p,[0 1]);
