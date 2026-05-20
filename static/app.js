/* ── Auth helpers ──────────────────────────────────────────────── */
function getToken() { return localStorage.getItem('token'); }

function setToken(t) { if(t) localStorage.setItem('token', t); else localStorage.removeItem('token'); }

async function authFetch(url, opts={}, ms=60000) {
  const token = getToken();
  if (token) {
    opts.headers = { ...opts.headers, 'Authorization': `Bearer ${token}` };
  }
  const ctrl = new AbortController();
  const id = setTimeout(() => ctrl.abort(), ms);
  try {
    const r = await fetch(url, { ...opts, signal: ctrl.signal });
    clearTimeout(id);
    if (r.status === 401) {
      setToken(null);
      window.location.href = '/login';
      throw new Error('Session expired');
    }
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    return r.json();
  } catch(e) { clearTimeout(id); throw e; }
}

/* ── State ─────────────────────────────────────────────────────── */
const S = {
  city: 'Lagos',
  season: '',
  n: 200,
  rowIdx: 170,
  lastRows: [],
  autoRefreshTimer: null,
  stateChart: null,
  osnrChart: null,
  user: null, // { id, username, role }
};

/* ── API Client ────────────────────────────────────────────────── */
const api = {
  status:    ()           => fetchWithTimeout('/api/status', {}, 10000),
  llmStatus: ()           => fetchWithTimeout('/api/llm-status', {}, 5000),
  run:       (c,s,n)     => { const p = new URLSearchParams({city:c,apply_ncc_drift:'true',n}); if(s) p.append('season',s); return authFetch('/api/run?'+p, {}, 90000); },
  context:   (c)         => authFetch(`/api/nigerian-context?city=${c}`, {}, 10000),
  allCities: ()          => authFetch('/api/nigerian-context/all-cities', {}, 10000),
  event:     (ev,c,idx)  => authFetch(`/api/simulate/event/${ev}?city=${c}&row_index=${idx}`, {}, 90000),
  diagnose:  (idx,c,s)   => { const p = new URLSearchParams({city:c}); if(s) p.append('season',s); return authFetch(`/api/diagnose/${idx}?`+p, {}, 90000); },
  me:        ()          => authFetch('/api/auth/me', {}, 10000),
  register:  (u,p,r)     => authFetch('/api/auth/register', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({username:u,password:p,role:r})}, 10000),
  listUsers: ()          => authFetch('/api/auth/users', {}, 10000),
  deleteUser:(id)        => authFetch(`/api/auth/users/${id}`, {method:'DELETE'}, 10000),
};

/* ── Fetch with timeout (public calls) ────────────────────────── */
async function fetchWithTimeout(url, opts={}, ms=60000) {
  const ctrl = new AbortController();
  const id = setTimeout(() => ctrl.abort(), ms);
  try {
    const r = await fetch(url, { ...opts, signal: ctrl.signal });
    clearTimeout(id);
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    return r.json();
  } catch(e) { clearTimeout(id); throw e; }
}

/* ── Format helpers ────────────────────────────────────────────── */
const fmt = {
  osnr:    v => v == null ? '—' : (+v).toFixed(2),
  ber:     v => v == null ? '—' : (+v).toExponential(2),
  lat:     v => v == null ? '—' : (+v).toFixed(1),
  pwr:     v => v == null ? '—' : (+v).toFixed(1),
  pct:     v => v == null ? '—' : (+v).toFixed(1) + '%',
};

/* ── Toast ─────────────────────────────────────────────────────── */
function toast(msg, type='ok') {
  const c = document.getElementById('toast-container');
  const t = document.createElement('div');
  t.className = `toast ${type}`;
  t.textContent = msg;
  c.appendChild(t);
  setTimeout(() => t.remove(), 4000);
}

/* ── Clock (Lagos = UTC+1) ─────────────────────────────────────── */
function updateClock() {
  const now = new Date(new Date().toLocaleString('en-US',{timeZone:'Africa/Lagos'}));
  const h = String(now.getHours()).padStart(2,'0');
  const m = String(now.getMinutes()).padStart(2,'0');
  const s = String(now.getSeconds()).padStart(2,'0');
  document.getElementById('clock').textContent = `${h}:${m}:${s}`;
}

