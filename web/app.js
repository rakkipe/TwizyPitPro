'use strict';
const $ = id => document.getElementById(id);
const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
let state, bootstrap, draft, draftIdentity, selectedPage='dashboard', currentPlan, polling=false, toastTimer, profileCache=[];
const urlToken = new URLSearchParams(location.search).get('viewer');
if(urlToken){sessionStorage.setItem('pit-viewer',urlToken);history.replaceState({},'',location.pathname+location.hash);}
const viewerToken = sessionStorage.getItem('pit-viewer') || '';
const pageInfo = {
  dashboard:['Pit dashboard','Alles onder controle.','Van eerste uitlezing tot de volgende stint.'],
  diagnostics:['Diagnose','Ken je machine.','Identiteit, firmware en storingen op één plek.'],
  tuning:['Tuning studio','Elke instelling telt.','Ontwerp, vergelijk en test je circuitafstelling.'],
  profiles:['Profielen','Een setup voor elke stint.','Bewaar je ideeën per model en firmwareversie.'],
  sessions:['Sessies & logs','Maak elke ronde inzichtelijk.','Telemetrie, handmatige rondetijden en je pitlogboek.'],
  hardware:['Hardware','Jouw verbonden pit.','Laptop, CAN-adapter en telefoon werken samen.']
};

async function api(path, body){
  const headers={'X-Pit-Viewer':viewerToken};
  const config={headers};
  if(body !== undefined){Object.assign(headers,{'Content-Type':'application/json','X-Pit-CSRF':bootstrap?.csrf || ''});config.method='POST';config.body=JSON.stringify(body);}
  if(body !== undefined && !path.startsWith('/api/security/') && path!=='/api/plan' && !(path==='/api/record'&&body.action==='lap'&&state?.session)) {
    headers['X-Pit-Owner']=await ownerConsent();
  }
  const response=await fetch(path,config);
  let result;
  try{result=await response.json();}catch{throw Error('Ongeldig serverantwoord. Controleer of Pit Pro nog draait.');}
  if(!response.ok)throw Error(result.error || 'Actie mislukt.');
  return result;
}
function toast(message,error=false){clearTimeout(toastTimer);$('toast').textContent=message;$('toast').className='visible'+(error?' error':'');toastTimer=setTimeout(()=>$('toast').className='',5500);}
function action(id,handler){const element=$(id);if(element.dataset.bound)return;element.dataset.bound='yes';element.addEventListener('click',async event=>{const button=event.currentTarget;if(button.classList.contains('busy'))return;button.classList.add('busy');try{await handler();}catch(error){toast(error.message,true);}finally{button.classList.remove('busy');}});}
async function refresh(){if(polling)return;polling=true;try{state=await api('/api/state');render();}catch(error){$('mode-pill').className='mode-pill offline';$('mode-pill').textContent='SERVER OFFLINE';$('persistent-alert').hidden=false;$('persistent-alert').textContent='Serververbinding verloren. Getoonde gegevens zijn niet actueel.';document.querySelectorAll('.metric-value b').forEach(el=>el.textContent='—');}finally{polling=false;}}
function format(value,digits=0){return typeof value==='number'&&Number.isFinite(value)?value.toLocaleString('nl-BE',{minimumFractionDigits:digits,maximumFractionDigits:digits}):'—';}
function shortTime(at){return at?new Date(at).toLocaleTimeString('nl-BE',{hour:'2-digit',minute:'2-digit',second:'2-digit'}):'—';}
function kv(label,value){return `<div class="kv"><span>${esc(label)}</span><strong>${esc(value??'Onbekend')}</strong></div>`;}
function setPage(page){if(!pageInfo[page])page='dashboard';selectedPage=page;document.querySelectorAll('.page').forEach(el=>el.classList.toggle('active',el.id==='page-'+page));document.querySelectorAll('.nav').forEach(el=>el.classList.toggle('active',el.dataset.page===page));const [label,title,subtitle]=pageInfo[page];$('breadcrumb').textContent=label;$('page-title').textContent=title;$('page-subtitle').textContent=subtitle;location.hash=page;if(state){render();if(page==='profiles')renderProfiles().catch(e=>toast(e.message,true));if(page==='sessions')renderSessions().catch(e=>toast(e.message,true));}window.scrollTo({top:0,behavior:'instant'});}
document.querySelectorAll('[data-page]').forEach(button=>button.addEventListener('click',()=>setPage(button.dataset.page)));
window.addEventListener('hashchange',()=>{const page=location.hash.slice(1);if(page!==selectedPage)setPage(page);});

