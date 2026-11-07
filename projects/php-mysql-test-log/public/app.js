'use strict';
const form = document.querySelector('#run-form');
const readings = document.querySelector('#measurements');
const add = document.querySelector('#add-reading');
const feedback = document.querySelector('#form-feedback');
function refreshRows() {
  [...readings.children].forEach((row, index) => {
    row.querySelector('legend').textContent = `Measurement ${index + 1}`;
    row.querySelector('.remove').disabled = readings.children.length === 1;
  });
  add.disabled = readings.children.length >= 100;
}
function fieldLabel(path) {
  const parts = path.split('.');
  if (parts[0] === 'measurements' && /^\d+$/.test(parts[1] || '')) {
    const label = {name: 'name', unit: 'unit', value: 'reading', lower_limit: 'lower limit', upper_limit: 'upper limit'}[parts[2]];
    return `Measurement ${Number(parts[1]) + 1}${label ? ', ' + label : ''}`;
  }
  return {sample: 'Sample name', notes: 'Notes', measurements: 'Measurements'}[path] || 'Test run';
}
function addReading() {
  const fragment = document.querySelector('#reading-template').content.cloneNode(true);
  fragment.querySelector('.remove').addEventListener('click', event => {
    event.target.closest('fieldset').remove();
    refreshRows();
  });
  readings.append(fragment);
  refreshRows();
}
add.addEventListener('click', addReading);
addReading();
form.addEventListener('submit', async event => {
  event.preventDefault();
  const save = document.querySelector('#save-run');
  save.disabled = true;
  feedback.textContent = 'Saving your test run…';
  const measurements = [...readings.children].map(row => Object.fromEntries(
    [...row.querySelectorAll('[data-field]')].map(input => [input.dataset.field, input.value])
  ));
  try {
    const response = await fetch('/api/runs', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({sample: form.elements.sample.value, notes: form.elements.notes.value, measurements})
    });
    const result = await response.json();
    if (!response.ok) {
      feedback.textContent = result.fields
        ? Object.entries(result.fields).map(([field, message]) => `${fieldLabel(field)}: ${message}`).join(' ')
        : result.error;
      return;
    }
    window.location.assign(`/?run=${result.id}#run-detail`);
  } catch {
    feedback.textContent = 'The save could not be confirmed. Check saved runs before trying again to avoid a duplicate.';
  } finally {
    save.disabled = false;
  }
});
