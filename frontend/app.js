/* ============ NAV ============ */
const crumbCat={dashboard:'Data',outliers:'Data',database:'Data',duplicates:'Features',correlation:'Features',selection:'Features',importance:'Features',missing:'Features',clustering:'Unsupervised',single:'Regression',compare:'Regression',ddpg:'Regression',active:'Active',codeopt:'System'};
const pageNames={dashboard:'数据可视化',outliers:'异常值检测',database:'数据库管理',duplicates:'重复值处理',correlation:'特征相关性',selection:'特征筛选与降维',importance:'特征重要性排序',missing:'缺失值处理',clustering:'聚类与降维',single:'单一模型',compare:'模型比较',ddpg:'深度强化学习',active:'单目标优化',codeopt:'代码优化'};
/* 分类标题点击折叠 */
document.querySelectorAll('.nav-cat').forEach(cat=>{
  cat.addEventListener('click',()=>{
    cat.parentElement.classList.toggle('collapsed');
  });
});

const navItems=document.querySelectorAll('.nav-item');
/* 路由跳转 —— 统一入口，同步 location.hash */
function navigate(p){
  const target=[...navItems].find(n=>n.dataset.page===p);
  if(!target)return;
  navItems.forEach(n=>n.classList.remove('active'));
  target.classList.add('active');
  document.querySelectorAll('.page').forEach(pg=>pg.classList.remove('active'));
  const pageEl=document.getElementById('page-'+p);
  if(pageEl)pageEl.classList.add('active');
  document.getElementById('crumb-cat').textContent=crumbCat[p]||'';
  document.getElementById('crumb-page').textContent=pageNames[p]||target.textContent.trim();
  document.getElementById('content').scrollTop=0;
  if(p==='dashboard')initDashboard();
  if(p==='outliers')initOutliers();
  if(p==='database')initDatabase();
  if(p==='duplicates')initDuplicates();
  if(p==='correlation')initCorrelation();
  if(p==='selection')initSelection();
  if(p==='importance')initImportance();
  if(p==='missing')initMissing();
  if(p==='clustering')initClustering();
  if(p==='single')initSingle();
  if(p==='compare')initCompare();
  if(p==='ddpg')initDDPG();
  if(p==='active')initActive();
  if(p==='codeopt')initCodeOpt();
  if(location.hash!=='#'+p)location.hash=p;
}
navItems.forEach(it=>{
  it.addEventListener('click',()=>navigate(it.dataset.page));
});
/* hash 变化时自动跳转 —— 支持浏览器前进/后退/刷新保留当前页 */
window.addEventListener('hashchange',()=>{
  const p=(location.hash||'').replace('#','');
  if(p && document.getElementById('page-'+p))navigate(p);
});

/* ============ TOAST ============ */
function toast(msg,type){
  const t=document.createElement('div');t.className='toast';
  t.innerHTML=msg+'<div class="toast-progress"></div>';
  /* 根据 type 设置左边框颜色：warn=橙 error=红 ok=绿 默认=当前青色 */
  if(type==='warn')t.style.borderLeftColor='var(--amber)';
  else if(type==='error')t.style.borderLeftColor='var(--danger)';
  else if(type==='ok')t.style.borderLeftColor='var(--success)';
  document.getElementById('toasts').appendChild(t);
  setTimeout(()=>{t.style.opacity='0';t.style.transform='translateX(20px)';t.style.transition='.3s ease';setTimeout(()=>t.remove(),300)},2600);
}

/* ============ DATA ============ */
const ELEMENTS=['Al','W','Ta','Ti','Cr','Ni','Mo','Hf','C','Co','B','V','Si','Fe','Nb','Zr','Re','Cb','Ce','Mn','S','P'];
const ELEMENT_STATS={
  Al:{med:6.0,q1:5.2,q3:6.8,min:3.5,max:8.2},
  W:{med:5.5,q1:4.0,q3:7.0,min:0,max:12},
  Ta:{med:1.5,q1:0.5,q3:3.0,min:0,max:6},
  Ti:{med:1.0,q1:0.5,q3:2.0,min:0,max:4.5},
  Cr:{med:9.0,q1:8.0,q3:10.0,min:5,max:15},
  Ni:{med:55,q1:50,q3:60,min:40,max:70},
  Mo:{med:1.5,q1:0.5,q3:2.5,min:0,max:5},
  Co:{med:8.0,q1:5.0,q3:12.0,min:0,max:20},
  Hf:{med:0.1,q1:0,q3:0.3,min:0,max:0.8},
  C:{med:0.07,q1:0.05,q3:0.1,min:0.01,max:0.2},
};
['B','V','Si','Fe','Nb','Zr','Re','Cb','Ce','Mn','S','P'].forEach(e=>ELEMENT_STATS[e]={med:0.1,q1:0,q3:0.3,min:0,max:1.5});

Chart.defaults.color='#94a3b8';
Chart.defaults.borderColor='rgba(31, 41, 55, 0.6)';
Chart.defaults.font.family='IBM Plex Mono';
Chart.defaults.font.size=10;

/* ============ iOS ANIMATION ENGINE ============ */
const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

/* ── CountUp Animation ── */
function countUp(el, target, opts = {}) {
  if (prefersReducedMotion || !el) { if(el) el.textContent = target; return; }
  const { duration = 800, prefix = '', suffix = '', decimals = 0 } = opts;
  const start = 0;
  const range = target - start;
  if (range === 0) return;
  const startTime = performance.now();
  function step(now) {
    const elapsed = Math.min((now - startTime) / duration, 1);
    const eased = 1 - Math.pow(1 - elapsed, 3); // ease-out cubic
    const current = start + range * eased;
    el.textContent = prefix + current.toFixed(decimals) + suffix;
    if (elapsed < 1) requestAnimationFrame(step);
  }
  requestAnimationFrame(step);
}

/* ── Ripple Effect for buttons ── */
document.addEventListener('pointerdown', (e) => {
  if (prefersReducedMotion) return;
  const btn = e.target.closest('.btn');
  if (!btn) return;
  const rect = btn.getBoundingClientRect();
  const x = ((e.clientX - rect.left) / rect.width * 100).toFixed(1);
  const y = ((e.clientY - rect.top) / rect.height * 100).toFixed(1);
  btn.style.setProperty('--ripple-x', x + '%');
  btn.style.setProperty('--ripple-y', y + '%');
}, { passive: true });

/* ── Passive scroll listeners for performance ── */
window.addEventListener('load', () => {
  document.querySelector('.content')?.addEventListener('scroll', () => {}, { passive: true });
  document.querySelector('.nav')?.addEventListener('scroll', () => {}, { passive: true });
});

/* ============ API 配置 ============ */
const API_BASE='http://127.0.0.1:5000';
let API_ONLINE=false;
const API_TIMEOUT=15000; // 15s 超时
async function api(path,opts={}){
  try{
    const ctrl=new AbortController();
    const timer=setTimeout(()=>ctrl.abort(),API_TIMEOUT);
    const r=await fetch(API_BASE+path,{...opts,signal:ctrl.signal});
    clearTimeout(timer);
    API_ONLINE=true;
    return await r.json();
  }catch(e){
    API_ONLINE=false;
    return {error: e.name==='AbortError'?'请求超时 (>15s)':'后端未启动'};
  }
}
function showOfflineHint(){
  if(!API_ONLINE){
    toast('⚠ 提示：后端未连接 · 显示模拟数据');
    /* 离线时短暂禁用所有按钮，防止用户反复点击 */
    const btns=document.querySelectorAll('button');
    btns.forEach(b=>{if(!b.disabled){b.dataset.offlineLock='1';b.disabled=true}});
    setTimeout(()=>{
      btns.forEach(b=>{if(b.dataset.offlineLock){b.dataset.offlineLock='';b.disabled=false}})
    },1500);
  }
}
/* 骨架屏 —— 在容器内显示 shimmer 动画 */
function showSkeleton(selector,text){
  const el=document.querySelector(selector);
  if(!el)return;
  el.innerHTML='<div class="skeleton-box"><div class="skeleton" style="height:14px;width:'+(60+Math.random()*30)+'%;margin-bottom:10px"></div><div class="skeleton" style="height:14px;width:'+(50+Math.random()*30)+'%;margin-bottom:10px"></div><div class="skeleton" style="height:14px;width:'+(70+Math.random()*20)+'%"></div><div style="text-align:center;color:var(--text-faint);font-size:11px;margin-top:14px;font-family:var(--mono)">'+(text||'加载中...')+'</div></div>';
}
function hideSkeleton(selector){
  const el=document.querySelector(selector);
  if(el){
    const sk=el.querySelector('.skeleton-box');
    if(sk)sk.remove();
  }
}

/* ============ DASHBOARD ============ */
let dashInit=false;
let distChart=null,corrChart=null,histChart=null;
/* 全局图表实例注册表 —— 统一销毁管理，防止内存泄漏 */
const CHARTS={}; // {id: chartInstance}
function makeChart(canvasId,config){
  if(CHARTS[canvasId]){try{CHARTS[canvasId].destroy()}catch(e){}}
  const el=document.getElementById(canvasId);
  if(!el)return null;
  CHARTS[canvasId]=new Chart(el,config);
  return CHARTS[canvasId];
}

function renderDistChart(type){
  const titles={boxplot:'元素含量四分位分布 (wt %)',violin:'元素含量小提琴分布 (wt %)',histogram:'元素含量中位数对比 (wt %)'};

  if(type==='boxplot'){
    distChart=makeChart('ch-dist',{
      type:'bar',
      data:{labels:ELEMENTS,datasets:[{
        label:'Q1–Q3',
        data:ELEMENTS.map(e=>[ELEMENT_STATS[e].q1,ELEMENT_STATS[e].q3]),
        backgroundColor:'rgba(10, 132, 255, .35)',borderColor:'#0A84FF',borderWidth:1,barPercentage:.7
      }]},
      options:{indexAxis:'y',maintainAspectRatio:false,
        plugins:{legend:{display:false},
          title:{display:true,text:titles[type],color:'#f8fafc',font:{family:'Inter',size:13,weight:'500'},align:'start',padding:{bottom:14}}},
        scales:{
          x:{grid:{color:'rgba(255,255,255,.02)'},ticks:{color:'#475569'}},
          y:{grid:{display:false},ticks:{color:'#94a3b8',font:{size:10}}}
        }
      }
    });
  }else if(type==='violin'){
    const scatterData=[];
    ELEMENTS.forEach((e,idx)=>{
      const s=ELEMENT_STATS[e];
      for(let k=0;k<12;k++){
        const v=s.med+(Math.random()-.5)*(s.q3-s.q1)*1.8;
        scatterData.push({x:Math.max(0,v),y:idx});
      }
    });
    const medians=ELEMENTS.map(e=>ELEMENT_STATS[e].med);
    distChart=makeChart('ch-dist',{
      data:{
        labels:ELEMENTS,
        datasets:[
          {type:'bar',label:'Q1–Q3',data:ELEMENTS.map(e=>[ELEMENT_STATS[e].q1,ELEMENT_STATS[e].q3]),
            backgroundColor:'rgba(10, 132, 255, .15)',borderColor:'rgba(10, 132, 255, .4)',borderWidth:1,barPercentage:.5},
          {type:'scatter',label:'样本点',data:scatterData,
            backgroundColor:'rgba(64, 156, 255, .7)',borderColor:'#409CFF',pointRadius:2.5},
          {type:'line',label:'中位数',data:medians.map((m,i)=>({x:m,y:i})),
            borderColor:'#0A84FF',borderWidth:2,pointRadius:4,pointBackgroundColor:'#0A84FF',showLine:false}
        ]
      },
      options:{indexAxis:'y',maintainAspectRatio:false,
        plugins:{legend:{display:false},
          title:{display:true,text:titles[type],color:'#f8fafc',font:{family:'Inter',size:13,weight:'500'},align:'start',padding:{bottom:14}}},
        scales:{
          x:{grid:{color:'rgba(255,255,255,.02)'},ticks:{color:'#475569'}},
          y:{grid:{display:false},ticks:{color:'#94a3b8',font:{size:10}}}
        }
      }
    });
  }else if(type==='histogram'){
    distChart=makeChart('ch-dist',{
      type:'bar',
      data:{labels:ELEMENTS,datasets:[{
        label:'中位数',
        data:ELEMENTS.map(e=>ELEMENT_STATS[e].med),
        backgroundColor:'rgba(10, 132, 255, .5)',borderColor:'#0A84FF',borderWidth:1,barPercentage:.6
      }]},
      options:{indexAxis:'y',maintainAspectRatio:false,
        plugins:{legend:{display:false},
          title:{display:true,text:titles[type],color:'#f8fafc',font:{family:'Inter',size:13,weight:'500'},align:'start',padding:{bottom:14}},
          tooltip:{callbacks:{label:c=>'中位数: '+c.raw.y.toFixed(3)+' wt %'}}},
        scales:{
          x:{grid:{color:'rgba(255,255,255,.02)'},ticks:{color:'#475569'}},
          y:{grid:{display:false},ticks:{color:'#94a3b8',font:{size:10}}}
        }
      }
    });
  }
}

function genCorrMatrix(seed){
  let s=seed;
  const rand=()=>{s=(s*9301+49297)%233280;return s/233280};
  const N=ELEMENTS.length;
  const corr=[];
  for(let i=0;i<N;i++){
    corr.push([]);
    for(let j=0;j<N;j++){
      if(i===j)corr[i].push(1);
      else if(j<i)corr[i].push(corr[j][i]);
      else corr[i].push(parseFloat((rand()*1.6-.8).toFixed(2)));
    }
  }
  return corr;
}