function render(){
  if(!state)return;
  const c=state.compatibility,s=state.sample, demo=state.mode==='demo', valid=state.connected && (s.age??0)<6;
  $('mode-pill').className='mode-pill'+(demo?'':state.connected?' live':' offline');
  $('mode-pill').innerHTML=`<i class="dot"></i>${demo?'DEMOMODUS':state.connected?'LIVE · ALLEEN LEZEN':'NIET VERBONDEN'}`;
  $('clock').textContent=new Date().toLocaleTimeString('nl-BE',{hour:'2-digit',minute:'2-digit'});
  $('vehicle-name').innerHTML=`TWIZY <em>${esc(c.model||'?')}</em>`;
  document.querySelector('.big-number').textContent=c.model||'?';
  $('firmware').textContent=c.software;
  $('active-profile').textContent=state.profile_name;
  $('vehicle-status').textContent=demo?'DEMO GEREED':state.connected?'ALLEEN UITLEZEN':'OFFLINE';
  $('hero-connection').textContent=demo?' Simulator verbonden':state.connected?' Controller verbonden':' Geen verbinding';
  $('footer-mode').textContent=demo?'Simulatie · geen voertuigdata':state.connected?'Live CANopen · alleen uitlezen':'Offline · data niet actueel';
  $('demo-run').disabled=!demo||!bootstrap.local||!!state.pending;
  $('demo-run').textContent=state.running?'Terug naar de pit ↙':'Start demoronde ↗';
  $('stint-title').textContent=state.running?'De demo is op het circuit.':'Van pitstraat naar circuit.';
  $('stint-copy').textContent=state.running?'Gesimuleerde telemetrie; geen voorspelling van rondetijd of prestaties.':'Test telemetrie en sessieopname zonder voertuig.';
  const alerts=[];
  if(!bootstrap.local)alerts.push('Telefoonviewer · bediening blijft op de laptop.');
  if(state.pending)alerts.push(`Demo-transactie: ${esc(state.pending.phase)}. ${bootstrap.local?'<button class="button" id="pending-cycle">Demo-contactcyclus</button><button class="button" id="pending-restore">Demo herstellen</button>':''}`);
  if(demo && !['none','writefail'].includes(state.fault_scenario))alerts.push('Gesimuleerde storing actief: '+esc(state.fault_scenario)+'. Tuningtoepassing geblokkeerd.');
  if(state.connected && !valid)alerts.push('Telemetrie verouderd. Controleer de busverbinding.');
  if(!demo&&state.connected)alerts.push('Live diagnose actief. Niet-uitgelezen waarden blijven onbekend. Deze release schrijft niet naar het voertuig.');
  $('persistent-alert').hidden=!alerts.length;const alertContent=alerts.join('<br>');if($('persistent-alert').dataset.content!==alertContent){$('persistent-alert').innerHTML=alertContent;$('persistent-alert').dataset.content=alertContent;}
  if($('pending-cycle'))action('pending-cycle',async()=>{await api('/api/cycle-demo',{});await refresh();toast('Demo-contactcyclus afgerond.');});
  if($('pending-restore'))action('pending-restore',async()=>{await api('/api/cycle-demo',{restore:true});draft=null;await refresh();toast('Demo hersteld vanuit snapshot.');});
  renderMetrics(valid?s:{});
  const checks=[['Model & firmware',c.label+' · '+c.software,c.known?'ok':'warn'],['Verbinding',demo?'Simulator · geen CAN-verkeer':state.connected?'CANopen · beschikbare leesvelden':'Geen verbinding',state.connected?'ok':'unknown'],['Diagnose',state.scan?'Rapport opgeslagen · '+shortTime(state.scan.at):'Nog geen scan uitgevoerd',state.scan?'ok':'unknown'],['Live tuning',c.locked?'Firmware vergrendeld':'Hardwarekwalificatie nog nodig','warn']];
  $('readiness-list').innerHTML=checks.map(([label,text,status])=>`<div class="readiness-row"><span class="check-dot ${status==='ok'?'':status}">${status==='ok'?'✓':status==='warn'?'!':'·'}</span><div><strong>${label}</strong><small>${esc(text)}</small></div></div>`).join('');
  const event=state.events[0];$('last-activity').innerHTML=event?`<div class="recent-title">${esc(event.title)} <small class="muted">${shortTime(event.at)}</small></div><p class="recent-detail">${esc(event.detail)}</p>`:'';
  $('chart-empty').hidden=state.running||state.history.some(p=>(p.speed??0)>0)||!demo;
  $('sample-label').textContent=demo?'Gesimuleerde data · circa 1 Hz':`Live SDO · laatste sample ${format(s.age,1)} s geleden`;
  if(selectedPage==='dashboard')drawTelemetry();
  if(!draft||draftIdentity!==c.fingerprint){draft={...Object.fromEntries(state.parameters.map(p=>[p.key,p.default])),...state.current};draftIdentity=c.fingerprint;renderEditor();}
  if(selectedPage==='tuning')renderTuneSummary();
  if(selectedPage==='diagnostics')renderDiagnostics();
  if(selectedPage==='sessions')renderLog();
  if(selectedPage==='hardware')renderHardware();
  for(const id of ['scan-dashboard','scan-diagnostics'])$(id).disabled=!bootstrap.local||!state.connected||state.busy;
  for(const id of ['record-start','record-lap','record-stop'])$(id).disabled=!bootstrap.local||(id==='record-start'?!!state.session||!state.connected:!state.session);
  $('record-title').textContent=state.session?`Opname actief · ${state.session.samples} samples`:'Leg je volgende stint vast.';
  ['connect-open','plan-profile','save-profile','switch-demo','hardware-connect'].forEach(id=>$(id).disabled=!bootstrap.local);
  $('fault-select').disabled=!demo||!bootstrap.local;
}
function renderMetrics(s){
  const rows=[['speed','Snelheid',s.speed,'km/u','↗',state.mode==='demo'?'Gesimuleerde snelheid':'Niet afgeleid zonder reductiekastcontrole'],['soc','Laadniveau',s.soc,'%','▱',state.mode==='demo'?'Gesimuleerde accu':'BMS niet uitgelezen'],['power','Elektrisch accuvermogen',s.power,'kW','ϟ',state.mode==='demo'?'Negatief = regeneratie':'Niet beschikbaar via deze SDO-scope'],['motor_temp','Motortemperatuur',s.motor_temp,'°C','♧',state.mode==='demo'?'Gesimuleerde temperatuur':'Gemeten · 4600:03']];
  if(!$('metric-cards').children.length)$('metric-cards').innerHTML=rows.map(([key,name,,,,note])=>`<article class="metric"><div class="metric-top"><span>${name}</span><span class="metric-icon" id="mi-${key}"></span></div><div class="metric-value"><b id="mv-${key}">—</b><small id="mu-${key}"></small></div><div class="metric-bottom"><span id="mn-${key}">${note}</span><span class="mini-bar"><i></i></span></div></article>`).join('');
  for(const [key,,value,unit,icon,note] of rows){$('mi-'+key).textContent=icon;$('mv-'+key).textContent=format(value,key==='power'?1:0);$('mu-'+key).textContent=unit;$('mn-'+key).textContent=note;}
}
function prepareCanvas(id){const canvas=$(id);if(!canvas||!canvas.clientWidth)return;const rect=canvas.getBoundingClientRect(),ratio=devicePixelRatio||1;canvas.width=Math.round(rect.width*ratio);canvas.height=Math.round(rect.height*ratio);const ctx=canvas.getContext('2d');ctx.scale(ratio,ratio);return {ctx,w:rect.width,h:rect.height};}
function drawTelemetry(){const dim=prepareCanvas('telemetry-chart');if(!dim)return;const {ctx,w,h}=dim, left=29,right=w-30,top=11,bottom=h-23;ctx.font='8px Segoe UI';ctx.textBaseline='middle';ctx.strokeStyle='#edf1e7';ctx.fillStyle='#a2ac95';for(let i=0;i<=4;i++){let y=top+(bottom-top)*i/4;ctx.beginPath();ctx.moveTo(left,y);ctx.lineTo(right,y);ctx.stroke();ctx.fillText(String(120-i*30),1,y);ctx.fillStyle='#7798a7';ctx.fillText(String(20-i*7.5),right+7,y);ctx.fillStyle='#a2ac95';}ctx.fillText('km/u',0,h-6);ctx.fillText('kW',right+4,h-6);
  const data=state.history;const stroke=(field,color,min,max,fill=false)=>{let points=data.map((d,i)=>({x:left+(right-left)*i/Math.max(89,data.length-1),y:typeof d[field]==='number'?bottom-(bottom-top)*(d[field]-min)/(max-min):null}));ctx.save();ctx.beginPath();ctx.rect(left,top,right-left,bottom-top);ctx.clip();ctx.beginPath();let open=false;for(const p of points){if(p.y===null){open=false;continue;}if(!open)ctx.moveTo(p.x,p.y);else ctx.lineTo(p.x,p.y);open=true;}ctx.lineWidth=1.7;ctx.strokeStyle=color;ctx.stroke();if(fill&&points.length&&points.every(p=>p.y!==null)){ctx.lineTo(points.at(-1).x,bottom);ctx.lineTo(points[0].x,bottom);ctx.closePath();const gradient=ctx.createLinearGradient(0,top,0,bottom);gradient.addColorStop(0,'#a5c75b30');gradient.addColorStop(1,'#a5c75b02');ctx.fillStyle=gradient;ctx.fill();}ctx.restore();};stroke('speed','#90ab55',0,120,true);stroke('power','#729eae',-10,20);ctx.fillStyle='#9fa991';for(let i=0;i<4;i++)ctx.fillText(i===3?'nu':`${90-i*30}s`,left+(right-left)*i/3-4,h-6);}
