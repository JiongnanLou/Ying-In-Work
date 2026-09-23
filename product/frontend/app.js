'use strict';
const $ = s => document.querySelector(s), $$ = s => [...document.querySelectorAll(s)];
const titles={home:'今日陪伴',health:'状态观察',relax:'互动放松',focus:'专注守护',history:'我的回顾',settings:'偏好设置'};
const labels={dark_circle:'眼周观察',tongue:'舌象观察',acne:'皮肤观察',emotion:'表情与状态'};
const state={status:null,page:'home',settingsLoaded:false,history:null,selectedMinutes:25,notice:0,voiceSeq:0,jobKey:'',exerciseWasActive:false,previewBusy:false};

let toastTimeout, pendingConfirm=null;
function toast(message,error=false){$('#toast').textContent=message;$('#toast').className='show'+(error?' error':'');clearTimeout(toastTimeout);toastTimeout=setTimeout(()=>$('#toast').className='',5500);}
function escapeHTML(value){return String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));}
async function api(path,data){const response=await fetch('/api/'+path,{method:data===undefined?'GET':'POST',headers:{'X-InWork-Token':window.INWORK_TOKEN,'Content-Type':'application/json'},body:data===undefined?undefined:JSON.stringify(data)});const body=await response.json();if(!response.ok)throw new Error(body.error||'操作未完成');return body;}
function bind(selector,fn){$$(selector).forEach(button=>button.addEventListener('click',async()=>{if(button.disabled)return;button.disabled=true;try{await fn(button);}catch(error){toast(error.message,true);}finally{button.disabled=false;}}));}
function confirmAction(title,text){if(pendingConfirm)return Promise.resolve(false);$('#confirmTitle').textContent=title;$('#confirmText').textContent=text;$('#confirmDialog').showModal();return new Promise(resolve=>{pendingConfirm=resolve;});}
function resolveConfirm(value){$('#confirmDialog').close();if(pendingConfirm)pendingConfirm(value);pendingConfirm=null;}
$('#confirmYes').onclick=()=>resolveConfirm(true);$('#confirmNo').onclick=()=>resolveConfirm(false);
$('#confirmDialog').addEventListener('cancel',e=>{e.preventDefault();resolveConfirm(false);});
function page(name){if(!titles[name])return;state.page=name;$$('.page').forEach(p=>p.classList.toggle('active',p.id==='page-'+name));$$('.nav').forEach(n=>n.classList.toggle('active',n.dataset.page===name));$('#pageTitle').textContent=titles[name];if(name==='history')loadHistory().catch(e=>toast(e.message,true));window.scrollTo(0,0);}
bind('[data-page]',b=>page(b.dataset.page));bind('[data-go]',b=>page(b.dataset.go));$('.brand').addEventListener('click',e=>{e.preventDefault();page('home');});
function clock(seconds){return Math.floor(seconds/60).toString().padStart(2,'0')+':'+Math.floor(seconds%60).toString().padStart(2,'0');}
function localTime(value){return new Date(value).toLocaleString('zh-CN',{month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit'});}
function sound(){if(!state.status?.settings.sound)return;try{const C=window.AudioContext||window.webkitAudioContext;const c=new C(),o=c.createOscillator(),g=c.createGain();o.connect(g);g.connect(c.destination);o.frequency.value=520;g.gain.value=.07;o.start();g.gain.exponentialRampToValueAtTime(.001,c.currentTime+.6);o.stop(c.currentTime+.6);setTimeout(()=>c.close(),800);}catch{}}
function loadSettings(s){const cfg=s.settings;$('#sitMinutes').value=cfg.sit_minutes;$('#eyeMinutes').value=cfg.eye_minutes;$('#focusMinutes').value=cfg.focus_minutes;$('#resolution').value=cfg.resolution;$('#sound').checked=cfg.sound;$('#cloudConsent').checked=cfg.cloud_consent;$('#autoEmotion').checked=cfg.auto_emotion;$('#autoStart').checked=cfg.auto_start;$('#autoTracking').checked=cfg.auto_tracking;$('#floatingWindow').checked=cfg.floating_window;$('#hardwareExercise').checked=cfg.hardware_exercise;$('#apiUrl').value=s.ai.base_url;$('#apiModel').value=s.ai.model;$('#apiKey').placeholder=s.ai.has_api_key?'已保存；留空保留现有密钥':'填写 API Key，使用 Windows 加密保存';state.selectedMinutes=cfg.focus_minutes;state.settingsLoaded=true;}
function render(s){state.status=s;if(!state.settingsLoaded)loadSettings(s);const running=s.camera.running,hardware=!!s.camera.capabilities?.gimbal;
  $('#deviceName').textContent=s.camera.device||'摄像头';
  $('#centerButton').disabled=!hardware;
  $('#hardwareExercise').disabled=!hardware;
  $('#hardwareExercise').checked=hardware&&s.settings.hardware_exercise;
  $('#hardwareHint').textContent=hardware?'相机随活动小幅转动；活动期间暂停追踪，结束后恢复。':'当前使用屏幕引导；连接 Link 2 后可启用云台联动。';
  $('#trackingStatus').textContent=s.tracking.label+(s.tracking.error?' · '+s.tracking.error:'');
  $('#trackingStatus').style.color=['error','warning'].includes(s.tracking.state)?'#A85621':'';
  $('#deviceCaption').textContent=running?(hardware?'Link 2 · 云台可用':'本机摄像头 · 画面模式'):(s.camera.error?'画面已中断':$('#deviceCaption').dataset.detected||'等待连接');
  $('#deviceDot').classList.toggle('online',running||$('#deviceCaption').dataset.detected==='设备已连接');
  $('#cameraBadge').textContent=running?'本地实时画面':'未开启';$('#cameraEmpty').hidden=running;$('#preview').hidden=!running;
  if(!running){$$('.live-projection,#preview').forEach(img=>img.removeAttribute('src'));$('#cameraEmpty').style.display='flex';}else $('#cameraEmpty').style.display='none';
  $('#companionButton').innerHTML=running?'暂停陪伴 <span>Ⅱ</span>':'开始陪伴 <span>↗</span>';
  $('#companionCopy').innerHTML=running?'小萤正在这里，陪你认真工作。<br>需要开会时，随时暂停就好。':'准备好了就开始吧。<br>小萤会安静陪伴，适时提醒你休息。';
  $('#heroNote').textContent=running?'本地陪伴进行中 · '+(s.settings.auto_emotion&&s.settings.cloud_consent?'已开启云端表情观察':'自动云端观察关闭'):'开启后进行本地在场检测 · 可随时暂停';
  $('#resolutionLabel').textContent=running?s.camera.resolution.join(' × ')+' · 实际画面':'优先 Link 2 · 自动适配本机摄像头';$('#cameraError').textContent=s.camera.error||s.camera.notice||(s.settings.auto_emotion&&s.settings.cloud_consent?'表情观察每10秒取样发送到 Qwen，其余预览留在本机。':'视频不保存；自动云端观察未开启。');
  $('#presenceValue').textContent=!running?'等待开始':({present:'在你身边',away:'暂未检测到人脸',unknown:'正在观察'}[s.presence]);$('#sitValue').textContent=running?Math.floor(s.sit.seconds/60)+' 分钟':'—';
  $('#focusValue').textContent=s.focus.active?clock(s.focus.remaining):'准备出发';$('#timer').textContent=clock(s.focus.active?s.focus.remaining:state.selectedMinutes*60);$('#timerCaption').textContent=s.focus.active?'只做眼前这一件事':'准备好，开始一件事';$('#focusButton').textContent=s.focus.active?'结束本轮专注':'开始专注';
  $('#sitProgress').style.width=(s.sit.progress*100)+'%';$('#eyeProgress').style.width=(s.eye.progress*100)+'%';$('#sitThreshold').textContent=s.settings.sit_minutes+' 分钟';$('#eyeThreshold').textContent=s.settings.eye_minutes+' 分钟';
  $('#dndButton').classList.toggle('selected',s.settings.dnd);$('#dndButton').textContent=s.settings.dnd?'☾ 免打扰中':'☾ 免打扰';
  $('#aiBadge').textContent=$('#configBadge').textContent=s.ai.configured?'已配置 · 可测试':'AI 待配置';
  $('#voiceStatus').textContent=s.voice.status;$('#voiceButton').textContent=s.voice.active?'停止语音聆听':'开启语音唤醒';
  for(const notice of s.notifications){if(notice.id>state.notice){state.notice=notice.id;if(!s.settings.dnd){toast(notice.label);sound();}}}
  if(s.voice.seq>state.voiceSeq){state.voiceSeq=s.voice.seq;if(s.voice.last_text)runCommand(s.voice.last_text,true).catch(e=>toast(e.message,true));}
  renderJob(s.job);renderExercise(s.exercise);renderMood(s);renderGame(s.game);$('#railCompanion').textContent=running?'暂停陪伴 Ⅱ':'开始陪伴 ↗';$('#railPresence').textContent=$('#presenceValue').textContent;$('#railFocus').textContent='专注 · '+$('#focusValue').textContent;window.inworkReady=true;
}
async function refresh(){try{render(await api('status'));}catch(e){$('#cameraError').textContent='无法连接本地服务：'+e.message;}finally{setTimeout(refresh,800);}}
async function preview(){if(state.status?.camera.running&&!state.previewBusy){state.previewBusy=true;try{const response=await fetch('/api/frame?token='+encodeURIComponent(window.INWORK_TOKEN),{cache:'no-store'});if(response.ok&&response.status!==204){const blob=await response.blob();const old=state.frameUrl;state.frameUrl=URL.createObjectURL(blob);$$('#preview,.live-projection').filter(img=>!img.closest('dialog')||img.closest('dialog').open).forEach(img=>img.src=state.frameUrl);if(old)URL.revokeObjectURL(old);}}catch{}finally{state.previewBusy=false;}}setTimeout(preview,100);}
bind('#companionButton,#railCompanion',async()=>{const running=state.status?.camera.running;toast(running?'正在停止采集并释放相机…':'正在检测可用摄像头…');await api(running?'camera/stop':'camera/start',{});render(await api('status'));toast(running?'已暂停陪伴，摄像头已释放':'小萤已到位，本地陪伴开始');});
bind('#centerButton',async()=>{await api('camera/center',{});toast('云台已回正');});
bind('#dndButton',async()=>{const s=await api('settings',{dnd:!state.status?.settings.dnd});toast(s.dnd?'已开启免打扰，提醒静默记录':'已恢复关怀提醒');render(await api('status'));});
bind('#hideButton',async()=>{if(window.pywebview?.api){await window.pywebview.api.hide();}else toast('收起到托盘功能在桌面 EXE 中可用');});
bind('[data-duration]',b=>{if(state.status?.focus.active)return toast('请先结束当前专注再调整时长');state.selectedMinutes=Number(b.dataset.duration);$$('[data-duration]').forEach(n=>n.classList.toggle('selected',n===b));$('#timer').textContent=clock(state.selectedMinutes*60);});
bind('#focusButton',async()=>{await api(state.status?.focus.active?'focus/stop':'focus/start',{minutes:state.selectedMinutes});render(await api('status'));});
bind('[data-reset]',async b=>{await api('reminder/reset',{kind:b.dataset.reset});toast('已重新计时');});
async function analyze(kind,fromVoice=false){if(!state.status?.ai.configured){page('settings');return toast('请先配置 Qwen 视觉模型连接',true);}if(!state.status.settings.cloud_consent){page('settings');return toast('请先在设置中允许将采集图像发送至 Qwen 服务',true);}if(!state.status.camera.running){page('home');return toast('请先开始陪伴，连接摄像头',true);}if(fromVoice&&!(await confirmAction('开始'+labels[kind]+'？','将采集 3 张画面并发送到已配置的 Qwen 服务。')))return;page('health');state.captureDismissed=false;await api('analyze',{kind});await refreshNow();toast('请面向相机，保持姿态与光线稳定');}
bind('[data-analyze]',b=>analyze(b.dataset.analyze));bind('#cancelAnalysis',()=>api('analyze/cancel',{}));
function renderJob(job){renderCapture(job);const key=JSON.stringify(job);if(key===state.jobKey)return;state.jobKey=key;$('#cancelAnalysis').hidden=!['capturing','analyzing'].includes(job.state);const box=$('#analysisResult');box.className='empty-state';
 if(job.state==='capturing')box.textContent='正在采集 '+labels[job.kind]+' · '+job.countdown+' 秒';
 else if(job.state==='analyzing')box.textContent='采集完成，Qwen 正在分析。结果返回后会保存到本机。';
 else if(job.state==='error'){box.textContent=job.error;toast(job.error,true);}
 else if(job.state==='done'){const r=job.result;box.className='';box.innerHTML='<p class="result-summary">'+escapeHTML(r.summary)+'</p><div class="metrics"><span>模型置信度 '+Math.round(r.confidence*100)+'%</span>'+Object.entries(r.metrics||{}).map(([k,v])=>'<span>'+escapeHTML(k)+'：'+escapeHTML(typeof v==='object'?JSON.stringify(v):v)+'</span>').join('')+'</div><ul class="suggestions">'+(r.suggestions||[]).map(v=>'<li>'+escapeHTML(v)+'</li>').join('')+'</ul>';}
 else box.textContent='还没有观察结果。选择上方一项开始。';
}
async function exercise(kind){await api('exercise/start',{kind,hardware:kind!=='breath'&&!!state.status?.camera.capabilities?.gimbal&&$('#hardwareExercise').checked});render(await api('status'));}
bind('[data-exercise]',b=>exercise(b.dataset.exercise));bind('#stopExercise',()=>api('exercise/stop',{}));$('#exerciseDialog').addEventListener('cancel',e=>{e.preventDefault();api('exercise/stop',{}).catch(e=>toast(e.message,true));});
function renderExercise(ex){if(ex.active){if(!$('#exerciseDialog').open)openImmersive('exerciseDialog');$('#exerciseKind').textContent={eye:'眼部米字操',neck:'颈部十字操',breath:'一分钟呼吸'}[ex.kind]+(ex.hardware?' · 云台联动':' · 屏幕引导');$('#exerciseLabel').textContent=ex.label;$('#exerciseStep').textContent=ex.step+' / '+ex.total;$('#guideDot').style.left=(50+ex.x*34)+'%';$('#guideDot').style.top=(50-ex.y*35)+'%';$('#guideDot').style.scale=ex.kind==='breath'?(ex.label.includes('吸')?'2.4':'1'):'1';state.exerciseWasActive=true;}else if(state.exerciseWasActive){closeImmersive('exerciseDialog');state.exerciseWasActive=false;toast(ex.error|| (ex.completed?'这一轮完成了，慢慢回到工作吧':'活动已结束'),!!ex.error);}}
bind('#gameReset',async()=>{await api('game/reset',{});await refreshNow();toast('新的对战准备好了');});
bind('#saveSettings',async()=>{const consent=$('#cloudConsent').checked,auto=$('#autoEmotion').checked;if(auto&&!consent)throw new Error('自动表情观察需要先允许云端图像分析');await api('settings',{sit_minutes:Number($('#sitMinutes').value),eye_minutes:Number($('#eyeMinutes').value),focus_minutes:Number($('#focusMinutes').value),resolution:$('#resolution').value,sound:$('#sound').checked,cloud_consent:consent,auto_emotion:auto,auto_start:$('#autoStart').checked,auto_tracking:$('#autoTracking').checked,floating_window:$('#floatingWindow').checked});state.selectedMinutes=Number($('#focusMinutes').value);toast('偏好已保存');render(await api('status'));});
bind('#saveAi',async()=>{await api('ai/config',{api_key:$('#apiKey').value,base_url:$('#apiUrl').value,model:$('#apiModel').value});$('#apiKey').value='';$('#apiKey').placeholder='已保存；留空保留现有密钥';toast('连接配置已加密保存');render(await api('status'));});
bind('#testAi',async()=>{$('#aiTestStatus').textContent='正在发送文字请求测试连接…';try{const r=await api('ai/test',{});$('#aiTestStatus').textContent='连接成功 · '+r.model+'。图像能力需通过实际观察进一步验证。';toast('文字连接测试通过');}catch(e){$('#aiTestStatus').textContent=e.message;throw e;}});
bind('#clearAi',async()=>{if(await confirmAction('移除本机密钥？','将删除当前用户保存的 Qwen 密钥。需要时可以重新填写。')){await api('ai/clear',{});toast('本机密钥已移除');render(await api('status'));}});
bind('#voiceButton',async()=>{await api(state.status?.voice.active?'voice/stop':'voice/start',{});render(await api('status'));});
async function runCommand(text,fromVoice=false){toast('指令：'+text);if(!/^(小萤|小莹|inwork|音沃克)/i.test(text.trim()))throw new Error('请以“小萤”开头，例如“小萤开始专注”');if(text.includes('暂停陪伴'))await api('camera/stop',{});else if(text.includes('开始陪伴'))await api('camera/start',{});else if(text.includes('开始专注')){page('focus');await api('focus/start',{minutes:state.selectedMinutes});}else if(text.includes('结束专注'))await api('focus/stop',{});else if(text.includes('米字操'))await exercise('eye');else if(text.includes('十字操'))await exercise('neck');else if(text.includes('石头剪刀布'))page('relax');else if(/眼周|黑眼圈/.test(text))await analyze('dark_circle',fromVoice);else if(text.includes('舌苔'))await analyze('tongue',fromVoice);else if(text.includes('皮肤'))await analyze('acne',fromVoice);else if(text.includes('情绪'))await analyze('emotion',fromVoice);else throw new Error('未识别指令，请试试“小萤开始专注”');}
bind('#commandSend',async()=>{await runCommand($('#commandInput').value);$('#commandInput').value='';});$('#commandInput').addEventListener('keydown',e=>{if(e.key==='Enter')$('#commandSend').click();});
async function loadHistory(){const data=state.history=await api('history');$('#analysisHistory').innerHTML=data.recent.length?data.recent.map(r=>'<article class="history-row"><h4>'+escapeHTML(labels[r.kind]||r.kind)+'</h4><p>'+escapeHTML(r.summary)+'</p><time>'+localTime(r.created_at)+' · 模型置信度 '+Math.round(r.confidence*100)+'%</time></article>').join(''):'还没有观察记录。完成一次状态观察后，它会出现在这里。';$('#eventHistory').innerHTML=data.events.length?data.events.map(e=>'<div class="timeline-row"><span class="timeline-dot"></span><div>'+escapeHTML(e.label)+'<small>'+localTime(e.created_at)+'</small></div></div>').join(''):'你的第一段陪伴，从今天开始。';renderTrend();}
function renderTrend(){const kind=$('#trendKind').value;const rows=(state.history?.trends||[]).filter(r=>r.kind===kind&&Number.isFinite(r.score)).reverse();if(rows.length<2){$('#trendChart').innerHTML='完成至少两次同类观察后，显示模型参考分趋势。';return;}const points=rows.map((r,i)=>(45+i*710/(rows.length-1))+','+(145-r.score*1.2)).join(' ');$('#trendChart').innerHTML='<svg class="trend-svg" viewBox="0 0 800 185" role="img" aria-label="'+escapeHTML(labels[kind])+'模型参考分趋势"><path d="M45 25H755 M45 85H755 M45 145H755" stroke="#e8edde" fill="none"/><text x="9" y="29" fill="#9da78a" font-size="10">100</text><text x="16" y="89" fill="#9da78a" font-size="10">50</text><text x="21" y="149" fill="#9da78a" font-size="10">0</text><polyline points="'+points+'" fill="none" stroke="#809b69" stroke-width="2.5"/>'+rows.map((r,i)=>'<circle cx="'+(45+i*710/(rows.length-1))+'" cy="'+(145-r.score*1.2)+'" r="4" fill="#d79361"><title>'+escapeHTML(localTime(r.created_at)+' · '+r.score)+'</title></circle>').join('')+'<text x="45" y="178" font-size="10" fill="#9da78a">'+escapeHTML(localTime(rows[0].created_at))+'</text><text x="755" y="178" text-anchor="end" font-size="10" fill="#9da78a">'+escapeHTML(localTime(rows.at(-1).created_at))+'</text></svg>';}
$('#trendKind').onchange=renderTrend;bind('#refreshHistory',loadHistory);
bind('#exportButton',async()=>{if(window.pywebview?.api){const r=await window.pywebview.api.export_records();if(r.saved)toast('已导出 '+r.name);}else{const data=await api('export');const url=URL.createObjectURL(new Blob([JSON.stringify(data,null,2)],{type:'application/json'}));const a=document.createElement('a');a.href=url;a.download='萤InWork-个人记录.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),5000);}});
bind('#clearData',async()=>{if(await confirmAction('清除全部个人记录？','将删除本机保存的观察结果、专注记录和陪伴足迹。此操作无法撤销，建议先导出。')){await api('data/clear',{confirm:true});toast('个人记录已清除');if(state.history)await loadHistory();}});

async function refreshNow(){render(await api('status'));}
const faces={happy:['(✿◕‿◕)','看起来心情不错'],calm:['(｡•ᴗ•｡)','此刻看起来很平静'],tired:['(－ω－) zZ','好像有一点倦意'],low:['(っ˘ω˘ς)','给你一个小小拥抱'],unknown:['(｡･ω･｡)','小萤还在观察']};
function renderMood(s){const meta=s.emotion_status||{},r=s.emotion;let face=faces.unknown,title='小萤在这里',detail='每 10 秒观察一次可见表情';
 if(!s.camera.running){title='陪伴已暂停';detail='点击开始陪伴，小萤继续陪着你';}
 else if(!s.settings.auto_emotion){title='本地陪伴中';detail='自动表情观察已关闭';}
 else if(!s.settings.cloud_consent||!s.ai.configured){title='本地陪伴中';detail='配置并允许 Qwen 图像分析后开启表情观察';}
 else {if(r){face=faces[r.confidence>=.6?r.mood:'unknown']||faces.unknown;title=face[1];detail='表情参考 · '+Math.round(r.confidence*100)+'% 置信度'+(meta.updated_at?' · '+new Date(meta.updated_at).toLocaleTimeString('zh-CN',{hour12:false}):'');}if(meta.state==='error'){title='这次没观察成功';detail='稍后自动重试 · '+meta.error;face=faces.unknown;}else if(meta.busy)detail+=' · 正在观察…';else if(['capturing','analyzing'].includes(s.job.state)||s.exercise.active||['loading','countdown','recognizing'].includes(s.game.state))detail+=' · 互动期间暂缓';else detail+=' · '+meta.next_in+' 秒后再观察';}
 $('#moodFace').textContent=face[0];$('#moodTitle').textContent=title;$('#moodDetail').textContent=detail;
}
async function setFullscreen(value){try{if(window.pywebview?.api)await window.pywebview.api.set_fullscreen(value);}catch(e){toast('全屏切换失败，已保留窗口内投屏',true);}}
function openImmersive(id){const d=$('#'+id);if(!d.open){d.showModal();setFullscreen(true);}}
function closeImmersive(id){const d=$('#'+id);if(d.open)d.close();if(!$$('dialog.immersive[open]').length)setFullscreen(false);}
bind('#expandCamera',()=>{if(!state.status?.camera.running)throw new Error('请先开始陪伴');openImmersive('cameraDialog');});
bind('#closeCamera',()=>closeImmersive('cameraDialog'));
$('#cameraDialog').addEventListener('cancel',e=>{e.preventDefault();closeImmersive('cameraDialog');});
const poseHints={dark_circle:'面向相机，让双眼位于画面中央，保持自然光线',tongue:'靠近相机，轻轻伸舌，让舌面完整出现在画面中',acne:'面向相机，露出需要观察的皮肤，保持画面稳定',emotion:'保持自然表情，面向相机就好'};
function renderCapture(job){if(['capturing','analyzing'].includes(job.state)&&!state.captureDismissed){openImmersive('captureDialog');$('#captureTitle').textContent=labels[job.kind];$('#captureCount').textContent=job.state==='capturing'?job.countdown:'✦';$('#captureHint').textContent=job.state==='capturing'?poseHints[job.kind]:'采集完成，正在分析 · 可以返回工位等待';$('#capturePhase').textContent=job.state==='capturing'?'6 秒采集 · '+Math.min(3,Math.floor((6-job.countdown)/2))+' / 3 帧':'Qwen 正在观察，本次结果将保存在本机';$('#cancelCapture').textContent=job.state==='capturing'?'取消观察 ×':'返回工位 ↗';}else if(!['capturing','analyzing'].includes(job.state))closeImmersive('captureDialog');}
async function dismissCapture(){state.captureDismissed=true;closeImmersive('captureDialog');if(state.status?.job.state==='capturing')await api('analyze/cancel',{});}
bind('#cancelCapture',dismissCapture);$('#captureDialog').addEventListener('cancel',e=>{e.preventDefault();dismissCapture().catch(e=>toast(e.message,true));});
bind('#hardwareExercise',()=>api('settings',{hardware_exercise:$('#hardwareExercise').checked}));
bind('#floatButton',async()=>{await api('settings',{floating_window:true});$('#floatingWindow').checked=true;if(window.pywebview?.api)await window.pywebview.api.show_float();else toast('桌面悬浮小萤将在 EXE 中显示');});
async function startGesture(){if(!state.status?.camera.running)throw new Error('请先开始陪伴，连接摄像头');await api('game/start',{});state.battleOpen=true;openImmersive('gameDialog');await refreshNow();}
bind('#gestureStart',startGesture);
bind('#nextRound',async()=>{if(state.status?.game.finished)await api('game/reset',{});await startGesture();});
async function closeGame(){state.battleOpen=false;closeImmersive('gameDialog');await api('game/stop',{});}
bind('#closeGame',closeGame);$('#gameDialog').addEventListener('cancel',e=>{e.preventDefault();closeGame().catch(e=>toast(e.message,true));});
const handIcons={rock:'✊',paper:'✋',scissors:'✌️'},handNames={rock:'石头',paper:'布',scissors:'剪刀'};
function renderGame(g){if(!g)return;$('#userScore').textContent=g.userWins;$('#cpuScore').textContent=g.cpuWins;$('#battleScore').textContent=g.userWins+' : '+g.cpuWins;
 const busy=['loading','countdown','recognizing'].includes(g.state);$('#gestureStart').disabled=busy||g.finished;$('#gameReset').disabled=busy;$('#nextRound').hidden=busy;$('#nextRound').textContent=g.finished?'再来一场 ↗':g.state==='result'?'下一回合 ↗':'重新出拳 ↗';
 let text='掌心朝向相机，握拳 / V 手势 / 张开手掌';$('#gameCount').textContent=g.state==='countdown'?g.countdown:g.state==='loading'?'…':'';$('#cpuHand').textContent=g.state==='result'?handIcons[g.cpu]:'✦';$('#cpuHint').textContent=g.state==='result'?'小萤出了'+handNames[g.cpu]:'小萤已选好，揭晓前保密';$('#detectedHand').textContent=g.detected?'看到了'+handNames[g.detected]+' · 再保持一下':g.state==='recognizing'?'请保持一个手势 · 还有 '+g.countdown+' 秒':text;
 const title={idle:'准备好，举起一只手',loading:'正在唤醒手势识别',countdown:'石头、剪刀、布！',recognizing:'请保持手势约半秒',result:g.finished?'本场对战结束':'本回合揭晓',retry:'再试一次',error:'手势识别遇到问题',cancelled:'对战已暂停'};$('#battleTitle').textContent=title[g.state]||'准备出拳';
 if(g.state==='result'){text='你出'+handNames[g.user]+'，小萤出'+handNames[g.cpu]+'。'+({win:'你赢了！',lose:'小萤赢了！',draw:'平局，再来！'}[g.outcome]);if(g.finished)text+=' '+(g.userWins>=2?'你赢下了这一场 🎉':'小萤赢下了这一场 🌟');$('#detectedHand').textContent='你的出拳：'+handIcons[g.user]+' '+handNames[g.user];}else if(g.error)text=g.error;
 $('#battleResult').textContent=text;$('#gameResult').textContent=g.state==='idle'?'本地识别真实手势，先赢两回合获胜。':text;
}
window.addEventListener('ying-command',e=>{const cmd=e.detail;closeImmersive('cameraDialog');if(titles[cmd])page(cmd);else if(cmd==='eye'||cmd==='neck')exercise(cmd).catch(e=>toast(e.message,true));else if(cmd==='game'){page('relax');startGesture().catch(e=>toast(e.message,true));}else if(labels[cmd])analyze(cmd).catch(e=>toast(e.message,true));});
$('#todayDate').textContent=new Date().toLocaleDateString('zh-CN',{month:'long',day:'numeric',weekday:'long'})+' · TODAY WITH YING';
api('devices').then(d=>{const found=d.devices.some(c=>c.supported);$('#deviceCaption').dataset.detected=found?'设备已连接':'未发现摄像头';$('#deviceCaption').textContent=$('#deviceCaption').dataset.detected;$('#deviceDot').classList.toggle('online',found);}).catch(()=>{$('#deviceCaption').dataset.detected='请检查设备连接';});
refresh();preview();
