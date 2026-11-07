% Octave BIST: fitting and uncertainty analysis.

%!test
%! p=pk_parameters(1); p.V=2; p.CL=0.04; p.infusion=1.5;
%! t=[2;10;24;48;96;200]; truth=pk_simulate(p,t);
%! start=p; start.V=4; start.CL=0.08;
%! f=pk_fit(t,truth.concentration,start,{'CL','V1'});
%! assert(f.params.CL,p.CL,2e-4); assert(f.params.V,p.V,2e-3);
%! assert(f.sse<1e-7); assert(f.exitflag>0);

%!test
%! p=pk_parameters(2); p.infusion=1.5; t=[2;10;24;48;96;200];
%! s=pk_simulate(p,t); initial=p; initial.CL=2*p.CL;
%! f=pk_fit(t,s.concentration,initial,{'CL'});
%! assert(f.params.CL,p.CL,2e-4); assert(f.sse<1e-7);

%!test
%! d=pk_load_data(); assert(numel(d.time)==6); assert(d.time(1)==25.5);
%! for n=1:3
%!   p=pk_parameters(n); p.infusion=1.5;
%!   f=pk_fit(d.time,d.concentration,p,{'CL','V1'});
%!   assert(f.sse<f.initial_sse); assert(f.exitflag>0);
%!   assert(all(f.predicted>0)); assert(isfinite(f.rmse));
%! end

%!test
%! p=pk_parameters(1); p.V=2; p.CL=0.4;
%! t=[0;1;2;5]; a=pk_sensitivity(p,t,{'CL'},0.001);
%! assert(a.elasticity(:,1),-p.CL/p.V*t,2e-5);

%!test
%! p=pk_parameters(3); t=[0;1;4];
%! a=pk_sensitivity(p,t,{'CL','Q1','V3'},0.005);
%! assert(size(a.elasticity),[3 3]); assert(all(isfinite(a.elasticity(:))));

%!test
%! p=pk_parameters(2); t=[0;1;4]; state=rng;
%! a=pk_monte_carlo(p,t,{'CL','V1'},0.2,20,42);
%! after=rng; assert(isequal(state,after));
%! b=pk_monte_carlo(p,t,{'CL','V1'},0.2,20,42);
%! assert(a.concentration,b.concentration,0);
%! assert(all(a.concentration(:)>=0)); assert(all(a.lower<=a.median));
%! assert(all(a.median<=a.upper)); assert(size(a.draws),[20 2]);

%!test
%! p=pk_parameters(1); s=pk_simulate(p,[0;2;4]);
%! a=pk_monte_carlo(p,[0;2;4],{'CL'},0,8,1);
%! assert(a.median,s.concentration,1e-10);
%! assert(a.lower,a.upper,1e-10);

%!error <positive> pk_fit([1;2],[1;0],pk_parameters(1),{'CL'})
%!error <same length> pk_fit([1;2],[1],pk_parameters(1),{'CL'})
%!error <parameter> pk_fit([1;2],[1;2],pk_parameters(1),{'nonsense'})
%!error <at least> pk_fit([1;2],[1;2],pk_parameters(1),{'CL','V1'})
%!error <step> pk_sensitivity(pk_parameters(1),[0;1],{'CL'},1)
%!error <CV> pk_monte_carlo(pk_parameters(1),[0;1],{'CL'},-0.1,10,1)
%!error <integer> pk_monte_carlo(pk_parameters(1),[0;1],{'CL'},0.1,1.5,1)

%!test
%! p=pk_parameters(1); p.infusion=1.5; t=[2;10;24;48];
%! observed=pk_simulate(p,t).concentration .* [1;1.1;0.9;1.05];
%! f=pk_fit(t,observed,p,{'CL'});
%! rows=pk_fit_residuals(t,observed,f);
%! assert(rows(:,1),t); assert(rows(:,2),observed);
%! assert(rows(:,3),f.predicted,1e-12);
%! assert(rows(:,4),f.predicted-observed,1e-12);
%! assert(rows(:,5),100*(f.predicted-observed)./observed,1e-10);

%!test
%! f=struct('predicted',[1 NaN]);
%! fail('pk_fit_residuals([0 1],[1 2],f)', 'finite and nonnegative');
%! f.predicted=[1 2];
%! fail('pk_fit_residuals([0 -1],[1 2],f)', 'finite and nonnegative');
