/* ── Auth helpers ──────────────────────────────────────────────── */
function getToken() { return localStorage.getItem('token'); }

function setToken(t) { 
  if(t) { 
    localStorage.setItem('token', t); 
  } else { 
    localStorage.removeItem('token');
  } 
}

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
      throw new Error('Session expired');
    }
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    return r.json();
  } catch(e) {
    clearTimeout(id);
    throw e;
  }
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
  user: null,
  telemFull: [],
  logsFull: [],
  telemShowAll: false,
  logsShowAll: false,
  weather: null,
  unreadCount: 0,
  _unreadPollTimer: null,
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
  summarize: (data)      => authFetch('/api/summarize', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)}, 30000),
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

/* ── Clock (city-aware, all Nigeria = WAT/UTC+1) ─────────────── */
const CITY_TIMEZONES = {
  Lagos: 'Africa/Lagos', Abuja: 'Africa/Lagos',
  PortHarcourt: 'Africa/Lagos', Kano: 'Africa/Lagos',
};
function updateClock() {
  const tz = CITY_TIMEZONES[S.city] || 'Africa/Lagos';
  const now = new Date(new Date().toLocaleString('en-US',{timeZone: tz}));
  const h = String(now.getHours()).padStart(2,'0');
  const m = String(now.getMinutes()).padStart(2,'0');
  const s = String(now.getSeconds()).padStart(2,'0');
  document.getElementById('clock').textContent = `${h}:${m}:${s}`;
  // Update label to show city name
  const lbl = document.querySelector('#hdr-time .lbl');
  if (lbl) lbl.textContent = S.city + ' Time';
}

/* ── Weather ──────────────────────────────────────────────────── */
async function fetchWeather() {
  try {
    const d = await authFetch(`/api/weather?city=${S.city}`, {}, 15000);
    S.weather = d;
    const el = document.getElementById('hdr-weather');
    if (el) {
      if (d.error || d.description === 'Unavailable') {
        el.querySelector('.val').innerHTML = `🌡️ N/A`;
        el.title = d.error || 'Weather unavailable';
      } else {
        const temp = d.temperature != null ? d.temperature + '°C' : '--';
        el.querySelector('.val').innerHTML = `${d.icon || '🌡️'} ${temp} · ${d.description || ''}`;
        el.title = `Humidity: ${d.humidity ?? '--'}% · Wind: ${d.wind_speed ?? '--'} km/h`;
      }
    }
  } catch(e) {
    console.error('[WEATHER] Fetch failed:', e.message || e);
    const el = document.getElementById('hdr-weather');
    if (el) el.querySelector('.val').innerHTML = '🌡️ N/A';
  }
}

/* ── Unread badge ─────────────────────────────────────────────── */
async function fetchUnreadCount() {
  try {
    const d = await authFetch('/api/cases/unread', {}, 8000);
    const count = d.unread || 0;
    S.unreadCount = count;
    // Panel title badge
    const badge = document.getElementById('unread-badge');
    if (badge) {
      badge.textContent = count;
      badge.style.display = count > 0 ? 'inline-flex' : 'none';
    }
    // Floating action button badge
    const fabBadge = document.getElementById('fab-unread-badge');
    if (fabBadge) {
      fabBadge.textContent = count;
      fabBadge.style.display = count > 0 ? 'flex' : 'none';
    }
  } catch { /* silent */ }
}