function drawMap(){const dim=prepareCanvas('map-chart');if(!dim||!draft)return;const {ctx,w,h}=dim;ctx.strokeStyle='#dce5ce';ctx.lineWidth=1;ctx.beginPath();ctx.moveTo(16,8);ctx.lineTo(16,h-17);ctx.lineTo(w-7,h-17);ctx.stroke();ctx.strokeStyle='#789d34';ctx.fillStyle='#789d34';ctx.lineWidth=2;ctx.beginPath();for(let i=1;i<=4;i++){const x=16+(w-30)*draft['D_speed'+i]/130,y=h-17-(h-28)*draft['D_level'+i]/100;i===1?ctx.moveTo(x,y):ctx.lineTo(x,y);}ctx.stroke();for(let i=1;i<=4;i++){ctx.beginPath();ctx.arc(16+(w-30)*draft['D_speed'+i]/130,h-17-(h-28)*draft['D_level'+i]/100,3,0,Math.PI*2);ctx.fill();}ctx.font='8px Segoe UI';ctx.fillStyle='#9caa89';ctx.fillText('0',13,h-3);ctx.fillText('130 km/u',w-46,h-3);}
window.addEventListener('resize',()=>{if(state){drawTelemetry();drawMap();}});

function renderDiagnostics(){const identity=state.identity,c=state.compatibility;const hex=v=>typeof v==='number'?'0x'+v.toString(16).toUpperCase().padStart(8,'0'):'Onbekend';$('identity-table').innerHTML=kv('Model / controllerfamilie',c.label)+kv('Software',c.software)+kv('Hardware',identity.hardware)+kv('Product-ID',hex(identity.product))+kv('Dictionary-revisie',hex(identity.revision))+kv('Serienummer',identity.serial)+kv('Herkomst',state.mode==='demo'?'SIMULATIE':'Uitgelezen / deels onbekend');$('compatibility-card').innerHTML=`<span class="info-chip">${esc(c.status)}</span><p class="muted">${esc(c.reason)}</p>${kv('Gekozen softwarevariant',c.variant)}${kv('Live schrijven','Niet beschikbaar')}${kv('Firmware flashen','Niet beschikbaar')}<p class="helper">${esc(c.model_note)}</p>`;
  const scan=state.scan;if(!scan){$('diagnostic-report').innerHTML='Voer een scan uit om de beschikbare gegevens vast te leggen.';$('register-table').innerHTML='';return;}
  $('diagnostic-report').innerHTML=scan.observations.map(o=>`<div class="observation"><span class="check-dot ${o.status==='ok'?'':o.status==='attention'?'warn':'unknown'}">${o.status==='ok'?'✓':o.status==='attention'?'!':'·'}</span><div><strong>${esc(o.name)}</strong><p>${esc(o.text)}</p></div></div>`).join('')+`<p class="helper">${esc(scan.scope)}</p>`;
  $('register-table').innerHTML=`<table><thead><tr><th>REGISTER</th><th>BETEKENIS</th><th>RUWE WAARDE</th><th>BYTES</th><th>STATUS</th></tr></thead><tbody>${scan.registers.map(r=>`<tr><td class="mono">${esc(r.address)}</td><td>${esc(r.key)}</td><td class="mono">${esc(r.raw??'—')}</td><td>${esc(r.width)}</td><td>${esc(r.error|| (state.mode==='demo'?'Demo':'Uitgelezen'))}</td></tr>`).join('')}</tbody></table>`;
}
function renderEditor(){const groups=[...new Set(state.parameters.map(p=>p.group))];$('group-filter').innerHTML='<option value="all">Alle instellingen</option>'+groups.map(g=>`<option value="${esc(g)}">${esc(g)}</option>`).join('');$('parameter-groups').innerHTML=groups.map(g=>`<article class="panel parameter-group" data-group="${esc(g)}"><div class="group-heading"><h3>${esc(g)}</h3><span>${state.parameters.filter(p=>p.group===g).length} INSTELLINGEN</span></div>${state.parameters.filter(p=>p.group===g).map(p=>`<div class="parameter-row" data-key="${p.key}"><div class="parameter-header"><label for="num-${p.key}">${esc(p.name)}</label><div class="number-field"><input type="number" id="num-${p.key}" data-key="${p.key}" min="${p.min}" max="${p.max}" step="1" value="${draft[p.key]}" aria-label="${esc(p.name)}"><span>${esc(p.unit)}</span></div></div><p>${esc(p.note)}</p><div class="range-line"><span>${p.min}</span><input type="range" id="range-${p.key}" data-key="${p.key}" min="${p.min}" max="${p.max}" step="1" value="${draft[p.key]}" aria-label="${esc(p.name)} schuifregelaar"><span>${p.max}</span></div></div>`).join('')}</article>`).join('');
  $('parameter-groups').querySelectorAll('input').forEach(input=>input.addEventListener('input',()=>{const key=input.dataset.key;draft[key]=input.value===''?NaN:Number(input.value);const other=$(input.type==='range'?'num-'+key:'range-'+key);other.value=input.value;currentPlan=null;renderTuneSummary();}));filterParameters();renderTuneSummary();}
