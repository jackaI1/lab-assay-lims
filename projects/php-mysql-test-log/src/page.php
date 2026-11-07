<?php
declare(strict_types=1);
function h(mixed $v): string { return htmlspecialchars((string)$v, ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8'); }
function verdict(bool $pass): string { return $pass ? 'Pass' : 'Fail'; }
?>
<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Bench test log</title><link rel="stylesheet" href="/style.css"><script src="/app.js" defer></script></head>
<body>
<header><a href="/">Bench test log</a><span>Readings, limits and a record to come back to.</span></header>
<main>
<section class="intro"><h1>Keep the reading.<br>Keep the reason it passed.</h1><p>Save a sample's measurements with the limits you used. A run passes only when every reading falls within its limits, including the boundary values.</p></section>
<div class="workspace">
<section class="entry" aria-labelledby="new-run"><h2 id="new-run">Record a test run</h2><p>Use a unique name for each measurement. Saved runs keep their original readings and limits.</p>
<noscript><p>Turn on JavaScript to enter a run here, or use the JSON API described in the README. Saved results below work without JavaScript.</p></noscript>
<form id="run-form">
<label>Sample or test name<input name="sample" required maxlength="120" placeholder="Coating sample A, rinse check"></label>
<label>Notes <span>(optional)</span><textarea name="notes" maxlength="2000" rows="2" placeholder="Instrument, preparation or anything to check next time"></textarea></label>
<div id="measurements"></div>
<button type="button" id="add-reading" class="secondary">Add measurement</button>
<p class="hint">Use decimals with up to 6 decimal places. Keep each value between -999999999999.999999 and 999999999999.999999.</p>
<p id="form-feedback" role="status" aria-live="polite"></p>
<button id="save-run" type="submit">Save test run</button>
</form>
<template id="reading-template"><fieldset><legend>Measurement</legend><div class="reading-name"><label>Name<input data-field="name" required maxlength="80" placeholder="Resistance"></label><label>Unit<input data-field="unit" required maxlength="24" placeholder="ohm"></label></div><div class="reading-values"><label>Reading<input data-field="value" type="text" inputmode="decimal" required placeholder="101.2"></label><label>Lower limit<input data-field="lower_limit" type="text" inputmode="decimal" required placeholder="95"></label><label>Upper limit<input data-field="upper_limit" type="text" inputmode="decimal" required placeholder="105"></label></div><button class="remove secondary" type="button">Remove measurement</button></fieldset></template>
</section>
<section class="results" aria-labelledby="results-title"><h2 id="results-title">Saved runs</h2>
<form method="get" class="filters"><label>Show<select name="status"><option value="all" <?= $status === 'all' ? 'selected' : '' ?>>All runs</option><option value="pass" <?= $status === 'pass' ? 'selected' : '' ?>>Passing runs</option><option value="fail" <?= $status === 'fail' ? 'selected' : '' ?>>Failing runs</option></select></label><button class="secondary">Filter results</button></form>
<?php if (!$listing['runs']): ?><p class="empty">No runs in this view yet. Record a test run to keep its readings and limits here.</p><?php endif ?>
<div class="run-list"><?php foreach ($listing['runs'] as $row): ?><a class="run" href="/?run=<?= h($row['id']) ?>&amp;status=<?= h($status) ?>&amp;page=<?= h($page) ?>"><span><strong><?= h($row['sample']) ?></strong><small>#<?= h($row['id']) ?> / <?= h($row['created_at']) ?> UTC / <?= h($row['readings']) ?> readings</small></span><span class="verdict <?= $row['passed'] ? 'pass' : 'fail' ?>"><?= verdict((bool)$row['passed']) ?></span></a><?php endforeach ?></div>
<nav aria-label="Results pages"><?php if ($page > 1): ?><a href="/?page=<?= $page - 1 ?>&amp;status=<?= h($status) ?>">Previous</a><?php endif ?> <span>Page <?= h($page) ?></span> <?php if ($listing['has_more']): ?><a href="/?page=<?= $page + 1 ?>&amp;status=<?= h($status) ?>">Next</a><?php endif ?></nav>
<?php if (isset($_GET['run']) && !$selected): ?><p role="alert">That run was not found. Choose a saved run above.</p><?php endif ?>
<?php if ($selected): ?><article id="run-detail"><h3><?= h($selected['sample']) ?> <span class="verdict <?= $selected['passed'] ? 'pass' : 'fail' ?>"><?= verdict($selected['passed']) ?></span></h3><p>Run #<?= h($selected['id']) ?> / <?= h($selected['created_at']) ?> UTC</p><p class="notes"><?= h($selected['notes']) ?></p><div class="table-scroll"><table><caption>Readings and inclusive limits</caption><thead><tr><th scope="col">Measurement</th><th scope="col">Reading</th><th scope="col">Limits</th><th scope="col">Result</th></tr></thead><tbody><?php foreach ($selected['measurements'] as $m): ?><tr><th scope="row"><?= h($m['name']) ?> (<?= h($m['unit']) ?>)</th><td><?= h($m['value']) ?></td><td><?= h($m['lower_limit']) ?> to <?= h($m['upper_limit']) ?></td><td class="<?= $m['passed'] ? 'pass' : 'fail' ?>"><?= verdict($m['passed']) ?></td></tr><?php endforeach ?></tbody></table></div><p><a href="/api/runs/<?= h($selected['id']) ?>">Open this run as JSON</a></p></article><?php endif ?>
</section>
</div>
</main><footer>A local bench notebook. Use synthetic data when sharing examples.</footer>
</body></html>