/* ── Auth check ────────────────────────────────────────────────── */
let _sessionTimer = null;
function startSessionTimer() {
  if (_sessionTimer) clearTimeout(_sessionTimer);
  _sessionTimer = setTimeout(() => {
    setToken(null);
    localStorage.setItem('_session_msg', 'Your session has expired. Please log in again.');
    window.location.href = '/';
  }, 3 * 60 * 1000); // 3 minutes
}
/* Reset timer on any user activity */
['click','keydown','mousemove','touchstart'].forEach(evt => {
  document.addEventListener(evt, () => { if (getToken()) startSessionTimer(); }, {passive:true});
});
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
    if (S.user.role === 'superadmin') {
      document.getElementById('user-mgmt-section').classList.remove('hidden');
    }
    try { applyTheme(S.user.profile?.theme || localStorage.getItem('oasis-theme') || 'dark'); } catch {}
    try { updateProfileUI(); } catch {}
    startSessionTimer();
    afterAuth();
  } catch (e) {
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

  const osnrPct = Math.min(100, Math.max(0, (osnrAvg-10)/15*100));
  setBar('b-osnr', osnrPct, osnrAvg>=19?'green':osnrAvg>=15?'amber':'red');
  setText('b-osnr-lbl', fmt.osnr(osnrAvg) + ' dB');
  const berPct = berAvg<=1e-7?100:berAvg<=1e-5?60:20;
  setBar('b-ber',  berPct, berPct>70?'green':berPct>40?'amber':'red');
  setText('b-ber-lbl', fmt.ber(berAvg));
  const latPct = Math.min(100,latAvg/150*100);
  setBar('b-lat',  latPct, latAvg<=25?'green':latAvg<=100?'amber':'red');
  setText('b-lat-lbl', fmt.lat(latAvg) + ' ms');
  const ap = (1-anomCount/rows.length)*100;
  setBar('b-anom', ap, ap>80?'green':ap>60?'amber':'red');
  setText('b-anom-lbl', anomCount + '/' + rows.length);
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

/* ── 4-Line Summary ───────────────────────────────────────────── */
function updateSummary(r) {
  const card = document.getElementById('summary-card');
  const body = document.getElementById('summary-body');
  const empty = document.getElementById('summary-empty');
  const badge = document.getElementById('summary-source-badge');
  if (!r.lines || !r.lines.length) {
    card.classList.add('hidden');
    empty.classList.remove('hidden');
    return;
  }
  card.classList.remove('hidden');
  empty.classList.add('hidden');
  badge.textContent = (r.source||'').toUpperCase();
  badge.className = 'badge ' + (r.source||'rule');
  body.innerHTML = r.lines.map((line, i) => {
    const cls = i === 0 ? 'problem' : i === r.lines.length-1 ? 'solution' : '';
    return `<div class="summary-line ${cls}">${line}</div>`;
  }).join('');
  card.classList.add('flash');
  setTimeout(()=>card.classList.remove('flash'), 700);
}

/* ── Update telemetry table ────────────────────────────────────── */
function renderTelemRows(rows) {
  const body = document.getElementById('telem-body');
  if(!rows||!rows.length){ body.innerHTML='<tr><td colspan="10" class="table-empty">No data</td></tr>'; return; }
  S.lastRows = rows;
  const show = S.telemShowAll ? rows : rows.slice(0, 5);
  body.innerHTML = show.map(r=>`
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
  const toggle = document.getElementById('telem-view-toggle');
  if(rows.length > 5) {
    toggle.classList.remove('hidden');
    toggle.textContent = S.telemShowAll ? 'Show Less' : `View ${rows.length - 5} More`;
  } else {
    toggle.classList.add('hidden');
  }
}

function toggleTelemView() {
  S.telemShowAll = !S.telemShowAll;
  renderTelemRows(S.telemFull);
}

function updateTable(rows) {
  S.telemFull = rows || [];
  S.telemShowAll = false;
  renderTelemRows(S.telemFull);
}

/* ── Run Pipeline ──────────────────────────────────────────────── */
async function runPipeline() {
  const btn = document.getElementById('run-btn');
  btn.classList.add('loading'); btn.textContent = '⏳ Running…';
  
  // Close sidebar on mobile
  const sidebar = document.getElementById('sidebar');
  const overlay = document.getElementById('sidebar-overlay');
  if (sidebar.classList.contains('open')) {
    sidebar.classList.remove('open');
    overlay.classList.add('hidden');
  }
  
  // Show pipeline running toast
  toast('Pipeline running...', 'inf');
  
  try {
    const d = await api.run(S.city, S.season, S.n);
    const sum = d.summary||{};
    updateMetrics(d.rows||[]);
    updateStateChart(sum.state_distribution);
    updateOsnrChart(d.rows||[]);
    updateCompliance(sum.ncc_compliance);
    updateTable(d.rows||[]);
    drawTwin(d.rows||[]);

    window._lastSummary = sum;
    window._lastNcc = sum.ncc_compliance;
    window._lastRows = d.rows||[];

    authFetch('/api/logs', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({city:S.city, season:S.season||null, n:S.n, rows:d.rows||[], summary: sum, ncc_compliance: sum.ncc_compliance})
    }).then(() => loadLogs()).catch(() => {});

    if(d.rows&&d.rows.length){
      document.getElementById('hdr-city-active').querySelector('.val').textContent = S.city;
    }

    logActivity('pipeline', `Pipeline run: <strong>${sum.total_records||0}</strong> records in <strong>${S.city}</strong> | Compliant: <strong>${sum.ncc_compliance?.overall_status||'?'}</strong>`);
    loadActivities();

    // Generate 4-line summary
    api.summarize({summary: sum, ncc: sum.ncc_compliance, diagnosis: window._lastDiagnosis||{}})
      .then(r => updateSummary(r))
      .catch(() => {});

    // Show explanation bar
    const eb = document.getElementById('explanation-bar');
    eb.classList.add('show');
    setTimeout(() => eb.classList.remove('show'), 15000);

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
    logActivity('diagnose', `Diagnosed row <strong>#${idx}</strong> in <strong>${S.city}</strong> — ${d.diagnosis||''}`);
    toast(`Diagnosis for row ${idx}`, 'inf');
    document.getElementById('diag-card').scrollIntoView({behavior:'smooth',block:'center'});

    // Generate 4-line summary
    const sum = window._lastSummary||{};
    api.summarize({diagnosis: d, summary: sum, ncc: sum.ncc_compliance||{}})
      .then(r => updateSummary(r))
      .catch(() => {});
  } catch(e) {
    toast('Diagnose error: '+e.message, 'err');
  } finally {
    document.getElementById('diag-btn').textContent = 'Diagnose';
  }
}

/* ── Fault event injection with feedback ────────────────────────── */

/* ── Send Summary to Phone ────────────────────────────────────── */
async function sendSummaryToPhone() {
  const btn = document.getElementById('send-summary-btn');
  if (!btn || btn.classList.contains('sending')) return;

  const sum = window._lastSummary;
  if (!sum || !sum.total_records) {
    toast('Run the pipeline first to generate a summary', 'err');
    return;
  }

  btn.classList.add('sending');
  btn.textContent = '⏳ Sending...';

  try {
    const result = await authFetch('/api/notifications/send-summary', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        city: S.city || 'Lagos',
        summary_data: {
          total_records: sum.total_records,
          state_distribution: sum.state_distribution || {},
          ncc_compliance: sum.ncc_compliance || {},
          top_issues: sum.top_issues || [],
        }
      })
    }, 30000);

    const sent = result.sent || {};
    const channels = [];
    if (sent.telegram) channels.push('Telegram');
    if (sent.whatsapp) channels.push('WhatsApp');

    if (channels.length) {
      toast('Summary sent to ' + channels.join(' & '), 'ok');
    } else {
      toast('No channels configured. Set Telegram/WhatsApp in Profile.', 'err');
    }
  } catch (e) {
    const msg = e.message || 'Failed to send';
    if (msg.includes('400') || msg.includes('No Telegram')) {
      toast('Save your Telegram/WhatsApp in Profile → Contact Information', 'err');
    } else {
      toast('Send failed: ' + msg, 'err');
    }
  } finally {
    btn.classList.remove('sending');
    btn.textContent = '📤 Send to Phone';
  }
}
async function injectEvent(evType, btn) {
  btn.classList.add('loading', 'active');
  const orig = btn.innerHTML;
  btn.querySelector('.f-name').textContent = 'Loading…';
  try {
    const idx = parseInt(document.getElementById('row-idx').value)||100;
    const d = await api.event(evType, S.city, idx);
    updateDiagnosis(d, S.city, S.season);
    updateLLMBadge(d.source);
    window._lastDiagnosis = d;
    toast(`Event injected: ${evType.replace(/_/g,' ')}`, 'ok');
    document.getElementById('diag-card').scrollIntoView({behavior:'smooth',block:'center'});
    logActivity('fault', `Fault injected: <strong>${evType.replace(/_/g,' ')}</strong> in ${S.city} — ${d.diagnosis||''}`);

    // Generate 4-line summary for fault event
    const sum = window._lastSummary||{};
    api.summarize({diagnosis: d, summary: sum, ncc: sum.ncc_compliance||{}})
      .then(r => updateSummary(r))
      .catch(() => {});
  } catch(e) {
    toast('Event error: '+e.message, 'err');
  } finally {
    btn.classList.remove('loading');
    btn.innerHTML = orig;
    setTimeout(() => btn.classList.remove('active'), 2000);
  }
}