function renderTuneSummary(){if(!draft)return;const changes=state.parameters.filter(p=>draft[p.key]!==state.current[p.key]);$('tune-summary').innerHTML=`<div class="change-count">${changes.length}<span>${state.mode==='demo'?'wijzigingen':'ontwerpvelden · beginsituatie onbekend'}</span></div>`+kv('Model',state.compatibility.label)+kv('Firmware',state.compatibility.software)+kv('Topsnelheid',format(draft.speed)+' km/u')+kv('Regeneratie gas los',format(draft.neutral)+' %');$('tuning-mode-note').textContent=state.mode==='demo'?'Bewerk de demo-instellingen. Vergelijk elke wijziging voordat je toepast.':'Ontwerp op modelreferenties. Werkelijke beginwaarden zijn niet als volledig profiel uitgelezen; live schrijven ontbreekt.';document.querySelectorAll('.parameter-row').forEach(row=>row.classList.toggle('changed',draft[row.dataset.key]!==state.current[row.dataset.key]));drawMap();}
function filterParameters(){const query=$('parameter-search').value.toLocaleLowerCase('nl'),group=$('group-filter').value;document.querySelectorAll('.parameter-group').forEach(section=>{let count=0;section.querySelectorAll('.parameter-row').forEach(row=>{const p=state.parameters.find(p=>p.key===row.dataset.key);const show=(group==='all'||p.group===group)&&(`${p.name} ${p.note} ${p.key}`.toLocaleLowerCase('nl').includes(query));row.hidden=!show;if(show)count++;});section.hidden=!count;});}
$('parameter-search').addEventListener('input',filterParameters);$('group-filter').addEventListener('change',filterParameters);
action('reset-editor',async()=>{draft={...Object.fromEntries(state.parameters.map(p=>[p.key,p.default])),...state.current};renderEditor();toast(state.mode==='demo'?'Editor terug op huidige demowaarden.':'Modelreferenties geladen; geen voertuigdefaults vastgesteld.');});
action('plan-profile',async()=>{currentPlan=await api('/api/plan',{values:draft});const p=currentPlan;$('plan-content').innerHTML=`<p class="helper">${esc(p.mode.toUpperCase())} · ${p.changes.length} wijzigingen · plan 60 seconden geldig</p><div class="table-scroll"><table><thead><tr><th>INSTELLING</th><th>VAN</th><th>NAAR</th></tr></thead><tbody>${p.changes.map(c=>`<tr><td>${esc(c.name)}</td><td>${esc(c.before??'Onbekend')} ${esc(c.unit)}</td><td><strong>${esc(c.after)} ${esc(c.unit)}</strong></td></tr>`).join('')}</tbody></table></div>${p.blockers.map(x=>`<div class="blocker">${esc(x)}</div>`).join('')}${p.can_simulate?'<div class="success-note">Demo: snapshot → toepassing → read-back → demo-contactcyclus.</div>':''}<details><summary>${p.mapped_fields??0} velden · ${p.register_targets?.length??0} registerdoelen</summary><p class="helper">Beginwaarden komen uitsluitend uit de bijbehorende voertuigscan. ? = onbekend.</p><div class="table-scroll"><table><thead><tr><th>REGISTER</th><th>BEGIN</th><th>DOEL</th><th>VELDEN</th></tr></thead><tbody>${(p.register_targets||[]).map(r=>`<tr><td>${esc(r.address)}</td><td>${esc(r.before??'?')}</td><td>${esc(r.raw??'Flags uitlezen')}</td><td>${esc(r.key)}</td></tr>`).join('')}</tbody></table></div><button class="button" id="export-register-plan">Registervergelijking exporteren</button></details><p class="helper">${esc(p.warning)}</p>`;if($('export-register-plan'))$('export-register-plan').onclick=()=>downloadObject(p,'twizy-registerdoelen.json');$('apply-plan').disabled=!p.can_simulate;$('plan-dialog').showModal();});
action('apply-plan',async()=>{try{await api('/api/apply-demo',{plan_id:currentPlan?.id});toast('Toegepast in demo. Rond nu de demo-contactcyclus af.');}finally{$('plan-dialog').close();draft=null;await refresh();}});
action('plan-close',async()=>$('plan-dialog').close());
action('save-profile',async()=>{await api('/api/profile',{name:$('profile-name').value,values:draft});toast('Versiegebonden profiel opgeslagen.');});