function renderCorrChart(method){
  const N=ELEMENTS.length;
  const seedMap={pearson:42,spearman:137,kendall:871};
  const corr=genCorrMatrix(seedMap[method]||42);
  const dataset=[];
  for(let i=0;i<N;i++)for(let j=0;j<N;j++){
    dataset.push({x:j,y:N-1-i,r:Math.abs(corr[i][j])*9,v:corr[i][j]});
  }
  corrChart=makeChart('ch-corr',{
    type:'bubble',
    data:{datasets:[{data:dataset,
      backgroundColor:dataset.map(d=>d.v>0?'rgba(10, 132, 255,'+(Math.abs(d.v)*.8)+')':'rgba(94, 92, 230,'+(Math.abs(d.v)*.8)+')'),
      borderColor:dataset.map(d=>d.v>0?'#0A84FF':'#5E5CE6')}]},
    options:{maintainAspectRatio:false,
      plugins:{legend:{display:false},
        title:{display:true,text:'元素相关性矩阵（青=正相关 · 紫=负相关 · 气泡大小=|r|）',color:'#f8fafc',font:{family:'Inter',size:13,weight:'500'},align:'start',padding:{bottom:14}},
        tooltip:{callbacks:{label:c=>ELEMENTS[c.raw.x]+' ↔ '+ELEMENTS[N-1-c.raw.y]+' : '+c.raw.v}}},
      scales:{
        x:{ticks:{color:'#94a3b8',stepSize:1,callback:v=>ELEMENTS[v]||''},grid:{color:'rgba(255,255,255,.02)'}},
        y:{ticks:{color:'#94a3b8',stepSize:1,callback:v=>ELEMENTS[N-1-v]||''},grid:{color:'rgba(255,255,255,.02)'}}
      }
    }
  });
}

function initDashboard(){
  if(dashInit)return;dashInit=true;
  renderDistChart('boxplot');

  document.querySelectorAll('#dist-chips .chip').forEach(c=>{
    c.addEventListener('click',()=>{
      document.querySelectorAll('#dist-chips .chip').forEach(x=>x.classList.remove('on'));
      c.classList.add('on');
      renderDistChart(c.dataset.type);
    });
  });

  const hvBins=[];const hvCounts=[];
  for(let i=160;i<=500;i+=20){hvBins.push(i+'–'+(i+20));hvCounts.push(Math.round(8+12*Math.exp(-Math.pow((i-330)/70,2))+Math.random()*4))}
  histChart=makeChart('ch-hist',{
    type:'bar',
    data:{labels:hvBins,datasets:[{
      data:hvCounts,
      backgroundColor:hvCounts.map((_,i)=>i>7&&i<13?'#0A84FF':'rgba(10, 132, 255,.3)'),
      borderColor:'#0A84FF',borderWidth:1
    }]},
    options:{maintainAspectRatio:false,
      plugins:{legend:{display:false},
        title:{display:true,text:'维氏硬度 HV 分布',color:'#f8fafc',font:{family:'Inter',size:13,weight:'500'},align:'start',padding:{bottom:14}}},
      scales:{
        x:{grid:{display:false},ticks:{color:'#475569',maxRotation:60}},
        y:{grid:{color:'rgba(255,255,255,.02)'},ticks:{color:'#475569'}}
      }
    }
  });

  renderCorrChart('pearson');
  document.querySelectorAll('#corr-chips .chip').forEach(c=>{
    c.addEventListener('click',()=>{
      document.querySelectorAll('#corr-chips .chip').forEach(x=>x.classList.remove('on'));
      c.classList.add('on');
      const m=c.dataset.method;
      document.getElementById('corr-method-label').textContent=m;
      renderCorrChart(m);
    });
  });
}

/* ============ SINGLE MODEL ============ */
let singleInit=false,scatterChart=null;
function initSingle(){
  if(singleInit){renderPreview();return}singleInit=true;

  const fc=document.getElementById('feat-chips');
  ELEMENTS.forEach((e)=>{
    const c=document.createElement('span');c.className='chip on';c.textContent=e;
    c.addEventListener('click',()=>c.classList.toggle('on'));
    fc.appendChild(c);
  });

  // 拉取实际数据统计，更新数据集信息卡
  api('/api/data/stats').then(res=>{
    if(res.error){showOfflineHint();return}
    const n=res.n_samples??'--';
    const ne=res.n_elements??22;
    document.getElementById('di-meta').textContent=`${n} 样本 · ${ne} 元素特征 · 目标 HV · 范围 ${Math.round(res.hv_min??0)}~${Math.round(res.hv_max??0)}`;
  });

  // 拉取 GAN 清洗统计
  api('/api/data/source_stats').then(res=>{
    if(res.error)return;
    document.getElementById('gan-clean-stats').innerHTML=
      `原始 <b style="color:var(--text)">${res.gan_total}</b> 条 → `+
      `清洗后 <b style="color:var(--ember-hot)">${res.gan_cleaned}</b> 条 `+
      `（删 ${res.gan_removed} 条）· 实测有效 ${res.real_valid} 条 · 混合总计 ${res.mix_default} 条`;
  });

  // 数据源切换：显示/隐藏 GAN 权重滑块和清洗信息
  function updateDataSourceUI(){
    const src=document.getElementById('data-source-sel').value;
    const isGAN=(src!=='real');
    const isMix=(src==='mix');
    // GAN 权重滑块：仅 mix 模式显示
    document.getElementById('gan-weight-field').style.display=isMix?'block':'none';
    // GAN 清洗信息：除 real 外都显示
    document.getElementById('gan-clean-info').style.display=isGAN?'block':'none';
    // 警告
    const warn=document.getElementById('ds-warning');
    const warnText=document.getElementById('ds-warning-text');
    if(src==='gan'){
      warn.style.display='block';
      warnText.textContent='⚠ GAN 数据的 HV 是模型生成值，非实测。R² 会虚高（0.99+），不反映真实预测能力。';
    }else if(src==='mix'){
      warn.style.display='block';
      warnText.textContent='⚠ 混合测试集 R² 会虚高，因为 GAN 样本易预测。建议用「GAN 训练 → 实测测试」看真实效果。';
    }else if(src==='gan_train_real_test'){
      warn.style.display='block';
      warnText.textContent='ℹ GAN 学偏了（Co 全 0、Ni 范围窄），此模式 R² 可能很低甚至为负，说明 GAN 数据对实测预测无效。';
    }else{
      warn.style.display='none';
    }
  }
  document.getElementById('data-source-sel').addEventListener('change',updateDataSourceUI);
  updateDataSourceUI();

  // GAN 权重滑块
  document.getElementById('gan-weight-slider').addEventListener('input',e=>{
    document.getElementById('gan-weight-val').textContent=(e.target.value/100).toFixed(2);
  });

  renderPreview();
  document.getElementById('row-slider').addEventListener('input',e=>{
    document.getElementById('row-val').textContent=e.target.value+' rows';
    renderPreview();
  });

  scatterChart=makeChart('ch-scatter',{
    type:'scatter',
    data:{datasets:[
      {label:'测试集',data:[],backgroundColor:'rgba(94, 92, 230,.7)',borderColor:'#5E5CE6',pointRadius:4}
    ]},
    options:{maintainAspectRatio:false,
      plugins:{legend:{position:'bottom',labels:{color:'#94a3b8'}}},
      scales:{
        x:{title:{display:true,text:'Actual HV',color:'#94a3b8'},grid:{color:'rgba(255,255,255,.02)'},ticks:{color:'#475569'}},
        y:{title:{display:true,text:'Predicted HV',color:'#94a3b8'},grid:{color:'rgba(255,255,255,.02)'},ticks:{color:'#475569'}}
      }
    }
  });

  // 算法下拉切换 → 重新渲染超参数表单
  document.getElementById('algo-sel').addEventListener('change',renderHyperFields);
  renderHyperFields();

  // 测试集比例滑块
  document.getElementById('ts-slider-single').addEventListener('input',e=>{
    document.getElementById('ts-val-single').textContent='0.'+e.target.value;
  });
  // CV 折数滑块
  document.getElementById('cv-folds-slider').addEventListener('input',e=>{
    document.getElementById('cv-val-display').textContent=e.target.value;
  });

  document.getElementById('train-btn').addEventListener('click',async()=>{
    const algo=document.getElementById('algo-sel').value;
    const btn=document.getElementById('train-btn');
    const autoOn=document.getElementById('auto-search-sw').classList.contains('on');
    const testSize=+document.getElementById('ts-val-single').textContent;
    const dataSource=document.getElementById('data-source-sel').value;
    const ganWeight=+document.getElementById('gan-weight-val').textContent;

    btn.disabled=true;
    btn.textContent=autoOn?'⏳ 网格搜索中...':'⏳ 训练中...';
    toast(autoOn?('▶ 正在网格搜索 '+algo+' ...'):('▶ 正在训练 '+algo+' ...'));

    let endpoint='/api/train/traditional', body={model:algo,test_size:testSize,data_source:dataSource,gan_weight:ganWeight};
    // 增强选项
    const ffEl=document.getElementById('single-feature-filter');
    const ttEl=document.getElementById('single-target-transform');
    if(ffEl) body.feature_filter=ffEl.value;
    if(ttEl) body.target_transform=ttEl.classList.contains('on')?'log':'off';
    if(autoOn){
      endpoint='/api/train/grid_search';
      body.cv_folds=+document.getElementById('cv-folds-slider').value;
    }else{
      body.params=collectHyperParams();
    }

    const res=await api(endpoint,{
      method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify(body)
    });
    btn.disabled=false;btn.textContent='▶ Train Model';
    if(res.error){
      showOfflineHint();
      toast('⚠ '+res.error);
      return;
    }
    const m=res.test_metrics||{};
    document.getElementById('m-r2').textContent=(m['R2_value']??0).toFixed(3);
    document.getElementById('m-rmse').textContent=(m['RMSE_value']??0).toFixed(1);
    document.getElementById('m-mae').textContent=(m['MAE_value']??0).toFixed(1);
    scatterChart.data.datasets[0].data=res.scatter||[];
    scatterChart.update();

    if(autoOn && res.best_params){
      const bp=Object.entries(res.best_params).map(([k,v])=>k+'='+v).join(', ');
      toast('✓ 搜索完成 · 最优 '+bp+' · 测试 R²='+(m['R2_value']??0).toFixed(3));
    }else{
      toast('✓ 训练完成 · R²='+(m['R2_value']??0).toFixed(3));
    }

    // 训练成功后，启用下载按钮
    document.getElementById('btn-download-model').disabled=false;
    document.getElementById('btn-download-csv').disabled=false;
    // 缓存最新散点数据，供交互式图表使用
    window._lastScatterData=res.scatter||[];
    if(window._chartType==='interactive'){renderInteractiveScatter();}
  });

  // 初始禁用下载按钮（必须先训练）
  document.getElementById('btn-download-model').disabled=true;
  document.getElementById('btn-download-csv').disabled=true;
}

/* ============ 单一模型 · 下载 CSV ============ */
async function downloadCSV(){
  const btn=document.getElementById('btn-download-csv');
  if(btn.disabled){toast('⚠ 请先训练一次模型');return;}
  btn.disabled=true;btn.textContent='⏳ 下载中...';
  try{
    const res=await fetch(API_BASE+'/api/train/export_csv');
    if(!res.ok){
      const err=await res.json().catch(()=>({error:'下载失败 (HTTP '+res.status+')'}));
      throw new Error(err.error||'下载失败');
    }
    const blob=await res.blob();
    const url=URL.createObjectURL(blob);
    const a=document.createElement('a');
    a.href=url;
    const cd=res.headers.get('Content-Disposition')||'';
    const fn=cd.match(/filename="?([^"]+)"?/);
    a.download=fn?fn[1]:'predictions.csv';
    document.body.appendChild(a);a.click();a.remove();
    URL.revokeObjectURL(url);
    toast('✓ 预测 CSV 已下载');
  }catch(e){
    toast('⚠ '+e.message);
    showOfflineHint();
  }
  btn.disabled=false;btn.textContent='↓ 下载预测 CSV';
}

/* ============ 单一模型 · 下载模型 pkl ============ */
async function downloadModel(){
  const btn=document.getElementById('btn-download-model');
  if(btn.disabled){toast('⚠ 请先训练一次模型');return;}
  btn.disabled=true;btn.textContent='⏳ 下载中...';
  try{
    const res=await fetch(API_BASE+'/api/train/export_model');
    if(!res.ok){
      const err=await res.json().catch(()=>({error:'下载失败 (HTTP '+res.status+')'}));
      throw new Error(err.error||'下载失败');
    }
    const blob=await res.blob();
    const url=URL.createObjectURL(blob);
    const a=document.createElement('a');
    a.href=url;
    const cd=res.headers.get('Content-Disposition')||'';
    const fn=cd.match(/filename="?([^"]+)"?/);
    a.download=fn?fn[1]:'model.pkl';
    document.body.appendChild(a);a.click();a.remove();
    URL.revokeObjectURL(url);
    toast('✓ 模型 pkl 已下载');
  }catch(e){
    toast('⚠ '+e.message);
    showOfflineHint();
  }
  btn.disabled=false;btn.textContent='↓ 下载模型';
}

/* ============ 单一模型 · 图表类型切换 ============ */
window._chartType='trad';  // 'trad' 或 'interactive'
function switchChartType(type){
  window._chartType=type;
  const trad=document.getElementById('chip-chart-trad');
  const inter=document.getElementById('chip-chart-interactive');
  const canvas=document.getElementById('ch-scatter');
  const interDiv=document.getElementById('scatter-interactive');
  if(type==='trad'){
    trad.classList.add('on');inter.classList.remove('on');
    canvas.style.display='block';interDiv.style.display='none';
  }else{
    trad.classList.remove('on');inter.classList.add('on');
    canvas.style.display='none';interDiv.style.display='block';
    renderInteractiveScatter();
  }
}