/* ── Auth check ────────────────────────────────────────────────── */
async function checkAuth() {
  const token = getToken();
  if (!token) {
    window.location.href = '/login';
    return;
  }
  try {
    S.user = await api.me();
    document.body.className = 'auth-ready';
    document.getElementById('header').style.display = '';
    document.querySelector('.layout').style.display = '';
    // Show superadmin-only UI
    if (S.user.role === 'superadmin') {
      document.getElementById('user-mgmt-section').classList.remove('hidden');
    }
    afterAuth();
  } catch {
    setToken(null);
    window.location.href = '/login';
  }
}

/* ── API Status check ──────────────────────────────────────────── */
async function checkStatus() {
  try {
    const d = await api.status();
    const dot  = document.querySelector('.pulse-dot');
    const text = document.getElementById('api-status-text');
    dot.className  = 'pulse-dot live';
    document.getElementById('api-status').className = 'status-pill ok';
    text.textContent = 'API Live';
    const sv = document.querySelector('#hdr-season .val');
    if(d.current_season) sv.textContent = d.current_season.charAt(0).toUpperCase()+d.current_season.slice(1);
  } catch {
    const dot = document.querySelector('.pulse-dot');
    dot.className = 'pulse-dot dead';
    document.getElementById('api-status').className = 'status-pill err';
    document.getElementById('api-status-text').textContent = 'API Offline';
  }
  checkLLMStatus();
}

async function checkLLMStatus() {
  try {
    const llm = await fetchWithTimeout('/api/llm-status', {}, 5000);
    const el = document.getElementById('llm-status-text');
    if (llm.available) el.textContent = 'LLM Active';
    else               el.textContent = 'LLM Unavailable';
  } catch {
    const el = document.getElementById('llm-status-text');
    el.textContent = 'LLM Offline';
  }
}

/* ── Charts ────────────────────────────────────────────────────── */
function initCharts() {
  const donutCtx = document.getElementById('stateChart').getContext('2d');
  S.stateChart = new Chart(donutCtx, {
    type: 'doughnut',
    data: {
      labels: ['NORMAL','DEGRADING','CRITICAL'],
      datasets: [{ data: [0,0,0], backgroundColor: ['#00ff88','#f59e0b','#ef4444'], borderWidth: 2, borderColor: '#071224' }]
    },
    options: {
      cutout: '72%', plugins: { legend: { display: false }, tooltip: { enabled: true } },
      animation: { duration: 600 }
    }
  });

  const lineCtx = document.getElementById('osnrChart').getContext('2d');
  const grad = lineCtx.createLinearGradient(0, 0, 0, 200);
  grad.addColorStop(0, 'rgba(0,255,136,0.3)');
  grad.addColorStop(1, 'rgba(0,255,136,0)');
  S.osnrChart = new Chart(lineCtx, {
    type: 'line',
    data: {
      labels: [],
      datasets: [{
        label: 'OSNR (dB)', data: [],
        borderColor: '#00ff88', backgroundColor: grad,
        borderWidth: 2, pointRadius: 3, pointBackgroundColor: '#00ff88',
        tension: 0.4, fill: true,
      },{
        label: 'NCC Min (15 dB)', data: [],
        borderColor: '#ef4444', borderDash: [5,5], borderWidth: 1,
        pointRadius: 0, fill: false,
      }]
    },
    options: {
      responsive: true, maintainAspectRatio: true,
      plugins: { legend: { labels: { color: '#7090b0', font: { size: 11 } } } },
      scales: {
        x: { ticks: { color: '#3d5a7a', maxRotation: 0, maxTicksLimit: 8 }, grid: { color: 'rgba(255,255,255,.04)' } },
        y: { ticks: { color: '#7090b0' }, grid: { color: 'rgba(255,255,255,.04)' },
             title: { display: true, text: 'dB', color: '#3d5a7a', font: { size: 10 } } }
      }
    }
  });
}