async function renderProfiles(){profileCache=await api('/api/profiles');const c=state.compatibility;const base=Object.fromEntries(state.parameters.map(p=>[p.key,p.default]));const presets=[{name:'Modelreferentie',note:'Bronreferentie per controllerfamilie. Geen backup van jouw voertuig.',symbol:'01',values:base},{name:'Wet · concept',note:'Rustigere gasrespons om in de simulator te vergelijken.',symbol:'02',values:{...base,drive:70,neutral:15,brake:20,ramp_accel:15,smooth:85}},{name:'Endurance · concept',note:'Lager aandrijfniveau als startpunt voor een eigen circuitontwerp.',symbol:'03',values:{...base,drive:85,neutral:20,brake:25,ramp_accel:20}}];
  $('profiles-list').innerHTML=presets.map((p,i)=>`<article class="panel profile-card"><div class="profile-symbol">${p.symbol} ↗</div><span class="tag">DEMO / ONTWERPREFERENTIE</span><h3>${esc(p.name)}</h3><p>${esc(p.note)}</p><small>${esc(c.label)} · ${esc(c.software)}</small><button class="button full preset-load" data-index="${i}">Bewerken in studio →</button></article>`).join('')+profileCache.map((p,i)=>{const matches=p.model===c.model&&p.software===c.software&&p.revision===state.identity.revision;return `<article class="panel profile-card"><div class="profile-symbol">▱</div><span class="tag">OPGESLAGEN ONTWERP</span><h3>${esc(p.name)}</h3><p>Twizy ${esc(p.model)} · ${esc(p.software)}<br>${new Date(p.at).toLocaleDateString('nl-BE')} · ${esc(p.origin)}</p><small>${matches?'Past bij geselecteerde referentie':'Andere model-/firmwarecombinatie'}</small><button class="button full saved-load" data-index="${i}" ${matches?'':'disabled'}>Laden in studio →</button></article>`;}).join('');
  document.querySelectorAll('.preset-load').forEach(b=>b.onclick=()=>loadDraft(presets[Number(b.dataset.index)]));document.querySelectorAll('.saved-load').forEach(b=>b.onclick=()=>loadDraft(profileCache[Number(b.dataset.index)]));}
