const $ = id => document.getElementById(id);
const names = {machine_fault:"Machine fault",cycle_drift:'Cycle time drifting',fault_rate:'Repeated faults',availability:'Availability below target',data_quality:'Unusable readings',connection_lost:'Machine data disconnected'};
const pct = n => n == null ? 'Unknown' : `${(n*100).toFixed(1)}%`;
const clock = t => t == null ? 'Unknown' : new Date(t*1000).toLocaleTimeString();
async function request(path, options) {
  const response = await fetch(path, options);
  if (!response.ok) throw new Error(`Request failed (${response.status}). Refresh and try again.`);
  return response.json();
}
function node(tag, text, cls) { const el=document.createElement(tag); el.textContent=text; if(cls)el.className=cls; return el; }
function alertView(a) {
  const box=node('article','','alert'+(a.state==='cleared'?' cleared':''));
  box.append(node('h3', names[a.rule] || a.rule), node('p',a.message), node('small',`${a.state} · First seen ${clock(a.opened)} · ${a.occurrences} observations`));
  if(a.state==='active') {
    const button=node('button','Acknowledge');
    button.onclick=async()=>{button.disabled=true; try {await request(`/api/alerts/${a.id}/ack`,{method:'POST'});await refresh();}catch(e){showError(e.message);button.disabled=false;}};
    box.append(button);
  }
  if(a.acknowledged)box.append(node('small',`Reviewed ${clock(a.acknowledged)}`));
  return box;
}
function showError(message){$('error').hidden=false;$('error').textContent=message;}
async function refresh(){
  try {
    const [s,rows]=await Promise.all([request('/api/status'),request('/api/readings?limit=60')]);
    $('error').hidden=true;
    $('connection').textContent=`Monitor updated ${clock(s.now)}`;
    $('condition').textContent={healthy:'Within configured limits',attention:'Needs attention',unknown:'Condition unknown'}[s.condition];
    $('condition').className=`condition ${s.condition}`;
    const v=s.latest?.raw || {};
    $('machine').textContent=s.condition==='unknown'?'Current machine condition cannot be confirmed. Inspect the rejected readings below.':`Motor ${v.motor_running?'running':'stopped'} · ${v.cycle_count} completed cycles · Fault code ${v.fault_code}`;
    $('availability').textContent=pct(s.metrics.availability);
    $('performance').textContent=pct(s.metrics.performance);
    $('fault-rate').textContent=s.metrics.fault_rate_per_minute==null?'Unknown':`${s.metrics.fault_rate_per_minute.toFixed(1)}/min`;
    $('drift').textContent=pct(s.metrics.cycle_time_drift);
    $('coverage').textContent=`Last ${s.config.window_seconds} seconds: ${s.metrics.observed_seconds.toFixed(1)} seconds of usable intervals (${pct(s.metrics.coverage)} coverage). Target cycle: ${s.config.ideal_cycle_seconds}s. Missing intervals are excluded.`;
    const active=s.alerts.filter(a=>a.state!=='cleared');
    $('alert-count').textContent=`${active.length} open`;
    // Preserve focused acknowledgement buttons during background refresh.
    if(!$('alerts').contains(document.activeElement)) $('alerts').replaceChildren(...(active.length?active.map(alertView):[node('p','No open alerts. Continue observing the line.')]));
    $('history').replaceChildren(...s.alerts.filter(a=>a.state==='cleared').map(alertView));
    $('report').textContent=s.report;
    $('demo').hidden=!s.demo;
    if(!s.demo){$('source-label').textContent='Configured OPC UA source · Read-only monitoring';$('scope').textContent='Observation only. This dashboard does not provide machine safety controls. Times shown in your local timezone.';}
    if(s.demo)$('scenario-status').textContent=`Applied: ${s.scenario.replaceAll('_',' ')}`;
    $('readings').replaceChildren(...rows.map(r=>{
      const tr=document.createElement('tr');const v=r.raw;
      [clock(r.received),v.cycle_count??'—',v.cycle_time??'—',typeof v.motor_running==='boolean'?(v.motor_running?'Running':'Stopped'):'—',v.fault_code??'—',r.accepted?'Accepted':r.reasons.join(', ')].forEach(value=>tr.append(node('td',String(value))));
      if(!r.accepted)tr.className='rejected';return tr;
    }));
    const points=rows.toReversed();
    const accepted=points.filter(r=>r.accepted);
    const svg=$('trend');svg.replaceChildren();
    if(accepted.length){
      const max=Math.max(s.config.ideal_cycle_seconds*2,...accepted.map(r=>r.raw.cycle_time));
      let path='';let segment=false;
      points.forEach((r,i)=>{if(!r.accepted){segment=false;return;}path+=`${segment?'L':'M'}${30+i*840/Math.max(1,points.length-1)},${115-r.raw.cycle_time/max*85} `;segment=true;});
      const line=document.createElementNS('http://www.w3.org/2000/svg','path');line.setAttribute('d',path);line.setAttribute('fill','none');line.setAttribute('stroke','#145f87');line.setAttribute('stroke-width','3');svg.append(line);
      const label=document.createElementNS('http://www.w3.org/2000/svg','text');label.setAttribute('x','16');label.setAttribute('y','20');label.setAttribute('font-size','12');label.textContent=`Cycle time (seconds), scale 0–${max.toFixed(1)}. Gaps are rejected readings.`;svg.append(label);
    }
  } catch(error) {
    $('connection').textContent='Monitor unavailable';
    $('condition').textContent='Condition unknown';$('condition').className='condition unknown';
    for(const id of ['availability','performance','fault-rate','drift'])$(id).textContent='Unknown';
    showError(error.message);
  }
}
async function apply(scenario){try{await request('/api/scenario',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({scenario})});await refresh();}catch(e){showError(e.message);}}
$('scenario-form').onsubmit=e=>{e.preventDefault();apply($('scenario').value);};
$('restore').onclick=()=>{$('scenario').value='normal';apply('normal');};
(async()=>{while(true){await refresh();await new Promise(resolve=>setTimeout(resolve,1000));}})();