/* ── Update KPI metrics ────────────────────────────────────────── */
function updateMetrics(rows) {
  if (!rows || !rows.length) return;
  const avg = key => rows.reduce((a,r)=>a+(+r[key]||0),0)/rows.length;
  const osnrAvg = avg('osnr_db');
  const berAvg  = avg('ber');
  const latAvg  = avg('latency_ms');
  const anomCount = rows.filter(r=>r.state==='CRITICAL'||r.state==='DEGRADING').length;

  setText('v-osnr', fmt.osnr(osnrAvg));
  setText('v-ber',  fmt.ber(berAvg));
  setText('v-lat',  fmt.lat(latAvg));
  setText('v-anom', anomCount);

  setBar('b-osnr', Math.min(100, Math.max(0, (osnrAvg-10)/15*100)), osnrAvg>=19?'green':osnrAvg>=15?'amber':'red');
  const berPct = berAvg<=1e-7?100:berAvg<=1e-5?60:20;
  setBar('b-ber',  berPct, berPct>70?'green':berPct>40?'amber':'red');
  setBar('b-lat',  Math.min(100,latAvg/150*100), latAvg<=25?'green':latAvg<=100?'amber':'red');
  const ap = (1-anomCount/rows.length)*100;
  setBar('b-anom', ap, ap>80?'green':ap>60?'amber':'red');
}

/* ── Update state donut ────────────────────────────────────────── */
function updateStateChart(dist) {
  if(!dist || !S.stateChart) return;
  const n = dist['NORMAL']||0, d = dist['DEGRADING']||0, c = dist['CRITICAL']||0;
  S.stateChart.data.datasets[0].data = [n,d,c];
  S.stateChart.update();
  const leg = document.getElementById('state-legend');
  leg.innerHTML = [
    { label:`Normal`, val:n, col:'#00ff88' },
    { label:`Degrading`, val:d, col:'#f59e0b' },
    { label:`Critical`, val:c, col:'#ef4444' },
  ].map(i=>`<div class="legend-item"><div class="legend-dot" style="background:${i.col}"></div>${i.label}: <strong>${i.val}</strong></div>`).join('');
}

/* ── Update OSNR line chart ────────────────────────────────────── */
function updateOsnrChart(rows) {
  if(!rows || !S.osnrChart) return;
  S.osnrChart.data.labels = rows.map(r=>r.time);
  S.osnrChart.data.datasets[0].data = rows.map(r=>+r.osnr_db);
  S.osnrChart.data.datasets[1].data = rows.map(()=>15);
  S.osnrChart.data.datasets[0].pointBackgroundColor = rows.map(r=>
    r.state==='CRITICAL'?'#ef4444':r.state==='DEGRADING'?'#f59e0b':'#00ff88'
  );
  S.osnrChart.update();
}

/* ── Update NCC compliance ─────────────────────────────────────── */
function updateCompliance(c) {
  if(!c) return;
  setCompBar('comp-osnr','cv-osnr', c.osnr_compliance_pct);
  setCompBar('comp-ber', 'cv-ber',  c.ber_compliance_pct);
  setCompBar('comp-lat', 'cv-lat',  c.latency_compliance_pct);
  const el = document.getElementById('comp-overall');
  const ok = c.overall_status === 'COMPLIANT';
  el.textContent = ok ? '✔ Compliant' : '✘ Non-Compliant';
  el.className = 'comp-status ' + (ok?'ok':'bad');
}

function setCompBar(barId, valId, pct) {
  const bar = document.getElementById(barId);
  const val = document.getElementById(valId);
  if(!bar||!val||pct==null) return;
  bar.style.width = pct+'%';
  bar.className = 'comp-bar';
  if(pct<70) bar.classList.add('crit');
  else if(pct<90) bar.classList.add('warn');
  val.textContent = fmt.pct(pct);
}

/* ── Update diagnosis panel ────────────────────────────────────── */
function updateDiagnosis(d, city, season) {
  const card    = document.getElementById('diag-card');
  const empty   = document.getElementById('diag-empty');
  const content = document.getElementById('diag-content');
  empty.classList.add('hidden');
  content.classList.remove('hidden');

  const state = (d.telemetry?.state || d.state || '').toUpperCase();
  const sb = document.getElementById('d-state-badge');
  sb.textContent = state || '—';
  sb.className = 'badge ' + (state || '');

  const src = (d.source||'').replace('_',' ').toUpperCase();
  document.getElementById('d-source-badge').textContent = src || '—';
  document.getElementById('d-urgency-badge').textContent = d.urgency || '—';
  const nccBadge = document.getElementById('d-ncc-badge');
  nccBadge.textContent = d.ncc_compliant ? 'NCC ✔' : 'NCC ✘';
  nccBadge.className   = 'badge ncc '+(d.ncc_compliant?'ok':'fail');

  setText('d-diagnosis', d.diagnosis||'—');
  setText('d-root',      d.root_cause||'—');
  setText('d-suggest',   d.suggestion||'—');
  setText('d-conf',      d.confidence||'—');
  document.getElementById('d-explanation').textContent = d.explanation||'';

  const t = d.telemetry||{};
  document.getElementById('d-city-season').textContent = `${city||S.city} | ${season||S.season||'auto'} season`;
  document.getElementById('d-telemetry').textContent = t.osnr_db!=null
    ? `OSNR ${fmt.osnr(t.osnr_db)} dB | BER ${fmt.ber(t.ber)} | Latency ${fmt.lat(t.latency_ms)} ms`
    : '';

  card.classList.add('flash');
  setTimeout(()=>card.classList.remove('flash'), 700);
}