/* ── City profile modal with glossary ──────────────────────────── */
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
      <p style="font-size:11px;color:var(--txt3);margin-top:8px">Season detected: ${d.current_season||'—'}</p>
      <details style="margin-top:16px;border-top:1px solid var(--border);padding-top:12px">
        <summary style="cursor:pointer;font-weight:600;color:var(--accent);font-size:13px">NCC Terminology & Knowhow</summary>
        <div style="margin-top:10px;font-size:12px;color:var(--txt2);line-height:1.7">
          <p><strong style="color:var(--txt)">NCC</strong> — Nigerian Communications Commission, the federal regulator for QoS in telecoms.</p>
          <p style="margin-top:8px"><strong style="color:var(--txt)">OSNR (Optical Signal-to-Noise Ratio)</strong> — Measures signal clarity in dB. Higher is better. NCC minimums: 15 dB for Lagos/Abuja, 14 dB for P/Harcourt & Kano. Below threshold = degradation risk.</p>
          <p style="margin-top:8px"><strong style="color:var(--txt)">BER (Bit Error Rate)</strong> — Ratio of corrupted bits to total transmitted. Lower is better. NCC max: 1×10⁻⁵ (Lagos/Abuja), 1.5×10⁻⁵ (P/Harcourt & Kano).</p>
          <p style="margin-top:8px"><strong style="color:var(--txt)">Latency</strong> — Round-trip delay in milliseconds. NCC max: 150 ms. Higher latency affects real-time services.</p>
          <p style="margin-top:8px"><strong style="color:var(--txt)">Power (dBm)</strong> — Optical power level. Normal range: -20 to +3 dBm. Dropping below -20 dBm indicates attenuation or cut.</p>
          <p style="margin-top:8px"><strong style="color:var(--txt)">Network States</strong> — <span style="color:#00ff88">NORMAL</span> (within NCC bounds), <span style="color:#f59e0b">DEGRADING</span> (approaching thresholds), <span style="color:#ef4444">CRITICAL</span> (threshold breached).</p>
          <p style="margin-top:8px"><strong style="color:var(--txt)">Baseline Drill</strong> — Seasonal NCC drift is simulated based on harmattan (Nov–Feb), rainy (Mar–Jun), dry (Jul–Sep), and normal (Oct) seasons. Each season shifts OSNR/BER baselines to reflect real Nigerian environmental conditions.</p>
          <p style="margin-top:8px"><strong style="color:var(--txt)">Anomalies</strong> — Rows flagged by IsolationForest as statistically deviant. Flagged rows are classified as DEGRADING or CRITICAL depending on severity.</p>
          <p style="margin-top:8px"><strong style="color:var(--txt)">Fault Simulation</strong> — Each fault type (fibre cut, generator fail, harmattan dust, rain attenuation, peak congestion) degrades specific telemetry metrics to model real Nigerian fibre faults.</p>
          <p style="margin-top:8px"><strong style="color:var(--txt)">Digital Twin</strong> — Real-time topology view of the 4-city network showing link health states between Lagos, Abuja, Port Harcourt, and Kano.</p>
        </div>
      </details>`;
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

/* ── Activity Log ─────────────────────────────────────────────── */
function logActivity(type, html) {
  authFetch('/api/activity', {
    method: 'POST', headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({ type, message: html.replace(/<[^>]+>/g, ''), html })
  }).catch(() => {});
  // Only add to visible feed for superadmin
  if (S.user?.role !== 'superadmin') return;
  const feed = document.getElementById('activity-feed');
  const item = document.createElement('div');
  item.className = 'activity-item';
  const icons = { pipeline:'▶', fault:'⚠️', diagnose:'🔍', login:'🔑', system:'⚙️' };
  item.innerHTML = `<span class="activity-icon">${icons[type]||'📋'}</span>
    <div class="activity-body">${html}</div>
    <span class="activity-time">just now</span>`;
  feed.insertBefore(item, feed.firstChild);
  while(feed.children.length > 50) feed.removeChild(feed.lastChild);
}

/* ── Digital Twin ─────────────────────────────────────────────── */
function drawTwin(rows) {
  const canvas = document.getElementById('twinCanvas');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  const rect = canvas.parentElement.getBoundingClientRect();
  canvas.width = canvas.parentElement.clientWidth;
  canvas.height = 320;

  const w = canvas.width, h = canvas.height;
  const cities = {
    Lagos:        { x: w*0.18, y: h*0.78 },
    Abuja:        { x: w*0.48, y: h*0.32 },
    PortHarcourt: { x: w*0.32, y: h*0.88 },
    Kano:         { x: w*0.68, y: h*0.18 },
  };

  // Determine states per city from last rows
  const stateColors = { NORMAL: '#00ff88', DEGRADING: '#f59e0b', CRITICAL: '#ef4444' };
  const cityStates = {};
  for (const city of Object.keys(cities)) {
    const cityRows = (rows||[]).filter(r => (r.city||S.city) === city);
    const lastState = cityRows.length ? cityRows[cityRows.length-1].state : 'NORMAL';
    cityStates[city] = lastState;
  }
  // If no city-specific data, use S.city for all
  if (!Object.values(cityStates).some(s => s)) {
    for (const city of Object.keys(cities)) cityStates[city] = 'NORMAL';
  }

  // Clear
  ctx.clearRect(0, 0, w, h);
  ctx.fillStyle = '#0B0F19';
  ctx.fillRect(0, 0, w, h);

  // Draw links
  const links = [
    ['Lagos','Abuja'], ['Abuja','Kano'], ['Lagos','PortHarcourt'],
    ['Abuja','PortHarcourt'], ['Kano','PortHarcourt']
  ];
  for (const [a, b] of links) {
    const p1 = cities[a], p2 = cities[b];
    const stA = cityStates[a]||'NORMAL', stB = cityStates[b]||'NORMAL';
    const worst = stA === 'CRITICAL' || stB === 'CRITICAL' ? 'CRITICAL' :
                  stA === 'DEGRADING' || stB === 'DEGRADING' ? 'DEGRADING' : 'NORMAL';
    ctx.beginPath();
    ctx.moveTo(p1.x, p1.y);
    ctx.lineTo(p2.x, p2.y);
    ctx.strokeStyle = stateColors[worst] || '#3d5a7a';
    ctx.lineWidth = worst === 'CRITICAL' ? 3 : 2;
    ctx.globalAlpha = worst === 'NORMAL' ? 0.3 : 0.7;
    ctx.stroke();
    ctx.globalAlpha = 1;

    // Midpoint label
    const mx = (p1.x + p2.x) / 2, my = (p1.y + p2.y) / 2;
    ctx.fillStyle = worst === 'NORMAL' ? '#3d5a7a' : stateColors[worst];
    ctx.font = '9px Inter, sans-serif';
    ctx.textAlign = 'center';
    ctx.fillText(worst, mx, my - 6);
  }

  // Draw city nodes
  for (const [name, pos] of Object.entries(cities)) {
    const st = cityStates[name]||'NORMAL';
    const col = stateColors[st] || '#3d5a7a';

    // Glow
    const grad = ctx.createRadialGradient(pos.x, pos.y, 2, pos.x, pos.y, 22);
    grad.addColorStop(0, col + '60');
    grad.addColorStop(1, col + '00');
    ctx.fillStyle = grad;
    ctx.beginPath(); ctx.arc(pos.x, pos.y, 22, 0, Math.PI*2); ctx.fill();

    // Node circle
    ctx.beginPath(); ctx.arc(pos.x, pos.y, 8, 0, Math.PI*2);
    ctx.fillStyle = col;
    ctx.fill();
    ctx.strokeStyle = '#0B0F19';
    ctx.lineWidth = 2;
    ctx.stroke();

    // Label
    ctx.fillStyle = '#e0f0ff';
    ctx.font = 'bold 11px Inter, sans-serif';
    ctx.textAlign = 'center';
    ctx.fillText(name, pos.x, pos.y + 22);
    ctx.font = '9px Inter, sans-serif';
    ctx.fillStyle = '#8899b3';
    ctx.fillText(st, pos.x, pos.y + 34);
  }
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
    console.log('[CHAT] Sending message:', msg, 'mode:', mode);
    const start = Date.now();
    const r = await authFetch('/api/chat', {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({message: msg, mode, context: {
        summary: window._lastSummary || null,
        ncc: window._lastNcc || null,
        diagnosis: window._lastDiagnosis || null,
      }})
    }, 300000);  // 5 min timeout — model cold load can take 2-3 min
    console.log('[CHAT] Response received in', (Date.now()-start)/1000 + 's', r);
    return r;
  },
  addMsg(role, text) {
    console.log('[CHAT] addMsg role=' + role + ' len=' + (text||'').length + ' first50=' + (text||'').substring(0,50).replace(/\n/g, '\\n'));
    const box = document.getElementById('chat-msgs');
    const d = document.createElement('div');
    d.className = 'chat-msg ' + role;
    d.textContent = text;
    box.appendChild(d);
    box.scrollTop = box.scrollHeight;
  },
  async diagnose() {
    const btn = document.getElementById('chat-diag-btn');
    btn.textContent = '…';
    btn.disabled = true;
    const loadingId = 'diag-loading-' + Date.now();
    const loadingEl = document.createElement('div');
    loadingEl.id = loadingId;
    loadingEl.className = 'chat-msg loading';
    loadingEl.innerHTML = 'Running Ollama diagnostics<span class="dots"><span>.</span><span>.</span><span>.</span></span>';
    document.getElementById('chat-msgs').appendChild(loadingEl);
    const r = await authFetch('/api/chat/diagnose');
    const el = document.getElementById(loadingId);
    if(el) el.remove();
    let text = '=== OLLAMA DIAGNOSTIC ===\n';
    text += `Ollama reachable : ${r.reachable}\n`;
    text += `CLI version      : ${r.cli_version || 'N/A'}\n`;
    text += `Available models : ${(r.models||[]).join(', ') || 'none'}\n`;
    if(r.errors && r.errors.length) {
      text += `\n--- ERRORS (${r.errors.length}) ---\n`;
      r.errors.forEach(e => text += `  • ${e}\n`);
    }
    text += `\n--- MODEL TESTS ---\n`;
    for(const [k, v] of Object.entries(r.tests || {})) {
      const ok = v.passed ? '✓' : '✗';
      text += `${ok} ${k}: `;
      if(v.passed) text += `${v.response || 'OK'}\n`;
      else if(v.status) text += `HTTP ${v.status} — ${(v.body_preview||'').slice(0,100)}\n`;
      else text += `${v.error || '?'}\n`;
    }
    if(r.fix_commands && r.fix_commands.length) {
      text += `\n--- FIX ---\n`;
      r.fix_commands.forEach(c => text += `${c}\n`);
    }
    chat.addMsg('system', text);
    btn.textContent = '🔍';
    btn.disabled = false;
  }
};

function toggleChat() {
  const p = document.getElementById('chat-panel');
  p.classList.remove('minimized');
  p.classList.toggle('hidden');
  if(!p.classList.contains('hidden')) document.getElementById('chat-input').focus();
  const nw = document.getElementById('nexus-chat-widget');
  if (p.classList.contains('hidden') && nw) { nw.style.display = ''; const nb = document.getElementById('nexus-chat-bubble'); if (nb) nb.style.display = ''; }
}

function closeAllPanels(except) {
  const chatPanel = document.getElementById('chat-panel');
  const complaintPanel = document.getElementById('complaint-panel');
  const profileDropdown = document.getElementById('profile-dropdown');
  const sidebar = document.getElementById('sidebar');
  const sidebarOverlay = document.getElementById('sidebar-overlay');
  if (except !== 'chat' && chatPanel) { chatPanel.classList.add('hidden'); chatPanel.classList.remove('minimized'); const nw = document.getElementById('nexus-chat-widget'); if (nw) { nw.style.display = ''; const nb = document.getElementById('nexus-chat-bubble'); if (nb) nb.style.display = ''; } }
  if (except !== 'complaint' && complaintPanel) { complaintPanel.classList.add('hidden'); complaintPanel.classList.add('minimized'); const fab = document.getElementById('complaint-toggle'); if (fab) fab.classList.remove('panel-open'); }
  if (except !== 'profile' && profileDropdown) profileDropdown.classList.add('hidden');
  if (except !== 'sidebar' && sidebar) { sidebar.classList.remove('open'); if (sidebarOverlay) sidebarOverlay.classList.remove('active'); }
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
  console.log('[CHAT] doChat — sending:', msg);
  chat.addMsg('user', msg);
  chat.addMsg('assistant', '…');
  try {
    const start = Date.now();
    const r = await chat.send(msg);
    const elapsed = (Date.now() - start) / 1000;
    console.log('[CHAT] doChat — response in', elapsed + 's, source:', r.source, 'reply len:', r.reply?.length);
    const msgs = document.getElementById('chat-msgs');
    msgs.removeChild(msgs.lastChild);
    if (!r.reply) {
      console.warn('[CHAT] Empty reply received');
      chat.addMsg('assistant', 'No response from Nexus AI');
    } else {
      chat.addMsg('assistant', r.reply);
    }
  } catch(e) {
    console.error('[CHAT] doChat — FAILED:', e.name, e.message);
    const msgs = document.getElementById('chat-msgs');
    msgs.removeChild(msgs.lastChild);
    chat.addMsg('assistant', 'Error: ' + e.message);
  }
}

/* ── Saved Logs ───────────────────────────────────────────────── */
function renderLogRows(runs) {
  const body = document.getElementById('logs-body');
  if(!runs||!runs.length) {
    body.innerHTML = '<tr><td colspan="6" class="table-empty">No saved runs</td></tr>';
    return;
  }
  const show = S.logsShowAll ? runs : runs.slice(0, 5);
  body.innerHTML = show.map(run => `
    <tr>
      <td>#${run.id}</td>
      <td>${run.created_at||'—'}</td>
      <td>${run.city||'—'}</td>
      <td>${run.season||'—'}</td>
      <td>${run.n_samples||'—'}</td>
      <td><button class="outline-btn small" onclick="deleteLog(${run.id})">Delete</button></td>
    </tr>
  `).join('');
  const toggle = document.getElementById('logs-view-toggle');
  if(runs.length > 5) {
    toggle.classList.remove('hidden');
    toggle.textContent = S.logsShowAll ? 'Show Less' : `View ${runs.length - 5} More`;
  } else {
    toggle.classList.add('hidden');
  }
}

function toggleLogsView() {
  S.logsShowAll = !S.logsShowAll;
  renderLogRows(S.logsFull);
}

async function loadLogs() {
  try {
    const data = await authFetch('/api/logs');
    S.logsFull = data.runs || [];
    S.logsShowAll = false;
    renderLogRows(S.logsFull);
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

/* ── Sidebar toggle (mobile) ─────────────────── */
function toggleSidebar() {
  const s = document.getElementById('sidebar');
  const o = document.getElementById('sidebar-overlay');
  const willOpen = !s.classList.contains('open');
  if (willOpen) closeAllPanels('sidebar');
  s.classList.toggle('open');
  o.classList.toggle('hidden');
}

/* ── Init (after auth check) ──────────────────────────────────── */
function afterAuth() {
  try {
  initCharts();
  updateClock();
  setInterval(updateClock, 1000);
  checkStatus();
  setInterval(checkStatus, 15000);
  fetchWeather();
  setInterval(fetchWeather, 300000); // every 5 min
  fetchUnreadCount();
  S._unreadPollTimer = setInterval(fetchUnreadCount, 10000); // every 10s

  // City buttons
  document.querySelectorAll('.city-btn').forEach(b => b.addEventListener('click', () => {
    document.querySelectorAll('.city-btn').forEach(x=>x.classList.remove('active'));
    b.classList.add('active');
    S.city = b.dataset.city;
    document.querySelector('#hdr-city-active .val').textContent = S.city;
    updateClock();
    fetchWeather();
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
  document.getElementById('send-summary-btn').addEventListener('click', sendSummaryToPhone);

  // Row index input
  document.getElementById('row-idx').addEventListener('change', e => { S.rowIdx=+e.target.value; });

  // Fault buttons
  document.querySelectorAll('.fault-btn').forEach(b => b.addEventListener('click', () => injectEvent(b.dataset.event, b)));

  // City profile
  document.getElementById('city-profile-btn').addEventListener('click', showCityProfile);
  document.getElementById('modal-close').addEventListener('click', () => document.getElementById('modal-overlay').classList.add('hidden'));
  document.getElementById('modal-overlay').addEventListener('click', e => { if(e.target===e.currentTarget) e.currentTarget.classList.add('hidden'); });

  // Simulation toggle — Real Fibre Lines reveals additional cities
  const simToggle = document.getElementById('sim-toggle');
  const simComingSoon = document.getElementById('sim-coming-soon');
  const realFibreCities = document.querySelectorAll('.real-fibre-city');
  if (simToggle) {
    simToggle.addEventListener('change', () => {
      if (simToggle.checked) {
        simComingSoon.style.display = 'block';
        realFibreCities.forEach(btn => btn.classList.remove('hidden'));
        toast('New cities unlocked: Kaduna, Enugu, Jos, Ibadan', 'ok');
        // Update city grid layout
        const grid = document.querySelector('.city-grid');
        if (grid) grid.style.gridTemplateColumns = 'repeat(2, 1fr)';
      } else {
        simComingSoon.style.display = 'none';
        realFibreCities.forEach(btn => {
          btn.classList.add('hidden');
          if (btn.classList.contains('active')) {
            btn.classList.remove('active');
            document.querySelector('.city-btn[data-city="Lagos"]').classList.add('active');
            S.city = 'Lagos';
            document.querySelector('#hdr-city-active .val').textContent = 'Lagos';
          }
        });
        const grid = document.querySelector('.city-grid');
        if (grid) grid.style.gridTemplateColumns = '';
      }
    });
  }

  // Auto button removed — feature coming soon handled via profile settings

  // Export
  document.getElementById('export-btn').addEventListener('click', exportCSV);

  // Explanation bar
  document.getElementById('eb-btn').addEventListener('click', async () => {
    document.getElementById('explanation-bar').classList.remove('show');
    const d = window._lastDiagnosis || window._lastSummary;
    if (!d) return;
    const msgs = document.getElementById('chat-msgs');
    console.log('[EXPLAIN] View Explanation clicked, hasEngaged=' + (msgs.querySelector('.chat-msg.user') !== null));
    const hasEngaged = msgs.querySelector('.chat-msg.user') !== null;
    const mode = document.getElementById('chat-mode').checked ? 'technical' : 'simple';

    // Show explanation bar loading
    const loadingId = 'exp-loading-' + Date.now();
    const loadingEl = document.createElement('div');
    loadingEl.id = loadingId;
    loadingEl.className = 'chat-msg loading';
    loadingEl.innerHTML = 'Generating explanation<span class="dots"><span>.</span><span>.</span><span>.</span></span>';
    msgs.appendChild(loadingEl);
    msgs.scrollTop = msgs.scrollHeight;

    const cp = document.getElementById('chat-panel');
    cp.classList.remove('hidden', 'minimized');

    try {
      const start = Date.now();
      const r = await chat.send(
        `Explain the latest pipeline results in ${mode} terms. ` +
        `Summary: ${JSON.stringify(window._lastSummary)}`
      );
      console.log('[EXPLAIN] Response in', (Date.now()-start)/1000 + 's');
      const el = document.getElementById(loadingId);
      if (el) el.remove();
      const reply = r.reply || 'No explanation available.';

      if (hasEngaged) {
        chat.addMsg('system', '──────── DIAGNOSIS EXPLANATION ────────');
      }
      chat.addMsg('assistant', reply);
      chat.addMsg('assistant', 'You can continue the conversation — ask me any questions about the telemetry, charts, or NCC compliance.');
    } catch (e) {
      console.error('[EXPLAIN] Failed:', e.name, e.message);
      const el = document.getElementById(loadingId);
      if (el) el.remove();
      chat.addMsg('assistant', 'Failed to generate explanation: ' + e.message);
    }
  });
  document.getElementById('eb-close').addEventListener('click', () => {
    document.getElementById('explanation-bar').classList.remove('show');
  });

  // Auto-refresh toggle
  document.getElementById('auto-refresh').addEventListener('change', e => setupAutoRefresh(e.target.checked));

  // Sidebar toggle (mobile)
  document.getElementById('sidebar-toggle').addEventListener('click', toggleSidebar);
  document.getElementById('sidebar-overlay').addEventListener('click', toggleSidebar);
  document.getElementById('sidebar-close-btn').addEventListener('click', toggleSidebar);

  // Chat toggle, minimize & send
  // Nexus chat widget
  const nexusFab = document.getElementById('nexus-fab');
  const nexusBubble = document.getElementById('nexus-chat-bubble');
  const nexusWidget = document.getElementById('nexus-chat-widget');
  if (nexusFab) nexusFab.addEventListener('click', () => { if (nexusWidget) nexusWidget.style.display = 'none'; closeAllPanels('chat'); const cp = document.getElementById('chat-panel'); cp.classList.remove('hidden'); cp.classList.remove('minimized'); document.getElementById('chat-input').focus(); });
  document.getElementById('chat-close').addEventListener('click', toggleChat);
  document.getElementById('chat-minimize').addEventListener('click', minimizeChat);
  document.getElementById('chat-send').addEventListener('click', doChat);
  document.getElementById('chat-input').addEventListener('keydown', e => { if(e.key==='Enter') doChat(); });
  document.getElementById('chat-mode').addEventListener('change', chatModeChanged);

  // Telemetry view toggle
  document.getElementById('telem-view-toggle').addEventListener('click', toggleTelemView);

  // Logs view toggle
  document.getElementById('logs-view-toggle').addEventListener('click', toggleLogsView);

  // Logs refresh
  document.getElementById('logs-refresh').addEventListener('click', loadLogs);

  // Logout (bound to dropdown Sign Out below)

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
  loadActivities();
  // Initial digital twin
  setTimeout(() => drawTwin([]), 300);
  // Poll activities every 15s (superadmin only)
  if (S.user?.role === 'superadmin') {
    loadActivities();
    setInterval(loadActivities, 15000);
  }
  // Re-draw twin on window resize
  let resizeTimer;
  window.addEventListener('resize', () => {
    clearTimeout(resizeTimer);
    resizeTimer = setTimeout(() => drawTwin(window._lastRows || []), 300);
  });

  // ── Profile Dropdown ──
  const profileDropdown = document.getElementById('profile-dropdown');
  document.getElementById('profile-trigger').addEventListener('click', (e) => {
    e.stopPropagation();
    const wasHidden = profileDropdown.classList.contains('hidden');
    closeAllPanels(wasHidden ? 'profile' : null);
    profileDropdown.classList.toggle('hidden');
  });
  profileDropdown.addEventListener('click', (e) => e.stopPropagation());
  document.addEventListener('click', () => profileDropdown.classList.add('hidden'));

  document.getElementById('dropdown-edit-profile').addEventListener('click', () => {
    profileDropdown.classList.add('hidden');
    openProfileModal();
  });
  document.getElementById('dropdown-settings').addEventListener('click', () => {
    profileDropdown.classList.add('hidden');
    toast('Workspace Settings coming soon', 'info');
  });
  document.getElementById('dropdown-usage').addEventListener('click', () => {
    profileDropdown.classList.add('hidden');
    toast('Project Usage coming soon', 'info');
  });
  document.getElementById('dropdown-docs').addEventListener('click', () => {
    profileDropdown.classList.add('hidden');
    window.location.href = '/blog';
  });
  document.getElementById('dropdown-status').addEventListener('click', () => {
    profileDropdown.classList.add('hidden');
    window.location.href = '/status';
  });
  document.getElementById('dropdown-support').addEventListener('click', () => {
    profileDropdown.classList.add('hidden');
    document.getElementById('complaint-toggle').click();
  });
  document.getElementById('dropdown-logout').addEventListener('click', () => {
    profileDropdown.classList.add('hidden');
    setToken(null);
    window.location.href = '/login';
  });
  // Avatar upload
  document.getElementById('avatar-upload-input').addEventListener('change', async (e) => {
    const file = e.target.files[0];
    if (!file) return;
    try {
      const b64 = await toBase64(file);
      // Convert to standardized WebP format via canvas
      const webp = await convertToWebP(b64);
      await authFetch('/api/profile', {
        method: 'PUT',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({settings: {avatar_data: webp}})
      });
      S.user.profile = S.user.profile || {};
      S.user.profile.settings = S.user.profile.settings || {};
      S.user.profile.settings.avatar_data = webp;
      updateProfileUI();
      logActivity('profile', 'Profile photo updated');
      toast('Photo updated!', 'ok');
    } catch (err) {
      toast('Failed to upload photo: ' + err.message, 'err');
    }
  });
  document.getElementById('profile-modal-close').addEventListener('click', () => {
    document.getElementById('profile-modal-overlay').classList.add('hidden');
  });
  document.getElementById('profile-modal-overlay').addEventListener('click', e => {
    if (e.target === e.currentTarget) e.currentTarget.classList.add('hidden');
  });
  document.getElementById('profile-save-btn').addEventListener('click', saveProfile);
  document.getElementById('theme-switch-dropdown').addEventListener('change', e => {
    const theme = e.target.checked ? 'light' : 'dark';
    applyTheme(theme);
    // Sync modal switch
    const modalSwitch = document.getElementById('theme-switch');
    if (modalSwitch) modalSwitch.checked = e.target.checked;
  });
  document.getElementById('theme-switch').addEventListener('change', e => {
    const theme = e.target.checked ? 'light' : 'dark';
    applyTheme(theme);
    // Sync dropdown switch
    document.getElementById('theme-switch-dropdown').checked = e.target.checked;
  });

  // ── Cases Panel ──
  document.getElementById('complaint-toggle').addEventListener('click', toggleComplaintPanel);
  document.getElementById('complaint-close').addEventListener('click', toggleComplaintPanel);
  document.getElementById('complaint-minimize').addEventListener('click', () => {
    document.getElementById('complaint-panel').classList.toggle('minimized');
  });
  document.getElementById('complaint-new-btn').addEventListener('click', toggleNewMsgDropdown);
  document.getElementById('complaint-send').addEventListener('click', sendComplaintMessage);
  document.getElementById('complaint-input').addEventListener('keydown', e => {
    if (e.key === 'Enter') sendComplaintMessage();
  });
  loadCasesList();
  } catch(e) { console.error('[INIT] afterAuth error:', e); }
}

// ── Profile Modal ──────────────────────────────────────────────────

async function openProfileModal() {
  console.log('[PROFILE] Opening profile modal');
  const overlay = document.getElementById('profile-modal-overlay');
  overlay.classList.remove('hidden');
  const me = S.user || {};
  document.getElementById('profile-name').textContent = me.username || '—';
  document.getElementById('profile-role').textContent = me.role || '—';
  document.getElementById('profile-joined').textContent = me.created_at || '—';

  const avatarEl = document.getElementById('profile-avatar');
  const avatarData = me.profile?.settings?.avatar_data;
  if (avatarData) {
    avatarEl.innerHTML = '';
    const img = document.createElement('img');
    img.src = avatarData;
    img.style.cssText = 'width:100%;height:100%;object-fit:cover;border-radius:50%';
    avatarEl.appendChild(img);
  } else {
    avatarEl.innerHTML = '';
    avatarEl.textContent = getInitials(me.username);
    avatarEl.style.background = me.profile?.avatar_color || '#FF9E00';
  }

  document.getElementById('profile-display-name').value = me.profile?.display_name || me.username || '';
  const isLight = (me.profile?.theme || 'dark') === 'light';
  document.getElementById('theme-switch').checked = isLight;
  document.getElementById('theme-switch-dropdown').checked = isLight;
  document.getElementById('theme-lbl').textContent = me.profile?.theme === 'light' ? 'Light' : 'Dark';
  document.getElementById('profile-avatar-color').value = me.profile?.avatar_color || '#FF9E00';
  
  // Populate contact fields
  const settings = me.profile?.settings || {};
  document.getElementById('profile-telegram').value = settings.telegram || '';
  document.getElementById('profile-whatsapp').value = settings.whatsapp || '';

  // Load user's activity
  try {
    const acts = await authFetch('/api/activity?own=true&limit=10');
    const container = document.getElementById('profile-recent-acts');
    if (acts.activities?.length) {
      container.innerHTML = acts.activities.slice(0, 5).map(a =>
        `<div style="font-size:12px;padding:4px 0;border-bottom:1px solid var(--border);display:flex;justify-content:space-between">
          <span>${a.message || ''}</span>
          <span style="color:var(--txt3);font-size:10px">${a.created_at || ''}</span>
        </div>`
      ).join('');
    } else {
      container.innerHTML = '<div style="color:var(--txt3);font-size:12px">No recent activity</div>';
    }
  } catch(e) {
    document.getElementById('profile-recent-acts').innerHTML = '<div style="color:var(--txt3);font-size:12px">Could not load activity</div>';
  }
}

async function saveProfile() {
  const btn = document.getElementById('profile-save-btn');
  btn.textContent = 'Saving...';
  btn.disabled = true;
  try {
    const displayName = document.getElementById('profile-display-name').value.trim();
    const theme = document.getElementById('theme-switch').checked ? 'light' : 'dark';
    const avatarColor = document.getElementById('profile-avatar-color').value;
    const telegram = document.getElementById('profile-telegram').value.trim();
    const whatsapp = document.getElementById('profile-whatsapp').value.trim();
    
    const settings = { ...(S.user.profile?.settings || {}) };
    if (telegram) settings.telegram = telegram;
    if (whatsapp) settings.whatsapp = whatsapp;
    
    await authFetch('/api/profile', {
      method: 'PUT',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({display_name: displayName, theme, avatar_color: avatarColor, settings})
    });
    S.user.profile = { ...(S.user.profile || {}), display_name: displayName, theme, avatar_color: avatarColor, settings };
    applyTheme(theme);
    updateProfileUI();
    toast('Profile saved!', 'ok');
  } catch(e) {
    toast('Failed to save profile: ' + e.message, 'err');
  } finally {
    btn.textContent = 'Save Changes';
    btn.disabled = false;
  }
}

function getInitials(name) {
  if (!name) return '?';
  return name.split(/[\s_]+/).map(w => w[0]).join('').toUpperCase().slice(0, 2) || '?';
}

function applyTheme(theme) {
  let overlay = document.getElementById('theme-fade-overlay');
  if (!overlay) {
    overlay = document.createElement('div');
    overlay.id = 'theme-fade-overlay';
    overlay.style.cssText = 'position:fixed;inset:0;z-index:9999;pointer-events:none;opacity:0;transition:opacity 0.5s ease;background:rgba(0,0,0,0.35);';
    document.body.appendChild(overlay);
  }
  overlay.style.opacity = '1';
  setTimeout(() => {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('oasis-theme', theme);
    const lbl = document.getElementById('theme-lbl');
    if (lbl) lbl.textContent = theme === 'light' ? 'Light' : 'Dark';
  }, 300);
  setTimeout(() => {
    overlay.style.opacity = '0';
    setTimeout(() => { if (overlay.parentNode) overlay.parentNode.removeChild(overlay); }, 500);
  }, 500);
}

/* ── Profile UI (greeting + avatar in header) ── */
function updateProfileUI() {
  const p = S.user?.profile || {};
  const displayName = p.display_name || S.user?.username || 'user';
  const firstName = displayName.split(/\s/)[0];
  const avatarData = p.settings?.avatar_data;
  const color = p.avatar_color || '#FF9E00';
  const initials = getInitials(displayName);
  const role = S.user?.role || 'user';

  // Set dynamic accent colour from avatar_color
  document.documentElement.style.setProperty('--accent', color);
  document.documentElement.style.setProperty('--accent2', color);
  const r = parseInt(color.slice(1,3),16), g = parseInt(color.slice(3,5),16), b = parseInt(color.slice(5,7),16);
  document.documentElement.style.setProperty('--accent-rgb', `${r},${g},${b}`);

  document.getElementById('profile-trigger').title = displayName + "'s Profile";
  document.getElementById('profile-greeting').textContent = 'Hi, ' + firstName;
  document.getElementById('dropdown-username').textContent = displayName;
  document.getElementById('dropdown-role-badge').textContent = role === 'superadmin' ? 'Superadmin' : 'User';
  document.getElementById('dropdown-role-badge').className = 'dropdown-role-badge ' + role;

  [document.getElementById('trigger-avatar'), document.getElementById('dropdown-avatar')].forEach(el => {
    if (avatarData) {
      el.innerHTML = '';
      const img = document.createElement('img');
      img.src = avatarData;
      img.style.cssText = 'width:100%;height:100%;object-fit:cover;border-radius:50%';
      el.appendChild(img);
    } else {
      el.innerHTML = '';
      el.textContent = initials;
      el.style.background = color;
    }
  });

  const triggerEl = document.getElementById('trigger-avatar');
  if (avatarData) {
    triggerEl.style.cursor = 'pointer';
    triggerEl.style.border = `2px solid ${color}`;
    triggerEl.onclick = (e) => {
      e.stopPropagation();
      window.location.href = avatarData;
    };
  } else {
    triggerEl.style.cursor = '';
    triggerEl.style.border = `2px solid ${color}`;
    triggerEl.onclick = null;
  }
  const dropEl = document.getElementById('dropdown-avatar');
  dropEl.style.border = `2px solid ${color}`;
}

function toBase64(file) {
  return new Promise((resolve, reject) => {
    const r = new FileReader();
    r.onload = () => resolve(r.result);
    r.onerror = reject;
    r.readAsDataURL(file);
  });
}

function convertToWebP(dataUrl) {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => {
      const max = 256;
      const s = Math.min(max / img.width, max / img.height, 1);
      const w = Math.round(img.width * s);
      const h = Math.round(img.height * s);
      const c = document.createElement('canvas');
      c.width = w;
      c.height = h;
      const ctx = c.getContext('2d');
      ctx.drawImage(img, 0, 0, w, h);
      resolve(c.toDataURL('image/webp', 0.8));
    };
    img.onerror = reject;
    img.src = dataUrl;
  });
}


// ── Cases Panel (Instagram DM style) ─────────────────────────────

let _activeCaseId = null;
let _casePollTimer = null;

function toggleComplaintPanel() {
  const p = document.getElementById('complaint-panel');
  const fab = document.getElementById('complaint-toggle');
  const wasHidden = p.classList.contains('hidden');
  closeAllPanels(wasHidden ? 'complaint' : null);
  p.classList.remove('minimized');
  p.classList.toggle('hidden');
  if (fab) fab.classList.toggle('panel-open', !p.classList.contains('hidden'));
  if (!p.classList.contains('hidden')) {
    loadCasesList();
    // Cases link visible for all users
    const casesBtn = document.getElementById('cases-link-btn');
    if (casesBtn) casesBtn.style.display = '';
    // Show correct form based on role
    const adminForm = document.getElementById('new-case-admin-form');
    const userForm = document.getElementById('new-case-user-form');
    const newBtn = document.getElementById('complaint-new-btn');
    const newDropdown = document.getElementById('new-msg-dropdown');
    if (S.user?.role === 'superadmin') {
      if (adminForm) adminForm.style.display = '';
      if (userForm) userForm.style.display = 'none';
      if (newBtn) newBtn.style.display = '';
      if (newDropdown) newDropdown.classList.add('hidden');
    } else {
      if (adminForm) adminForm.style.display = 'none';
      if (userForm) userForm.style.display = '';
      if (newBtn) newBtn.style.display = 'none';
      // Auto-show the new case form for regular users
      if (newDropdown) newDropdown.classList.remove('hidden');
    }
  } else {
    if (_casePollTimer) { clearInterval(_casePollTimer); _casePollTimer = null; }
    closeCaseThread();
  }
}

function closeCaseThread() {
  const thread = document.getElementById('case-thread');
  const list = document.getElementById('cases-list');
  if (thread) thread.style.display = 'none';
  if (list) list.style.maxHeight = '';
  _activeCaseId = null;
  if (_casePollTimer) { clearInterval(_casePollTimer); _casePollTimer = null; }
}

async function loadCasesList() {
  const list = document.getElementById('cases-list');
  try {
    const data = await authFetch('/api/cases', {}, 10000);
    if (!data.cases?.length) {
      list.innerHTML = `<div class="cases-empty">
        <div style="font-size:40px;margin-bottom:12px;opacity:.4">✉️</div>
        <div style="font-size:14px;font-weight:600;color:var(--txt2);margin-bottom:4px">No messages yet</div>
        <div style="font-size:12px;color:var(--txt3)">Click ✏️ to start a conversation</div>
      </div>`;
      return;
    }
    list.innerHTML = data.cases.map(c => {
      const initials = (c.user_name || '?').slice(0, 2).toUpperCase();
      const avatarBg = c.avatar_color || '#FF9E00';
      const timeAgo = _timeAgo(c.last_message_at || c.updated_at);
      const preview = (c.last_message || c.subject || '').slice(0, 80);
      const subject = (c.subject || 'No subject').slice(0, 40);
      const unread = c.unread_count || 0;
      const isActive = c.id === _activeCaseId;
      const closedTag = c.status === 'closed' ? '<span style="font-size:9px;color:var(--red);background:rgba(239,68,68,.12);padding:2px 8px;border-radius:8px;font-weight:600">Closed</span>' : '<span style="font-size:9px;color:#22c55e;background:rgba(34,197,94,.12);padding:2px 8px;border-radius:8px;font-weight:600">Open</span>';
      const senderName = c.last_sender || c.user_name || 'Unknown';
      const typeTag = c.complaint_type ? `<span style="font-size:9px;padding:2px 6px;border-radius:6px;font-weight:700;background:rgba(0,255,136,.1);color:var(--accent);margin-right:4px">${c.complaint_type}</span>` : '';
      const caseNum = c.case_number ? `<span style="font-size:10px;color:var(--txt3);font-family:var(--mono)">${c.case_number}</span>` : '';
      return `<div class="case-item ${isActive ? 'active' : ''}" onclick="openCase(${c.id})" data-case-id="${c.id}">
        <div class="case-item-left">
          <div class="case-avatar" style="background:${avatarBg}">
            ${c.avatar_data ? `<img src="${c.avatar_data}" alt="" style="width:100%;height:100%;object-fit:cover;border-radius:50%" />` : `<span>${initials}</span>`}
          </div>
        </div>
        <div class="case-item-body">
          <div class="case-item-top">
            ${typeTag}
            <span class="case-item-name">${c.user_name || 'Unknown'}</span>
            <span class="case-item-time">${timeAgo}</span>
          </div>
          <div class="case-item-subject">${caseNum} ${subject}</div>
          <div class="case-item-preview">${senderName}: ${preview}</div>
          <div class="case-item-bottom">
            ${closedTag}
            ${unread > 0 ? `<span class="case-item-unread">${unread}</span>` : ''}
          </div>
        </div>
      </div>`;
    }).join('');
  } catch(e) {
    console.error('[CASES] Load error:', e);
    list.innerHTML = `<div class="cases-empty">
      <div style="font-size:40px;margin-bottom:12px;opacity:.4">✉️</div>
      <div style="font-size:14px;font-weight:600;color:var(--txt2);margin-bottom:4px">No messages yet</div>
      <div style="font-size:12px;color:var(--txt3)">Click ✏️ to start a conversation</div>
    </div>`;
  }
}

function toggleNewMsgDropdown() {
  const dd = document.getElementById('new-msg-dropdown');
  dd.classList.toggle('hidden');
}

async function createCaseForUser() {
  const typeEl = document.getElementById('admin-case-type');
  const inp = document.getElementById('new-msg-subject');
  const subject = inp.value.trim();
  const complaintType = typeEl ? typeEl.value : 'OT';
  if (!subject) { toast('Enter a subject', 'err'); return; }
  try {
    const data = await authFetch('/api/complaints', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({subject, complaint_type: complaintType})
    });
    inp.value = '';
    document.getElementById('new-msg-dropdown').classList.add('hidden');
    toast('Conversation started!', 'ok');
    await loadCasesList();
    openCase(data.complaint.id);
  } catch(e) { toast('Failed: ' + e.message, 'err'); }
}

async function userFileNewCase() {
  const subjectEl = document.getElementById('user-case-subject');
  const bodyEl = document.getElementById('user-case-body');
  const typeEl = document.getElementById('user-case-type');
  const subject = subjectEl.value.trim();
  const body = bodyEl.value.trim();
  const complaintType = typeEl ? typeEl.value : 'OT';
  if (!subject) { toast('Enter a case header', 'err'); return; }
  try {
    const data = await authFetch('/api/complaints', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({subject, message: body || undefined, complaint_type: complaintType})
    });
    subjectEl.value = '';
    bodyEl.value = '';
    document.getElementById('new-msg-dropdown').classList.add('hidden');
    toast('Case filed! Redirecting…', 'ok');
    // Redirect to cases.html with the new case ID
    window.location.href = '/cases?case=' + data.complaint.id;
  } catch(e) { toast('Failed: ' + e.message, 'err'); }
}

async function openCase(caseId) {
  _activeCaseId = caseId;
  // Highlight in list
  document.querySelectorAll('.case-item').forEach(el => {
    el.style.background = +el.dataset.caseId === caseId ? 'rgba(0,255,136,.06)' : '';
  });
  // Show thread
  const thread = document.getElementById('case-thread');
  const list = document.getElementById('cases-list');
  if (thread) thread.style.display = 'flex';
  if (list) list.style.maxHeight = '160px';
  // Load messages
  await loadCaseMessages(caseId);
  // Mark as read
  try { await authFetch(`/api/cases/${caseId}/read`, {method:'POST'}); } catch {}
  fetchUnreadCount();
  // Start polling
  if (_casePollTimer) clearInterval(_casePollTimer);
  _casePollTimer = setInterval(() => { if (_activeCaseId) loadCaseMessages(_activeCaseId); }, 5000);
}

async function loadCaseMessages(caseId) {
  try {
    const data = await authFetch(`/api/complaints/${caseId}/messages`, {}, 10000);
    const msgs = document.getElementById('complaint-msgs');
    const complaint = data.complaint || {};
    const isClosed = complaint.status === 'closed';
    // Update header
    const nameEl = document.getElementById('thread-case-name');
    const statusEl = document.getElementById('thread-case-status');
    if (nameEl) nameEl.textContent = complaint.subject || `Case #${caseId}`;
    if (statusEl) {
      statusEl.textContent = isClosed ? 'Closed' : 'Open';
      statusEl.style.background = isClosed ? 'rgba(255,255,255,.06)' : 'rgba(0,255,136,.12)';
      statusEl.style.color = isClosed ? 'var(--txt3)' : 'var(--accent)';
    }
    if (!data.messages?.length) {
      msgs.innerHTML = `<div class="chat-msg system" style="text-align:center;color:var(--txt3);font-size:11px;padding:8px">No messages yet.</div>`;
    } else {
      msgs.innerHTML = data.messages.map(m => {
        const isMe = m.sender_name === S.user?.username;
        const isSystem = m.message_type === 'system';
        if (isSystem) return `<div class="chat-msg system" style="text-align:center;color:var(--txt3);font-size:11px;padding:4px">${m.message}</div>`;
        const ts = m.created_at ? new Date(m.created_at).toLocaleTimeString([], {hour:'2-digit', minute:'2-digit'}) : '';
        const bg = isMe ? 'var(--accent)' : 'var(--bg3)';
        const color = isMe ? '#000' : 'var(--txt)';
        const align = isMe ? 'flex-end' : 'flex-start';
        const radius = isMe ? '12px 12px 4px 12px' : '12px 12px 12px 4px';
        return `<div style="display:flex;flex-direction:column;align-items:${align};margin-bottom:6px">
          <div style="font-size:10px;color:var(--txt3);margin-bottom:2px;${isMe ? 'text-align:right' : ''}">${isMe ? 'You' : m.sender_name}</div>
          <div style="max-width:80%;padding:8px 12px;border-radius:${radius};background:${bg};color:${color};font-size:13px;line-height:1.4">${m.message}</div>
          <div style="font-size:9px;color:var(--txt3);margin-top:2px;${isMe ? 'text-align:right' : ''}">${ts}</div>
        </div>`;
      }).join('');
    }
    if (isClosed) {
      msgs.innerHTML += `<div class="chat-msg system" style="text-align:center;color:var(--txt3);font-size:11px;padding:6px;background:rgba(255,255,255,.03);border-radius:8px;margin-top:4px">🔒 Case closed${complaint.resolution_notes ? ': ' + complaint.resolution_notes : ''}</div>`;
      document.getElementById('complaint-input').disabled = true;
      document.getElementById('complaint-send').disabled = true;
    } else {
      document.getElementById('complaint-input').disabled = false;
      document.getElementById('complaint-send').disabled = false;
    }
    msgs.scrollTop = msgs.scrollHeight;
  } catch(e) {
    console.error('[CASES] Load messages error:', e);
  }
}