/* ============ 单一模型 · 交互式散点图（ECharts，支持缩放/平移/框选/悬停） ============ */
let _echartsScatter=null;  // ECharts 实例缓存
function renderInteractiveScatter(){
  const data=window._lastScatterData||[];
  const container=document.getElementById('scatter-interactive');
  if(!container)return;
  if(data.length===0){
    if(_echartsScatter){_echartsScatter.clear();_echartsScatter=null;}
    container.innerHTML='<div style="display:flex;align-items:center;justify-content:center;height:100%;color:#475569">请先训练模型</div>';
    return;
  }

  // 初始化或复用 ECharts 实例
  if(_echartsScatter){_echartsScatter.dispose();}
  _echartsScatter=echarts.init(container,null,{renderer:'canvas'});

  // 计算 x/y 范围（包含对角线）
  const xs=data.map(d=>d.x),ys=data.map(d=>d.y);
  const lo=Math.min(...xs,...ys),hi=Math.max(...xs,...ys);
  const pad=(hi-lo)*0.05;

  // 按误差分组染色
  const range=hi-lo||1;
  const good=[],mid=[],bad=[];
  data.forEach((d,i)=>{
    const err=Math.abs(d.x-d.y)/range;
    const item={value:[d.x,d.y],idx:i+1,err:(d.y-d.x)};
    if(err<0.05)good.push(item);
    else if(err<0.15)mid.push(item);
    else bad.push(item);
  });

  const option={
    backgroundColor:'transparent',
    grid:{left:60,right:30,top:30,bottom:70},
    tooltip:{
      trigger:'item',
      backgroundColor:'rgba(44,44,46,.92)',
      borderColor:'#409CFF',
      borderWidth:1,
      textStyle:{color:'#F5F5F7',fontSize:12},
      formatter:p=>{
        const d=p.data;
        return `<div style="font-family:monospace">
          <div style="color:#409CFF;font-weight:600;margin-bottom:4px">样本 #${d.idx}</div>
          <div>实际 HV: <b style="color:#FFFFFF">${d.value[0].toFixed(1)}</b></div>
          <div>预测 HV: <b style="color:#FFFFFF">${d.value[1].toFixed(1)}</b></div>
          <div>误差: <b style="color:${d.err>=0?'#FFD60A':'#FF453A'}">${d.err>=0?'+':''}${d.err.toFixed(1)}</b></div>
        </div>`;
      }
    },
    legend:{
      data:['误差<5%','5~15%','>15%'],
      top:4,
      textStyle:{color:'#94a3b8',fontSize:11},
      itemWidth:10,itemHeight:10
    },
    xAxis:{
      type:'value',
      name:'Actual HV',
      nameLocation:'middle',
      nameGap:30,
      nameTextStyle:{color:'#94a3b8',fontSize:11},
      min:lo-pad,max:hi+pad,
      axisLine:{lineStyle:{color:'#48484A'}},
      axisLabel:{color:'#475569',fontFamily:'monospace'},
      splitLine:{lineStyle:{color:'rgba(255,255,255,.03)'}}
    },
    yAxis:{
      type:'value',
      name:'Predicted HV',
      nameLocation:'middle',
      nameGap:40,
      nameTextStyle:{color:'#94a3b8',fontSize:11},
      min:lo-pad,max:hi+pad,
      axisLine:{lineStyle:{color:'#48484A'}},
      axisLabel:{color:'#475569',fontFamily:'monospace'},
      splitLine:{lineStyle:{color:'rgba(255,255,255,.03)'}}
    },
    dataZoom:[
      {type:'inside',xAxisIndex:0,filterMode:'none'},  // 滚轮缩放 X
      {type:'inside',yAxisIndex:0,filterMode:'none'},  // 滚轮缩放 Y
      {type:'slider',xAxisIndex:0,bottom:8,height:18,  // 底部滑块缩放
        borderColor:'#48484A',backgroundColor:'rgba(15,23,42,.5)',
        fillerColor:'rgba(64,156,255,.15)',handleStyle:{color:'#409CFF'},
        textStyle:{color:'#8E8E93',fontSize:10}}
    ],
    brush:{
      toolbox:['rect','polygon','clear'],
      throttleType:'debounce',
      throttleDelay:300,
      brushStyle:{borderColor:'#409CFF',backgroundColor:'rgba(64,156,255,.15)',borderWidth:1}
    },
    toolbox:{
      right:10,top:4,
      feature:{
        dataZoom:{yAxisIndex:'all',title:{zoom:'框选放大',back:'还原'}},
        restore:{title:'复位'},
        saveAsImage:{title:'保存 PNG',name:'scatter_plot',pixelRatio:2}
      },
      iconStyle:{borderColor:'#8E8E93'},
      emphasis:{iconStyle:{borderColor:'#409CFF'}}
    },
    series:[
      // 理想预测对角线
      {
        name:'理想预测线',type:'line',silent:true,
        data:[[lo,lo],[hi,hi]],
        lineStyle:{color:'#475569',type:'dashed',width:1.5},
        symbol:'none',z:1
      },
      {
        name:'误差<5%',type:'scatter',
        data:good,
        symbolSize:9,
        itemStyle:{color:'#409CFF',opacity:0.8,borderColor:'rgba(0,0,0,.3)',borderWidth:0.5},
        emphasis:{itemStyle:{borderColor:'#fff',borderWidth:2,symbolSize:12}},
        z:3
      },
      {
        name:'5~15%',type:'scatter',
        data:mid,
        symbolSize:9,
        itemStyle:{color:'#FFD60A',opacity:0.8,borderColor:'rgba(0,0,0,.3)',borderWidth:0.5},
        emphasis:{itemStyle:{borderColor:'#fff',borderWidth:2,symbolSize:12}},
        z:3
      },
      {
        name:'>15%',type:'scatter',
        data:bad,
        symbolSize:9,
        itemStyle:{color:'#FF453A',opacity:0.8,borderColor:'rgba(0,0,0,.3)',borderWidth:0.5},
        emphasis:{itemStyle:{borderColor:'#fff',borderWidth:2,symbolSize:12}},
        z:3
      }
    ]
  };

  _echartsScatter.setOption(option);

  // 响应窗口大小变化
  if(!window._echartsResizeBound){
    window.addEventListener('resize',()=>{
      if(_echartsScatter){_echartsScatter.resize();}
    });
    window._echartsResizeBound=true;
  }
}

/* ============ 单一模型 · 超参数表单 ============ */
// 每个算法的可调超参数定义
const HYPER_SCHEMA={
  ExtraTreesRegressor:[
    {key:'n_estimators',label:'树数 (n_estimators)',type:'number',default:200,min:10,max:1000,step:10,hint:'越多越稳但越慢'},
    {key:'max_depth',label:'最大深度 (max_depth)',type:'number',default:'',min:1,max:50,step:1,hint:'留空=不限，容易过拟合'},
  ],
  RandomForestRegressor:[
    {key:'n_estimators',label:'树数 (n_estimators)',type:'number',default:200,min:10,max:1000,step:10,hint:'越多越稳但越慢'},
    {key:'max_depth',label:'最大深度 (max_depth)',type:'number',default:'',min:1,max:50,step:1,hint:'留空=不限，容易过拟合'},
  ],
  GradientBoostingRegressor:[
    {key:'n_estimators',label:'树数 (n_estimators)',type:'number',default:200,min:10,max:1000,step:10,hint:' boosting 轮数'},
    {key:'learning_rate',label:'学习率 (learning_rate)',type:'number',default:0.1,min:0.01,max:1,step:0.01,hint:'小学习率配多树'},
    {key:'max_depth',label:'每棵树深度 (max_depth)',type:'number',default:3,min:1,max:20,step:1,hint:'单棵树深度'},
  ],
  XGBoostRegressor:[
    {key:'n_estimators',label:'树数 (n_estimators)',type:'number',default:200,min:10,max:1000,step:10,hint:'boosting 轮数'},
    {key:'learning_rate',label:'学习率 (learning_rate)',type:'number',default:0.1,min:0.01,max:1,step:0.01,hint:'小学习率配多树'},
    {key:'max_depth',label:'最大深度 (max_depth)',type:'number',default:6,min:1,max:20,step:1,hint:'单棵树深度，默认6'},
    {key:'subsample',label:'行采样 (subsample)',type:'number',default:0.8,min:0.3,max:1,step:0.05,hint:'每棵树用的样本比例'},
    {key:'colsample_bytree',label:'列采样 (colsample_bytree)',type:'number',default:0.8,min:0.3,max:1,step:0.05,hint:'每棵树用的特征比例'},
  ],
  StackingRegressor:[
    {key:'n_estimators',label:'基模型 ExtraTrees 树数',type:'number',default:200,min:50,max:500,step:50,hint:'Stacking 基模型 ET 的树数'},
    {key:'max_depth',label:'基模型 ET 最大深度',type:'number',default:'',min:1,max:50,step:1,hint:'留空=不限'},
  ],
  AdaBoostRegressor:[
    {key:'n_estimators',label:'弱学习器数 (n_estimators)',type:'number',default:100,min:10,max:500,step:10,hint:' boosting 轮数'},
    {key:'learning_rate',label:'学习率 (learning_rate)',type:'number',default:1.0,min:0.01,max:5,step:0.01,hint:'贡献缩减率'},
  ],
  BaggingRegressor:[
    {key:'n_estimators',label:'基学习器数 (n_estimators)',type:'number',default:50,min:5,max:500,step:5,hint:'bagging 的基模型数'},
  ],
  'SVR (RBF)':[
    {key:'C',label:'正则强度 (C)',type:'number',default:1.0,min:0.01,max:100,step:0.1,hint:'大=拟合激进，小=保守'},
    {key:'gamma',label:'核宽度 (gamma)',type:'select',default:'scale',options:['scale','auto'],hint:'RBF 核影响范围'},
  ],
  'SVR (Linear)':[
    {key:'C',label:'正则强度 (C)',type:'number',default:1.0,min:0.01,max:100,step:0.1,hint:'大=拟合激进，小=保守'},
  ],
  MLPRegressor:[
    {key:'hidden_layer_sizes',label:'隐藏层 (如 128,64)',type:'text',default:'128,64',hint:'逗号分隔的神经元数'},
    {key:'max_iter',label:'最大迭代 (max_iter)',type:'number',default:500,min:100,max:3000,step:100,hint:'迭代上限'},
  ],
  'Ridge / Lasso':[
    {key:'alpha',label:'正则强度 (alpha)',type:'number',default:1.0,min:0.001,max:100,step:0.1,hint:'大=强正则防过拟合'},
  ],
  PolynomialRegression:[
    {key:'alpha',label:'Ridge 正则强度 (alpha)',type:'number',default:1.0,min:0.001,max:100,step:0.1,hint:'多项式+Ridge 防过拟合'},
  ],
  LinearRegression:[],
  BayesianRidge:[],
  HuberRegressor:[],
  GaussianProcessRegressor:[
    {key:'alpha',label:'数值稳定性 (alpha)',type:'number',default:0.000001,min:0.0000001,max:0.1,step:0.0000001,hint:'大=更稳定但欠拟合'},
    {key:'n_restarts',label:'重启优化次数 (n_restarts)',type:'number',default:3,min:0,max:10,step:1,hint:'越多越可能找到最优核参数'},
  ],
  KernelRidge:[
    {key:'alpha',label:'正则强度 (alpha)',type:'number',default:1.0,min:0.001,max:100,step:0.1,hint:'大=强正则防过拟合'},
    {key:'kernel',label:'核函数 (kernel)',type:'select',default:'rbf',options:['rbf','poly','linear'],hint:'rbf=高斯核，poly=多项式'},
    {key:'gamma',label:'核宽度 (gamma)',type:'number',default:0.001,min:0.0001,max:1,step:0.001,hint:'小=远距离影响，大=局部拟合'},
  ],
};

function renderHyperFields(){
  const algo=document.getElementById('algo-sel').value;
  const schema=HYPER_SCHEMA[algo]||[];
  const wrap=document.getElementById('hyper-fields');
  if(schema.length===0){
    wrap.innerHTML='<div style="grid-column:1/-1;font-size:12px;color:var(--text-dim);padding:8px 0">此算法无可调超参数，使用默认配置训练。</div>';
    return;
  }
  let html='';
  schema.forEach(f=>{
    const id='hf-'+f.key;
    let inputHtml='';
    if(f.type==='number'){
      const min=f.min!==undefined?'min="'+f.min+'"':'';
      const max=f.max!==undefined?'max="'+f.max+'"':'';
      const step=f.step!==undefined?'step="'+f.step+'"':'';
      inputHtml='<input class="input" type="number" id="'+id+'" value="'+f.default+'" '+min+' '+max+' '+step+' placeholder="默认">';
    }else if(f.type==='select'){
      inputHtml='<select class="select" id="'+id+'">';
      f.options.forEach(o=>inputHtml+='<option'+(o===f.default?' selected':'')+'>'+o+'</option>');
      inputHtml+='</select>';
    }else{
      inputHtml='<input class="input" type="text" id="'+id+'" value="'+f.default+'" placeholder="默认">';
    }
    html+='<div class="field">'+
      '<label class="field-label" for="'+id+'">'+f.label+'</label>'+
      inputHtml+
      (f.hint?'<div style="font-size:10.5px;color:var(--text-faint);margin-top:4px">'+f.hint+'</div>':'')+
    '</div>';
  });
  wrap.innerHTML=html;
}