/* ── Update telemetry table ────────────────────────────────────── */
function updateTable(rows) {
  const body = document.getElementById('telem-body');
  if(!rows||!rows.length){ body.innerHTML='<tr><td colspan="10" class="table-empty">No data</td></tr>'; return; }
  S.lastRows = rows;
  body.innerHTML = rows.map(r=>`
    <tr class="${r.state||''}">
      <td>${r.time??'—'}</td>
      <td>${r.hour_of_day??'—'}</td>
      <td>${fmt.osnr(r.osnr_db)}</td>
      <td>${fmt.ber(r.ber)}</td>
      <td>${fmt.pwr(r.power_dbm)}</td>
      <td>${fmt.lat(r.latency_ms)}</td>
      <td>${r.event||'—'}</td>
      <td>${(r.fault_cause||'NONE').replace(/_/g,' ')}</td>
      <td><span class="state-tag ${r.state||''}">${r.state||'—'}</span></td>
      <td style="font-size:10px;max-width:140px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="${r.recommended_action||''}">${(r.recommended_action||'—').replace(/_/g,' ')}</td>
    </tr>`).join('');
}

/* ── Run Pipeline ──────────────────────────────────────────────── */
async function runPipeline() {
  const btn = document.getElementById('run-btn');
  btn.classList.add('loading'); btn.textContent = '⏳ Running…';
  try {
    const d = await api.run(S.city, S.season, S.n);
    const sum = d.summary||{};
    updateMetrics(d.rows||[]);
    updateStateChart(sum.state_distribution);
    updateOsnrChart(d.rows||[]);
    updateCompliance(sum.ncc_compliance);
    updateTable(d.rows||[]);

    window._lastSummary = sum;
    window._lastNcc = sum.ncc_compliance;

    authFetch('/api/logs', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({city:S.city, season:S.season||null, n:S.n, rows:d.rows||[], summary: sum, ncc_compliance: sum.ncc_compliance})
    }).then(() => loadLogs()).catch(() => {});

    if(d.rows&&d.rows.length){
      document.getElementById('hdr-city-active').querySelector('.val').textContent = S.city;
    }
    toast(`Pipeline complete — ${sum.total_records||0} records | ${S.city}`, 'ok');
  } catch(e) {
    toast('Pipeline error: '+e.message, 'err');
  } finally {
    btn.classList.remove('loading');
    btn.innerHTML = '<span class="run-icon">▶</span> Run Pipeline';
  }
}

/* ── Diagnose row ──────────────────────────────────────────────── */
async function diagnoseRow() {
  const idx = parseInt(document.getElementById('row-idx').value)||0;
  document.getElementById('diag-btn').textContent = '…';
  try {
    const d = await api.diagnose(idx, S.city, S.season);
    updateDiagnosis(d, S.city, S.season);
    updateLLMBadge(d.source);
    window._lastDiagnosis = d;
    toast(`Diagnosis for row ${idx}`, 'inf');
  } catch(e) {
    toast('Diagnose error: '+e.message, 'err');
  } finally {
    document.getElementById('diag-btn').textContent = 'Diagnose';
  }
}

/* ── Fault event injection ─────────────────────────────────────── */
async function injectEvent(evType, btn) {
  btn.classList.add('loading');
  const orig = btn.innerHTML;
  btn.querySelector('.f-name').textContent = 'Loading…';
  try {
    const idx = parseInt(document.getElementById('row-idx').value)||100;
    const d = await api.event(evType, S.city, idx);
    updateDiagnosis(d, S.city, S.season);
    updateLLMBadge(d.source);
    window._lastDiagnosis = d;
    toast(`Event injected: ${evType.replace(/_/g,' ')}`, 'ok');
  } catch(e) {
    toast('Event error: '+e.message, 'err');
  } finally {
    btn.classList.remove('loading');
    btn.innerHTML = orig;
  }
}

