% Run all Octave BIST files and fail the process on any failed/skipped test.
root=fileparts(fileparts(mfilename('fullpath')));
addpath(fullfile(root,'src'));
files=dir(fullfile(root,'tests','test_*.m'));
passed=0; total=0;
for k=1:numel(files)
  path=fullfile(files(k).folder,files(k).name);
  [n,nmax,nxfail,nbug,nskip,nrtskip,nregression]=test(path,'quiet');
  fprintf('%s: %d/%d passed\n',files(k).name,n,nmax);
  assert(n==nmax && nxfail==0 && nbug==0 && nskip==0 && nrtskip==0 && nregression==0, ...
         ['Test failure in ' files(k).name]);
  passed=passed+n; total=total+nmax;
end
assert(total>0,'No tests discovered');
fprintf('TOTAL: %d/%d passed\n',passed,total);
