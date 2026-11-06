function d = pk_load_data()
%PK_LOAD_DATA Load rounded group-mean concentrations digitized from Li 2022.
% D has time (h), concentration (ug/mL), dose=50 (mg/m2), infusion=1.5 (h).
% See data/README.md for Figure 3A attribution, calibration and limitations.
  root=fileparts(fileparts(mfilename('fullpath')));
  x=dlmread(fullfile(root,'data','li2022_test_encapsulated.csv'),',',1,0);
  d=struct('time',x(:,1),'concentration',x(:,2),'dose',50,'infusion',1.5, ...
           'source','Li et al. 2022, doi:10.3389/fonc.2022.1070001, Fig 3A');
end