/* ── City profile modal ────────────────────────────────────────── */
async function showCityProfile() {
  try {
    const d = await api.context(S.city);
    const b = d.baselines||{};
    const r = d.risk_factors||{};
    document.getElementById('modal-title').textContent = `${S.city} — NCC Profile`;
    document.getElementById('modal-body').innerHTML = `
      <p style="color:var(--txt2);font-size:13px;margin-bottom:16px">${d.description||''}</p>
      <div class="profile-grid">
        <div class="profile-item"><div class="p-lbl">OSNR Baseline</div><div class="p-val">${fmt.osnr(b.osnr_db)} dB</div></div>
        <div class="profile-item"><div class="p-lbl">Latency Baseline</div><div class="p-val">${fmt.lat(b.latency_ms)} ms</div></div>
        <div class="profile-item"><div class="p-lbl">BER Baseline</div><div class="p-val">${fmt.ber(b.ber)}</div></div>
        <div class="profile-item"><div class="p-lbl">Availability</div><div class="p-val">${b.availability_pct}%</div></div>
        <div class="profile-item"><div class="p-lbl">Peak Hours</div><div class="p-val" style="font-size:14px">${(r.peak_hours||[]).join(', ')}:00</div></div>
        <div class="profile-item"><div class="p-lbl">Gen. Failure Risk</div><div class="p-val" style="font-size:14px">${((r.generator_failure_risk||0)*100).toFixed(0)}%/day</div></div>
      </div>
      <p style="font-size:11px;color:var(--txt3);margin-top:8px">Season detected: ${d.current_season||'—'}</p>`;
    document.getElementById('modal-overlay').classList.remove('hidden');
  } catch(e) {
    toast('Could not load city profile', 'err');
  }
}

/* ── LLM badge ─────────────────────────────────────────────────── */
function updateLLMBadge(source) {
  const el = document.getElementById('llm-status-text');
  if(source==='llm') el.textContent = 'LLM Active';
  else               el.textContent = 'Rule Engine';
}

/* ── DOM helpers ───────────────────────────────────────────────── */
function setText(id, val) { const el=document.getElementById(id); if(el) el.textContent=val; }
function setBar(id, pct, cls) {
  const el=document.getElementById(id); if(!el) return;
  el.style.width = Math.min(100,Math.max(0,pct))+'%';
  el.className = 'metric-bar-fill '+cls;
}

/* ── Export CSV ────────────────────────────────────────────────── */
function exportCSV() {
  if(!S.lastRows.length){ toast('No data to export','err'); return; }
  const keys = Object.keys(S.lastRows[0]);
  const csv  = [keys.join(','), ...S.lastRows.map(r=>keys.map(k=>JSON.stringify(r[k]??'')).join(','))].join('\n');
  const a = document.createElement('a');
  a.href = 'data:text/csv;charset=utf-8,' + encodeURIComponent(csv);
  a.download = `swift_fhs_${S.city}_${Date.now()}.csv`;
  a.click();
  toast('CSV exported','ok');
}

/* ── Auto-refresh ──────────────────────────────────────────────── */
function setupAutoRefresh(on) {
  clearInterval(S.autoRefreshTimer);
  if(on) S.autoRefreshTimer = setInterval(runPipeline, 30000);
}

/* ── Chat Agent ───────────────────────────────────────────────── */
const chat = {
  async send(msg) {
    const mode = document.getElementById('chat-mode').checked ? 'technical' : 'simple';
    const r = await authFetch('/api/chat', {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({message: msg, mode, context: {
        summary: window._lastSummary || null,
        ncc: window._lastNcc || null,
        diagnosis: window._lastDiagnosis || null,
      }})
    });
    return r;
  },
  addMsg(role, text) {
    const box = document.getElementById('chat-msgs');
    const d = document.createElement('div');
    d.className = 'chat-msg ' + role;
    d.textContent = text;
    box.appendChild(d);
    box.scrollTop = box.scrollHeight;
  },
};

