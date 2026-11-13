'use strict';
const $ = id => document.getElementById(id);
const esc = value => String(value).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const namesCN = {LLR:'右下唇',LLL:'左下唇',TON:'舌头',JL:'下巴',JR:'下巴',LR:'眼球左右',UD:'眼球上下'};
let state, selection = ['UD'], selectionMode = 'single', ownToken = null;
let lastToken = null;
let draft = {}, signs = {}, seq = 0, pending = null, sending = false, generation = 0;
let axesKey = '', listKey = '', recordsKey = '', networkOK = false, lastError = '';
const session = () => state?.calibration?.session;
const owned = () => Boolean(ownToken && session()?.token === ownToken);
const exploring = () => owned() && session().phase === 'range';
const sameNames = names => [...names].sort().join(',') === [...selection].sort().join(',');
const show = (message, error = false) => { $('notice').textContent = message; $('notice').classList.toggle('error', error); };
const run = fn => async event => { try { await fn(event); } catch (e) { show(e.message, true); } };

async function request(op, args = {}) {
  const response = await fetch('/api', {method:'POST', headers:{'Content-Type':'application/json','X-Head':'1'}, body:JSON.stringify({op,...args}), signal:AbortSignal.timeout(6000)});
  const data = await response.json();
  if (data.state) ingest(data.state);
  if (!response.ok || data.error) throw new Error(data.error || '操作未被接受');
  return data;
}
function ingest(next) {
  if (state && next.stamp < state.stamp) return;
  state = next; networkOK = true;
  if (ownToken && session()?.token !== ownToken) {ownToken = null; pending = null; generation++;}
  render();
}
function observation() {
  const result = {text:$('obs-text').value};
  for (const k of ['reached','buzz','jitter','heat']) result[k] = $('obs-'+k).value;
  return result;
}
function resetObservation() {
  for (const k of ['reached','buzz','jitter','heat']) $('obs-'+k).value = 'unknown';
  $('obs-text').value = '';
}
function limits(n) {return state.verified_ranges[n] || state.limits[n];}
function choose(names) {
  if (session() || state.busy || state.powered.length || state.held.length) {
    show('切换控制对象前，请先全部卸力。', true); return;
  }
  lastToken = null;
  selection = [...new Set(names)].sort();
  if (selection.includes('JL') || selection.includes('JR')) selection = [...new Set([...selection,'JL','JR'])].sort();
  draft = Object.fromEntries(selection.map(n => [n,state.angles[n] ?? 90]));
  resetObservation(); axesKey = null; render();
}
function chooseMotor(n, group) {
  if (selectionMode === 'pair') return choose(group);
  if (selectionMode === 'single') return choose([n]);
  let result = selection.includes(n) ? selection.filter(x => x !== n) : [...selection,n];
  if ((n === 'JL' || n === 'JR') && selection.includes(n)) result = result.filter(x => !['JL','JR'].includes(x));
  choose(result);
}
function buildMotors() {
  const key = JSON.stringify([selection,selectionMode,state.boards,Boolean(session()),state.busy,state.powered]);
  if (key === listKey) return; listKey = key;
  $('motor-list').innerHTML = [...state.groups].reverse().map(g => `<div class="motor-group"><div class="group-label"><span>${esc(g.label)}</span><button class="group-pick" data-group="${esc(g.names.join(','))}">选此组</button></div><div class="motor-buttons">${g.names.map(n => `<button class="${selection.includes(n)?'selected ':''}${state.blocked[n]?'fault':''}" aria-pressed="${selection.includes(n)}" data-motor="${n}" data-members="${g.names.join(',')}" title="${esc(state.blocked[n] || g.label)}">${n}<small>${state.blocked[n]?'隔离':(state.boards.includes(state.servo_boards[n])?'●':'离线')}</small></button>`).join('')}</div></div>`).join('');
  $('motor-list').querySelectorAll('[data-motor]').forEach(b => b.onclick = () => chooseMotor(b.dataset.motor,b.dataset.members.split(',')));
  $('motor-list').querySelectorAll('[data-group]').forEach(b => b.onclick = () => choose(b.dataset.group.split(',')));
}
function buildAxes() {
  const key = selection.join(',');
  if (key === axesKey) return; axesKey = key;
  $('axes').innerHTML = selection.map(n => {
    const [lo,hi] = limits(n); signs[n] = state.dirs[n]; draft[n] = state.angles[n] ?? 90;
    return `<section class="axis" data-axis="${n}"><div class="axis-heading"><div class="axis-name">${n}<small>${esc(namesCN[n] || state.groups.find(g=>g.names.includes(n))?.label || '')} · ${state.servo_boards[n]}</small></div><div class="axis-readings"><label>指令角度<output id="actual-${n}">—</output></label><label>滑块目标<output class="target" id="target-${n}">90.0°</output></label></div></div><input type="range" id="slider-${n}" aria-label="${n} 目标角度" min="${lo}" max="${hi}" step="0.5" value="90"><div class="range-labels"><span>${lo}°</span><span>${state.verified_ranges[n]?'已记录的范围':'配置限位 · 尚非机械验收范围'}</span><span>${hi}°</span></div><div class="axis-controls"><button data-n="${n}" data-d="-1">−1°</button><button data-n="${n}" data-d="-0.5">−0.5°</button><button data-n="${n}" data-d="0.5">+0.5°</button><button data-n="${n}" data-d="1">+1°</button><select id="sign-${n}" aria-label="${n} 组联动方向"><option value="1">组正向 → 增大角度</option><option value="-1">组正向 → 减小角度</option></select></div><label class="axis-direction">实际方向说明<input id="direction-${n}" maxlength="120" placeholder="待核实，例如：增角时下唇向上"></label></section>`;
  }).join('');
  selection.forEach(n => {
    $('slider-'+n).oninput = e => adjust(n,Number(e.target.value));
    $('sign-'+n).value = String(signs[n]);
    $('sign-'+n).onchange = e => {signs[n] = Number(e.target.value);};
  });
  $('axes').querySelectorAll('[data-d]').forEach(b => b.onclick = () => adjust(b.dataset.n,draft[b.dataset.n]+Number(b.dataset.d)));
  paintDraft();
}
function paintDraft() {
  for (const n of selection) {
    if (!$('slider-'+n)) continue;
    $('slider-'+n).value = draft[n] ?? 90;
    $('target-'+n).textContent = Number(draft[n] ?? 90).toFixed(1)+'°';
  }
}
function adjust(n, value) {
  if (!exploring() || !networkOK) {paintDraft(); return;}
  let affected = $('linked').checked ? [...selection] : [n];
  if (['JL','JR'].includes(n) && !affected.includes(n === 'JL'?'JR':'JL')) affected.push(n === 'JL'?'JR':'JL');
  const factors = Object.fromEntries(affected.map(x => [x, $('linked').checked ? signs[x]/signs[n] : 1]));
  if (['JL','JR'].includes(n)) factors[n === 'JL'?'JR':'JL'] = -1;
  let delta = value-draft[n], low = -Infinity, high = Infinity;
  for (const x of affected) {
    const [lo,hi] = limits(x), sign = factors[x];
    low = Math.max(low,Math.min((lo-draft[x])/sign,(hi-draft[x])/sign));
    high = Math.min(high,Math.max((lo-draft[x])/sign,(hi-draft[x])/sign));
  }
  delta = Math.max(low,Math.min(high,delta));
  for (const x of affected) draft[x] = Math.round((draft[x]+delta*factors[x])*100)/100;
  paintDraft(); queueTarget();
}
function queueTarget() {
  pending = {token:ownToken,seq:++seq,angles:{...draft},speed:Number($('speed').value)};
  flushTargets();
}
async function flushTargets() {
  if (sending || !pending) return;
  sending = true;
  const expected = generation;
  try {
    while (pending && expected === generation) {
      const goal = pending; pending = null;
      await request('cal_target',goal);
    }
  } catch(e) {
    if (expected !== generation) return;
    pending = null; show(e.message,true);
    if (owned()) {draft = {...session().goal}; paintDraft();}
  } finally {sending = false; if (pending) flushTargets();}
}
function renderRecords() {
  const records = state.calibration.records;
  const key = JSON.stringify([records.map(r=>r.id),exploring(),selection]);
  if (recordsKey === key) return; recordsKey = key;
  $('record-count').textContent = `${records.length} 条记录${records.length===100?'（最近）':''}`;
  if (!records.length) return;
  $('record-list').innerHTML = [...records].reverse().map(r => {
    const o = r.observations, words = {yes:'是',no:'否',unknown:'未确认'};
    return `<article class="record"><h4>${esc(r.name)}</h4><time>${esc(new Date(r.saved_at).toLocaleString('zh-CN',{hour12:false}))}</time><div class="angles">${Object.entries(r.angles).map(([n,v])=>`${n} ${Number(v).toFixed(1)}°`).join(' · ')}</div><p>到位 ${words[o.reached]} / 嗡声 ${words[o.buzz]}<br>抖动 ${words[o.jitter]} / 异常热 ${words[o.heat]}</p><p>${esc(o.text)}</p>${Object.entries(r.directions).map(([n,d])=>`<p>${n}：${esc(d)}</p>`).join('')}<button data-restore="${r.id}" ${exploring()&&sameNames(Object.keys(r.angles))?'':'disabled'}>慢速回到此位置</button></article>`;
  }).join('');
  $('record-list').querySelectorAll('[data-restore]').forEach(b => b.onclick = run(async () => {
    pending = null;
    const record = records.find(r => r.id === b.dataset.restore);
    await request('cal_restore',{token:ownToken,record_id:record.id,seq:++seq,speed:Number($('speed').value)});
    draft = {...record.angles}; paintDraft(); show('正在低速接近记录位置，请观察机构。');
  }));
}
function render() {
  if (!state) return;
  const cal = session(), mine = owned(), range = exploring(), diagnostic = selection.length===1 && selection[0]==='LLR';
  const previous = state.calibration.last_session;
  const canRecordPrevious = !cal && previous?.token===lastToken && sameNames(previous.names);
  $('mode').textContent = state.mode==='sim'?'仿真 / 不连接电机':'真机 / ROG';
  $('mode').classList.toggle('live',state.mode==='hardware');
  $('boards').textContent = `${state.boards.length} / 3 控制板在线`;
  $('selection-count').textContent = `已选 ${selection.length} 个 · ${selection.join(' / ') || '—'}`;
  $('selection-title').innerHTML = `${esc(selection.join(' + ') || '选择电机')} <span>${selection.length===1?esc(namesCN[selection[0]] || ''):'组合控制'}</span>`;
  $('power-status').textContent = state.powered.length ? `${state.powered.length} 个通电` : '已卸力';
  $('power-status').classList.toggle('live',state.powered.length>0);
  $('diagnostic').hidden = !diagnostic; $('normal-controls').hidden = diagnostic;
  buildMotors(); buildAxes();
  const locked = selection.some(n => state.blocked[n] || !state.boards.includes(state.servo_boards[n]));
  $('begin').disabled = !networkOK || !selection.length || locked || state.busy || state.powered.length>0 || state.held.length>0;
  $('manual').disabled = mine && cal.phase==='center' ? !networkOK : $('begin').disabled;
  $('manual').textContent = mine ? (range ? '手动调节中' : '转为手动调节') : '通电并手动调节';
  $('probe').disabled = !networkOK || !state.llr_unloaded || !state.boards.includes('mouth') || state.busy || state.powered.length>0;
  $('probe-status').textContent = state.llr_probe || (state.llr_unloaded?'已启用拆舵盘检查模式。':'服务未启用拆舵盘检查模式。');
  $('capture').disabled = !(mine && cal.at_goal || canRecordPrevious) || sending || Boolean(pending);
  $('capture').textContent = canRecordPrevious ? '补记上次位置（已卸力）' : '记录当前位置';
  $('speed').disabled = !range; $('return90').disabled = !range;
  $('session-message').textContent = cal ? (mine ? `${cal.phase==='center'?'90° 观察；点击上方转为手动调节即可使用滑块':'手动调节中，可直接拖动滑块'} · ${Math.ceil(cal.remaining)} 秒后自动卸力` : '另一个页面持有标定会话；当前页面只读。可按全部卸力结束。') : (locked?'所选通道含隔离或离线电机；LLR 请单独进入检查入口。':'已卸力。点击通电并手动调节后，即可拖动滑块；观察项无需先填写。');
  $('step-center').classList.toggle('active',!range); $('step-range').classList.toggle('active',range); $('step-save').classList.toggle('active',range&&cal.at_goal);
  for (const n of selection) {
    $('actual-'+n).textContent = Number(state.angles[n] ?? 90).toFixed(1)+'°';
    $('slider-'+n).disabled = !range || !networkOK;
    $('sign-'+n).disabled = ['JL','JR'].includes(n);
  }
  $('axes').querySelectorAll('[data-d]').forEach(b=>b.disabled = !range || !networkOK);
  $('emotion-save').disabled = !mine || !cal.at_goal;
  $('emotion-play').disabled = state.busy;
  $('emotion-state').textContent = state.library.labels.map(p=>`${p.label}：${p.problem || '已保存'}`).join(' · ')+(state.preview?'\n预览 '+JSON.stringify(state.preview.angles):'');
  renderRecords();
  if (state.error && state.error !== lastError) {lastError = state.error; show(state.error,true);}
}
document.querySelectorAll('[data-mode]').forEach(b => b.onclick = () => {
  selectionMode = b.dataset.mode;
  document.querySelectorAll('[data-mode]').forEach(x=>x.setAttribute('aria-pressed',String(x===b)));
  render();
});
async function begin(manual) {
  const expected = generation; $('begin').disabled = true; $('manual').disabled = true;
  await request('cal_begin',{names:selection,duration:Number($('center-duration').value),epoch:state.calibration.epoch,manual});
  const token = session()?.token;
  if (expected !== generation) {if(token) await request('cal_stop',{token}); return;}
  ownToken = token; lastToken = token; seq = 0; draft = {...session().goal}; paintDraft(); render();
  show(manual ? '已通电，可直接拖动滑块或用 ±0.5° / ±1° 微调，默认 5°/秒。' : '已发送 90°，到时自动卸力；也可点击转为手动调节继续调整。');
}
$('begin').onclick = run(() => begin(false));
$('manual').onclick = run(async () => {
  if (owned() && session().phase==='center') {
    await request('cal_range',{token:ownToken});
    draft = {...session().goal}; paintDraft(); render();
    show('已转为手动调节，可以直接拖动滑块；不需要先填写观察。');
  } else await begin(true);
});
$('return90').onclick = () => {if(exploring()){draft = Object.fromEntries(selection.map(n=>[n,90])); paintDraft(); queueTarget();}};
$('speed').onchange = () => {if(exploring()) queueTarget();};
$('capture').onclick = run(async () => {
  const directions = Object.fromEntries(selection.map(n=>[n,$('direction-'+n).value]));
  await request('cal_capture',{token:ownToken || lastToken,name:$('position-name').value,kind:$('position-kind').value,observation:observation(),directions});
  show('位置与现场观察已保存，可导出或在相同组合内慢速返回。');
});
$('probe').onclick = run(async () => {await request('probe_llr',{duration:Number($('probe-duration').value),epoch:state.calibration.epoch}); show('LLR 90° 检查已开始，到时自动卸力；有异常可立即按 Esc。');});
$('probe-save').onclick = run(async () => {
  if (!$('probe-note').value.trim()) throw new Error('请先填写本次 LLR 观察。');
  await request('note',{servos:['LLR'],status:'info',text:'LLR 拆舵盘检查 / '+$('probe-note').value}); show('LLR 观察已写入标定日志。');
});
$('stop').onclick = run(async () => {
  generation++; pending = null; ownToken = null;
  await request('relax'); show('已请求全部卸力。若仍有受力或声音，请断开舵机电源。');
});
document.addEventListener('keydown',e=>{if(e.key==='Escape'){e.preventDefault();$('stop').click();}});
$('emotion-save').onclick = run(async () => {await request('save_expression',{label:$('emotion').value,revision:state.library.revision,title:$('position-name').value,text:$('obs-text').value});show('表情已保存。');});
$('emotion-preview').onclick = run(async () => {await request('load_expression',{label:$('emotion').value});show('已加载角度预览，没有驱动电机。');});
$('emotion-play').onclick = run(async () => {await request('emotion',{label:$('emotion').value,transition:5,revision:state.library.revision});show('正在按已保存的表情慢速重放。');});
window.addEventListener('pagehide',()=>{
  if (ownToken) fetch('/api',{method:'POST',headers:{'Content-Type':'application/json','X-Head':'1'},body:JSON.stringify({op:'cal_stop',token:ownToken}),keepalive:true}).catch(()=>{});
});
let polling = false, touching = false;
async function poll() {
  if (polling) return; polling = true;
  try {
    const response = await fetch('/state',{signal:AbortSignal.timeout(2500)});
    if (!response.ok) throw new Error('状态读取失败');
    ingest(await response.json());
  } catch(e) {networkOK=false; pending=null; if(state) render(); show('连接中断：控制已禁用，服务端将在连接超时后尝试卸力。若仍受力请断开 5V。',true);}
  finally {polling=false;}
}
setInterval(poll,500);
setInterval(async()=>{
  if (!owned() || touching || !networkOK) return;
  touching=true;
  const token = ownToken;
  try {await request('cal_touch',{token});} catch(e){if(ownToken===token) show(e.message,true);} finally{touching=false;}
},1000);
poll().then(()=>{if(networkOK) show('已连接。选电机 → 通电并手动调节 → 拖动滑块；页面不会自动通电。');});