function collectHyperParams(){
  const algo=document.getElementById('algo-sel').value;
  const schema=HYPER_SCHEMA[algo]||[];
  const params={};
  schema.forEach(f=>{
    const el=document.getElementById('hf-'+f.key);
    if(!el)return;
    let v=el.value;
    if(v===''||v===null||v===undefined)return;
    if(f.type==='number'){
      v=parseFloat(v);
      if(isNaN(v))return;
    }else if(f.key==='hidden_layer_sizes'){
      // 字符串保留，后端解析
    }
    params[f.key]=v;
  });
  return params;
}

function toggleAutoSearch(){
  const on=document.getElementById('auto-search-sw').classList.contains('on');
  document.getElementById('cv-field').style.display=on?'block':'none';
  // 手动面板变灰提示
  const hyperCol=document.getElementById('hyper-col');
  hyperCol.style.opacity=on?'0.5':'1';
  hyperCol.style.pointerEvents=on?'none':'auto';
}

async function renderPreview(){
  const tbl=document.getElementById('preview-table');
  const rows=+document.getElementById('row-slider').value;
  const res=await api('/api/data/preview?n='+rows);
  if(res.error){
    showOfflineHint();
    let html='<thead><tr><th>#</th>';
    ELEMENTS.slice(0,8).forEach(e=>html+='<th>'+e+'</th>');
    html+='<th>HV</th></tr></thead><tbody>';
    for(let i=0;i<rows;i++){
      html+='<tr><td class="idx">'+(i+1)+'</td>';
      ELEMENTS.slice(0,8).forEach(e=>{
        const s=ELEMENT_STATS[e];
        html+='<td>'+(s.med+(Math.random()-.5)*s.med*.4).toFixed(3)+'</td>';
      });
      html+='<td class="tgt">'+Math.round(200+Math.random()*280)+'</td></tr>';
    }
    tbl.innerHTML=html+'</tbody>';
    return;
  }
  const cols=res.columns||[];
  const targetIdx=cols.length-1;
  let html='<thead><tr><th>#</th>';
  cols.forEach(c=>html+='<th>'+c+'</th>');
  html+='</tr></thead><tbody>';
  (res.rows||[]).forEach((row,i)=>{
    html+='<tr><td class="idx">'+(i+1)+'</td>';
    row.forEach((v,j)=>{
      const isTarget=j===targetIdx;
      html+='<td'+(isTarget?' class="tgt"':'')+'>'+(typeof v==='number'?v.toFixed(3):v??'')+'</td>';
    });
    html+='</tr>';
  });
  tbl.innerHTML=html+'</tbody>';
}

/* ============ COMPARE ============ */
let cmpInit=false;
function initCompare(){
  if(cmpInit)return;cmpInit=true;

  document.querySelectorAll('#cmp-chips .chip').forEach(c=>c.addEventListener('click',()=>c.classList.toggle('on')));
  document.getElementById('ts-slider').addEventListener('input',e=>document.getElementById('ts-val').textContent='0.'+e.target.value);
  document.getElementById('cv-slider').addEventListener('input',e=>document.getElementById('cv-val').textContent=e.target.value);

  makeChart('ch-radar',{
    type:'radar',
    data:{
      labels:['R²','1/RMSE','1/MAE','训练速度','泛化性','可解释'],
      datasets:[
        {label:'Stacked(主)',data:[0.98,0.91,0.88,0.6,0.95,0.5],backgroundColor:'rgba(10, 132, 255,.15)',borderColor:'#0A84FF',borderWidth:2,pointBackgroundColor:'#0A84FF'},
        {label:'CatBoost',data:[0.96,0.85,0.82,0.7,0.92,0.4],backgroundColor:'rgba(94, 92, 230,.1)',borderColor:'#5E5CE6',borderWidth:1.5,pointBackgroundColor:'#5E5CE6'},
        {label:'XGBoost',data:[0.95,0.83,0.8,0.75,0.9,0.4],backgroundColor:'rgba(16, 185, 129,.1)',borderColor:'#30D158',borderWidth:1.5,pointBackgroundColor:'#30D158'},
        {label:'RandomForest',data:[0.93,0.78,0.75,0.65,0.85,0.6],backgroundColor:'rgba(56, 189, 248,.08)',borderColor:'#64D2FF',borderWidth:1.5,pointBackgroundColor:'#64D2FF'}
      ]
    },
    options:{maintainAspectRatio:false,
      plugins:{legend:{position:'bottom',labels:{color:'#94a3b8',boxWidth:10}}},
      scales:{r:{angleLines:{color:'rgba(255,255,255,.04)'},grid:{color:'rgba(255,255,255,.04)'},pointLabels:{color:'#94a3b8',font:{size:10}},ticks:{display:false,suggestedMin:0,suggestedMax:1}}}
    }
  });

  document.getElementById('cmp-train').addEventListener('click',async()=>{
    const picked=[...document.querySelectorAll('#cmp-chips .chip.on')].map(c=>c.dataset.model);
    const ts=parseFloat('0.'+document.getElementById('ts-slider').value)||0.2;
    const cv=parseInt(document.getElementById('cv-slider').value)||5;
    const btn=document.getElementById('cmp-train');
    btn.disabled=true;btn.textContent='⏳ 批量训练中...';
    const ffEl=document.getElementById('cmp-feature-filter');
    const ttEl=document.getElementById('cmp-target-transform');
    const res=await api('/api/train/compare',{
      method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({
        models:picked,test_size:ts,cv_folds:cv,
        feature_filter:ffEl?ffEl.value:'off',
        target_transform:ttEl&&ttEl.classList.contains('on')?'log':'off',
      })
    });
    btn.disabled=false;btn.textContent='▶ 训练并比较';
    if(res.error){showOfflineHint();return}
    // 主模型锁定：按测试集 R² 最高自动锁定
    if(res.best){
      const bestM=(res.models||[]).find(m=>m.model===res.best);
      document.getElementById('primary-model-tag').textContent='PRIMARY · LOCKED';
      document.getElementById('primary-model-name').textContent=res.best;
      if(bestM){
        const cvStr=(bestM.cv_r2_mean!==null&&bestM.cv_r2_mean!==undefined)
          ? ' · CV R²='+bestM.cv_r2_mean.toFixed(3) : '';
        document.getElementById('primary-model-meta').textContent=
          'R²='+(bestM.r2!==null?bestM.r2.toFixed(3):'—')+
          ' · RMSE='+(bestM.rmse!==null?bestM.rmse.toFixed(1):'—')+
          ' · MAE='+(bestM.mae!==null?bestM.mae.toFixed(1):'—')+cvStr;
      }
      document.getElementById('primary-model-badge').textContent='主模型';
    }
    // 报表
    const rowsEl2=document.getElementById('cmp-rows');
    rowsEl2.innerHTML='';
    const maxR2=Math.max(...(res.models||[]).map(m=>m.r2??0));
    (res.models||[]).forEach(m=>{
      const d=document.createElement('div');d.className='cmp-row';
      const isBest=m.model===res.best;
      const cvStr=(m.cv_r2_mean!==null&&m.cv_r2_mean!==undefined)
        ? m.cv_r2_mean.toFixed(3)+'±'+m.cv_r2_std.toFixed(3) : '—';
      d.innerHTML='<div class="cmp-name">'+m.model+(isBest?' <span class="tag tag-success" style="margin-left:6px">BEST</span>':'')+'</div>'+
        '<div>'+(m.r2!==null?m.r2.toFixed(3):'—')+'</div>'+
        '<div>'+cvStr+'</div>'+
        '<div>'+(m.rmse!==null?m.rmse.toFixed(1):'—')+'</div>'+
        '<div>'+(m.mae!==null?m.mae.toFixed(1):'—')+'</div>'+
        '<div>'+m.time.toFixed(1)+'s</div>'+
        '<div><div class="cmp-bar"><div class="cmp-bar-fill" style="width:'+(m.r2?Math.round(m.r2/maxR2*100):0)+'%"></div></div></div>';
      rowsEl2.appendChild(d);
    });
    // 雷达图：用真实训练结果更新
    updateCompareRadar(res.models||[]);
  });
}

// 雷达图：按真实训练结果渲染（R² / CV-R² / 1/RMSE / 1/MAE / 训练速度 / 稳定性）
function updateCompareRadar(models){
  const valid=models.filter(m=>m.r2!==null&&m.r2!==undefined);
  if(valid.length===0)return;
  const colors=['#0A84FF','#5E5CE6','#30D158','#64D2FF','#FF9F0A','#FF453A','#BF5AF2','#FF375F','#84cc16','#14b8a6','#f97316','#14b8a6','#0ea5e9','#22c55e','#eab308'];
  const maxRm=Math.max(...valid.map(m=>m.rmse||1));
  const maxMa=Math.max(...valid.map(m=>m.mae||1));
  const maxT=Math.max(...valid.map(m=>m.time||1));
  const datasets=valid.map((m,i)=>{
    const c=colors[i%colors.length];
    return {
      label:m.model,
      data:[
        Math.max(0,Math.min(1,m.r2)),                              // R²
        m.cv_r2_mean!==null&&m.cv_r2_mean!==undefined?Math.max(0,Math.min(1,m.cv_r2_mean)):0,  // CV R²
        1-(m.rmse||maxRm)/maxRm,                                   // 1/RMSE 归一化
        1-(m.mae||maxMa)/maxMa,                                    // 1/MAE 归一化
        1-(m.time||maxT)/maxT,                                     // 训练速度（越快越大）
        m.cv_r2_std!==null&&m.cv_r2_std!==undefined?Math.max(0,1-m.cv_r2_std*5):0.5,           // 稳定性（std 越小越大）
      ],
      backgroundColor:c+'22',
      borderColor:c,
      borderWidth:1.8,
      pointBackgroundColor:c,
    };
  });
  makeChart('ch-radar',{
    type:'radar',
    data:{labels:['R²','CV R²','1/RMSE','1/MAE','训练速度','稳定性'],datasets},
    options:{maintainAspectRatio:false,
      plugins:{legend:{position:'bottom',labels:{color:'#94a3b8',boxWidth:10}}},
      scales:{r:{angleLines:{color:'rgba(255,255,255,.04)'},grid:{color:'rgba(255,255,255,.04)'},pointLabels:{color:'#94a3b8',font:{size:10}},ticks:{display:false,suggestedMin:0,suggestedMax:1}}}
    }
  });
}

/* ============ ACTIVE LEARNING ============ */
let alInit=false;
function initActive(){
  if(alInit)return;alInit=true;

  // 探索滑块联动
  document.getElementById('al-explore').addEventListener('input',e=>{
    document.getElementById('al-explore-val').textContent=e.target.value;
  });

  // 导出按钮
  document.getElementById('al-export').addEventListener('click',async()=>{
    try{
      const res=await fetch(API_BASE+'/api/active/export_csv');
      if(!res.ok){const e=await res.json();toast('⚠ '+(e.error||'导出失败'));return}
      const blob=await res.blob();
      const cd=res.headers.get('Content-Disposition')||'';
      const m=cd.match(/filename="?([^"]+)"?/);
      const fn=m?m[1]:'recommended_samples.csv';
      const a=document.createElement('a');
      a.href=URL.createObjectURL(blob);a.download=fn;a.click();
      URL.revokeObjectURL(a.href);
      toast('✓ 已导出 '+fn);
    }catch(err){toast('⚠ 导出失败: '+err.message)}
  });

  document.getElementById('al-train').addEventListener('click',async()=>{
    const btn=document.getElementById('al-train');
    const payload={
      model_name:document.getElementById('al-model').value,
      strategy:document.getElementById('al-strategy').value,
      n_candidates:parseInt(document.getElementById('al-n-candidates').value)||5000,
      n_recommend:parseInt(document.getElementById('al-n-recommend').value)||8,
      explore_ratio:parseFloat(document.getElementById('al-explore').value)||0.5,
      cv_folds:parseInt(document.getElementById('al-cv-folds').value)||5,
    };
    btn.disabled=true;btn.textContent='⏳ 优化中...（训练+CV+采样+打分）';
    document.getElementById('al-status-tag').textContent='运行中';
    const res=await api('/api/active/optimize',{
      method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify(payload)
    });
    btn.disabled=false;btn.textContent='▶ Train · Optimize';
    if(res.error){showOfflineHint();toast('⚠ '+res.error);document.getElementById('al-status-tag').textContent='错误';return}
    renderActiveResult(res);
  });

  function renderActiveResult(res){
    const meta=res.meta||{};
    const recs=res.recommendations||[];
    // 顶部指标
    document.getElementById('al-n-train').textContent=meta.n_train||'—';
    document.getElementById('al-cv-r2').textContent=(meta.cv_r2_mean??'—').toFixed?.(3)||(meta.cv_r2_mean??'—');
    document.getElementById('al-y-best').textContent=Math.round(meta.y_best||0);
    document.getElementById('al-n-cand').textContent=meta.n_candidates||'—';
    document.getElementById('al-status-tag').textContent='完成';
    // 02 卡片
    document.getElementById('al-r2-display').innerHTML=(meta.cv_r2_mean??0).toFixed(3)+'<em>R²</em>';
    const stratMap={ei:'EI',ucb:'UCB',bayes:'Bayes',thompson:'Thompson',greedy:'Greedy'};
    document.getElementById('al-model-display').textContent=
      (meta.model_name||'')+' · '+(stratMap[meta.strategy]||meta.strategy)+' · CV R²='+(meta.cv_r2_mean??0).toFixed(3)+'±'+(meta.cv_r2_std??0).toFixed(3);
    // 散点图
    renderFrontier(res.scatter||[],recs);
    // 推荐看板
    renderRecs(recs);
    // 启用导出
    document.getElementById('al-export').disabled=false;
    toast('✓ 优化完成 · 推荐 '+recs.length+' 个配方');
  }

  function renderFrontier(scatter,recs){
    const normal=scatter.filter(p=>!p.recommended).map(p=>({x:p.pred,y:p.sigma}));
    const recommended=scatter.filter(p=>p.recommended).map(p=>({x:p.pred,y:p.sigma}));
    makeChart('ch-al-frontier',{
      type:'scatter',
      data:{datasets:[
        {label:'设计空间',data:normal,backgroundColor:'rgba(94, 92, 230,.2)',borderColor:'rgba(94, 92, 230,.4)',pointRadius:2},
        {label:'推荐',data:recommended,backgroundColor:'#0A84FF',borderColor:'#409CFF',pointRadius:6}
      ]},
      options:{maintainAspectRatio:false,
        plugins:{legend:{display:true,position:'bottom',labels:{color:'#94a3b8',boxWidth:10}}},
        scales:{
          x:{title:{display:true,text:'预测 HV',color:'#94a3b8',font:{size:10}},grid:{color:'rgba(255,255,255,.02)'},ticks:{color:'#475569',font:{size:9}}},
          y:{title:{display:true,text:'不确定性 σ',color:'#94a3b8',font:{size:10}},grid:{color:'rgba(255,255,255,.02)'},ticks:{color:'#475569',font:{size:9}}}
        }
      }
    });
  }

  function renderRecs(recs){
    const grid=document.getElementById('rec-grid');
    grid.innerHTML='';
    recs.forEach(r=>{
      const c=document.createElement('div');c.className='rec-card';
      // 取前 8 个非零元素显示
      const compEntries=Object.entries(r.composition||{})
        .filter(([k,v])=>v>0.01)
        .sort((a,b)=>b[1]-a[1])
        .slice(0,8);
      const compHtml=compEntries.map(([k,v])=>'<b>'+k+'</b>'+v.toFixed(2)).join(' ');
      c.innerHTML='<div class="rec-rank">'+String(r.rank).padStart(2,'0')+'</div>'+
        '<div class="rec-pred">'+r.predicted_hv+' <small>HV</small></div>'+
        '<div style="font-family:var(--sans);font-size:10px;color:var(--text-faint);margin-top:4px;font-weight:500">σ=±'+r.uncertainty+' · score='+r.score+'</div>'+
        '<div class="rec-comp">'+compHtml+'</div>';
      grid.appendChild(c);
    });
  }
}