function toggleChat() {
  const p = document.getElementById('chat-panel');
  p.classList.remove('minimized');
  p.classList.toggle('hidden');
  if(!p.classList.contains('hidden')) document.getElementById('chat-input').focus();
}

function minimizeChat() {
  const p = document.getElementById('chat-panel');
  p.classList.toggle('minimized');
}

function chatModeChanged() {
  const el = document.getElementById('chat-mode-lbl');
  el.textContent = document.getElementById('chat-mode').checked ? 'Technical' : 'Simple';
}

document.addEventListener('click', e => {
  const p = document.getElementById('chat-panel');
  if(p.classList.contains('minimized') && p.contains(e.target) && !e.target.closest('.chat-hdr-minimize')) {
    p.classList.remove('minimized');
    document.getElementById('chat-input').focus();
  }
});

async function doChat() {
  const inp = document.getElementById('chat-input');
  const msg = inp.value.trim();
  if(!msg) return;
  inp.value = '';
  chat.addMsg('user', msg);
  chat.addMsg('assistant', '…');
  try {
    const r = await chat.send(msg);
    const msgs = document.getElementById('chat-msgs');
    msgs.removeChild(msgs.lastChild);
    chat.addMsg('assistant', r.reply || 'No response');
  } catch(e) {
    const msgs = document.getElementById('chat-msgs');
    msgs.removeChild(msgs.lastChild);
    chat.addMsg('assistant', 'Error: ' + e.message);
  }
}

/* ── Saved Logs ───────────────────────────────────────────────── */
async function loadLogs() {
  try {
    const r = await authFetch('/api/logs');
    const data = await r;
    const body = document.getElementById('logs-body');
    if(!data.runs || !data.runs.length) {
      body.innerHTML = '<tr><td colspan="6" class="table-empty">No saved runs</td></tr>';
      return;
    }
    body.innerHTML = data.runs.map(run => `
      <tr>
        <td>#${run.id}</td>
        <td>${run.created_at||'—'}</td>
        <td>${run.city||'—'}</td>
        <td>${run.season||'—'}</td>
        <td>${run.n_samples||'—'}</td>
        <td><button class="outline-btn small" onclick="deleteLog(${run.id})">Delete</button></td>
      </tr>
    `).join('');
  } catch(e) {
    console.error('Failed to load logs:', e);
  }
}

async function deleteLog(runId) {
  if(!confirm(`Delete pipeline run #${runId}?`)) return;
  try {
    await authFetch(`/api/logs/${runId}`, {method:'DELETE'});
    loadLogs();
  } catch(e) {
    console.error('Failed to delete log:', e);
  }
}

/* ── User Management (superadmin) ──────────────────────────────── */
async function loadUsers() {
  try {
    const data = await api.listUsers();
    const body = document.getElementById('users-body');
    if (!data.users || !data.users.length) {
      body.innerHTML = '<tr><td colspan="5" class="table-empty">No users</td></tr>';
      return;
    }
    body.innerHTML = data.users.map(u => `
      <tr>
        <td>#${u.id}</td>
        <td>${u.username}</td>
        <td><span class="state-tag ${u.role === 'superadmin' ? 'NORMAL' : 'DEGRADING'}">${u.role}</span></td>
        <td>${u.created_at || '—'}</td>
        <td>${u.username !== S.user?.username
          ? `<button class="outline-btn small" onclick="deleteUser(${u.id}, '${u.username}')">Delete</button>`
          : '<span style="color:var(--txt3);font-size:11px">you</span>'}
        </td>
      </tr>
    `).join('');
  } catch(e) {
    toast('Failed to load users', 'err');
  }
}

async function deleteUser(id, username) {
  if (!confirm(`Delete user "${username}"?`)) return;
  try {
    await api.deleteUser(id);
    toast(`User "${username}" deleted`, 'ok');
    loadUsers();
  } catch(e) {
    toast('Failed to delete user', 'err');
  }
}

/* ── Logout ─────────────────────────────────────────────────────── */
function logout() {
  setToken(null);
  window.location.href = '/login';
}

