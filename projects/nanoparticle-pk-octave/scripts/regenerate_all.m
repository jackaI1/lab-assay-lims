% Refit public observations and regenerate every committed figure and CSV.
root=fileparts(fileparts(mfilename('fullpath')));
addpath(fullfile(root,'src'));
pk_regenerate(root);