function loadDraft(profile){draft={...profile.values};$('profile-name').value=profile.name;renderEditor();setPage('tuning');toast('Ontwerp geladen; nog niet toegepast.');}
function downloadObject(object,name){const url=URL.createObjectURL(new Blob([JSON.stringify(object,null,2)],{type:'application/json'}));const a=document.createElement('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}
async function downloadAPI(path,name){const response=await fetch(path,{headers:{'X-Pit-Viewer':viewerToken}});if(!response.ok){const err=await response.json();throw Error(err.error);}const url=URL.createObjectURL(await response.blob());const a=document.createElement('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}
action('export-profile',async()=>{downloadObject({format:'TwizyPitPro-profile-v1',name:$('profile-name').value,model:state.compatibility.model,software:state.compatibility.software,revision:state.identity.revision,qualified:false,origin:state.mode,values:draft},'twizy-profiel.json');toast('Profielontwerp geëxporteerd.');});
$('import-profile').addEventListener('change',async event=>{try{const file=event.target.files[0];if(!file)return;if(file.size>100000)throw Error('Profielbestand te groot.');const profile=JSON.parse(await file.text());if(profile.format!=='TwizyPitPro-profile-v1'||profile.model!==state.compatibility.model||profile.software!==state.compatibility.software||profile.revision!==state.identity.revision)throw Error('Profielindeling, model, firmware of revisie wijkt af.');await api('/api/plan',{values:profile.values});loadDraft(profile);}catch(error){toast(error.message,true);}finally{event.target.value='';}});
for(const id of ['export-global','export-diagnostic'])action(id,()=>downloadAPI('/api/export/report','twizy-pitrapport.json'));
action('export-variants',()=>downloadAPI('/api/export/variants','twizy-versiepakketten.json'));

async function scan(){toast('Diagnose gestart…');await api('/api/diagnose',{});await refresh();setPage('diagnostics');toast('Diagnoserapport opgeslagen.');}
action('scan-dashboard',scan);action('scan-diagnostics',scan);action('hero-identify',async()=>setPage('diagnostics'));
action('demo-run',async()=>{await api('/api/demo',{running:!state.running});await refresh();});
async function openConnect(){const ports=await api('/api/ports');$('com-port').innerHTML='<option value="">Selecteer COM-poort</option>'+ports.map(p=>`<option value="${esc(p.port)}">${esc(p.port)} · ${esc(p.description)}</option>`).join('');$('connection-mode').value=state.mode==='live'?'live':'demo';updateConnectionFields();$('connect-dialog').showModal();}
function updateConnectionFields(){const demo=$('connection-mode').value==='demo';$('com-port').disabled=demo;$('adapter-type').disabled=demo;}
$('connection-mode').addEventListener('change',updateConnectionFields);
action('connect-open',openConnect);action('hardware-connect',openConnect);
action('connect-submit',async()=>{toast('Verbinding wordt ingesteld…');await api('/api/connect',{mode:$('connection-mode').value,port:$('com-port').value,adapter:$('adapter-type').value});$('connect-dialog').close();draft=null;await refresh();toast('Verbinding ingesteld.');});
action('disconnect-submit',async()=>{await api('/api/disconnect',{});$('connect-dialog').close();await refresh();toast('Verbinding gesloten.');});
action('switch-demo',async()=>{await api('/api/connect',{mode:'demo',model:$('demo-model').value,software:$('demo-firmware').value});draft=null;await refresh();toast('Demo geladen. Model en firmware opnieuw beoordeeld.');});
$('fault-select').addEventListener('change',async()=>{try{await api('/api/demo',{fault:$('fault-select').value});await refresh();toast('Demoscenario gewijzigd.');}catch(error){toast(error.message,true);}});
function renderHardware(){$('fault-select').value=state.fault_scenario;if(bootstrap.lan&&bootstrap.phone_urls.length)$('phone-status').innerHTML='Open op hetzelfde wifinetwerk:<br>'+bootstrap.phone_urls.map(url=>`<a href="${esc(url)}" target="_blank" rel="noreferrer">${esc(url)}</a>`).join('<br>')+'<br>Deze link geeft kijktoegang zolang deze server draait.';}
for(const [id,act] of [['record-start','start'],['record-lap','lap'],['record-stop','stop']])action(id,async()=>{await api('/api/record',{action:act,name:$('session-name').value});await refresh();await renderSessions();toast(act==='start'?'Sessieopname gestart.':act==='lap'?'Handmatige rondemarkering opgeslagen.':'Sessie opgeslagen.');});
async function renderSessions(){const sessions=await api('/api/sessions');$('sessions-list').innerHTML=sessions.length?sessions.map(s=>`<div class="session-item"><div><strong>${esc(s.name)}</strong><small>${esc(s.mode.toUpperCase())} · ${s.samples} samples · ${new Date(s.at).toLocaleDateString('nl-BE')}</small></div><button class="button small export-session" data-session="${s.id}">CSV ↗</button></div>`).join(''):'<p class="empty-state">Start je eerste opname; elke sample bewaart zijn herkomst.</p>';document.querySelectorAll('.export-session').forEach(b=>b.onclick=()=>downloadAPI('/api/export/session?id='+b.dataset.session,'twizy-sessie.csv').catch(e=>toast(e.message,true)));if(!state.session&&sessions.length)renderLaps(sessions[0].laps);else renderLaps(state.session?.laps||[]);}
function renderLaps(laps){const best= Math.min(...laps.map(l=>l.seconds));$('lap-list').innerHTML=laps.length?`<table><thead><tr><th>RONDE</th><th>TIJD</th><th>VERSCHIL</th></tr></thead><tbody>${laps.map(l=>`<tr><td>${l.number.toString().padStart(2,'0')}</td><td class="mono">${format(l.seconds,3)} s</td><td>${l.seconds===best?'Beste':'+ '+format(l.seconds-best,3)+' s'}</td></tr>`).join('')}</tbody></table>`:'<p class="empty-state">Nog geen handmatige rondemarkeringen.</p>';}
function renderLog(){$('event-list').innerHTML=state.events.map(e=>`<div class="event-row ${esc(e.level)}"><span class="event-time">${shortTime(e.at)}</span><div><strong>${esc(e.title)}</strong><p>${esc(e.detail)} · ${esc(e.mode.toUpperCase())}</p></div></div>`).join('');if(state.session)renderLaps(state.session.laps);}

async function init(){try{bootstrap=await api('/api/bootstrap');await refresh();setPage(location.hash.slice(1)||'dashboard');setInterval(refresh,1000);}catch(error){toast(error.message,true);$('persistent-alert').hidden=false;$('persistent-alert').textContent=error.message;}}
let ownerDialogBusy=false;
async function ownerConsent(setupOnly=false){
  if(ownerDialogBusy)throw Error('Er wacht al een eigenaarsbevestiging.');
  const security=await api('/api/security/status');
  if(security.retry_after)throw Error(`Te veel pogingen. Wacht ${security.retry_after} seconden.`);
  if(ownerDialogBusy)throw Error('Er wacht al een eigenaarsbevestiging.');
  ownerDialogBusy=true;
  const dialog=document.createElement('dialog');
  const setup=!security.configured;
  dialog.innerHTML=`<form method="dialog" class="modal"><div class="eyebrow">EIGENAARSBEVEILIGING</div><h2>${setup?'Jouw pit. Jouw toestemming.':'Bevestig deze handeling.'}</h2><p class="muted">${setup?'Kies een privéwachtwoord van minimaal 8 tekens. Wijzigingen blijven geblokkeerd totdat je dit hebt ingesteld.':'Voer je eigenaarswachtwoord in. Je geeft toestemming voor één handeling.'}</p><label>Eigenaarswachtwoord<input id="owner-password" type="password" minlength="8" maxlength="128" autocomplete="${setup?'new-password':'off'}" required></label>${setup?'<label>Herhaal wachtwoord<input id="owner-repeat" type="password" minlength="8" maxlength="128" autocomplete="new-password" required></label>':''}<button class="button primary full" value="approve">${setup?'Beveiliging instellen':'Goedkeuren'}</button><button class="button full" value="cancel" formnovalidate>Annuleren</button></form>`;
  document.body.appendChild(dialog);dialog.showModal();dialog.querySelector('input').focus();
  try{
    const password=await new Promise((resolve,reject)=>{dialog.addEventListener('close',()=>{if(dialog.returnValue!=='approve')return reject(Error('Geannuleerd; niets gewijzigd.'));const value=dialog.querySelector('#owner-password').value;if(setup&&value!==dialog.querySelector('#owner-repeat').value)return reject(Error('Wachtwoorden komen niet overeen.'));resolve(value);},{once:true});});
    if(setup){await api('/api/security/setup',{password});toast('Eigenaarsbeveiliging ingesteld.');}
    return password;
  }finally{dialog.querySelectorAll('input').forEach(input=>input.value='');dialog.remove();ownerDialogBusy=false;}
}
const ownerButton=document.createElement('button');ownerButton.className='button small';ownerButton.textContent='Beveiliging';ownerButton.setAttribute('aria-label','Eigenaarsbeveiliging');document.querySelector('.top-actions').prepend(ownerButton);
const androidButton=document.createElement('button');androidButton.className='button small';androidButton.textContent='Android APK ↓';androidButton.onclick=()=>downloadAPI('/api/download/android','TwizyPitPro-0.2.0.apk').catch(e=>toast(e.message,true));$('phone-status').parentElement.appendChild(androidButton);
ownerButton.onclick=async()=>{try{const status=await api('/api/security/status');if(!status.configured)await ownerConsent(true);else await changeOwnerPassword();}catch(e){toast(e.message,true);}};
async function changeOwnerPassword(){
  if(ownerDialogBusy)throw Error('Er wacht al een eigenaarsbevestiging.');ownerDialogBusy=true;
  const dialog=document.createElement('dialog');dialog.innerHTML='<form method="dialog" class="modal"><div class="eyebrow">BEVEILIGING ACTIEF</div><h2>Jij houdt de controle.</h2><p class="muted">Elke wijziging vraagt je wachtwoord. Hieronder kun je een nieuw wachtwoord instellen.</p><label>Huidig wachtwoord<input name="current" type="password" minlength="8" maxlength="128" autocomplete="off" required></label><label>Nieuw wachtwoord<input name="password" type="password" minlength="8" maxlength="128" autocomplete="new-password" required></label><label>Herhaal nieuw wachtwoord<input name="repeat" type="password" minlength="8" maxlength="128" autocomplete="new-password" required></label><button class="button primary full" value="change">Wachtwoord wijzigen</button><button class="button full" value="cancel" formnovalidate>Sluiten</button></form>';
  document.body.appendChild(dialog);dialog.showModal();
  try{await new Promise(resolve=>dialog.addEventListener('close',resolve,{once:true}));if(dialog.returnValue!=='change')return;const fields=dialog.querySelector('form').elements;if(fields.password.value!==fields.repeat.value)throw Error('Nieuwe wachtwoorden komen niet overeen.');await api('/api/security/change',{current:fields.current.value,password:fields.password.value});toast('Eigenaarswachtwoord gewijzigd.');}
  finally{dialog.querySelectorAll('input').forEach(input=>input.value='');dialog.remove();ownerDialogBusy=false;}
}
init();