/* ============ OUTLIERS ============ */
let olInit=false,olChart=null;
function initOutliers(){
  if(olInit){return}olInit=true;
  // contamination 滑块
  const slider=document.getElementById('ol-cont-slider');
  const val=document.getElementById('ol-cont-val');
  slider.addEventListener('input',()=>{
    val.textContent='0.'+slider.value.padStart(2,'0');
  });
  document.getElementById('ol-run').addEventListener('click',async()=>{
    const method=document.getElementById('ol-method-sel').value;
    const cont=parseFloat(val.textContent);
    const btn=document.getElementById('ol-run');
    btn.disabled=true;btn.textContent='⏳ 检测中...';
    toast('▶ 正在执行异常值检测...');
    showSkeleton('#ol-table','运行 '+method+' 中...');
    const res=await api('/api/outliers/detect',{
      method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({method,contamination:cont})
    });
    btn.disabled=false;btn.textContent='▶ 运行异常值检测';
    if(res.error){showOfflineHint();toast('⚠ '+res.error);return}
    document.getElementById('ol-total').textContent=res.total;
    document.getElementById('ol-n').textContent=res.n_outliers;
    document.getElementById('ol-ratio').textContent='占比 '+(res.n_outliers/res.total*100).toFixed(1)+'%';
    document.getElementById('ol-method').textContent=method;
    document.getElementById('ol-count-tag').textContent=res.n_outliers+' 条';
    // 表格
    const tbl=document.getElementById('ol-table');
    let html='<thead><tr><th>#</th><th>样本索引</th><th>详情</th></tr></thead><tbody>';
    (res.outliers||[]).forEach((o,i)=>{
      const det=Object.entries(o.values||{}).slice(0,6).map(([k,v])=>k+'='+(+v).toFixed(2)).join(' · ');
      html+='<tr><td class="idx">'+(i+1)+'</td><td class="tgt">'+o.index+'</td><td>'+det+'</td></tr>';
    });
    if(!res.outliers||!res.outliers.length)html+='<tr><td colspan="3" style="text-align:center;color:var(--text-faint);padding:24px">✓ 未检测到异常样本</td></tr>';
    tbl.innerHTML=html+'</tbody>';
    // 图表：HV 散点 + 异常高亮
    olChart=makeChart('ch-outliers',{
      type:'bar',
      data:{labels:['正常样本','异常样本'],datasets:[{
        data:[res.total-res.n_outliers,res.n_outliers],
        backgroundColor:['rgba(10,132,255,.4)','rgba(239,68,68,.7)'],
        borderColor:['#0A84FF','#FF453A'],borderWidth:1,barPercentage:.5
      }]},
      options:{maintainAspectRatio:false,
        plugins:{legend:{display:false},
          title:{display:true,text:'异常 vs 正常样本数',color:'#f8fafc',font:{family:'Inter',size:13,weight:'500'},align:'start',padding:{bottom:14}}},
        scales:{x:{grid:{display:false},ticks:{color:'#94a3b8'}},
          y:{grid:{color:'rgba(255,255,255,.02)'},ticks:{color:'#475569'}}}
      }
    });
    toast('✓ 检测完成 · 异常 '+res.n_outliers+' 条');
  });
}

/* ============ DATABASE ============ */
let dbInit=false,dbSchema=null;
function initDatabase(){
  if(dbInit)return;dbInit=true;
  // 加载初始信息
  dbSchema=null;
  // 拉表结构
  api('/api/database/schema').then(res=>{
    if(res.error){showOfflineHint();return}
    dbSchema=res;
    document.getElementById('db-rows').textContent=res.n_rows;
    document.getElementById('db-cols').textContent=(res.columns||[]).length;
    const allCols=(res.columns||[]).map(c=>c.name);
    const numCols=(res.columns||[]).filter(c=>c.type==='number').map(c=>c.name);
    // 填充列下拉
    function fillSel(id,cols,placeholder){
      const sel=document.getElementById(id);
      if(placeholder)sel.innerHTML='<option value="">'+placeholder+'</option>';
      else sel.innerHTML='';
      cols.forEach(c=>{
        const o=document.createElement('option');o.value=c;o.textContent=c;
        sel.appendChild(o);
      });
    }
    fillSel('db-cols-sel',allCols);
    fillSel('db-order-col',allCols,'不排序');
    fillSel('db-agg-col',numCols,'（COUNT 时留空）');
    fillSel('db-agg-group',allCols);
  });

  // 查询模式切换
  document.querySelectorAll('#db-mode .chip').forEach(c=>{
    c.addEventListener('click',()=>{
      document.querySelectorAll('#db-mode .chip').forEach(x=>x.classList.remove('on'));
      c.classList.add('on');
      const mode=c.dataset.mode;
      document.getElementById('db-panel-select').style.display=mode==='select'?'block':'none';
      document.getElementById('db-panel-aggregate').style.display=mode==='aggregate'?'block':'none';
    });
  });

  // 筛选条件
  function addFilterRow(col='',op='>',val=''){
    if(!dbSchema)return;
    const numCols=dbSchema.columns.filter(c=>c.type==='number').map(c=>c.name);
    const allCols=dbSchema.columns.map(c=>c.name);
    const row=document.createElement('div');
    row.style.cssText='display:flex;gap:6px;margin-bottom:6px;align-items:center';
    const colSel=document.createElement('select');colSel.className='input';colSel.style.flex='2';
    colSel.innerHTML=allCols.map(c=>'<option value="'+c+'"'+(c===col?' selected':'')+'>'+c+'</option>').join('');
    const opSel=document.createElement('select');opSel.className='input';opSel.style.flex='1';
    ['>','<','>=','<=','=','!=','between','contains'].forEach(o=>{
      const op=document.createElement('option');op.value=o;op.textContent=o;opSel.appendChild(op);
    });
    opSel.value=op;
    const valInp=document.createElement('input');valInp.className='input';valInp.style.flex='2';
    valInp.placeholder='数值（between 用 a,b）';valInp.value=val;
    const delBtn=document.createElement('button');delBtn.className='btn btn-ghost';delBtn.textContent='×';
    delBtn.style.cssText='flex:0 0 auto;padding:4px 10px';
    delBtn.onclick=()=>row.remove();
    row.appendChild(colSel);row.appendChild(opSel);row.appendChild(valInp);row.appendChild(delBtn);
    document.getElementById('db-filters').appendChild(row);
  }
  document.getElementById('db-add-filter').addEventListener('click',()=>{
    if(!dbSchema){toast('请先等待数据列加载','warn');return;}
    addFilterRow();
  });

  // 预设
  const PRESETS={
    top10:{mode:'select',limit:10},
    hard:{mode:'select',filters:[{col:'Vickers Hardness (HV)',op:'>',val:'400'}],limit:100},
    eleavg:{mode:'aggregate',agg:{func:'avg',col:'Al',group_by:[]},limit:50},
    count:{mode:'aggregate',agg:{func:'count',col:'',group_by:[]},limit:10},
    sorted_hv:{mode:'select',order_by:{col:'Vickers Hardness (HV)',desc:true},limit:20},
    ni_range:{mode:'select',filters:[{col:'Ni',op:'between',val:'5,10'}],limit:50},
  };
  document.querySelectorAll('#db-quick .chip').forEach(c=>{
    c.addEventListener('click',()=>applyPreset(c.dataset.preset));
  });
  function applyPreset(name){
    const p=PRESETS[name];if(!p)return;
    // 模式
    document.querySelectorAll('#db-mode .chip').forEach(x=>x.classList.toggle('on',x.dataset.mode===p.mode));
    document.getElementById('db-panel-select').style.display=p.mode==='select'?'block':'none';
    document.getElementById('db-panel-aggregate').style.display=p.mode==='aggregate'?'block':'none';
    // 清空筛选
    document.getElementById('db-filters').innerHTML='';
    if(p.filters){p.filters.forEach(f=>addFilterRow(f.col,f.op,f.val));}
    // 排序
    if(p.order_by){
      document.getElementById('db-order-col').value=p.order_by.col;
      document.getElementById('db-order-dir').value=p.order_by.desc?'desc':'asc';
    }
    // 聚合
    if(p.agg){
      document.getElementById('db-agg-func').value=p.agg.func;
      if(p.agg.col)document.getElementById('db-agg-col').value=p.agg.col;
    }
    // limit
    document.getElementById('db-limit').value=p.limit;
    document.getElementById('db-limit-val').textContent=p.limit;
    runQuery();
  }

  // limit 滑块联动
  document.getElementById('db-limit').addEventListener('input',e=>{
    document.getElementById('db-limit-val').textContent=e.target.value;
  });

  document.getElementById('db-run').addEventListener('click',runQuery);
  async function runQuery(){
    const btn=document.getElementById('db-run');
    const mode=[...document.querySelectorAll('#db-mode .chip.on')].map(x=>x.dataset.mode)[0]||'select';
    const limit=parseInt(document.getElementById('db-limit').value)||100;
    const payload={limit};
    if(mode==='select'){
      // 选列
      const cols=[...document.querySelectorAll('#db-cols-sel option:checked')].map(o=>o.value);
      if(cols.length)payload.columns=cols;
      // 筛选
      const filters=[];
      document.querySelectorAll('#db-filters > div').forEach(row=>{
        const col=row.querySelector('select').value;
        const op=row.querySelectorAll('select')[1].value;
        const val=row.querySelector('input').value;
        if(col&&op&&val)filters.push({col,op,val});
      });
      if(filters.length)payload.filters=filters;
      // 排序
      const obCol=document.getElementById('db-order-col').value;
      const obDir=document.getElementById('db-order-dir').value;
      if(obCol)payload.order_by={col:obCol,desc:obDir==='desc'};
    }else{
      // 聚合
      const func=document.getElementById('db-agg-func').value;
      const col=document.getElementById('db-agg-col').value;
      const group=[...document.querySelectorAll('#db-agg-group option:checked')].map(o=>o.value);
      payload.aggregate={func,col,group_by:group};
    }
    btn.disabled=true;btn.textContent='⏳ 执行中...';
    document.getElementById('db-status').textContent='执行中';
    const res=await api('/api/database/query',{
      method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify(payload)
    });
    btn.disabled=false;btn.textContent='▶ 执行查询';
    if(res.error){showOfflineHint();toast('⚠ '+res.error);document.getElementById('db-status').textContent='错误';return}
    document.getElementById('db-status').textContent='完成';
    document.getElementById('db-result-tag').textContent=res.n+' 行';
    const tbl=document.getElementById('db-table');
    const cols=res.columns||[];
    let html='<thead><tr><th>#</th>';
    cols.forEach(c=>html+='<th>'+c+'</th>');
    html+='</tr></thead><tbody>';
    (res.rows||[]).forEach((row,i)=>{
      html+='<tr><td class="idx">'+(i+1)+'</td>';
      row.forEach(v=>{
        const num=typeof v==='number';
        html+='<td'+(num?' style="text-align:right"':'')+'>'+(num?(Math.abs(v)<1?v.toFixed(4):v.toFixed(2)):(v??''))+'</td>';
      });
      html+='</tr>';
    });
    if(!res.rows||!res.rows.length)html+='<tr><td colspan="'+(cols.length+1)+'" style="text-align:center;color:var(--text-faint);padding:24px">查询返回 0 行</td></tr>';
    tbl.innerHTML=html+'</tbody>';
    toast('✓ 查询完成 · 返回 '+res.n+' 行');
  }
}