/* ── Init (after auth check) ──────────────────────────────────── */
function afterAuth() {
  initCharts();
  updateClock();
  setInterval(updateClock, 1000);
  checkStatus();
  setInterval(checkStatus, 15000);

  // City buttons
  document.querySelectorAll('.city-btn').forEach(b => b.addEventListener('click', () => {
    document.querySelectorAll('.city-btn').forEach(x=>x.classList.remove('active'));
    b.classList.add('active');
    S.city = b.dataset.city;
    document.querySelector('#hdr-city-active .val').textContent = S.city;
    toast(`City set to ${S.city}`,'inf');
  }));

  // Season buttons
  document.querySelectorAll('.season-btn').forEach(b => b.addEventListener('click', () => {
    document.querySelectorAll('.season-btn').forEach(x=>x.classList.remove('active'));
    b.classList.add('active');
    S.season = b.dataset.season;
  }));

  // Sample count slider
  const slider = document.getElementById('sample-count');
  slider.addEventListener('input', () => { S.n=+slider.value; document.getElementById('sample-val').textContent=S.n; });

  // Run button
  document.getElementById('run-btn').addEventListener('click', runPipeline);

  // Diagnose button
  document.getElementById('diag-btn').addEventListener('click', diagnoseRow);

  // Row index input
  document.getElementById('row-idx').addEventListener('change', e => { S.rowIdx=+e.target.value; });

  // Fault buttons
  document.querySelectorAll('.fault-btn').forEach(b => b.addEventListener('click', () => injectEvent(b.dataset.event, b)));

  // City profile
  document.getElementById('city-profile-btn').addEventListener('click', showCityProfile);
  document.getElementById('modal-close').addEventListener('click', () => document.getElementById('modal-overlay').classList.add('hidden'));
  document.getElementById('modal-overlay').addEventListener('click', e => { if(e.target===e.currentTarget) e.currentTarget.classList.add('hidden'); });

  // Export
  document.getElementById('export-btn').addEventListener('click', exportCSV);

  // Auto-refresh toggle
  document.getElementById('auto-refresh').addEventListener('change', e => setupAutoRefresh(e.target.checked));

  // Chat toggle, minimize & send
  document.getElementById('chat-toggle').addEventListener('click', toggleChat);
  document.getElementById('chat-close').addEventListener('click', toggleChat);
  document.getElementById('chat-minimize').addEventListener('click', minimizeChat);
  document.getElementById('chat-send').addEventListener('click', doChat);
  document.getElementById('chat-input').addEventListener('keydown', e => { if(e.key==='Enter') doChat(); });
  document.getElementById('chat-mode').addEventListener('change', chatModeChanged);

  // Logs refresh
  document.getElementById('logs-refresh').addEventListener('click', loadLogs);

  // Logout
  document.getElementById('logout-btn').addEventListener('click', logout);

  // User management (superadmin only)
  const userMgmt = document.getElementById('user-mgmt-section');
  if (userMgmt && S.user?.role === 'superadmin') {
    document.getElementById('users-refresh').addEventListener('click', loadUsers);
    document.getElementById('user-add-btn').addEventListener('click', () => {
      document.getElementById('user-modal-overlay').classList.remove('hidden');
    });
    document.getElementById('user-modal-close').addEventListener('click', () => {
      document.getElementById('user-modal-overlay').classList.add('hidden');
    });
    document.getElementById('user-modal-overlay').addEventListener('click', e => {
      if (e.target === e.currentTarget) e.currentTarget.classList.add('hidden');
    });
    document.getElementById('user-add-form').addEventListener('submit', async (e) => {
      e.preventDefault();
      const username = document.getElementById('user-form-username').value.trim();
      const password = document.getElementById('user-form-password').value;
      const role = document.getElementById('user-form-role').value;
      const errEl = document.getElementById('user-form-error');
      errEl.style.display = 'none';
      if (!username || !password) { errEl.textContent = 'All fields required'; errEl.style.display = 'block'; return; }
      try {
        await api.register(username, password, role);
        toast(`User "${username}" created`, 'ok');
        document.getElementById('user-modal-overlay').classList.add('hidden');
        document.getElementById('user-add-form').reset();
        loadUsers();
      } catch(e) {
        errEl.textContent = e.message || 'Failed to create user';
        errEl.style.display = 'block';
      }
    });
    loadUsers();
  }

  // Run on load
  runPipeline();
  loadLogs();
}

/* ── Bootstrap ────────────────────────────────────────────────── */
document.addEventListener('DOMContentLoaded', () => {
  document.body.className = 'auth-loading';
  document.getElementById('header').style.display = 'none';
  document.querySelector('.layout').style.display = 'none';
  checkAuth();
});