async function createComplaint() {
  const dd = document.getElementById('new-msg-dropdown');
  if (dd.classList.contains('hidden')) {
    toggleNewMsgDropdown();
    return;
  }
  const typeEl = document.getElementById('admin-case-type');
  const inp = document.getElementById('new-msg-subject');
  const subject = inp.value.trim();
  const complaintType = typeEl ? typeEl.value : 'OT';
  if (!subject) { toast('Enter a subject', 'err'); return; }
  try {
    const data = await authFetch('/api/complaints', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({subject, complaint_type: complaintType})
    });
    inp.value = '';
    dd.classList.add('hidden');
    toast('Case created!', 'ok');
    _activeCaseId = data.complaint.id;
    await loadCasesList();
    await loadCaseMessages(_activeCaseId);
    document.getElementById('case-thread').style.display = 'flex';
    document.getElementById('cases-list').style.maxHeight = '160px';
  } catch(e) {
    toast('Failed: ' + e.message, 'err');
  }
}

async function sendComplaintMessage() {
  const inp = document.getElementById('complaint-input');
  const msg = inp.value.trim();
  if (!msg) return;

  // If no active case, auto-create one (for regular users messaging admin)
  if (!_activeCaseId) {
    try {
      const data = await authFetch('/api/complaints', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({subject: 'New conversation', complaint_type: 'OT'})
      });
      _activeCaseId = data.complaint.id;
      await loadCasesList();
      // Open the newly created case
      const thread = document.getElementById('case-thread');
      const list = document.getElementById('cases-list');
      if (thread) thread.style.display = 'flex';
      if (list) list.style.maxHeight = '160px';
    } catch(e) {
      toast('Failed to start conversation: ' + e.message, 'err');
      return;
    }
  }

  inp.value = '';
  try {
    await authFetch(`/api/complaints/${_activeCaseId}/messages`, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({message: msg})
    });
    await loadCaseMessages(_activeCaseId);
    fetchUnreadCount();
  } catch(e) {
    toast('Failed to send: ' + e.message, 'err');
  }
}