/* ============ DUPLICATES ============ */
let dpInit=false,dpChart=null;
function initDuplicates(){
  if(dpInit)return;dpInit=true;
  document.getElementById('dp-run').addEventListener('click',async()=>{
    const btn=document.getElementById('dp-run');
    btn.disabled=true;btn.textContent='⏳ 检测中...';
    toast('▶ 正在检测重复样本...');
    const res=await api('/api/duplicates/detect');
    btn.disabled=false;btn.textContent='▶ 检测重复样本';
    if(res.error){showOfflineHint();toast('⚠ '+res.error);return}

    const total=res.total;
    const nDup=res.n_duplicates;
    const tempGroups=res.temp_exp_groups||0;
    const realDupCount=res.real_dup_count||0;
    const realDupGroups=res.real_dup_groups||0;
    const uniqComp=res.n_unique_compositions||(total-nDup);

    // 指标卡
    document.getElementById('dp-total').textContent=total;
    document.getElementById('dp-n').textContent=nDup;
    document.getElementById('dp-ratio').textContent='占比 '+(nDup/total*100).toFixed(1)+'%';
    document.getElementById('dp-temp-groups').textContent=tempGroups;
    document.getElementById('dp-temp-hint').textContent=tempGroups>0?'同配方不同温度':'无';
    document.getElementById('dp-real').textContent=realDupCount;
    document.getElementById('dp-real-hint').textContent=realDupCount>0?(realDupGroups+' 组需处理'):'无真重复';
    document.getElementById('dp-count-tag').textContent=nDup+' 条';

    // 说明卡片：有温度实验时显示
    const explainCard=document.getElementById('dp-explain-card');
    if(tempGroups>0){
      explainCard.style.display='block';
      document.getElementById('dp-explain-tag').textContent=realDupCount>0?('部分需处理'):('全部正常');
      document.getElementById('dp-explain-tag').className='tag '+(realDupCount>0?'tag-ember':'tag-success');
    }else{
      explainCard.style.display='none';
    }

    // 表格
    const tbl=document.getElementById('dp-table');
    const cols=res.columns||[];
    const nameIdx=cols.indexOf('Image_Name');
    // 解析温度后缀
    function parseTemp(name){
      if(typeof name!=='string')return null;
      const m=name.match(/-(\d+)$/);
      return m?parseInt(m[1]):null;
    }
    // 按成分分组，判断每组是否多温度
    const grpMap={};
    (res.rows||[]).forEach((row,i)=>{
      const key=cols.filter(c=>c!=='Image_Name'&&c!=='Vickers Hardness (HV)').map(c=>row[cols.indexOf(c)]).join('|');
      if(!grpMap[key])grpMap[key]={rows:[],temps:new Set()};
      grpMap[key].rows.push(i);
      const t=parseTemp(row[nameIdx]);
      if(t!==null)grpMap[key].temps.add(t);
    });

    let html='<thead><tr><th>#</th>';
    cols.forEach(c=>html+='<th>'+c+'</th>');
    html+='<th>类型</th></tr></thead><tbody>';
    (res.rows||[]).forEach((row,i)=>{
      const key=cols.filter(c=>c!=='Image_Name'&&c!=='Vickers Hardness (HV)').map(c=>row[cols.indexOf(c)]).join('|');
      const grp=grpMap[key];
      const isTempExp=grp&&grp.temps.size>1;
      html+='<tr><td class="idx">'+(i+1)+'</td>';
      row.forEach((v,j)=>{
        const isTarget=j===cols.length-1;
        html+='<td'+(isTarget?' class="tgt"':'')+'>'+(typeof v==='number'?(Math.abs(v)<1?v.toFixed(4):v.toFixed(2)):(v??''))+'</td>';
      });
      html+='<td>'+(isTempExp?'<span class="tag tag-success">独立实验</span>':'<span class="tag tag-ember">真重复</span>')+'</td>';
      html+='</tr>';
    });
    if(!res.rows||!res.rows.length)html+='<tr><td colspan="'+(cols.length+2)+'" style="text-align:center;color:var(--text-faint);padding:24px">✓ 未检测到重复样本</td></tr>';
    tbl.innerHTML=html+'</tbody>';

    // 图表：3 类分布
    const normalCount=total-nDup;
    const variantCount=nDup-realDupCount;
    dpChart=makeChart('ch-duplicates',{
      type:'doughnut',
      data:{labels:['唯一样本','独立实验','真重复'],datasets:[{
        data:[normalCount,variantCount,realDupCount],
        backgroundColor:['rgba(10,132,255,.5)','rgba(16,185,129,.6)','rgba(239,68,68,.7)'],
        borderColor:['#0A84FF','#30D158','#FF453A'],borderWidth:1
      }]},
      options:{maintainAspectRatio:false,
        plugins:{legend:{position:'bottom',labels:{color:'#94a3b8',boxWidth:10}}}
      }
    });
    const msg=realDupCount>0
      ?'✓ 检测完成 · 独立实验 '+tempGroups+' 组 / 真重复 '+realDupCount+' 条需处理'
      :'✓ 检测完成 · 重复 '+nDup+' 条全部为独立实验，无需处理';
    toast(msg);
  });
}

/* ============ CORRELATION PAGE ============ */
let corrPageInit=false,corrPageChart=null;
function initCorrelation(){
  if(corrPageInit)return;corrPageInit=true;
  const methodChips=document.querySelectorAll('#corr-method-chips .chip');
  methodChips.forEach(c=>{
    c.addEventListener('click',()=>{
      methodChips.forEach(x=>x.classList.remove('on'));
      c.classList.add('on');
      loadCorr(c.dataset.method);
    });
  });
  async function loadCorr(method){
    toast('▶ 加载 '+method+' 相关性矩阵...');
    showSkeleton('#corr-pairs-table','计算 '+method+' 矩阵中...');
    const res=await api('/api/correlation/matrix?method='+method);
    if(res.error){showOfflineHint();toast('⚠ '+res.error);return}
    const cols=res.columns||[];
    const matrix=res.matrix||[];
    const N=cols.length;
    const dataset=[];
    for(let i=0;i<N;i++)for(let j=0;j<N;j++){
      const v=matrix[i][j];
      dataset.push({x:j,y:N-1-i,r:Math.abs(v)*9,v:v});
    }
    corrPageChart=makeChart('ch-corr-page',{
      type:'bubble',
      data:{datasets:[{data:dataset,
        backgroundColor:dataset.map(d=>d.v>0?'rgba(10, 132, 255,'+(Math.abs(d.v)*.8)+')':'rgba(94, 92, 230,'+(Math.abs(d.v)*.8)+')'),
        borderColor:dataset.map(d=>d.v>0?'#0A84FF':'#5E5CE6')}]},
      options:{maintainAspectRatio:false,
        plugins:{legend:{display:false},
          title:{display:true,text:'元素相关性矩阵（青=正相关 · 紫=负相关 · 气泡大小=|r|）',color:'#f8fafc',font:{family:'Inter',size:13,weight:'500'},align:'start',padding:{bottom:14}},
          tooltip:{callbacks:{label:c=>cols[c.raw.x]+' ↔ '+cols[N-1-c.raw.y]+' : '+c.raw.v.toFixed(3)}}},
        scales:{
          x:{ticks:{color:'#94a3b8',stepSize:1,callback:v=>cols[v]||''},grid:{color:'rgba(255,255,255,.02)'}},
          y:{ticks:{color:'#94a3b8',stepSize:1,callback:v=>cols[N-1-v]||''},grid:{color:'rgba(255,255,255,.02)'}}
        }
      }
    });
    // 高耦合对
    const pairs=res.high_pairs||[];
    document.getElementById('corr-pairs-tag').textContent=pairs.length+' 对';
    const tbl=document.getElementById('corr-pairs-table');
    let html='<thead><tr><th>#</th><th>元素 A</th><th>元素 B</th><th>相关系数 r</th><th>强度</th></tr></thead><tbody>';
    pairs.forEach((p,i)=>{
      const strength=Math.abs(p.r)>=0.9?'极强':Math.abs(p.r)>=0.8?'强':'中';
      html+='<tr><td class="idx">'+(i+1)+'</td><td class="tgt">'+p.a+'</td><td class="tgt">'+p.b+'</td><td>'+(p.r>0?'+':'')+p.r.toFixed(3)+'</td><td><span class="tag tag-ember">'+strength+'</span></td></tr>';
    });
    if(!pairs.length)html+='<tr><td colspan="5" style="text-align:center;color:var(--text-faint);padding:24px">✓ 无 |r|≥0.7 的高耦合对</td></tr>';
    tbl.innerHTML=html+'</tbody>';
    toast('✓ '+method+' 矩阵已加载 · 高耦合 '+pairs.length+' 对');
  }
  loadCorr('pearson');
}

/* ============ PCA / SELECTION ============ */
let pcaInit=false,pcaChart=null;
function initSelection(){
  if(pcaInit)return;pcaInit=true;
  const slider=document.getElementById('pca-slider');
  const val=document.getElementById('pca-slider-val');
  slider.addEventListener('input',()=>{val.textContent=slider.value});
  document.getElementById('pca-run').addEventListener('click',()=>loadPCA(+slider.value));
  async function loadPCA(n){
    toast('▶ 计算 PCA (n='+n+')...');
    showSkeleton('#pca-table','PCA 降维中...');
    const res=await api('/api/features/pca?n='+n);
    if(res.error){showOfflineHint();toast('⚠ '+res.error);return}
    const ev=res.explained_variance||[];
    const cum=res.cumulative||[];
    const comps=res.components||[];
    document.getElementById('pca-n').textContent=res.n_components;
    document.getElementById('pca-cum').textContent=(cum[cum.length-1]*100).toFixed(1)+'%';
    document.getElementById('pca-pc1').textContent=(ev[0]*100).toFixed(1)+'%';
    // 建议维度：累积方差≥90%
    let rec=res.n_components;
    for(let i=0;i<cum.length;i++){if(cum[i]>=0.9){rec=i+1;break}}
    document.getElementById('pca-rec').textContent=rec+' 维';
    // 表格
    const tbl=document.getElementById('pca-table');
    let html='<thead><tr><th>PC</th><th>方差占比</th><th>累积</th><th>Top-1</th><th>Top-2</th><th>Top-3</th></tr></thead><tbody>';
    for(let i=0;i<ev.length;i++){
      const top3=(comps[i]||[]).join(' / ')||'—';
      const t=comps[i]||[];
      html+='<tr><td class="tgt">PC'+(i+1)+'</td><td>'+(ev[i]*100).toFixed(2)+'%</td><td>'+(cum[i]*100).toFixed(1)+'%</td><td>'+(t[0]||'—')+'</td><td>'+(t[1]||'—')+'</td><td>'+(t[2]||'—')+'</td></tr>';
    }
    tbl.innerHTML=html+'</tbody>';
    // 图表
    pcaChart=makeChart('ch-pca',{
      data:{labels:ev.map((_,i)=>'PC'+(i+1)),datasets:[
        {type:'bar',label:'单成分方差',data:ev.map(v=>v*100),
          backgroundColor:'rgba(10,132,255,.4)',borderColor:'#0A84FF',borderWidth:1,barPercentage:.6,order:2},
        {type:'line',label:'累积方差',data:cum.map(v=>v*100),
          borderColor:'#409CFF',backgroundColor:'rgba(64,156,255,.1)',
          borderWidth:2,pointRadius:3,pointBackgroundColor:'#409CFF',fill:true,tension:.3,order:1}
      ]},
      options:{maintainAspectRatio:false,
        plugins:{legend:{position:'bottom',labels:{color:'#94a3b8',boxWidth:10}},
          title:{display:true,text:'方差解释曲线（≥90% 为建议维度）',color:'#f8fafc',font:{family:'Inter',size:13,weight:'500'},align:'start',padding:{bottom:14}}},
        scales:{
          x:{grid:{display:false},ticks:{color:'#475569',font:{size:9}}},
          y:{grid:{color:'rgba(255,255,255,.02)'},ticks:{color:'#475569',callback:v=>v+'%'},max:100}
        }
      }
    });
    toast('✓ PCA 完成 · 累积方差 '+(cum[cum.length-1]*100).toFixed(1)+'%');
  }
  loadPCA(10);
}

