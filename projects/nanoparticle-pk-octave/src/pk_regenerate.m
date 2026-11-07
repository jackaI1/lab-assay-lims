function pk_regenerate(root)
%PK_REGENERATE Refit cited data and write all figures and CSVs under ROOT.
% Called by scripts/regenerate_all.m. This is the complete offline workflow.
  % Headless on Linux and macOS. Own one figure at a time; close on errors.
  warning('off','Octave:gnuplot-graphics');
  graphics_toolkit('gnuplot');
  out=fullfile(root,'figures'); results=fullfile(root,'results');
  if ~exist(out,'dir'), mkdir(out); end
  if ~exist(results,'dir'), mkdir(results); end
  d=pk_load_data(); t=unique([linspace(0,360,181)';d.time;1.5]);
  labels={'1 compartment','2 compartments (assumed exchange)','3 compartments (assumed exchange)'};
  colors=[0.15 0.35 0.6;0.8 0.35 0.1;0.2 0.55 0.35];
  fits=cell(1,3); curves=zeros(numel(t),3); metrics=zeros(3,6);
  for n=1:3
    p=pk_parameters(n); p.dose=d.dose; p.infusion=d.infusion;
    fits{n}=pk_fit(d.time,d.concentration,p,{'CL','V1'});
    f=fits{n}; assert(f.exitflag>0,'Fit did not converge');
    s=pk_simulate(f.params,t); curves(:,n)=s.concentration;
    assert(max(abs(sum(s.amount,2)+s.eliminated-s.delivered))<1e-6);
    metrics(n,:)=[n f.params.CL f.params.V(1) f.sse f.rmse f.exitflag];
  end
  save_csv(fullfile(results,'fits.csv'), ...
    'compartments,CL_L_h_m2,V1_L_m2,log_sse,rmse_ug_ml,exitflag',metrics);
  residual_rows=[];
  for n=1:3
    rows=pk_fit_residuals(d.time,d.concentration,fits{n});
    residual_rows=[residual_rows; n*ones(numel(d.time),1) rows];
  end
  save_csv(fullfile(results,'fit_residuals.csv'), ...
    'compartments,time_h,observed_ug_ml,predicted_ug_ml,error_ug_ml,error_percent',residual_rows);
  save_csv(fullfile(results,'curves.csv'),'time_h,one_ug_ml,two_ug_ml,three_ug_ml',[t curves]);

  h=new_figure(); guard=onCleanup(@() close(h));
  subplot(2,1,1); hold on;
  for n=1:3, plot(t,curves(:,n),'LineWidth',1.6,'Color',colors(n,:)); end
  plot(d.time,d.concentration,'ko','MarkerFaceColor','k','MarkerSize',5);
  xlabel('Hours from infusion start'); ylabel('Encapsulated drug (ug/mL)');
  title('Li 2022 Fig 3A: fits to digitized means (exchange assumed)');
  legend([labels {'Digitized means'}],'Location','northeast'); grid on;
  subplot(2,1,2); hold on;
  for n=1:3
    plot(d.time,fits{n}.residual,'o-','Color',colors(n,:),'LineWidth',1.2);
  end
  plot([0 360],[0 0],'k:');
  xlabel('Hours from infusion start'); ylabel('log(predicted / observed)');
  title('Residuals at the six fitted observations'); grid on;
  print(h,fullfile(out,'fits.png'),'-dpng','-r120'); clear guard;

  p=fits{3}.params; st=linspace(2,360,100)';
  names={'CL','V1','Q1','Q2','V2','V3'};
  sensitivity=pk_sensitivity(p,st,names);
  save_csv(fullfile(results,'sensitivity.csv'), ...
    'time_h,CL,V1,Q1,Q2,V2,V3',[st sensitivity.elasticity]);
  h=new_figure(); guard=onCleanup(@() close(h));
  plot(st,sensitivity.elasticity,'LineWidth',1.5);
  xlabel('Hours from infusion start'); ylabel('Fractional response / fractional change');
  title('Local sensitivity, 3-compartment fit (exchange assumed; +/-1%)');
  legend(names,'Location','southwest'); grid on;
  print(h,fullfile(out,'sensitivity.png'),'-dpng','-r120'); clear guard;

  mc=pk_monte_carlo(p,t,{'CL','V1'},0.2,200,2026);
  save_csv(fullfile(results,'monte_carlo.csv'), ...
    'time_h,p05_ug_ml,median_ug_ml,p95_ug_ml',[t mc.lower mc.median mc.upper]);
  save_csv(fullfile(results,'monte_carlo_draws.csv'), ...
    'CL_L_h_m2,V1_L_m2,auc_0_360_ug_h_ml',[mc.draws mc.auc']);
  h=new_figure(); guard=onCleanup(@() close(h)); hold on;
  fill([t;flipud(t)],[mc.lower;flipud(mc.upper)],[0.82 0.9 0.95],'EdgeColor','none');
  plot(t,mc.median,'Color',colors(1,:),'LineWidth',1.8);
  plot(d.time,d.concentration,'ko','MarkerFaceColor','k');
  xlabel('Hours from infusion start'); ylabel('Encapsulated drug (ug/mL)');
  title('200 scenarios, seed 2026: ASSUMED CV=20%, independent CL and V1');
  legend({'5th-95th percentile scenarios','Median scenario','Digitized means'},'Location','northeast'); grid on;
  print(h,fullfile(out,'variability.png'),'-dpng','-r120'); clear guard;

  s=pk_simulate(p,t);
  save_csv(fullfile(results,'mass_balance.csv'), ...
    'time_h,central_mg_m2,pool2_mg_m2,pool3_mg_m2,eliminated_mg_m2,delivered_mg_m2', ...
    [t s.amount s.eliminated s.delivered]);
  h=new_figure(); guard=onCleanup(@() close(h));
  plot(t,[s.amount s.eliminated],'LineWidth',1.5);
  xlabel('Hours from infusion start'); ylabel('Amount (mg/m^2)');
  title('3-compartment fit: ASSUMED exchange pools (not measured organs)');
  legend({'Central','Pool 2','Pool 3','Eliminated'},'Location','east'); grid on;
  print(h,fullfile(out,'compartments.png'),'-dpng','-r120'); clear guard;
  expected={'fits.png','sensitivity.png','variability.png','compartments.png'};
  for k=1:numel(expected)
    info=dir(fullfile(out,expected{k})); assert(~isempty(info) && info.bytes>5000);
  end
  fprintf('Generated 4 figures and 7 CSV files; 200 Monte Carlo draws.\n');
  fprintf('1-compartment fit: CL=%.6f L/h/m2, V1=%.6f L/m2, RMSE=%.4f ug/mL\n', ...
          metrics(1,2),metrics(1,3),metrics(1,5));
end

function h = new_figure()
  h=figure('visible','off','position',[100 100 1000 760],'color','w');
  set(h,'defaultaxesfontsize',12,'defaulttextfontsize',12);
end

function save_csv(path,header,values)
  fid=fopen(path,'w'); assert(fid>=0,['Cannot write ' path]);
  guard=onCleanup(@() fclose(fid)); fprintf(fid,'%s\n',header); clear guard;
  dlmwrite(path,values,'-append','delimiter',',','precision','%.10g');
end