function _timeAgo(dateStr) {
  if (!dateStr) return '';
  const d = new Date(dateStr);
  const now = new Date();
  const diff = Math.floor((now - d) / 1000);
  if (diff < 60) return 'just now';
  if (diff < 3600) return Math.floor(diff/60) + 'm';
  if (diff < 86400) return Math.floor(diff/3600) + 'h';
  if (diff < 604800) return Math.floor(diff/86400) + 'd';
  return d.toLocaleDateString();
}


// ── Activity Feed ────────────────────────────────────────────────

async function loadActivities() {
  const feed = document.getElementById('activity-feed');
  if (!feed) return;
  try {
    const isSuper = S.user?.role === 'superadmin';
    const url = isSuper ? '/api/activity?limit=100' : '/api/activity?own=true&limit=100';
    const data = await authFetch(url, {}, 10000);
    if (!data.activities || !data.activities.length) {
      feed.innerHTML = '<div style="color:var(--txt3);font-size:12px;text-align:center;padding:20px">No recent activity</div>';
      return;
    }
    const icons = { pipeline:'▶', fault:'⚠️', diagnose:'🔍', login:'🔑', system:'⚙️', profile:'👤', case:'📋', notification:'📤', signup:'🆕' };
    feed.innerHTML = data.activities.map(a => {
      let extra = '';
      if (a.type === 'login' && a.user_agent) {
        extra = `<span style="font-size:10px;color:var(--txt3);display:block">device: ${a.user_agent}</span>`;
      }
      if (isSuper && a.username) {
        extra += `<span style="font-size:10px;color:var(--accent);display:block">user: ${a.username}</span>`;
      }
      return `<div class="activity-item">
        <span class="activity-icon">${icons[a.type]||'📋'}</span>
        <div class="activity-body">${a.html || a.message || ''}${extra}</div>
        <span class="activity-time">${a.created_at || ''}</span>
      </div>`;
    }).join('');
  } catch(e) { /* silent */ }
}

function downloadActivityLog() {
  const token = getToken();
  fetch('/api/activity/download', { headers: { 'Authorization': 'Bearer ' + token } })
    .then(r => r.blob())
    .then(blob => {
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'activity_log.csv';
      a.click();
      URL.revokeObjectURL(url);
    })
    .catch(e => toast('Download failed: ' + e.message, 'err'));
}

/* ── Bootstrap ────────────────────────────────────────────────── */
document.addEventListener('DOMContentLoaded', () => {
  document.body.className = 'auth-loading';
  document.getElementById('header').style.display = 'none';
  document.querySelector('.layout').style.display = 'none';
  checkAuth();
});