/* ============ IMPORTANCE ============ */
let impInit=false,impChart=null;
function initImportance(){
  if(impInit)return;impInit=true;
  document.getElementById('imp-run').addEventListener('click',async()=>{
    const model=document.getElementById('imp-model-sel').value;
    document.getElementById('imp-model').textContent=model.replace('Regressor','');
    const btn=document.getElementById('imp-run');
    btn.disabled=true;btn.textContent='⏳ 训练中...';
    toast('▶ 训练 '+model+' ...');
    showSkeleton('#imp-top-grid','训练 '+model+' 中...');
    // 使用 /api/features/importance（固定 ExtraTrees），如选其他模型则提示
    const res=await api('/api/features/importance');
    btn.disabled=false;btn.textContent='▶ 训练并计算重要性';
    if(res.error){showOfflineHint();toast('⚠ '+res.error);return}
    const feats=res.features||[];
    const imps=res.importances||[];
    if(!feats.length){toast('⚠ 无数据');return}
    document.getElementById('imp-top1').textContent=feats[0];
    document.getElementById('imp-top1-v').textContent='贡献 '+(imps[0]*100).toFixed(1)+'%';
    const top5Sum=imps.slice(0,5).reduce((a,b)=>a+b,0);
    document.getElementById('imp-top5').textContent=(top5Sum*100).toFixed(1)+'%';
    document.getElementById('imp-n').textContent=feats.length;
    // 图表：横向条形图
    const revFeats=feats.slice().reverse();
    const revImps=imps.slice().reverse();
    impChart=makeChart('ch-importance',{
      type:'bar',
      data:{labels:revFeats,datasets:[{
        label:'重要性',
        data:revImps.map(v=>v*100),
        backgroundColor:revImps.map((v,i)=>i>=revImps.length-5?'rgba(10,132,255,.7)':'rgba(10,132,255,.25)'),
        borderColor:revImps.map((v,i)=>i>=revImps.length-5?'#0A84FF':'rgba(10,132,255,.4)'),
        borderWidth:1,barPercentage:.7
      }]},
      options:{indexAxis:'y',maintainAspectRatio:false,
        plugins:{legend:{display:false},
          title:{display:true,text:'元素对维氏硬度的重要性（%）',color:'#f8fafc',font:{family:'Inter',size:13,weight:'500'},align:'start',padding:{bottom:14}}},
        scales:{
          x:{grid:{color:'rgba(255,255,255,.02)'},ticks:{color:'#475569'}},
          y:{grid:{display:false},ticks:{color:'#94a3b8',font:{size:10}}}
        }
      }
    });
    // Top-5 卡片
    const grid=document.getElementById('imp-top-grid');
    grid.innerHTML='';
    feats.slice(0,5).forEach((f,i)=>{
      const c=document.createElement('div');c.className='rec-card';
      c.innerHTML='<div class="rec-rank">'+(i+1).toString().padStart(2,'0')+'</div>'+
        '<div class="rec-pred">'+f+' <small>'+(imps[i]*100).toFixed(1)+'%</small></div>'+
        '<div style="font-family:var(--sans);font-size:10px;color:var(--text-faint);margin-top:4px;font-weight:500">FEATURE IMPORTANCE</div>'+
        '<div class="rec-comp">合金元素 · 贡献度 '+(imps[i]*100).toFixed(2)+'%</div>';
      grid.appendChild(c);
    });
    toast('✓ 重要性计算完成 · Top1: '+feats[0]);
  });
}

/* ============ MISSING ============ */
let msInit=false,msChart=null;
function initMissing(){
  if(msInit)return;msInit=true;
  loadStats();
  document.getElementById('ms-refresh').addEventListener('click',loadStats);
  document.getElementById('ms-fill').addEventListener('click',async()=>{
    const strategy=document.getElementById('ms-strategy').value;
    const btn=document.getElementById('ms-fill');
    btn.disabled=true;btn.textContent='⏳ 填充中...';
    toast('▶ 执行 '+strategy+' 填充...');
    const res=await api('/api/missing/fill',{
      method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({strategy})
    });
    btn.disabled=false;btn.textContent='▶ 执行填充';
    if(res.error){showOfflineHint();toast('⚠ '+res.error);return}
    document.getElementById('ms-status').textContent='已填充';
    toast('✓ 填充完成 · '+res.before+' → '+res.after+'（剩余 '+(res.rows_remaining)+' 行）');
    setTimeout(loadStats,500);
  });
  async function loadStats(){
    toast('▶ 重新统计缺失值...');
    showSkeleton('#ms-table','统计缺失值中...');
    const res=await api('/api/missing/stats');
    if(res.error){showOfflineHint();toast('⚠ '+res.error);return}
    document.getElementById('ms-total').textContent=res.total_rows;
    document.getElementById('ms-n').textContent=res.total_missing;
    const nCols=res.total_columns||(res.columns?res.columns.length:24);
    document.getElementById('ms-ratio').textContent='占 '+(res.total_missing/(res.total_rows*nCols)*100).toFixed(1)+'%';
    const cols=res.columns||[];
    const missCols=cols.filter(c=>c.missing>0);
    document.getElementById('ms-cols').textContent=missCols.length;
    // 表格
    const tbl=document.getElementById('ms-table');
    let html='<thead><tr><th>列名</th><th>缺失数</th><th>总行数</th><th>缺失率</th></tr></thead><tbody>';
    cols.forEach(c=>{
      html+='<tr><td class="tgt">'+c.column+'</td><td>'+(c.missing>0?'<span style="color:var(--danger)">'+c.missing+'</span>':'0')+'</td><td>'+c.total+'</td><td>'+c.ratio+'%</td></tr>';
    });
    if(!cols.length)html+='<tr><td colspan="4" style="text-align:center;color:var(--text-faint);padding:24px">无数据</td></tr>';
    tbl.innerHTML=html+'</tbody>';
    // 图表
    msChart=makeChart('ch-missing',{
      type:'bar',
      data:{labels:cols.map(c=>c.column),datasets:[{
        label:'缺失率 (%)',
        data:cols.map(c=>c.ratio),
        backgroundColor:cols.map(c=>c.ratio>0?'rgba(239,68,68,.6)':'rgba(10,132,255,.2)'),
        borderColor:cols.map(c=>c.ratio>0?'#FF453A':'#0A84FF'),borderWidth:1
      }]},
      options:{maintainAspectRatio:false,
        plugins:{legend:{display:false},
          title:{display:true,text:'各列缺失率 (%)',color:'#f8fafc',font:{family:'Inter',size:13,weight:'500'},align:'start',padding:{bottom:14}}},
        scales:{
          x:{grid:{display:false},ticks:{color:'#475569',maxRotation:60,font:{size:9}}},
          y:{grid:{color:'rgba(255,255,255,.02)'},ticks:{color:'#475569'}}
        }
      }
    });
    toast('✓ 统计完成 · 缺失 '+res.total_missing+' 处 / '+missCols.length+' 列');
  }
}

/* ============ CLUSTERING ============ */
let clInit=false,clChart=null;
const CL_COLORS=['#0A84FF','#5E5CE6','#30D158','#FF9F0A','#FF453A','#64D2FF','#BF5AF2','#FF375F'];
function initClustering(){
  if(clInit)return;clInit=true;
  const slider=document.getElementById('cl-slider');
  const val=document.getElementById('cl-slider-val');
  slider.addEventListener('input',()=>{val.textContent=slider.value});
  document.getElementById('cl-run').addEventListener('click',()=>loadClusters(+slider.value));
  async function loadClusters(k){
    toast('▶ 运行 K-Means (k='+k+')...');
    const btn=document.getElementById('cl-run');
    btn.disabled=true;btn.textContent='⏳ 聚类中...';
    showSkeleton('#cl-table','K-Means 聚类中...');
    const res=await api('/api/clustering/kmeans',{
      method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({n_clusters:k})
    });
    btn.disabled=false;btn.textContent='▶ 运行 K-Means';
    if(res.error){showOfflineHint();toast('⚠ '+res.error);return}
    const labels=res.labels||[];
    const x=res.pca_x||[];
    const y=res.pca_y||[];
    const hv=res.hv||[];
    const n=labels.length;
    document.getElementById('cl-k').textContent=k;
    document.getElementById('cl-total').textContent=n;
    // 簇统计
    const clusters={};
    for(let i=0;i<n;i++){
      const lb=labels[i];
      if(!clusters[lb])clusters[lb]={count:0,hvs:[]};
      clusters[lb].count++;
      clusters[lb].hvs.push(hv[i]);
    }
    const clKeys=Object.keys(clusters);
    let maxCl=0,maxN=0;
    clKeys.forEach(k2=>{if(clusters[k2].count>maxN){maxN=clusters[k2].count;maxCl=k2}});
    document.getElementById('cl-max').textContent='簇 '+maxCl;
    document.getElementById('cl-max-n').textContent=maxN+' 样本';
    document.getElementById('cl-pca').textContent='2D';
    // 簇统计表
    const tbl=document.getElementById('cl-table');
    let html='<thead><tr><th>簇</th><th>样本数</th><th>占比</th><th>HV 均值</th><th>HV 范围</th></tr></thead><tbody>';
    clKeys.sort((a,b)=>+a-+b).forEach(lb=>{
      const c=clusters[lb];
      const mean=c.hvs.reduce((a,b)=>a+b,0)/c.hvs.length;
      const min=Math.min(...c.hvs),max=Math.max(...c.hvs);
      html+='<tr><td class="tgt" style="color:'+CL_COLORS[lb]+'">簇 '+lb+'</td><td>'+c.count+'</td><td>'+(c.count/n*100).toFixed(1)+'%</td><td>'+mean.toFixed(1)+'</td><td>'+min.toFixed(0)+'–'+max.toFixed(0)+'</td></tr>';
    });
    tbl.innerHTML=html+'</tbody>';
    // 散点图
    const datasets=clKeys.map(lb=>{
      const data=[];
      for(let i=0;i<n;i++){if(labels[i]===+lb)data.push({x:x[i],y:y[i]})}
      return {label:'簇 '+lb,data:data,backgroundColor:CL_COLORS[lb]+'aa',borderColor:CL_COLORS[lb],pointRadius:4};
    });
    clChart=makeChart('ch-cluster',{
      type:'scatter',
      data:{datasets:datasets},
      options:{maintainAspectRatio:false,
        plugins:{legend:{position:'bottom',labels:{color:'#94a3b8',boxWidth:10}}},
        scales:{
          x:{title:{display:true,text:'PC1',color:'#94a3b8'},grid:{color:'rgba(255,255,255,.02)'},ticks:{color:'#475569'}},
          y:{title:{display:true,text:'PC2',color:'#94a3b8'},grid:{color:'rgba(255,255,255,.02)'},ticks:{color:'#475569'}}
        }
      }
    });
    toast('✓ 聚类完成 · '+k+' 簇 / '+n+' 样本');
  }
  loadClusters(4);
}

/* ============ DDPG 深度强化学习 ============ */
let ddpgInit=false,ddpgLossChart=null,ddpgScatterChart=null,ddpgPollTimer=null,ddpgCurrentTaskId=null;
function initDDPG(){
  if(ddpgInit)return;ddpgInit=true;

  // 开始训练
  document.getElementById('ddpg-start').addEventListener('click',startDDPG);
  // 手动刷新
  document.getElementById('ddpg-refresh').addEventListener('click',()=>{
    if(ddpgCurrentTaskId){pollDDPGStatus();}
    else{toast('没有进行中的任务','warn');}
  });

  async function startDDPG(){
    const body={
      data_source:document.getElementById('ddpg-data-source').value,
      epochs:parseInt(document.getElementById('ddpg-epochs').value),
      batch_size:parseInt(document.getElementById('ddpg-batch').value),
      lr_actor:parseFloat(document.getElementById('ddpg-lr-actor').value),
      lr_critic:parseFloat(document.getElementById('ddpg-lr-critic').value),
      test_size:parseFloat(document.getElementById('ddpg-test-size').value),
    };
    const btn=document.getElementById('ddpg-start');
    btn.disabled=true;btn.textContent='⏳ 启动中...';
    try{
      const res=await api('/api/ddpg/train',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
      if(res.error){toast('启动失败: '+res.error,'error');btn.disabled=false;btn.textContent='▶ 开始训练';return;}
      ddpgCurrentTaskId=res.task_id;
      document.getElementById('ddpg-task-id').textContent='Task: '+res.task_id;
      document.getElementById('ddpg-status').textContent='训练中';
      document.getElementById('ddpg-loss-tag').textContent='训练中';
      document.getElementById('ddpg-loss-tag').className='tag tag-success';
      toast('DDPG 训练已启动（异步）','ok');
      btn.textContent='▶ 训练中...';
      // 开始轮询
      startPolling();
    }catch(e){
      toast('网络错误: '+e.message,'error');
      btn.disabled=false;btn.textContent='▶ 开始训练';
    }
  }

  function startPolling(){
    stopPolling();
    pollDDPGStatus();
    ddpgPollTimer=setInterval(pollDDPGStatus,2000);  // 2秒轮询
  }
  function stopPolling(){
    if(ddpgPollTimer){clearInterval(ddpgPollTimer);ddpgPollTimer=null;}
  }

  async function pollDDPGStatus(){
    if(!ddpgCurrentTaskId)return;
    const res=await api('/api/ddpg/status/'+ddpgCurrentTaskId);
    if(res.error){
      toast('查询失败: '+res.error,'warn');
      stopPolling();return;
    }
    // 更新顶部指标
    document.getElementById('ddpg-status').textContent=
      res.status==='pending'?'排队中':
      res.status==='running'?'训练中':
      res.status==='done'?'完成':
      res.status==='error'?'错误':'未知';
    if(res.device){
      document.getElementById('ddpg-device').textContent=res.device.includes('cuda')?'GPU':'CPU';
    }
    if(res.n_train){
      document.getElementById('ddpg-data-info').textContent=`${res.n_train}/${res.n_val}/${res.n_test} (训/验/测) · ${res.n_features}维`;
    }
    if(res.total_epochs){
      document.getElementById('ddpg-epoch').textContent=`${res.epoch||0} / ${res.total_epochs}`;
      document.getElementById('ddpg-progress').textContent=`${(res.progress||0).toFixed(1)}%`;
    }
    if(res.val_r2!==undefined){
      document.getElementById('ddpg-val-r2').textContent=res.val_r2.toFixed(4);
    }
    if(res.best_val_r2!==undefined){
      document.getElementById('ddpg-best-r2').textContent='最佳 '+res.best_val_r2.toFixed(4);
    }

    // 更新损失曲线
    if(res.losses){
      const cl=res.losses.critic||[];
      const al=res.losses.actor||[];
      const labels=cl.map((_,i)=>i);
      if(!ddpgLossChart){
        ddpgLossChart=makeChart('ch-ddpg-loss',{
          type:'line',
          data:{labels:labels,datasets:[
            {label:'Critic Loss',data:cl,borderColor:'#0A84FF',backgroundColor:'rgba(10,132,255,.1)',borderWidth:1.5,tension:.3,pointRadius:0},
            {label:'Actor Loss',data:al,borderColor:'#FF9F0A',backgroundColor:'rgba(245,158,11,.1)',borderWidth:1.5,tension:.3,pointRadius:0}
          ]},
          options:{maintainAspectRatio:false,animation:{duration:0},
            plugins:{legend:{position:'bottom',labels:{color:'#94a3b8',boxWidth:10}}},
            scales:{
              x:{display:false},
              y:{grid:{color:'rgba(255,255,255,.02)'},ticks:{color:'#475569'}}
            }
          }
        });
      }else{
        ddpgLossChart.data.labels=labels;
        ddpgLossChart.data.datasets[0].data=cl;
        ddpgLossChart.data.datasets[1].data=al;
        ddpgLossChart.update('none');
      }
    }

    // 训练完成
    if(res.status==='done'){
      stopPolling();
      const btn=document.getElementById('ddpg-start');
      btn.disabled=false;btn.textContent='▶ 开始训练';
      document.getElementById('ddpg-loss-tag').textContent='完成';
      document.getElementById('ddpg-loss-tag').className='tag tag-success';
      document.getElementById('ddpg-result-tag').textContent='已完成';
      document.getElementById('ddpg-result-tag').className='tag tag-success';
      // 更新指标表
      if(res.metrics){
        const m=res.metrics;
        const tbl=document.getElementById('ddpg-metrics-table');
        let html='<thead><tr><th>数据集</th><th>R²</th><th>RMSE</th><th>MAE</th></tr></thead><tbody>';
        html+=`<tr><td class="tgt">训练集</td><td>${m.train.r2.toFixed(4)}</td><td>${m.train.rmse.toFixed(2)}</td><td>${m.train.mae.toFixed(2)}</td></tr>`;
        html+=`<tr><td class="tgt">验证集</td><td>${m.val.r2.toFixed(4)}</td><td>${m.val.rmse.toFixed(2)}</td><td>${m.val.mae.toFixed(2)}</td></tr>`;
        html+=`<tr><td class="tgt">测试集</td><td>${m.test.r2.toFixed(4)}</td><td>${m.test.rmse.toFixed(2)}</td><td>${m.test.mae.toFixed(2)}</td></tr>`;
        tbl.innerHTML=html+'</tbody>';
        document.getElementById('ddpg-summary').innerHTML=
          `训练完成 · 共 ${res.epoch} 轮`+(res.early_stopped?' · <span style="color:var(--amber)">早停触发</span>':'')+
          `<br>最佳验证集 R²: <b style="color:var(--ember-hot)">${res.best_val_r2?.toFixed(4)}</b>`+
          `<br>测试集 R²: <b style="color:var(--success)">${m.test.r2.toFixed(4)}</b> · RMSE: ${m.test.rmse.toFixed(2)} HV`;
      }
      // 更新散点图
      if(res.scatter){
        const scatterData=res.scatter.map(p=>({x:p.x,y:p.y}));
        const allVals=res.scatter.flatMap(p=>[p.x,p.y]);
        const minV=Math.min(...allVals),maxV=Math.max(...allVals);
        if(!ddpgScatterChart){
          ddpgScatterChart=makeChart('ch-ddpg-scatter',{
            type:'scatter',
            data:{datasets:[{
              label:'测试集样本',
              data:scatterData,
              backgroundColor:'rgba(10,132,255,.5)',
              borderColor:'#0A84FF',borderWidth:1,pointRadius:4
            }]},
            options:{maintainAspectRatio:false,
              plugins:{legend:{position:'bottom',labels:{color:'#94a3b8',boxWidth:10}},
                tooltip:{callbacks:{label:c=>`真实: ${c.raw.x.toFixed(1)} → 预测: ${c.raw.y.toFixed(1)}`}}},
              scales:{
                x:{title:{display:true,text:'真实 HV',color:'#94a3b8'},grid:{color:'rgba(255,255,255,.02)'},ticks:{color:'#475569'},min:minV,max:maxV},
                y:{title:{display:true,text:'预测 HV',color:'#94a3b8'},grid:{color:'rgba(255,255,255,.02)'},ticks:{color:'#475569'},min:minV,max:maxV}
              }
            }
          });
        }else{
          ddpgScatterChart.data.datasets[0].data=scatterData;
          ddpgScatterChart.options.scales.x.min=minV;
          ddpgScatterChart.options.scales.x.max=maxV;
          ddpgScatterChart.options.scales.y.min=minV;
          ddpgScatterChart.options.scales.y.max=maxV;
          ddpgScatterChart.update('none');
        }
        // 理想线（y=x）：每次都同步更新端点为新的 [minV,minV] 和 [maxV,maxV]
        if(!ddpgScatterChart.data.datasets[1]){
          ddpgScatterChart.data.datasets.push({
            label:'理想 y=x',data:[{x:minV,y:minV},{x:maxV,y:maxV}],
            type:'line',borderColor:'rgba(16,185,129,.5)',borderWidth:1,borderDash:[5,5],pointRadius:0,fill:false
          });
        }else{
          ddpgScatterChart.data.datasets[1].data=[{x:minV,y:minV},{x:maxV,y:maxV}];
        }
        ddpgScatterChart.update('none');
      }
      toast('DDPG 训练完成！测试集 R²='+(res.metrics?.test.r2||0).toFixed(4),'ok');
    }

    // 错误
    if(res.status==='error'){
      stopPolling();
      const btn=document.getElementById('ddpg-start');
      btn.disabled=false;btn.textContent='▶ 开始训练';
      document.getElementById('ddpg-status').textContent='错误';
      document.getElementById('ddpg-loss-tag').textContent='错误';
      document.getElementById('ddpg-loss-tag').className='tag tag-danger';
      toast('训练失败: '+(res.error||'未知错误'),'error');
    }
  }

  // 页面不可见时暂停轮询
  document.addEventListener('visibilitychange',()=>{
    if(document.hidden){stopPolling();}
    else if(ddpgCurrentTaskId){
      /* 仅当任务尚未结束（done/error）时恢复轮询，pending/running 都需继续 */
      const st=document.getElementById('ddpg-status').textContent;
      if(st!=='完成'&&st!=='错误'){startPolling();}
    }
  });
}

/* ============ CODE OPT (类 Windows 任务管理器) ============ */
let coInit=false,coCpuChart=null,coMemChart=null;
function initCodeOpt(){
  if(coInit)return;coInit=true;
  // 独立的历史数据缓冲
  const cpuHist=[],memHist=[],labels=[];
  const MAX_POINTS=120;  // 2 分钟历史
  let autoRefresh=true;
  let monitorTimer=null;
  let recommendLoaded=false;

  // 立即刷新按钮
  document.getElementById('co-refresh').addEventListener('click',()=>{loadSysInfo();loadRecommend();});
  // 暂停/继续自动刷新
  document.getElementById('co-toggle-auto').addEventListener('click',()=>{
    autoRefresh=!autoRefresh;
    const btn=document.getElementById('co-toggle-auto');
    const tag=document.getElementById('co-live-tag');
    if(autoRefresh){
      btn.textContent='⏸ 暂停';
      tag.textContent='● LIVE';tag.className='tag tag-success';
      startMonitor();
    }else{
      btn.textContent='▶ 继续';
      tag.textContent='⏸ PAUSED';tag.className='tag tag-ember';
      stopMonitor();
    }
  });

  function startMonitor(){
    stopMonitor();
    monitorTimer=setInterval(loadSysInfo,1000);
  }
  function stopMonitor(){
    if(monitorTimer){clearInterval(monitorTimer);monitorTimer=null;}
  }

  // 首次加载
  loadSysInfo();
  loadRecommend();
  startMonitor();

  // 渐变填充函数：曲线下方从 50% 透明度渐变到完全透明
  function gradFn(hexColor){
    return function(ctx){
      const chart=ctx.chart;
      const {ctx:c,chartArea}=chart;
      if(!chartArea)return hexColor+'15';  // 首次渲染前 chartArea 不存在
      const g=c.createLinearGradient(0,chartArea.top,0,chartArea.bottom);
      g.addColorStop(0,hexColor+'80');  // 顶部 50% 透明
      g.addColorStop(1,hexColor+'00');  // 底部完全透明
      return g;
    };
  }

  // 构建单个 Task Manager 风格图表
  function buildTmChart(canvasId,dataArr,color){
    return makeChart(canvasId,{
      type:'line',
      data:{labels:labels.slice(),datasets:[{
        data:dataArr.slice(),
        borderColor:color,
        backgroundColor:gradFn(color),
        borderWidth:2,
        tension:0.35,       // 平滑曲线
        pointRadius:0,      // 不显示数据点
        fill:true           // 渐变填充
      }]},
      options:{
        maintainAspectRatio:false,
        animation:{duration:0},  // 无动画，避免滚动时跳动
        plugins:{legend:{display:false},tooltip:{enabled:false}},
        scales:{
          x:{display:false},  // 隐藏时间轴
          y:{
            max:100,min:0,
            grid:{color:'rgba(255,255,255,.04)',drawBorder:false},
            ticks:{
              color:'#475569',
              font:{size:10,family:'IBM Plex Mono'},
              stepSize:25,
              callback:v=>v+'%'
            }
          }
        }
      }
    });
  }

  async function loadSysInfo(){
    const res=await api('/api/system/info');
    if(res.error){return}
    // 顶部指标卡（GPU / PyTorch / 采样间隔 / 数据点）
    if(res.cuda_available){
      document.getElementById('co-gpu').textContent=res.gpu_name||'GPU';
      document.getElementById('co-gpu-mem').textContent=(res.gpu_memory_total||0).toFixed(1)+' GB 显存';
    }else{
      document.getElementById('co-gpu').textContent='CPU 模式';
      document.getElementById('co-gpu-mem').textContent='未检测到 CUDA';
    }
    document.getElementById('co-torch').textContent=res.torch_version||'—';
    document.getElementById('co-cuda').textContent='CUDA '+(res.cuda_available?'可用':'不可用');
    // Task Manager 大字当前值
    document.getElementById('tm-cpu-val').textContent=res.cpu_percent.toFixed(0);
    document.getElementById('tm-cpu-info').textContent=res.cpu_count+' 核心 · '+res.cpu_percent.toFixed(1)+'%';
    document.getElementById('tm-mem-val').textContent=res.mem_percent.toFixed(0);
    document.getElementById('tm-mem-info').textContent=res.mem_used.toFixed(1)+' / '+res.mem_total.toFixed(1)+' GB';
    document.getElementById('co-points').textContent=cpuHist.length+' / '+MAX_POINTS;
    // 追加历史数据
    const now=new Date();
    const tlabel=String(now.getHours()).padStart(2,'0')+':'+String(now.getMinutes()).padStart(2,'0')+':'+String(now.getSeconds()).padStart(2,'0');
    cpuHist.push(res.cpu_percent);
    memHist.push(res.mem_percent);
    labels.push(tlabel);
    if(cpuHist.length>MAX_POINTS){
      cpuHist.shift();memHist.shift();labels.shift();
    }
    // 更新或创建两个独立图表
    if(!coCpuChart){
      coCpuChart=buildTmChart('ch-cpu',cpuHist,'#409CFF');
    }else{
      coCpuChart.data.labels=labels;
      coCpuChart.data.datasets[0].data=cpuHist;
      coCpuChart.update('none');
    }
    if(!coMemChart){
      coMemChart=buildTmChart('ch-mem',memHist,'#818CF8');
    }else{
      coMemChart.data.labels=labels;
      coMemChart.data.datasets[0].data=memHist;
      coMemChart.update('none');
    }
  }

  async function loadRecommend(){
    if(recommendLoaded)return;
    const res=await api('/api/system/recommend');
    if(res.error){return}
    recommendLoaded=true;
    // 推荐表
    const tbl=document.getElementById('co-rec-table');
    let html='<thead><tr><th>参数</th><th>推荐值</th><th>依据</th></tr></thead><tbody>';
    (res.recs||[]).forEach(r=>{html+='<tr><td class="tgt">'+r.p+'</td><td>'+(typeof r.v==='string'?r.v:String(r.v))+'</td><td>'+r.why+'</td></tr>'});
    tbl.innerHTML=html+'</tbody>';
    // 优化建议
    document.getElementById('co-tips').innerHTML=(res.tips||[]).join('<br>');
  }

  // 页面不可见时暂停监控，可见时恢复
  document.addEventListener('visibilitychange',()=>{
    if(document.hidden){stopMonitor();}
    else if(autoRefresh){startMonitor();}
  });
}

/* ============ SIDEBAR TOGGLE ============ */
(function(){
  const toggle=document.getElementById('sidebar-toggle');
  if(!toggle)return;
  toggle.addEventListener('click',()=>{
    const app=document.querySelector('.app');
    app.classList.toggle('collapsed');
    toggle.textContent=app.classList.contains('collapsed')?'\u203A':'\u2039';
    toggle.title=app.classList.contains('collapsed')?'展开侧边栏':'折叠侧边栏';
  });
})();

/* ============ INIT ============ */
/* 启动时根据 hash 恢复页面 —— 刷新后仍停留在原页 */
const initialPage=(location.hash||'').replace('#','');
if(initialPage && document.getElementById('page-'+initialPage)){
  navigate(initialPage);
}else{
  initDashboard();
}
toast('✓ FORGE 系统就绪 · Premium 主题已启用');
