/**
 * @file app.js —— FORGE-HV 前端交互逻辑核心文件
 *
 * 作用：
 *   - FORGE-HV 高温合金维氏硬度（HV）预测平台的全部前端交互逻辑
 *   - 严格对照论文《基于深度确定性策略梯度的合金维氏硬度预测算法》裁剪
 *   - 处理用户交互（导航、滑块、按钮）、调用后端 API、渲染数据图表
 *
 * 页面结构（7 个功能页，按论文章节顺序）：
 *   1. 数据可视化（dashboard）   —— 第 2 章 数据准备与预处理
 *   2. 异常值检测（outliers）    —— 第 2 章 公式(1)(2)(3) 分位数截断
 *   3. 元素相关性（correlation） —— 第 2 章 22 种元素成分关系
 *   4. 数据库管理（database）    —— 数据可视化查询（保留）
 *   5. DDPG 模型训练（ddpg）     —— 第 3-4 章 网络模型设计与训练策略
 *   6. 5.3 硬度预测对比（cmp53） —— 第 5.3 节 原始数据 DDPG vs LR/PR/SVR
 *   7. 5.4 GAN 数据扩充对比（cmp54） —— 第 5.4 节 GAN 增强后 DDPG vs LR/PR/SVR
 *
 * 对比算法（论文 5.1 节，严格 4 种）：
 *   LinearRegression / PolynomialRegression / SVR / DDPG
 * 评估指标（论文 5.2 节，严格 4 个）：
 *   RMSE / MAE / R² / MAPE
 *
 * 依赖：
 *   - 原生 JavaScript（无框架）
 *   - Chart.js（图表库，由 index.html 引入）
 *   - ECharts（交互式散点图，由 index.html 引入）
 *
 * 运行环境：
 *   - 浏览器，由 frontend/index.html 以 <script> 标签引入
 */

/* ============ NAV ============ */
/* 面包屑分类与页面名映射（11 个页面：7 论文页 + 4 系统管理页） */
const crumbCat = {
  dashboard: '数据准备', outliers: '数据准备', correlation: '数据准备', database: '数据准备',
  ddpg: 'DDPG 模型',
  cmp53: '实验对比', cmp54: '实验对比',
  'data-mgr': '系统管理', history: '系统管理', users: '系统管理', settings: '系统管理',
};
const pageNames = {
  dashboard: '数据可视化', outliers: '异常值检测', correlation: '元素相关性', database: '数据库管理',
  ddpg: 'DDPG 训练',
  cmp53: '5.3 硬度预测对比', cmp54: '5.4 GAN 数据扩充对比',
  'data-mgr': '数据管理', history: '历史记录', users: '用户管理', settings: '系统设置',
};

/* 分类标题点击折叠 */
document.querySelectorAll('.nav-cat').forEach(cat => {
  cat.addEventListener('click', () => cat.parentElement.classList.toggle('collapsed'));
});

const navItems = document.querySelectorAll('.nav-item');
/**
 * 路由跳转 —— 统一入口，同步 location.hash
 * 切换激活的导航项与页面容器，更新面包屑，并触发对应页面的 init 函数
 * @param {string} p - 页面标识
 */
function navigate(p) {
  const target = [...navItems].find(n => n.dataset.page === p);
  if (!target) return;
  navItems.forEach(n => n.classList.remove('active'));
  target.classList.add('active');
  document.querySelectorAll('.page').forEach(pg => pg.classList.remove('active'));
  const pageEl = document.getElementById('page-' + p);
  if (pageEl) pageEl.classList.add('active');
  document.getElementById('crumb-cat').textContent = crumbCat[p] || '';
  document.getElementById('crumb-page').textContent = pageNames[p] || target.textContent.trim();
  document.getElementById('content').scrollTop = 0;
  if (p === 'dashboard') initDashboard();
  if (p === 'outliers') initOutliers();
  if (p === 'correlation') initCorrelation();
  if (p === 'database') initDatabase();
  if (p === 'ddpg') initDDPG();
  if (p === 'cmp53') initCmp53();
  if (p === 'cmp54') initCmp54();
  if (p === 'data-mgr') initDataMgr();
  if (p === 'history') initHistory();
  if (p === 'users') initUsers();
  if (p === 'settings') initSettings();
  applyGuestRestrictions(p);
  if (location.hash !== '#' + p) location.hash = p;
}
/**
 * 游客权限拦截 —— 进入页面后禁用写入类按钮
 * 游客可读不可写：训练/导入/上传/检测/异常值处理等按钮全部禁用
 * @param {string} page - 当前页面标识
 */
function applyGuestRestrictions(page) {
  if (!isGuest()) return;
  // 各页面需要禁用的写入按钮 id 列表
  const writeBtns = {
    dashboard: ['upload-btn', 'reset-btn'],
    outliers: ['ol-run'],
    ddpg: ['ddpg-run', 'ddpg-save'],
    cmp53: ['cmp53-run'],
    cmp54: ['cmp54-run'],
    'data-mgr': ['dm-add', 'dm-batch'],
  };
  const ids = writeBtns[page] || [];
  ids.forEach(id => {
    const el = document.getElementById(id);
    if (el) { el.disabled = true; el.title = '游客无权操作，请登录'; }
  });
}
navItems.forEach(it => it.addEventListener('click', () => navigate(it.dataset.page)));
/* hash 变化时自动跳转 —— 支持浏览器前进/后退/刷新保留当前页 */
window.addEventListener('hashchange', () => {
  const p = (location.hash || '').replace('#', '');
  if (p && document.getElementById('page-' + p)) navigate(p);
});

/* ============ TOAST ============ */
/**
 * 弹出 Toast 通知
 * @param {string} msg - 通知内容（支持 HTML）
 * @param {string} [type] - 类型：'warn' | 'error' | 'ok'，决定左边框颜色
 */
function toast(msg, type) {
  const t = document.createElement('div');
  t.className = 'toast';
  t.innerHTML = msg + '<div class="toast-progress"></div>';
  if (type === 'warn') t.style.borderLeftColor = 'var(--amber)';
  else if (type === 'error') t.style.borderLeftColor = 'var(--danger)';
  else if (type === 'ok') t.style.borderLeftColor = 'var(--success)';
  document.getElementById('toasts').appendChild(t);
  setTimeout(() => {
    t.style.opacity = '0';
    t.style.transform = 'translateX(20px)';
    t.style.transition = '.3s ease';
    setTimeout(() => t.remove(), 300);
  }, 2600);
}

/* ============ DATA ============ */
/* 22 种合金元素列名（与后端 config.composition_columns 一致） */
const ELEMENTS = ['Al', 'W', 'Ta', 'Ti', 'Cr', 'Ni', 'Mo', 'Hf', 'C', 'Co', 'B', 'V', 'Si', 'Fe', 'Nb', 'Zr', 'Re', 'Cb', 'Ce', 'Mn', 'S', 'P'];
/* 元素统计模拟值（用于 dashboard 分布图；真实值由后端 /api/data/stats 提供） */
const ELEMENT_STATS = {
  Al: { med: 6.0, q1: 5.2, q3: 6.8, min: 3.5, max: 8.2 },
  W: { med: 5.5, q1: 4.0, q3: 7.0, min: 0, max: 12 },
  Ta: { med: 1.5, q1: 0.5, q3: 3.0, min: 0, max: 6 },
  Ti: { med: 1.0, q1: 0.5, q3: 2.0, min: 0, max: 4.5 },
  Cr: { med: 9.0, q1: 8.0, q3: 10.0, min: 5, max: 15 },
  Ni: { med: 55, q1: 50, q3: 60, min: 40, max: 70 },
  Mo: { med: 1.5, q1: 0.5, q3: 2.5, min: 0, max: 5 },
  Co: { med: 8.0, q1: 5.0, q3: 12.0, min: 0, max: 20 },
  Hf: { med: 0.1, q1: 0, q3: 0.3, min: 0, max: 0.8 },
  C: { med: 0.07, q1: 0.05, q3: 0.1, min: 0.01, max: 0.2 },
};
['B', 'V', 'Si', 'Fe', 'Nb', 'Zr', 'Re', 'Cb', 'Ce', 'Mn', 'S', 'P'].forEach(e => ELEMENT_STATS[e] = { med: 0.1, q1: 0, q3: 0.3, min: 0, max: 1.5 });

Chart.defaults.color = '#64748b';
Chart.defaults.borderColor = 'rgba(15, 23, 42, 0.08)';
Chart.defaults.font.family = 'IBM Plex Mono';
Chart.defaults.font.size = 10;

/* ============ iOS ANIMATION ENGINE ============ */
const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

/**
 * 数字滚动动画：从 0 缓动到 target
 * @param {HTMLElement} el - 显示数字的元素
 * @param {number} target - 目标数值
 * @param {Object} [opts] - 选项：duration/prefix/suffix/decimals
 */
function countUp(el, target, opts = {}) {
  if (prefersReducedMotion || !el) { if (el) el.textContent = target; return; }
  const { duration = 800, prefix = '', suffix = '', decimals = 0 } = opts;
  const start = 0;
  const range = target - start;
  if (range === 0) return;
  const startTime = performance.now();
  function step(now) {
    const elapsed = Math.min((now - startTime) / duration, 1);
    const eased = 1 - Math.pow(1 - elapsed, 3);
    const current = start + range * eased;
    el.textContent = prefix + current.toFixed(decimals) + suffix;
    if (elapsed < 1) requestAnimationFrame(step);
  }
  requestAnimationFrame(step);
}

/* 按钮涟漪效果 */
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

/* ============ API 配置 ============ */
const API_BASE = 'http://127.0.0.1:5000';
let API_ONLINE = false;
const API_TIMEOUT = 30000; // 30s 超时（DDPG 训练可能较慢）

/**
 * 统一 API 调用封装：fetch + AbortController 超时控制
 * @param {string} path - 接口路径
 * @param {Object} [opts] - fetch 配置
 * @returns {Promise<Object>} 后端返回 JSON，失败时为 { error: string }
 */
async function api(path, opts = {}) {
  try {
    const ctrl = new AbortController();
    const timer = setTimeout(() => ctrl.abort(), API_TIMEOUT);
    const headers = { ...(opts.headers || {}) };
    // 自动附加 JWT token（登录接口本身不需要）
    const token = localStorage.getItem('forge_token');
    if (token && !path.startsWith('/api/auth/login')) {
      headers['Authorization'] = 'Bearer ' + token;
    }
    // JSON 请求体自动设置 Content-Type
    if (opts.body && typeof opts.body === 'object' && !(opts.body instanceof FormData)) {
      headers['Content-Type'] = 'application/json';
      opts.body = JSON.stringify(opts.body);
    }
    const r = await fetch(API_BASE + path, { ...opts, headers, signal: ctrl.signal });
    clearTimeout(timer);
    API_ONLINE = true;
    // 401 / 403 跳登录
    if (r.status === 401 || r.status === 403) {
      const data = await r.json().catch(() => ({}));
      // 触发未登录事件，由 auth 模块处理跳转
      window.dispatchEvent(new CustomEvent('auth:unauthorized', { detail: data }));
      return data || { error: '未登录或权限不足' };
    }
    return await r.json();
  } catch (e) {
    API_ONLINE = false;
    return { error: e.name === 'AbortError' ? '请求超时 (>30s)' : '后端未启动' };
  }
}

/** 离线提示 */
function showOfflineHint() {
  if (!API_ONLINE) {
    toast('⚠ 提示：后端未连接 · 显示模拟数据');
    const btns = document.querySelectorAll('button');
    btns.forEach(b => { if (!b.disabled) { b.dataset.offlineLock = '1'; b.disabled = true; } });
    setTimeout(() => {
      btns.forEach(b => { if (b.dataset.offlineLock) { b.dataset.offlineLock = ''; b.disabled = false; } });
    }, 1500);
  }
}

/** 骨架屏 */
function showSkeleton(selector, text) {
  const el = document.querySelector(selector);
  if (!el) return;
  el.innerHTML = '<div class="skeleton-box"><div class="skeleton" style="height:14px;width:' + (60 + Math.random() * 30) + '%;margin-bottom:10px"></div><div class="skeleton" style="height:14px;width:' + (50 + Math.random() * 30) + '%;margin-bottom:10px"></div><div class="skeleton" style="height:14px;width:' + (70 + Math.random() * 20) + '%"></div><div style="text-align:center;color:var(--text-faint);font-size:11px;margin-top:14px;font-family:var(--mono)">' + (text || '加载中...') + '</div></div>';
}
function hideSkeleton(selector) {
  const el = document.querySelector(selector);
  if (el) { const sk = el.querySelector('.skeleton-box'); if (sk) sk.remove(); }
}

/* ============ CHART 工具 ============ */
/* 全局图表实例注册表 —— 统一销毁管理，防止内存泄漏 */
const CHARTS = {};
/**
 * 创建或重建 Chart.js 图表实例
 * @param {string} canvasId - canvas 元素 id
 * @param {Object} config - Chart.js 配置对象
 * @returns {Chart|null}
 */
function makeChart(canvasId, config) {
  if (CHARTS[canvasId]) { try { CHARTS[canvasId].destroy(); } catch (e) { } }
  const el = document.getElementById(canvasId);
  if (!el) return null;
  CHARTS[canvasId] = new Chart(el, config);
  return CHARTS[canvasId];
}

/* ============ DASHBOARD ============ */
/* 数据可视化首页：元素分布、HV 直方图、数据导入 */
let dashInit = false;
let distChart = null, histChart = null;

/**
 * 渲染元素含量分布图（boxplot / violin / histogram）
 * @param {string} type - 'boxplot' | 'violin' | 'histogram'
 */
function renderDistChart(type) {
  const titles = { boxplot: '元素含量四分位分布 (wt %)', violin: '元素含量小提琴分布 (wt %)', histogram: '元素含量中位数对比 (wt %)' };

  if (type === 'boxplot') {
    distChart = makeChart('ch-dist', {
      type: 'bar',
      data: { labels: ELEMENTS, datasets: [{ label: 'Q1–Q3', data: ELEMENTS.map(e => [ELEMENT_STATS[e].q1, ELEMENT_STATS[e].q3]), backgroundColor: 'rgba(10, 132, 255, .35)', borderColor: '#0A84FF', borderWidth: 1, barPercentage: .7 }] },
      options: { indexAxis: 'y', maintainAspectRatio: false, plugins: { legend: { display: false }, title: { display: true, text: titles[type], color: '#1e293b', font: { family: 'Inter', size: 13, weight: '500' }, align: 'start', padding: { bottom: 14 } } }, scales: { x: { grid: { color: 'rgba(15, 23, 42, .04)' }, ticks: { color: '#64748b' } }, y: { grid: { display: false }, ticks: { color: '#475569', font: { size: 10 }, autoSkip: false } } } }
    });
  } else if (type === 'violin') {
    const scatterData = [];
    ELEMENTS.forEach((e, idx) => { const s = ELEMENT_STATS[e]; for (let k = 0; k < 12; k++) { const v = s.med + (Math.random() - .5) * (s.q3 - s.q1) * 1.8; scatterData.push({ x: Math.max(0, v), y: idx }); } });
    const medians = ELEMENTS.map(e => ELEMENT_STATS[e].med);
    distChart = makeChart('ch-dist', {
      data: { labels: ELEMENTS, datasets: [
        { type: 'bar', label: 'Q1–Q3', data: ELEMENTS.map(e => [ELEMENT_STATS[e].q1, ELEMENT_STATS[e].q3]), backgroundColor: 'rgba(10, 132, 255, .15)', borderColor: 'rgba(10, 132, 255, .4)', borderWidth: 1, barPercentage: .5 },
        { type: 'scatter', label: '样本点', data: scatterData, backgroundColor: 'rgba(64, 156, 255, .7)', borderColor: '#409CFF', pointRadius: 2.5 },
        { type: 'line', label: '中位数', data: medians.map((m, i) => ({ x: m, y: i })), borderColor: '#0A84FF', borderWidth: 2, pointRadius: 4, pointBackgroundColor: '#0A84FF', showLine: false }
      ] },
      options: { indexAxis: 'y', maintainAspectRatio: false, plugins: { legend: { display: false }, title: { display: true, text: titles[type], color: '#1e293b', font: { family: 'Inter', size: 13, weight: '500' }, align: 'start', padding: { bottom: 14 } } }, scales: { x: { grid: { color: 'rgba(15, 23, 42, .04)' }, ticks: { color: '#64748b' } }, y: { grid: { display: false }, ticks: { color: '#475569', font: { size: 10 }, autoSkip: false } } } }
    });
  } else if (type === 'histogram') {
    distChart = makeChart('ch-dist', {
      type: 'bar',
      data: { labels: ELEMENTS, datasets: [{ label: '中位数', data: ELEMENTS.map(e => ELEMENT_STATS[e].med), backgroundColor: 'rgba(10, 132, 255, .5)', borderColor: '#0A84FF', borderWidth: 1, barPercentage: .6 }] },
      options: { indexAxis: 'y', maintainAspectRatio: false, plugins: { legend: { display: false }, title: { display: true, text: titles[type], color: '#1e293b', font: { family: 'Inter', size: 13, weight: '500' }, align: 'start', padding: { bottom: 14 } }, tooltip: { callbacks: { label: c => '中位数: ' + c.raw.y.toFixed(3) + ' wt %' } } }, scales: { x: { grid: { color: 'rgba(15, 23, 42, .04)' }, ticks: { color: '#64748b' } }, y: { grid: { display: false }, ticks: { color: '#475569', font: { size: 10 }, autoSkip: false } } } }
    });
  }
}

/**
 * Dashboard 首页初始化（仅执行一次）
 * 渲染分布图、HV 直方图，绑定数据导入按钮
 */
function initDashboard() {
  if (dashInit) return; dashInit = true;

  renderDistChart('boxplot');
  /* 分布图 chip 切换 */
  document.querySelectorAll('#dist-chips .chip').forEach(c => {
    c.addEventListener('click', () => {
      document.querySelectorAll('#dist-chips .chip').forEach(x => x.classList.remove('on'));
      c.classList.add('on');
      renderDistChart(c.dataset.type);
    });
  });

  /* HV 分布直方图（模拟数据，真实数据由后端 /api/data/stats 提供） */
  const hvBins = [], hvCounts = [];
  for (let i = 160; i <= 500; i += 20) { hvBins.push(i + '–' + (i + 20)); hvCounts.push(Math.round(8 + 12 * Math.exp(-Math.pow((i - 330) / 70, 2)) + Math.random() * 4)); }
  histChart = makeChart('ch-hist', {
    type: 'bar',
    data: { labels: hvBins, datasets: [{ data: hvCounts, backgroundColor: hvCounts.map((_, i) => i > 7 && i < 13 ? '#0A84FF' : 'rgba(10, 132, 255, .3)'), borderColor: '#0A84FF', borderWidth: 1 }] },
    options: { maintainAspectRatio: false, plugins: { legend: { display: false }, title: { display: true, text: '维氏硬度 HV 分布', color: '#1e293b', font: { family: 'Inter', size: 13, weight: '500' }, align: 'start', padding: { bottom: 14 } } }, scales: { x: { grid: { display: false }, ticks: { color: '#64748b', maxRotation: 60 } }, y: { grid: { color: 'rgba(15, 23, 42, .04)' }, ticks: { color: '#64748b' } } } }
  });

  /* 拉取真实数据统计，更新指标卡 */
  api('/api/data/stats').then(res => {
    if (res.error) { showOfflineHint(); return; }
    /* 若返回上传状态，更新上传标签 */
    if (res.using_uploaded) {
      const tag = document.getElementById('upload-status');
      if (tag) { tag.textContent = '使用上传数据'; tag.className = 'tag tag-success'; }
    }
  });

  /* ===== 数据导入逻辑（对应论文 2 章数据来源说明） ===== */
  const uploadBtn = document.getElementById('upload-btn');
  const resetBtn = document.getElementById('reset-btn');
  const uploadFile = document.getElementById('upload-file');
  const uploadStatus = document.getElementById('upload-status');
  const uploadInfo = document.getElementById('upload-info');

  /* 点击"导入数据文件"按钮 → 触发隐藏的 file input */
  if (uploadBtn) {
    uploadBtn.addEventListener('click', () => uploadFile && uploadFile.click());
  }
  /* 文件选择后 → FormData 上传到后端 /api/data/upload */
  if (uploadFile) {
    uploadFile.addEventListener('change', async () => {
      const file = uploadFile.files[0];
      if (!file) return;
      uploadBtn.disabled = true;
      uploadBtn.textContent = '⏳ 上传中...';
      uploadStatus.textContent = '上传中...';
      uploadStatus.className = 'tag tag-ember';
      try {
        const fd = new FormData();
        fd.append('file', file);
        const r = await fetch(API_BASE + '/api/data/upload', { method: 'POST', body: fd });
        const res = await r.json();
        uploadBtn.disabled = false;
        uploadBtn.textContent = '↑ 导入数据文件';
        if (res.error) {
          toast('⚠ 上传失败：' + res.error, 'error');
          uploadStatus.textContent = '上传失败';
          uploadStatus.className = 'tag tag-danger';
          return;
        }
        API_ONLINE = true;
        uploadStatus.textContent = '使用上传数据';
        uploadStatus.className = 'tag tag-success';
        uploadInfo.textContent = '当前：' + res.filename + ' · ' + res.n_rows + ' 行 × ' + res.n_cols + ' 列';
        toast('✓ 数据导入成功：' + res.filename + '（' + res.n_rows + ' 行）', 'ok');
      } catch (e) {
        uploadBtn.disabled = false;
        uploadBtn.textContent = '↑ 导入数据文件';
        API_ONLINE = false;
        toast('⚠ 上传失败：后端未启动', 'error');
        uploadStatus.textContent = '上传失败';
        uploadStatus.className = 'tag tag-danger';
      }
      /* 清空 input 以便重复选择同一文件 */
      uploadFile.value = '';
    });
  }
  /* 恢复默认数据 */
  if (resetBtn) {
    resetBtn.addEventListener('click', async () => {
      resetBtn.disabled = true;
      const res = await api('/api/data/reset', { method: 'POST' });
      resetBtn.disabled = false;
      if (res.error) { showOfflineHint(); toast('⚠ 重置失败：' + res.error, 'error'); return; }
      uploadStatus.textContent = '使用默认数据';
      uploadStatus.className = 'tag tag-ember';
      uploadInfo.textContent = '默认：data/data_with_microstructure.xlsx（149 条实测）';
      toast('✓ 已恢复默认数据', 'ok');
    });
  }
}

/* ============ OUTLIERS ============ */
/* 异常值检测页：分位数截断（论文 2 章）/ IsolationForest / IQR / Z-score */
let olInit = false, olChart = null;
/**
 * 异常值检测页初始化（仅一次）
 * 绑定方法切换、分位滑块、contamination 滑块与运行按钮
 */
function initOutliers() {
  if (olInit) return; olInit = true;

  /* contamination 滑块（仅 IsolationForest 用） */
  const contSlider = document.getElementById('ol-cont-slider');
  const contVal = document.getElementById('ol-cont-val');
  if (contSlider) {
    contSlider.addEventListener('input', () => {
      contVal.textContent = '0.' + contSlider.value.padStart(2, '0');
    });
  }
  /* 分位数截断：下/上分位滑块（论文 2 章公式 1-3） */
  const lowSlider = document.getElementById('ol-low-slider');
  const lowVal = document.getElementById('ol-low-val');
  const highSlider = document.getElementById('ol-high-slider');
  const highVal = document.getElementById('ol-high-val');
  if (lowSlider) {
    lowSlider.addEventListener('input', () => {
      lowVal.textContent = (lowSlider.value / 100).toFixed(2);
    });
  }
  if (highSlider) {
    highSlider.addEventListener('input', () => {
      highVal.textContent = (highSlider.value / 100).toFixed(2);
    });
  }

  /* 方法切换时显示/隐藏对应控件 */
  const methodSel = document.getElementById('ol-method-sel');
  function updateMethodUI() {
    const m = methodSel.value;
    const showQuantile = (m === 'quantile_clip');
    const showCont = (m === 'isolation_forest');
    /* 分位滑块行 */
    const lowRow = lowSlider ? lowSlider.closest('div').parentElement : null;
    /* 显示/隐藏由 select 切换：简化处理，控件始终可见但 placeholder 不同 */
  }
  if (methodSel) {
    methodSel.addEventListener('change', updateMethodUI);
    updateMethodUI();
  }

  /* 运行检测 */
  document.getElementById('ol-run').addEventListener('click', async () => {
    const method = methodSel.value;
    const cont = parseFloat(contVal.textContent);
    const lowQ = lowSlider ? parseFloat(lowVal.textContent) : 0.01;
    const highQ = highSlider ? parseFloat(highVal.textContent) : 0.99;
    const btn = document.getElementById('ol-run');
    btn.disabled = true; btn.textContent = '⏳ 检测中...';
    toast('▶ 正在执行异常值检测 (' + method + ') ...');
    showSkeleton('#ol-table', '运行 ' + method + ' 中...');
    document.getElementById('ol-status').textContent = '检测中';

    const payload = { method, contamination: cont };
    /* 分位数截断传上下分位 */
    if (method === 'quantile_clip') {
      payload.low_quantile = lowQ;
      payload.high_quantile = highQ;
    }
    const res = await api('/api/outliers/detect', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    btn.disabled = false; btn.textContent = '▶ 运行异常值检测';
    if (res.error) { showOfflineHint(); toast('⚠ ' + res.error, 'error'); document.getElementById('ol-status').textContent = '错误'; return; }

    /* 更新指标卡 */
    document.getElementById('ol-total').textContent = res.total;
    document.getElementById('ol-n').textContent = res.n_outliers;
    document.getElementById('ol-ratio').textContent = '占比 ' + (res.n_outliers / res.total * 100).toFixed(1) + '%';
    const methodLabel = { quantile_clip: '分位数截断', isolation_forest: 'IsolationForest', iqr: 'IQR', zscore: 'Z-score' }[method] || method;
    document.getElementById('ol-method').textContent = methodLabel;
    document.getElementById('ol-status').textContent = '完成';
    document.getElementById('ol-status').className = 'metric-val good';
    document.getElementById('ol-count-tag').textContent = res.n_outliers + ' 条';

    /* 异常样本表 */
    const tbl = document.getElementById('ol-table');
    let html = '<thead><tr><th>#</th><th>样本索引</th><th>详情</th></tr></thead><tbody>';
    (res.outliers || []).forEach((o, i) => {
      const det = Object.entries(o.values || {}).slice(0, 6).map(([k, v]) => k + '=' + (+v).toFixed(2)).join(' · ');
      html += '<tr><td class="idx">' + (i + 1) + '</td><td class="tgt">' + o.index + '</td><td>' + det + '</td></tr>';
    });
    if (!res.outliers || !res.outliers.length) html += '<tr><td colspan="3" style="text-align:center;color:var(--text-faint);padding:24px">✓ 未检测到异常样本</td></tr>';
    tbl.innerHTML = html + '</tbody>';

    /* 正常 vs 异常 柱状图 */
    olChart = makeChart('ch-outliers', {
      type: 'bar',
      data: { labels: ['正常样本', '异常样本'], datasets: [{ data: [res.total - res.n_outliers, res.n_outliers], backgroundColor: ['rgba(10,132,255,.4)', 'rgba(239,68,68,.7)'], borderColor: ['#0A84FF', '#FF453A'], borderWidth: 1, barPercentage: .5 }] },
      options: { maintainAspectRatio: false, plugins: { legend: { display: false }, title: { display: true, text: '异常 vs 正常样本数', color: '#1e293b', font: { family: 'Inter', size: 13, weight: '500' }, align: 'start', padding: { bottom: 14 } } }, scales: { x: { grid: { display: false }, ticks: { color: '#475569' } }, y: { grid: { color: 'rgba(15, 23, 42, .04)' }, ticks: { color: '#64748b' } } } }
    });
    toast('✓ 检测完成 · 异常 ' + res.n_outliers + ' 条', 'ok');
  });
}

/* ============ CORRELATION PAGE ============ */
/* 元素相关性页（原"特征相关性"改名）：气泡矩阵 + 高耦合对表格 */
let corrPageInit = false, corrPageChart = null;
/**
 * 元素相关性页初始化（仅一次）：绑定方法 chip，默认加载 pearson
 */
function initCorrelation() {
  if (corrPageInit) return; corrPageInit = true;
  const methodChips = document.querySelectorAll('#corr-method-chips .chip');
  methodChips.forEach(c => {
    c.addEventListener('click', () => {
      methodChips.forEach(x => x.classList.remove('on'));
      c.classList.add('on');
      loadCorr(c.dataset.method);
    });
  });
  /**
   * 拉取并渲染相关性矩阵与高耦合对
   * @param {string} method - 'pearson' | 'spearman' | 'kendall'
   */
  async function loadCorr(method) {
    toast('▶ 加载 ' + method + ' 元素相关性矩阵...');
    showSkeleton('#corr-pairs-table', '计算 ' + method + ' 矩阵中...');
    const res = await api('/api/correlation/matrix?method=' + method);
    if (res.error) { showOfflineHint(); toast('⚠ ' + res.error, 'error'); return; }
    const cols = res.columns || [];
    const matrix = res.matrix || [];
    const N = cols.length;
    const dataset = [];
    for (let i = 0; i < N; i++) for (let j = 0; j < N; j++) {
      const v = matrix[i][j];
      dataset.push({ x: j, y: N - 1 - i, r: Math.abs(v) * 9, v: v });
    }
    corrPageChart = makeChart('ch-corr-page', {
      type: 'bubble',
      data: { datasets: [{ data: dataset, backgroundColor: dataset.map(d => d.v > 0 ? 'rgba(10, 132, 255,' + (Math.abs(d.v) * .8) + ')' : 'rgba(94, 92, 230,' + (Math.abs(d.v) * .8) + ')'), borderColor: dataset.map(d => d.v > 0 ? '#0A84FF' : '#5E5CE6') }] },
      options: { maintainAspectRatio: false, plugins: { legend: { display: false }, title: { display: true, text: '元素相关性矩阵（蓝=正相关 · 紫=负相关 · 气泡大小=|r|）', color: '#1e293b', font: { family: 'Inter', size: 13, weight: '500' }, align: 'start', padding: { bottom: 14 } }, tooltip: { callbacks: { label: c => cols[c.raw.x] + ' ↔ ' + cols[N - 1 - c.raw.y] + ' : ' + c.raw.v.toFixed(3) } } }, scales: { x: { ticks: { color: '#475569', stepSize: 1, callback: v => cols[v] || '' }, grid: { color: 'rgba(15, 23, 42, .04)' } }, y: { ticks: { color: '#475569', stepSize: 1, callback: v => cols[N - 1 - v] || '' }, grid: { color: 'rgba(15, 23, 42, .04)' } } } }
    });
    /* 高耦合对表格 */
    const pairs = res.high_pairs || [];
    document.getElementById('corr-pairs-tag').textContent = pairs.length + ' 对';
    const tbl = document.getElementById('corr-pairs-table');
    let html = '<thead><tr><th>#</th><th>元素 A</th><th>元素 B</th><th>相关系数 r</th><th>强度</th></tr></thead><tbody>';
    pairs.forEach((p, i) => {
      const strength = Math.abs(p.r) >= 0.9 ? '极强' : Math.abs(p.r) >= 0.8 ? '强' : '中';
      html += '<tr><td class="idx">' + (i + 1) + '</td><td class="tgt">' + p.a + '</td><td class="tgt">' + p.b + '</td><td>' + (p.r > 0 ? '+' : '') + p.r.toFixed(3) + '</td><td><span class="tag tag-ember">' + strength + '</span></td></tr>';
    });
    if (!pairs.length) html += '<tr><td colspan="5" style="text-align:center;color:var(--text-faint);padding:24px">✓ 无 |r|≥0.7 的高耦合对</td></tr>';
    tbl.innerHTML = html + '</tbody>';
    toast('✓ ' + method + ' 矩阵已加载 · 高耦合 ' + pairs.length + ' 对', 'ok');
  }
  loadCorr('pearson');
}

/* ============ DATABASE ============ */
/* 数据库管理页：表结构展示 + 可视化查询（选列/筛选/排序/聚合） + 预设 */
let dbInit = false, dbSchema = null;
/**
 * 数据库管理页初始化（仅一次）
 */
function initDatabase() {
  if (dbInit) return; dbInit = true;
  dbSchema = null;
  /* 拉表结构 */
  api('/api/database/schema').then(res => {
    if (res.error) { showOfflineHint(); return; }
    dbSchema = res;
    document.getElementById('db-rows').textContent = res.n_rows;
    document.getElementById('db-cols').textContent = (res.columns || []).length;
    const allCols = (res.columns || []).map(c => c.name);
    const numCols = (res.columns || []).filter(c => c.type === 'number').map(c => c.name);
    function fillSel(id, cols, placeholder) {
      const sel = document.getElementById(id);
      if (placeholder) sel.innerHTML = '<option value="">' + placeholder + '</option>';
      else sel.innerHTML = '';
      cols.forEach(c => { const o = document.createElement('option'); o.value = c; o.textContent = c; sel.appendChild(o); });
    }
    fillSel('db-cols-sel', allCols);
    fillSel('db-order-col', allCols, '不排序');
    fillSel('db-agg-col', numCols, '（COUNT 时留空）');
    fillSel('db-agg-group', allCols);
  });

  /* 查询模式切换 */
  document.querySelectorAll('#db-mode .chip').forEach(c => {
    c.addEventListener('click', () => {
      document.querySelectorAll('#db-mode .chip').forEach(x => x.classList.remove('on'));
      c.classList.add('on');
      const mode = c.dataset.mode;
      document.getElementById('db-panel-select').style.display = mode === 'select' ? 'block' : 'none';
      document.getElementById('db-panel-aggregate').style.display = mode === 'aggregate' ? 'block' : 'none';
    });
  });

  /* 筛选条件行 */
  function addFilterRow(col = '', op = '>', val = '') {
    if (!dbSchema) return;
    const allCols = dbSchema.columns.map(c => c.name);
    const row = document.createElement('div');
    row.style.cssText = 'display:flex;gap:6px;margin-bottom:6px;align-items:center';
    const colSel = document.createElement('select'); colSel.className = 'input'; colSel.style.flex = '2';
    colSel.innerHTML = allCols.map(c => '<option value="' + c + '"' + (c === col ? ' selected' : '') + '>' + c + '</option>').join('');
    const opSel = document.createElement('select'); opSel.className = 'input'; opSel.style.flex = '1';
    ['>', '<', '>=', '<=', '=', '!=', 'between', 'contains'].forEach(o => { const op = document.createElement('option'); op.value = o; op.textContent = o; opSel.appendChild(op); });
    opSel.value = op;
    const valInp = document.createElement('input'); valInp.className = 'input'; valInp.style.flex = '2';
    valInp.placeholder = '数值（between 用 a,b）'; valInp.value = val;
    const delBtn = document.createElement('button'); delBtn.className = 'btn btn-ghost'; delBtn.textContent = '×';
    delBtn.style.cssText = 'flex:0 0 auto;padding:4px 10px';
    delBtn.onclick = () => row.remove();
    row.appendChild(colSel); row.appendChild(opSel); row.appendChild(valInp); row.appendChild(delBtn);
    document.getElementById('db-filters').appendChild(row);
  }
  document.getElementById('db-add-filter').addEventListener('click', () => {
    if (!dbSchema) { toast('请先等待数据列加载', 'warn'); return; }
    addFilterRow();
  });

  /* 预设查询 */
  const PRESETS = {
    top10: { mode: 'select', limit: 10 },
    hard: { mode: 'select', filters: [{ col: 'Vickers Hardness (HV)', op: '>', val: '400' }], limit: 100 },
    eleavg: { mode: 'aggregate', agg: { func: 'avg', col: 'Al', group_by: [] }, limit: 50 },
    count: { mode: 'aggregate', agg: { func: 'count', col: '', group_by: [] }, limit: 10 },
    sorted_hv: { mode: 'select', order_by: { col: 'Vickers Hardness (HV)', desc: true }, limit: 20 },
    ni_range: { mode: 'select', filters: [{ col: 'Ni', op: 'between', val: '5,10' }], limit: 50 },
  };
  document.querySelectorAll('#db-quick .chip').forEach(c => {
    c.addEventListener('click', () => applyPreset(c.dataset.preset));
  });
  function applyPreset(name) {
    const p = PRESETS[name]; if (!p) return;
    document.querySelectorAll('#db-mode .chip').forEach(x => x.classList.toggle('on', x.dataset.mode === p.mode));
    document.getElementById('db-panel-select').style.display = p.mode === 'select' ? 'block' : 'none';
    document.getElementById('db-panel-aggregate').style.display = p.mode === 'aggregate' ? 'block' : 'none';
    document.getElementById('db-filters').innerHTML = '';
    if (p.filters) { p.filters.forEach(f => addFilterRow(f.col, f.op, f.val)); }
    if (p.order_by) { document.getElementById('db-order-col').value = p.order_by.col; document.getElementById('db-order-dir').value = p.order_by.desc ? 'desc' : 'asc'; }
    if (p.agg) { document.getElementById('db-agg-func').value = p.agg.func; if (p.agg.col) document.getElementById('db-agg-col').value = p.agg.col; }
    document.getElementById('db-limit').value = p.limit;
    document.getElementById('db-limit-val').textContent = p.limit;
    runQuery();
  }

  /* limit 滑块 */
  document.getElementById('db-limit').addEventListener('input', e => {
    document.getElementById('db-limit-val').textContent = e.target.value;
  });

  document.getElementById('db-run').addEventListener('click', runQuery);
  /**
   * 执行查询：构造 payload 调用后端 /api/database/query，渲染结果表
   */
  async function runQuery() {
    const btn = document.getElementById('db-run');
    const mode = [...document.querySelectorAll('#db-mode .chip.on')].map(x => x.dataset.mode)[0] || 'select';
    const limit = parseInt(document.getElementById('db-limit').value) || 100;
    const payload = { limit };
    if (mode === 'select') {
      const cols = [...document.querySelectorAll('#db-cols-sel option:checked')].map(o => o.value);
      if (cols.length) payload.columns = cols;
      const filters = [];
      document.querySelectorAll('#db-filters > div').forEach(row => {
        const col = row.querySelector('select').value;
        const op = row.querySelectorAll('select')[1].value;
        const val = row.querySelector('input').value;
        if (col && op && val) filters.push({ col, op, val });
      });
      if (filters.length) payload.filters = filters;
      const obCol = document.getElementById('db-order-col').value;
      const obDir = document.getElementById('db-order-dir').value;
      if (obCol) payload.order_by = { col: obCol, desc: obDir === 'desc' };
    } else {
      const func = document.getElementById('db-agg-func').value;
      const col = document.getElementById('db-agg-col').value;
      const group = [...document.querySelectorAll('#db-agg-group option:checked')].map(o => o.value);
      payload.aggregate = { func, col, group_by: group };
    }
    btn.disabled = true; btn.textContent = '⏳ 执行中...';
    document.getElementById('db-status').textContent = '执行中';
    const res = await api('/api/database/query', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    btn.disabled = false; btn.textContent = '▶ 执行查询';
    if (res.error) { showOfflineHint(); toast('⚠ ' + res.error, 'error'); document.getElementById('db-status').textContent = '错误'; return; }
    document.getElementById('db-status').textContent = '完成';
    document.getElementById('db-result-tag').textContent = res.n + ' 行';
    const tbl = document.getElementById('db-table');
    const cols = res.columns || [];
    let html = '<thead><tr><th>#</th>';
    cols.forEach(c => html += '<th>' + c + '</th>');
    html += '</tr></thead><tbody>';
    (res.rows || []).forEach((row, i) => {
      html += '<tr><td class="idx">' + (i + 1) + '</td>';
      row.forEach(v => {
        const num = typeof v === 'number';
        html += '<td' + (num ? ' style="text-align:right"' : '') + '>' + (num ? (Math.abs(v) < 1 ? v.toFixed(4) : v.toFixed(2)) : (v ?? '')) + '</td>';
      });
      html += '</tr>';
    });
    if (!res.rows || !res.rows.length) html += '<tr><td colspan="' + (cols.length + 1) + '" style="text-align:center;color:var(--text-faint);padding:24px">查询返回 0 行</td></tr>';
    tbl.innerHTML = html + '</tbody>';
    toast('✓ 查询完成 · 返回 ' + res.n + ' 行', 'ok');
  }
}

/* ============ DDPG 深度强化学习 ============ */
/* DDPG 页：异步训练 + 轮询状态，实时更新损失曲线与测试集散点图 */
let ddpgInit = false, ddpgLossChart = null, ddpgScatterChart = null, ddpgPollTimer = null, ddpgCurrentTaskId = null;
/**
 * DDPG 页初始化（仅一次）：绑定开始/刷新按钮，注册 visibilitychange 暂停轮询
 */
function initDDPG() {
  if (ddpgInit) return; ddpgInit = true;

  document.getElementById('ddpg-start').addEventListener('click', startDDPG);
  document.getElementById('ddpg-refresh').addEventListener('click', () => {
    if (ddpgCurrentTaskId) { pollDDPGStatus(); }
    else { toast('没有进行中的任务', 'warn'); }
  });

  /**
   * 启动 DDPG 异步训练：POST 参数到后端，拿到 task_id 后开始轮询
   */
  async function startDDPG() {
    const body = {
      data_source: document.getElementById('ddpg-data-source').value,
      epochs: parseInt(document.getElementById('ddpg-epochs').value),
      batch_size: parseInt(document.getElementById('ddpg-batch').value),
      lr_actor: parseFloat(document.getElementById('ddpg-lr-actor').value),
      lr_critic: parseFloat(document.getElementById('ddpg-lr-critic').value),
      test_size: parseFloat(document.getElementById('ddpg-test-size').value),
    };
    const btn = document.getElementById('ddpg-start');
    btn.disabled = true; btn.textContent = '⏳ 启动中...';
    try {
      const res = await api('/api/ddpg/train', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
      if (res.error) { toast('启动失败: ' + res.error, 'error'); btn.disabled = false; btn.textContent = '▶ 开始训练'; return; }
      ddpgCurrentTaskId = res.task_id;
      document.getElementById('ddpg-task-id').textContent = 'Task: ' + res.task_id;
      document.getElementById('ddpg-status').textContent = '训练中';
      document.getElementById('ddpg-loss-tag').textContent = '训练中';
      document.getElementById('ddpg-loss-tag').className = 'tag tag-success';
      toast('DDPG 训练已启动（异步）', 'ok');
      btn.textContent = '▶ 训练中...';
      startPolling();
    } catch (e) {
      toast('网络错误: ' + e.message, 'error');
      btn.disabled = false; btn.textContent = '▶ 开始训练';
    }
  }

  function startPolling() {
    stopPolling();
    pollDDPGStatus();
    ddpgPollTimer = setInterval(pollDDPGStatus, 2000);
  }
  function stopPolling() {
    if (ddpgPollTimer) { clearInterval(ddpgPollTimer); ddpgPollTimer = null; }
  }

  /**
   * 拉取训练状态并更新 UI：状态标签 / 设备 / 进度 / 损失曲线 / 完成或错误处理
   * 指标表含 MAPE 列（论文 5.2 节四维指标）
   */
  async function pollDDPGStatus() {
    if (!ddpgCurrentTaskId) return;
    const res = await api('/api/ddpg/status/' + ddpgCurrentTaskId);
    if (res.error) { toast('查询失败: ' + res.error, 'warn'); stopPolling(); return; }
    /* 顶部指标 */
    document.getElementById('ddpg-status').textContent =
      res.status === 'pending' ? '排队中' :
      res.status === 'running' ? '训练中' :
      res.status === 'done' ? '完成' :
      res.status === 'error' ? '错误' : '未知';
    if (res.device) { document.getElementById('ddpg-device').textContent = res.device.includes('cuda') ? 'GPU' : 'CPU'; }
    if (res.n_train) { document.getElementById('ddpg-data-info').textContent = res.n_train + '/' + res.n_val + '/' + res.n_test + ' (训/验/测) · ' + res.n_features + '维'; }
    if (res.total_epochs) {
      document.getElementById('ddpg-epoch').textContent = (res.epoch || 0) + ' / ' + res.total_epochs;
      document.getElementById('ddpg-progress').textContent = (res.progress || 0).toFixed(1) + '%';
    }
    if (res.val_r2 !== undefined) { document.getElementById('ddpg-val-r2').textContent = res.val_r2.toFixed(4); }
    if (res.best_val_r2 !== undefined) { document.getElementById('ddpg-best-r2').textContent = '最佳 ' + res.best_val_r2.toFixed(4); }

    /* 损失曲线 */
    if (res.losses) {
      const cl = res.losses.critic || [];
      const al = res.losses.actor || [];
      const labels = cl.map((_, i) => i);
      if (!ddpgLossChart) {
        ddpgLossChart = makeChart('ch-ddpg-loss', {
          type: 'line',
          data: { labels: labels, datasets: [
            { label: 'Critic Loss', data: cl, borderColor: '#0A84FF', backgroundColor: 'rgba(10,132,255,.1)', borderWidth: 1.5, tension: .3, pointRadius: 0 },
            { label: 'Actor Loss', data: al, borderColor: '#FF9F0A', backgroundColor: 'rgba(245,158,11,.1)', borderWidth: 1.5, tension: .3, pointRadius: 0 }
          ] },
          options: { maintainAspectRatio: false, animation: { duration: 0 }, plugins: { legend: { position: 'bottom', labels: { color: '#475569', boxWidth: 10 } } }, scales: { x: { display: false }, y: { grid: { color: 'rgba(15, 23, 42, .04)' }, ticks: { color: '#64748b' } } } }
        });
      } else {
        ddpgLossChart.data.labels = labels;
        ddpgLossChart.data.datasets[0].data = cl;
        ddpgLossChart.data.datasets[1].data = al;
        ddpgLossChart.update('none');
      }
    }

    /* 训练完成 —— 渲染指标表（含 MAPE 列）与散点图 */
    if (res.status === 'done') {
      stopPolling();
      const btn = document.getElementById('ddpg-start');
      btn.disabled = false; btn.textContent = '▶ 开始训练';
      document.getElementById('ddpg-loss-tag').textContent = '完成';
      document.getElementById('ddpg-loss-tag').className = 'tag tag-success';
      document.getElementById('ddpg-result-tag').textContent = '已完成';
      document.getElementById('ddpg-result-tag').className = 'tag tag-success';
      /* 指标表：R² / RMSE / MAE / MAPE（论文 5.2 节四维指标） */
      if (res.metrics) {
        const m = res.metrics;
        const tbl = document.getElementById('ddpg-metrics-table');
        let html = '<thead><tr><th>数据集</th><th>R²</th><th>RMSE</th><th>MAE</th><th>MAPE(%)</th></tr></thead><tbody>';
        html += '<tr><td class="tgt">训练集</td><td>' + m.train.r2.toFixed(4) + '</td><td>' + m.train.rmse.toFixed(2) + '</td><td>' + m.train.mae.toFixed(2) + '</td><td>' + (m.train.mape || 0).toFixed(2) + '</td></tr>';
        html += '<tr><td class="tgt">验证集</td><td>' + m.val.r2.toFixed(4) + '</td><td>' + m.val.rmse.toFixed(2) + '</td><td>' + m.val.mae.toFixed(2) + '</td><td>' + (m.val.mape || 0).toFixed(2) + '</td></tr>';
        html += '<tr><td class="tgt">测试集</td><td>' + m.test.r2.toFixed(4) + '</td><td>' + m.test.rmse.toFixed(2) + '</td><td>' + m.test.mae.toFixed(2) + '</td><td>' + (m.test.mape || 0).toFixed(2) + '</td></tr>';
        tbl.innerHTML = html + '</tbody>';
        document.getElementById('ddpg-summary').innerHTML =
          '训练完成 · 共 ' + res.epoch + ' 轮' + (res.early_stopped ? ' · <span style="color:var(--amber)">早停触发</span>' : '') +
          '<br>最佳验证集 R²: <b style="color:var(--ember-hot)">' + (res.best_val_r2 ? res.best_val_r2.toFixed(4) : '—') + '</b>' +
          '<br>测试集 R²: <b style="color:var(--success)">' + m.test.r2.toFixed(4) + '</b> · RMSE: ' + m.test.rmse.toFixed(2) + ' HV · MAPE: ' + (m.test.mape || 0).toFixed(2) + '%';
      }
      /* 散点图 */
      if (res.scatter) {
        const scatterData = res.scatter.map(p => ({ x: p.x, y: p.y }));
        const allVals = res.scatter.flatMap(p => [p.x, p.y]);
        const minV = Math.min(...allVals), maxV = Math.max(...allVals);
        if (!ddpgScatterChart) {
          ddpgScatterChart = makeChart('ch-ddpg-scatter', {
            type: 'scatter',
            data: { datasets: [{ label: '测试集样本', data: scatterData, backgroundColor: 'rgba(10,132,255,.5)', borderColor: '#0A84FF', borderWidth: 1, pointRadius: 4 }] },
            options: { maintainAspectRatio: false, plugins: { legend: { position: 'bottom', labels: { color: '#475569', boxWidth: 10 } }, tooltip: { callbacks: { label: c => '真实: ' + c.raw.x.toFixed(1) + ' → 预测: ' + c.raw.y.toFixed(1) } } }, scales: { x: { title: { display: true, text: '真实 HV', color: '#475569' }, grid: { color: 'rgba(15, 23, 42, .04)' }, ticks: { color: '#64748b' }, min: minV, max: maxV }, y: { title: { display: true, text: '预测 HV', color: '#475569' }, grid: { color: 'rgba(15, 23, 42, .04)' }, ticks: { color: '#64748b' }, min: minV, max: maxV } } }
          });
        } else {
          ddpgScatterChart.data.datasets[0].data = scatterData;
          ddpgScatterChart.options.scales.x.min = minV;
          ddpgScatterChart.options.scales.x.max = maxV;
          ddpgScatterChart.options.scales.y.min = minV;
          ddpgScatterChart.options.scales.y.max = maxV;
          ddpgScatterChart.update('none');
        }
        /* 理想线 y=x */
        if (!ddpgScatterChart.data.datasets[1]) {
          ddpgScatterChart.data.datasets.push({ label: '理想 y=x', data: [{ x: minV, y: minV }, { x: maxV, y: maxV }], type: 'line', borderColor: 'rgba(16,185,129,.5)', borderWidth: 1, borderDash: [5, 5], pointRadius: 0, fill: false });
        } else {
          ddpgScatterChart.data.datasets[1].data = [{ x: minV, y: minV }, { x: maxV, y: maxV }];
        }
        ddpgScatterChart.update('none');
      }
      toast('DDPG 训练完成！测试集 R²=' + (res.metrics ? res.metrics.test.r2 : 0).toFixed(4), 'ok');
    }

    /* 错误 */
    if (res.status === 'error') {
      stopPolling();
      const btn = document.getElementById('ddpg-start');
      btn.disabled = false; btn.textContent = '▶ 开始训练';
      document.getElementById('ddpg-status').textContent = '错误';
      document.getElementById('ddpg-loss-tag').textContent = '错误';
      document.getElementById('ddpg-loss-tag').className = 'tag tag-danger';
      toast('训练失败: ' + (res.error || '未知错误'), 'error');
    }
  }

  /* 页面不可见时暂停轮询 */
  document.addEventListener('visibilitychange', () => {
    if (document.hidden) { stopPolling(); }
    else if (ddpgCurrentTaskId) {
      const st = document.getElementById('ddpg-status').textContent;
      if (st !== '完成' && st !== '错误') { startPolling(); }
    }
  });
}

/* ============ CMP53 · 5.3 硬度预测对比（原始数据） ============ */
/* 5.3 节对比实验：原始 149 条数据上 DDPG vs LR/PR/SVR
   - 传统算法：调用 /api/train/compare（含 K 折 CV）
   - DDPG：调用 /api/ddpg/train + 轮询 /api/ddpg/status
   - 报表：每个模型一行（测试集），DDPG 额外显示训练集/验证集
   - 散点图：DDPG 测试集预测 vs 真实
*/
let cmp53Init = false, cmp53ScatterChart = null, cmp53DDPGTaskId = null, cmp53DDPGTimer = null;
function initCmp53() {
  if (cmp53Init) return; cmp53Init = true;
  /* 滑块联动 */
  document.getElementById('cmp53-ts').addEventListener('input', e => {
    document.getElementById('cmp53-ts-val').textContent = '0.' + e.target.value;
  });
  document.getElementById('cmp53-cv').addEventListener('input', e => {
    document.getElementById('cmp53-cv-val').textContent = e.target.value;
  });
  /* 算法 chip 切换 */
  document.querySelectorAll('#cmp53-chips .chip').forEach(c => {
    c.addEventListener('click', () => c.classList.toggle('on'));
  });

  document.getElementById('cmp53-run').addEventListener('click', () => runCmpExperiment('53'));
}

/* ============ CMP54 · 5.4 GAN 数据扩充对比 ============ */
let cmp54Init = false, cmp54ScatterChart = null, cmp54DDPGTaskId = null, cmp54DDPGTimer = null;
function initCmp54() {
  if (cmp54Init) return; cmp54Init = true;
  document.getElementById('cmp54-ts').addEventListener('input', e => {
    document.getElementById('cmp54-ts-val').textContent = '0.' + e.target.value;
  });
  document.getElementById('cmp54-cv').addEventListener('input', e => {
    document.getElementById('cmp54-cv-val').textContent = e.target.value;
  });
  document.querySelectorAll('#cmp54-chips .chip').forEach(c => {
    c.addEventListener('click', () => c.classList.toggle('on'));
  });
  document.getElementById('cmp54-run').addEventListener('click', () => runCmpExperiment('54'));
}

/**
 * 运行 5.3 / 5.4 节对比实验
 * @param {string} pageId - '53' 或 '54'，对应 cmp53 / cmp54 页面
 */
async function runCmpExperiment(pageId) {
  const prefix = 'cmp' + pageId;
  const btn = document.getElementById(prefix + '-run');
  const tag = document.getElementById(prefix + '-tag');
  const tbl = document.getElementById(prefix + '-table');
  const dataSource = (pageId === '53') ? 'real' : 'gan';
  const dataSourceLabel = (pageId === '53') ? '原始数据' : 'GAN 扩充';

  /* 收集选中的算法 */
  const picked = [...document.querySelectorAll('#' + prefix + '-chips .chip.on')].map(c => c.dataset.model);
  if (picked.length === 0) { toast('⚠ 请至少选择一个算法', 'warn'); return; }
  const pickedTraditional = picked.filter(m => m !== 'DDPG');
  const pickedDDPG = picked.includes('DDPG');

  const ts = parseFloat('0.' + document.getElementById(prefix + '-ts').value) || 0.2;
  const cv = parseInt(document.getElementById(prefix + '-cv').value) || 5;

  btn.disabled = true; btn.textContent = '⏳ 运行中...';
  tag.textContent = '运行中'; tag.className = 'tag tag-success';
  toast('▶ 运行 5.' + pageId + ' 节对比实验（' + dataSourceLabel + '）...');

  let rowsHtml = '<thead><tr><th>模型</th><th>数据集</th><th>RMSE (HV)</th><th>MAE (HV)</th><th>R²</th><th>MAPE (%)</th></tr></thead><tbody>';
  let traditionalResults = [];
  let ddpgResult = null;

  /* 1. 传统算法批量对比（/api/train/compare） */
  if (pickedTraditional.length > 0) {
    tbl.innerHTML = rowsHtml + '<tr><td colspan="6" style="text-align:center;color:var(--text-faint);padding:24px">⏳ 正在训练传统算法 (' + pickedTraditional.join(', ') + ')...</td></tr></tbody>';
    const res = await api('/api/train/compare', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ models: pickedTraditional, test_size: ts, cv_folds: cv, data_source: dataSource })
    });
    if (res.error) { showOfflineHint(); toast('⚠ ' + res.error, 'error'); btn.disabled = false; btn.textContent = '▶ 运行 5.' + pageId + ' 节对比实验'; tag.textContent = '失败'; tag.className = 'tag tag-danger'; return; }
    traditionalResults = res.models || [];
    /* 渲染传统算法行（测试集） */
    traditionalResults.forEach(m => {
      const err = m.error;
      rowsHtml += '<tr>' +
        '<td class="tgt">' + m.model + (err ? ' <span class="tag tag-danger" style="margin-left:4px">ERR</span>' : '') + '</td>' +
        '<td>测试集</td>' +
        '<td>' + (m.rmse != null ? m.rmse.toFixed(2) : '—') + '</td>' +
        '<td>' + (m.mae != null ? m.mae.toFixed(2) : '—') + '</td>' +
        '<td>' + (m.r2 != null ? m.r2.toFixed(4) : '—') + '</td>' +
        '<td>' + (m.mape != null ? m.mape.toFixed(2) : '—') + '</td>' +
        '</tr>';
    });
  }

  /* 2. DDPG 训练（异步 + 轮询） */
  if (pickedDDPG) {
    rowsHtml += '<tr><td colspan="6" style="text-align:center;color:var(--ember);padding:16px">⏳ DDPG 训练中（异步，可能耗时较长）...</td></tr>';
    tbl.innerHTML = rowsHtml + '</tbody>';
    const ddpgRes = await api('/api/ddpg/train', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ data_source: dataSource, epochs: 500, batch_size: 32, lr_actor: 1e-4, lr_critic: 5e-4, test_size: ts })
    });
    if (ddpgRes.error) {
      rowsHtml = rowsHtml.replace(/<tr><td colspan="6"[^>]*>⏳ DDPG[^<]*<\/td><\/tr>/, '<tr><td class="tgt">DDPG</td><td colspan="5" style="color:var(--danger)">错误：' + ddpgRes.error + '</td></tr>');
      tbl.innerHTML = rowsHtml + '</tbody>';
      toast('⚠ DDPG 启动失败：' + ddpgRes.error, 'error');
    } else {
      /* 轮询 DDPG 状态 */
      ddpgResult = await pollDDPGForCompare(ddpgRes.task_id, prefix);
      /* 移除"DDPG 训练中"占位行 */
      rowsHtml = rowsHtml.replace(/<tr><td colspan="6"[^>]*>⏳ DDPG[^<]*<\/td><\/tr>/, '');
      if (ddpgResult && ddpgResult.metrics) {
        const m = ddpgResult.metrics;
        rowsHtml += '<tr><td class="tgt" rowspan="3"><b>DDPG</b><br><small style="color:var(--text-faint)">本论文主算法</small></td><td>训练集</td><td>' + m.train.rmse.toFixed(2) + '</td><td>' + m.train.mae.toFixed(2) + '</td><td>' + m.train.r2.toFixed(4) + '</td><td>' + (m.train.mape || 0).toFixed(2) + '</td></tr>';
        rowsHtml += '<tr><td>验证集</td><td>' + m.val.rmse.toFixed(2) + '</td><td>' + m.val.mae.toFixed(2) + '</td><td>' + m.val.r2.toFixed(4) + '</td><td>' + (m.val.mape || 0).toFixed(2) + '</td></tr>';
        rowsHtml += '<tr><td><b>测试集</b></td><td><b>' + m.test.rmse.toFixed(2) + '</b></td><td><b>' + m.test.mae.toFixed(2) + '</b></td><td><b style="color:var(--success)">' + m.test.r2.toFixed(4) + '</b></td><td><b>' + (m.test.mape || 0).toFixed(2) + '</b></td></tr>';
        /* 渲染 DDPG 测试集散点 */
        if (ddpgResult.scatter) {
          renderCmpScatter(prefix, ddpgResult.scatter, 'DDPG 测试集预测 vs 真实（5.' + pageId + ' · ' + dataSourceLabel + '）');
        }
      } else {
        rowsHtml += '<tr><td class="tgt">DDPG</td><td colspan="5" style="color:var(--danger)">训练失败</td></tr>';
      }
    }
  }

  tbl.innerHTML = rowsHtml + '</tbody>';
  btn.disabled = false; btn.textContent = '▶ 运行 5.' + pageId + ' 节对比实验';
  tag.textContent = '已完成'; tag.className = 'tag tag-success';
  toast('✓ 5.' + pageId + ' 节对比实验完成', 'ok');
}

/**
 * 轮询 DDPG 训练状态直到完成（用于 cmp53/cmp54 页面）
 * @param {string} taskId - DDPG 任务 id
 * @param {string} prefix - 'cmp53' 或 'cmp54'
 * @returns {Promise<Object|null>} 训练结果（含 metrics / scatter），失败返回 null
 */
function pollDDPGForCompare(taskId, prefix) {
  return new Promise((resolve) => {
    let elapsed = 0;
    const MAX_WAIT = 600; /* 最大等待 10 分钟（600 次 × 1s） */
    const timer = setInterval(async () => {
      elapsed++;
      if (elapsed > MAX_WAIT) {
        clearInterval(timer);
        resolve(null);
        return;
      }
      const res = await api('/api/ddpg/status/' + taskId);
      if (res.error) { clearInterval(timer); resolve(null); return; }
      if (res.status === 'done') { clearInterval(timer); resolve(res); return; }
      if (res.status === 'error') { clearInterval(timer); resolve(null); return; }
      /* 更新表格中的进度提示行 */
      const tbl = document.getElementById(prefix + '-table');
      const progressText = res.progress ? ' (' + res.progress.toFixed(0) + '%)' : '';
      const placeholder = tbl.querySelector('td[colspan="6"]');
      if (placeholder && placeholder.textContent.includes('DDPG')) {
        placeholder.textContent = '⏳ DDPG 训练中' + progressText + '（' + (res.epoch || 0) + '/' + (res.total_epochs || 0) + ' 轮）...';
      }
    }, 2000);
  });
}

/**
 * 渲染对比页散点图（DDPG 测试集预测 vs 真实）
 * @param {string} prefix - 'cmp53' 或 'cmp54'
 * @param {Array} scatter - 散点数据 [{x: 真实, y: 预测}, ...]
 * @param {string} title - 图表标题
 */
function renderCmpScatter(prefix, scatter, title) {
  const canvasId = 'ch-' + prefix + '-scatter';
  const scatterData = scatter.map(p => ({ x: p.x, y: p.y }));
  const allVals = scatter.flatMap(p => [p.x, p.y]);
  const minV = Math.min(...allVals), maxV = Math.max(...allVals);
  const chart = makeChart(canvasId, {
    type: 'scatter',
    data: { datasets: [
      { label: 'DDPG 测试集', data: scatterData, backgroundColor: 'rgba(10,132,255,.5)', borderColor: '#0A84FF', borderWidth: 1, pointRadius: 4 },
      { label: '理想 y=x', data: [{ x: minV, y: minV }, { x: maxV, y: maxV }], type: 'line', borderColor: 'rgba(16,185,129,.5)', borderWidth: 1, borderDash: [5, 5], pointRadius: 0, fill: false }
    ] },
    options: { maintainAspectRatio: false, plugins: { legend: { position: 'bottom', labels: { color: '#475569', boxWidth: 10 } }, tooltip: { callbacks: { label: c => '真实: ' + c.raw.x.toFixed(1) + ' → 预测: ' + c.raw.y.toFixed(1) } } }, scales: { x: { title: { display: true, text: '真实 HV', color: '#475569' }, grid: { color: 'rgba(15, 23, 42, .04)' }, ticks: { color: '#64748b' }, min: minV, max: maxV }, y: { title: { display: true, text: '预测 HV', color: '#475569' }, grid: { color: 'rgba(15, 23, 42, .04)' }, ticks: { color: '#64748b' }, min: minV, max: maxV } } }
  });
  if (prefix === 'cmp53') cmp53ScatterChart = chart;
  else cmp54ScatterChart = chart;
}

/* ============ SIDEBAR TOGGLE ============ */
/* 侧边栏折叠按钮 */
(function () {
  const toggle = document.getElementById('sidebar-toggle');
  if (!toggle) return;
  toggle.addEventListener('click', () => {
    const app = document.querySelector('.app');
    app.classList.toggle('collapsed');
    toggle.textContent = app.classList.contains('collapsed') ? '\u203A' : '\u2039';
    toggle.title = app.classList.contains('collapsed') ? '展开侧边栏' : '折叠侧边栏';
  });
})();

/* ============ AUTH · 鉴权模块 ============ */
let CURRENT_USER = null;

/** 显示登录覆盖层（同时检查是否开放游客浏览 / 注册） */
async function showLogin() {
  document.getElementById('login-overlay').classList.add('show');
  // 默认回到登录模式（避免上次停留在注册模式）
  switchLoginMode('login');
  document.getElementById('login-username').focus();
  // 拉取系统设置，决定显示哪些入口
  try {
    const res = await api('/api/settings');
    const s = (res && res.settings) || {};
    const allowGuest = s.allow_guest_browse === 'true';
    const allowRegister = s.allow_register !== 'false'; // 默认开启
    document.getElementById('login-guest').style.display = allowGuest ? 'block' : 'none';
    document.getElementById('login-switch').style.display = allowRegister ? 'block' : 'none';
  } catch (e) { /* 后端未启动时隐藏 */ }
}
/** 切换登录/注册模式
 * @param {string} mode - 'login' | 'register'
 */
function switchLoginMode(mode) {
  const isRegister = mode === 'register';
  // 注册模式额外字段
  ['reg-field-confirm', 'reg-field-display', 'reg-field-email'].forEach(id => {
    document.getElementById(id).style.display = isRegister ? 'block' : 'none';
  });
  // 切换主按钮
  document.getElementById('login-submit').style.display = isRegister ? 'none' : 'block';
  document.getElementById('register-submit').style.display = isRegister ? 'block' : 'none';
  // 切换底部链接
  document.getElementById('login-switch').style.display = isRegister ? 'none' : 'block';
  document.getElementById('register-switch').style.display = isRegister ? 'block' : 'none';
  // 切换标题副文案
  document.getElementById('login-sub').textContent = isRegister
    ? 'v3.1 · 论文对齐版 · 填写信息注册新账号'
    : 'v3.1 · 论文对齐版 · 请登录后使用';
  // 清空错误提示
  document.getElementById('login-error').textContent = '';
  // 调整密码框 autocomplete
  document.getElementById('login-password').autocomplete = isRegister ? 'new-password' : 'current-password';
}
/** 隐藏登录覆盖层 */
function hideLogin() {
  document.getElementById('login-overlay').classList.remove('show');
}
/** 退出登录 */
function logout() {
  localStorage.removeItem('forge_token');
  localStorage.removeItem('forge_user');
  CURRENT_USER = null;
  updateUserUI();
  showLogin();
  toast('已退出登录');
}
/** 当前用户是否为游客 */
function isGuest() {
  return CURRENT_USER && CURRENT_USER.role === 'guest';
}
/** 当前用户是否为管理员 */
function isAdmin() {
  return CURRENT_USER && CURRENT_USER.role === 'admin';
}
/** 更新顶栏用户区显示 */
function updateUserUI() {
  const avatar = document.getElementById('user-avatar');
  const name = document.getElementById('user-name');
  const infoName = document.getElementById('user-info-name');
  const infoRole = document.getElementById('user-info-role');
  if (CURRENT_USER) {
    avatar.textContent = (CURRENT_USER.username || 'U').charAt(0).toUpperCase();
    avatar.style.background = 'linear-gradient(135deg, var(--ember), var(--copper))';
    avatar.style.color = '#fff';
    name.textContent = CURRENT_USER.username;
    infoName.textContent = CURRENT_USER.display_name || CURRENT_USER.username;
    const roleMap = { admin: '管理员', user: '普通用户', guest: '游客' };
    infoRole.textContent = roleMap[CURRENT_USER.role] || '未知';
    infoRole.style.color = CURRENT_USER.role === 'admin' ? 'var(--ember)'
      : CURRENT_USER.role === 'guest' ? 'var(--amber)'
      : 'var(--text-dim)';
  } else {
    avatar.textContent = 'U';
    avatar.style.background = 'var(--bg-hover)';
    avatar.style.color = 'var(--text-faint)';
    name.textContent = '未登录';
    infoName.textContent = '—';
    infoRole.textContent = '—';
  }
}
/** 执行登录 */
async function doLogin() {
  const username = document.getElementById('login-username').value.trim();
  const password = document.getElementById('login-password').value.trim();
  const errBox = document.getElementById('login-error');
  errBox.textContent = '';
  if (!username || !password) {
    errBox.textContent = '请输入用户名和密码';
    return;
  }
  const btn = document.getElementById('login-submit');
  btn.disabled = true; btn.textContent = '登录中...';
  const res = await api('/api/auth/login', { method: 'POST', body: { username, password } });
  btn.disabled = false; btn.textContent = '登 录 →';
  if (res.error) {
    errBox.textContent = res.error;
    return;
  }
  localStorage.setItem('forge_token', res.token);
  localStorage.setItem('forge_user', JSON.stringify(res.user));
  CURRENT_USER = res.user;
  updateUserUI();
  hideLogin();
  toast('✓ 欢迎回来，' + (res.user.display_name || res.user.username), 'ok');
  // 触发当前页 init
  const cur = (location.hash || '').replace('#', '') || 'dashboard';
  navigate(cur);
}
/** 游客登录（无需账号密码） */
async function doGuestLogin() {
  const btn = document.getElementById('login-guest');
  const errBox = document.getElementById('login-error');
  errBox.textContent = '';
  btn.disabled = true; btn.textContent = '进入中...';
  const res = await api('/api/auth/guest', { method: 'POST' });
  btn.disabled = false; btn.textContent = '👤 以游客身份浏览';
  if (res.error) {
    errBox.textContent = res.error;
    return;
  }
  localStorage.setItem('forge_token', res.token);
  localStorage.setItem('forge_user', JSON.stringify(res.user));
  CURRENT_USER = res.user;
  updateUserUI();
  hideLogin();
  toast('✓ 已以游客身份进入（只读模式）', 'ok');
  navigate('dashboard');
}
/** 执行注册（注册成功后自动登录） */
async function doRegister() {
  const username = document.getElementById('login-username').value.trim();
  const password = document.getElementById('login-password').value.trim();
  const confirm = document.getElementById('reg-confirm').value.trim();
  const display = document.getElementById('reg-display').value.trim();
  const email = document.getElementById('reg-email').value.trim();
  const errBox = document.getElementById('login-error');
  errBox.textContent = '';
  // 前端基础校验（与后端规则一致）
  if (!username || !password) {
    errBox.textContent = '用户名和密码不能为空';
    return;
  }
  if (username.length < 3 || username.length > 20) {
    errBox.textContent = '用户名长度需 3-20 个字符';
    return;
  }
  if (!/^[A-Za-z0-9_]+$/.test(username)) {
    errBox.textContent = '用户名只能含字母、数字、下划线';
    return;
  }
  if (password.length < 6 || password.length > 64) {
    errBox.textContent = '密码长度需 6-64 个字符';
    return;
  }
  if (password !== confirm) {
    errBox.textContent = '两次输入的密码不一致';
    return;
  }
  const btn = document.getElementById('register-submit');
  btn.disabled = true; btn.textContent = '注册中...';
  const res = await api('/api/auth/register', {
    method: 'POST',
    body: { username, password, display_name: display, email: email },
  });
  btn.disabled = false; btn.textContent = '注 册 并 登 录 →';
  if (res.error) {
    errBox.textContent = res.error;
    return;
  }
  // 注册成功 → 自动登录
  localStorage.setItem('forge_token', res.token);
  localStorage.setItem('forge_user', JSON.stringify(res.user));
  CURRENT_USER = res.user;
  updateUserUI();
  hideLogin();
  toast('✓ 注册成功，欢迎加入，' + (res.user.display_name || res.user.username), 'ok');
  navigate('dashboard');
}
/** 检查登录状态 */
async function checkAuth() {
  const token = localStorage.getItem('forge_token');
  const userJson = localStorage.getItem('forge_user');
  if (!token) { await showLogin(); return; }
  if (userJson) {
    try { CURRENT_USER = JSON.parse(userJson); } catch (e) { CURRENT_USER = null; }
  }
  // 调 /me 验证 token 是否还有效
  const res = await api('/api/auth/me');
  if (res.error) {
    logout();
    return;
  }
  CURRENT_USER = res.user;
  updateUserUI();
  hideLogin();
}
/** 监听 401/403 自动跳登录 */
window.addEventListener('auth:unauthorized', () => {
  toast('⚠ 登录已过期，请重新登录', 'warn');
  logout();
});

/* ============ 顶栏用户菜单交互 ============ */
document.getElementById('user-menu').addEventListener('click', (e) => {
  e.stopPropagation();
  document.getElementById('user-dropdown').classList.toggle('show');
});
document.addEventListener('click', () => {
  document.getElementById('user-dropdown').classList.remove('show');
});
document.getElementById('user-logout').addEventListener('click', logout);
document.getElementById('user-goto-settings').addEventListener('click', () => navigate('settings'));
document.getElementById('user-change-pwd').addEventListener('click', () => {
  document.getElementById('pwd-modal').style.display = 'flex';
});
document.getElementById('pwd-close').addEventListener('click', () => document.getElementById('pwd-modal').style.display = 'none');
document.getElementById('pwd-cancel').addEventListener('click', () => document.getElementById('pwd-modal').style.display = 'none');
document.getElementById('pwd-save').addEventListener('click', async () => {
  const oldPwd = document.getElementById('pwd-old').value;
  const newPwd = document.getElementById('pwd-new').value;
  const confirm = document.getElementById('pwd-confirm').value;
  if (!oldPwd || !newPwd) return toast('原密码和新密码不能为空', 'warn');
  if (newPwd !== confirm) return toast('两次新密码不一致', 'warn');
  if (newPwd.length < 6) return toast('新密码至少 6 位', 'warn');
  const res = await api('/api/auth/change_password', { method: 'POST', body: { old_password: oldPwd, new_password: newPwd } });
  if (res.error) return toast(res.error, 'error');
  toast('✓ 密码修改成功', 'ok');
  document.getElementById('pwd-modal').style.display = 'none';
  ['pwd-old', 'pwd-new', 'pwd-confirm'].forEach(id => document.getElementById(id).value = '');
});
document.getElementById('login-submit').addEventListener('click', doLogin);
document.getElementById('login-password').addEventListener('keydown', (e) => { if (e.key === 'Enter') doLogin(); });
document.getElementById('login-guest').addEventListener('click', doGuestLogin);
document.getElementById('login-username').addEventListener('keydown', (e) => { if (e.key === 'Enter') document.getElementById('login-password').focus(); });
// 注册相关事件
document.getElementById('register-submit').addEventListener('click', doRegister);
document.getElementById('reg-confirm').addEventListener('keydown', (e) => { if (e.key === 'Enter') doRegister(); });
document.getElementById('reg-email').addEventListener('keydown', (e) => { if (e.key === 'Enter') doRegister(); });
document.getElementById('goto-register').addEventListener('click', () => switchLoginMode('register'));
document.getElementById('goto-login').addEventListener('click', () => switchLoginMode('login'));

/* ============ PAGE · 数据管理 ============ */
let dmState = { page: 1, size: 20, keyword: '', sort: '', dir: 'asc', columns: [] };
function initDataMgr() {
  // 游客禁用写入按钮（新增/批量导入），查询/导出/分析可用
  const guest = isGuest();
  ['dm-add', 'dm-batch'].forEach(id => {
    const el = document.getElementById(id);
    if (el) { el.disabled = guest; el.title = guest ? '游客无权操作，请登录' : ''; }
  });
  loadDmRows();
}
async function loadDmRows() {
  const params = new URLSearchParams({
    page: dmState.page, size: dmState.size, keyword: dmState.keyword,
    sort: dmState.sort, dir: dmState.dir,
  });
  const res = await api('/api/data/rows?' + params.toString());
  if (res.error) {
    document.getElementById('dm-table').querySelector('tbody').innerHTML =
      '<tr><td colspan="20" style="text-align:center;color:var(--danger);padding:20px">' + res.error + '</td></tr>';
    return;
  }
  dmState.columns = res.columns || [];
  // 更新排序列下拉
  const sortSel = document.getElementById('dm-sort');
  if (sortSel.children.length <= 1) {
    dmState.columns.forEach(c => {
      if (c === '_row_id') return;
      const opt = document.createElement('option');
      opt.value = c; opt.textContent = c;
      sortSel.appendChild(opt);
    });
  }
  // 渲染表头
  const thead = document.getElementById('dm-table').querySelector('thead');
  thead.innerHTML = '<tr>' + ['操作', ...res.columns.map(c => '<th>' + c + '</th>')].join('') + '</tr>';
  // 渲染行
  const tbody = document.getElementById('dm-table').querySelector('tbody');
  if (!res.items || !res.items.length) {
    tbody.innerHTML = '<tr><td colspan="' + (res.columns.length + 1) + '" style="text-align:center;color:var(--text-faint);padding:20px">暂无数据</td></tr>';
  } else {
    tbody.innerHTML = res.items.map(row =>
      '<tr>' +
      '<td style="white-space:nowrap"><button class="btn btn-ghost dm-edit" data-row=\'' + JSON.stringify(row).replace(/'/g, '&#39;') + '\' style="padding:4px 10px;font-size:11px;margin-right:4px">✎</button><button class="btn btn-ghost dm-del" data-id="' + row._row_id + '" style="padding:4px 10px;font-size:11px;color:var(--danger)">✕</button></td>' +
      res.columns.map(c => '<td>' + (row[c] === null || row[c] === undefined ? '' : row[c]) + '</td>').join('') +
      '</tr>'
    ).join('');
    // 绑定编辑/删除
    tbody.querySelectorAll('.dm-edit').forEach(btn => btn.addEventListener('click', () => openEditRow(JSON.parse(btn.dataset.row))));
    tbody.querySelectorAll('.dm-del').forEach(btn => btn.addEventListener('click', () => delRow(btn.dataset.id)));
  }
  document.getElementById('dm-info').textContent = '共 ' + res.total + 条 + ' · 第 ' + res.page + ' 页';
  document.getElementById('dm-page').textContent = res.page + ' / ' + Math.max(1, Math.ceil(res.total / res.size));
}
document.getElementById('dm-search-btn').addEventListener('click', () => {
  dmState.keyword = document.getElementById('dm-search').value.trim();
  dmState.sort = document.getElementById('dm-sort').value;
  dmState.dir = document.getElementById('dm-dir').value;
  dmState.page = 1; loadDmRows();
});
document.getElementById('dm-search').addEventListener('keydown', e => { if (e.key === 'Enter') document.getElementById('dm-search-btn').click(); });
document.getElementById('dm-prev').addEventListener('click', () => { if (dmState.page > 1) { dmState.page--; loadDmRows(); } });
document.getElementById('dm-next').addEventListener('click', () => { dmState.page++; loadDmRows(); });
document.getElementById('dm-add').addEventListener('click', () => openEditRow(null));
document.getElementById('dm-batch').addEventListener('click', () => document.getElementById('dm-batch-file').click());
document.getElementById('dm-batch-file').addEventListener('change', async (e) => {
  const file = e.target.files[0]; if (!file) return;
  const fd = new FormData(); fd.append('file', file);
  const r = await fetch(API_BASE + '/api/data/batch_import', {
    method: 'POST',
    headers: { 'Authorization': 'Bearer ' + localStorage.getItem('forge_token') },
    body: fd,
  });
  const res = await r.json();
  if (res.error) return toast(res.error, 'error');
  toast('✓ 导入成功：追加 ' + res.appended_rows + ' 行，共 ' + res.total_rows + ' 行', 'ok');
  loadDmRows();
  e.target.value = '';
});
document.getElementById('dm-export-xlsx').addEventListener('click', () => downloadExport('xlsx'));
document.getElementById('dm-export-csv').addEventListener('click', () => downloadExport('csv'));
async function downloadExport(fmt) {
  const r = await fetch(API_BASE + '/api/data/export?format=' + fmt, {
    headers: { 'Authorization': 'Bearer ' + localStorage.getItem('forge_token') }
  });
  if (!r.ok) { toast('导出失败', 'error'); return; }
  const blob = await r.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url; a.download = 'data_export.' + (fmt === 'csv' ? 'csv' : 'xlsx');
  a.click(); URL.revokeObjectURL(url);
}
document.getElementById('dm-analysis').addEventListener('click', async () => {
  document.getElementById('dm-analysis-card').style.display = '';
  const res = await api('/api/data/analysis');
  if (res.error) return toast(res.error, 'error');
  // 渲染 HV 直方图
  if (res.target_stats && res.target_stats.hist_counts) {
    makeChart('dm-hist-chart', {
      type: 'bar',
      data: {
        labels: res.target_stats.hist_bins.slice(0, -1).map(v => v.toFixed(0)),
        datasets: [{ label: '样本数', data: res.target_stats.hist_counts, backgroundColor: 'rgba(10,132,255,.6)' }]
      },
      options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } },
        scales: { x: { grid: { color: 'rgba(15,23,42,.04)' } }, y: { grid: { color: 'rgba(15,23,42,.04)' } } } }
    });
  }
  // 渲染相关性 Top 10
  if (res.correlation_top && res.correlation_top.length) {
    makeChart('dm-corr-chart', {
      type: 'bar',
      data: {
        labels: res.correlation_top.map(x => x.element),
        datasets: [{ label: '|相关系数|', data: res.correlation_top.map(x => x.abs_corr), backgroundColor: 'rgba(94,92,230,.6)' }]
      },
      options: { indexAxis: 'y', responsive: true, maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: { x: { grid: { color: 'rgba(15,23,42,.04)' } }, y: { grid: { color: 'rgba(15,23,42,.04)' } } } }
    });
  }
  // 统计表
  const statsHtml = '<div style="font-family:var(--sans);font-size:12px;font-weight:600;color:var(--text);margin-bottom:10px">特征统计摘要（前 10 个）</div>' +
    '<div class="table-wrap"><table class="data"><thead><tr><th>特征</th><th>count</th><th>min</th><th>max</th><th>mean</th><th>std</th><th>median</th><th>Q1</th><th>Q3</th></tr></thead><tbody>' +
    Object.entries(res.feature_stats || {}).slice(0, 10).map(([k, v]) =>
      '<tr><td>' + k + '</td><td>' + v.count + '</td><td>' + v.min.toFixed(3) + '</td><td>' + v.max.toFixed(3) + '</td><td>' + v.mean.toFixed(3) + '</td><td>' + v.std.toFixed(3) + '</td><td>' + v.median.toFixed(3) + '</td><td>' + v.q1.toFixed(3) + '</td><td>' + v.q3.toFixed(3) + '</td></tr>'
    ).join('') + '</tbody></table></div>';
  document.getElementById('dm-stats-table').innerHTML = statsHtml;
});
document.getElementById('dm-analysis-close').addEventListener('click', () => document.getElementById('dm-analysis-card').style.display = 'none');

function openEditRow(row) {
  const isEdit = !!row;
  document.getElementById('user-modal-title').textContent = isEdit ? '编辑行 (id=' + row._row_id + ')' : '新增一行';
  const body = document.getElementById('user-modal').querySelector('.modal-body');
  // 动态生成字段
  const cols = dmState.columns.filter(c => c !== '_row_id');
  body.innerHTML = (isEdit ? '<input type="hidden" id="um-rowid" value="' + row._row_id + '">' : '') +
    cols.map(c => {
      const v = isEdit ? (row[c] === null || row[c] === undefined ? '' : row[c]) : '';
      return '<div class="field"><label class="field-label">' + c + '</label><input class="input dm-field" data-col="' + c + '" value="' + v + '"></div>';
    }).join('');
  document.getElementById('user-modal').style.display = 'flex';
  document.getElementById('user-save').onclick = async () => {
    const data = {};
    body.querySelectorAll('.dm-field').forEach(inp => { data[inp.dataset.col] = inp.value; });
    if (isEdit) {
      const res = await api('/api/data/rows/' + row._row_id, { method: 'PUT', body: data });
      if (res.error) return toast(res.error, 'error');
      toast('✓ 已保存', 'ok');
    } else {
      const res = await api('/api/data/rows', { method: 'POST', body: data });
      if (res.error) return toast(res.error, 'error');
      toast('✓ 新增成功', 'ok');
    }
    document.getElementById('user-modal').style.display = 'none';
    loadDmRows();
  };
}
async function delRow(rowId) {
  if (!confirm('确认删除该行？此操作不可恢复。')) return;
  const res = await api('/api/data/rows/' + rowId, { method: 'DELETE' });
  if (res.error) return toast(res.error, 'error');
  toast('✓ 已删除', 'ok');
  loadDmRows();
}
document.getElementById('user-close').addEventListener('click', () => document.getElementById('user-modal').style.display = 'none');
document.getElementById('user-cancel').addEventListener('click', () => document.getElementById('user-modal').style.display = 'none');

/* ============ PAGE · 历史记录 ============ */
let hisState = { page: 1, size: 20 };
function initHistory() { loadHistory(); }
async function loadHistory() {
  const params = new URLSearchParams({ page: hisState.page, size: hisState.size });
  const alg = document.getElementById('his-algorithm').value;
  const src = document.getElementById('his-source').value;
  const from = document.getElementById('his-from').value;
  const to = document.getElementById('his-to').value;
  if (alg) params.set('algorithm', alg);
  if (src) params.set('data_source', src);
  if (from) params.set('date_from', from);
  if (to) params.set('date_to', to);
  const res = await api('/api/history?' + params.toString());
  if (res.error) return toast(res.error, 'error');
  const tbody = document.getElementById('his-table').querySelector('tbody');
  if (!res.items || !res.items.length) {
    tbody.innerHTML = '<tr><td colspan="13" style="text-align:center;color:var(--text-faint);padding:20px">暂无历史记录</td></tr>';
  } else {
    tbody.innerHTML = res.items.map(r => {
      const m = (r.metrics && typeof r.metrics === 'object') ? r.metrics : {};
      const test = m.test || m;
      return '<tr>' +
        '<td>' + r.id + '</td>' +
        '<td>' + (r.created_at || '').replace('T', ' ').slice(0, 19) + '</td>' +
        '<td>' + (r.username || '—') + '</td>' +
        '<td>' + (r.task_type || '') + '</td>' +
        '<td>' + (r.algorithm || '') + '</td>' +
        '<td>' + (r.data_source || '') + '</td>' +
        '<td>' + (r.n_samples || '') + '</td>' +
        '<td>' + (test.r2 !== undefined ? (+test.r2).toFixed(4) : '—') + '</td>' +
        '<td>' + (test.rmse !== undefined ? (+test.rmse).toFixed(2) : '—') + '</td>' +
        '<td>' + (test.mae !== undefined ? (+test.mae).toFixed(2) : '—') + '</td>' +
        '<td>' + (test.mape !== undefined ? (+test.mape).toFixed(2) + '%' : '—') + '</td>' +
        '<td>' + (r.status || '') + '</td>' +
        '<td>' + (CURRENT_USER && CURRENT_USER.role === 'admin' ? '<button class="btn btn-ghost his-del" data-id="' + r.id + '" style="padding:4px 8px;font-size:11px;color:var(--danger)">✕</button>' : '') + '</td>' +
        '</tr>';
    }).join('');
    tbody.querySelectorAll('.his-del').forEach(b => b.addEventListener('click', async () => {
      if (!confirm('删除该历史记录？')) return;
      const res = await api('/api/history/' + b.dataset.id, { method: 'DELETE' });
      if (res.error) return toast(res.error, 'error');
      toast('✓ 已删除', 'ok'); loadHistory();
    }));
  }
  document.getElementById('his-info').textContent = '共 ' + res.total + ' 条 · 第 ' + res.page + ' 页';
  document.getElementById('his-page').textContent = res.page + ' / ' + Math.max(1, Math.ceil(res.total / res.size));
}
document.getElementById('his-search').addEventListener('click', () => { hisState.page = 1; loadHistory(); });
document.getElementById('his-prev').addEventListener('click', () => { if (hisState.page > 1) { hisState.page--; loadHistory(); } });
document.getElementById('his-next').addEventListener('click', () => { hisState.page++; loadHistory(); });
document.getElementById('his-export').addEventListener('click', async () => {
  const r = await fetch(API_BASE + '/api/history/export', {
    headers: { 'Authorization': 'Bearer ' + localStorage.getItem('forge_token') }
  });
  if (!r.ok) return toast('导出失败', 'error');
  const blob = await r.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url; a.download = 'history.csv'; a.click();
  URL.revokeObjectURL(url);
});

/* ============ PAGE · 用户管理 ============ */
let usState = { page: 1, size: 50, keyword: '' };
function initUsers() {
  if (CURRENT_USER && CURRENT_USER.role !== 'admin') {
    document.getElementById('us-table').querySelector('tbody').innerHTML =
      '<tr><td colspan="8" style="text-align:center;color:var(--danger);padding:20px">仅管理员可访问</td></tr>';
    return;
  }
  loadUsers();
}
async function loadUsers() {
  const params = new URLSearchParams({ page: usState.page, size: usState.size, keyword: usState.keyword });
  const res = await api('/api/users?' + params.toString());
  if (res.error) return toast(res.error, 'error');
  const tbody = document.getElementById('us-table').querySelector('tbody');
  if (!res.items || !res.items.length) {
    tbody.innerHTML = '<tr><td colspan="8" style="text-align:center;color:var(--text-faint);padding:20px">暂无用户</td></tr>';
    return;
  }
  tbody.innerHTML = res.items.map(u =>
    '<tr>' +
    '<td>' + u.id + '</td>' +
    '<td><b>' + u.username + '</b></td>' +
    '<td>' + (u.display_name || '—') + '</td>' +
    '<td>' + (u.email || '—') + '</td>' +
    '<td><span class="tag ' + (u.role === 'admin' ? 'tag-ember' : '') + '">' + u.role + '</span></td>' +
    '<td>' + (u.created_at || '').replace('T', ' ').slice(0, 19) + '</td>' +
    '<td>' + (u.last_login ? u.last_login.replace('T', ' ').slice(0, 19) : '—') + '</td>' +
    '<td><button class="btn btn-ghost us-edit" data-id="' + u.id + '" style="padding:4px 10px;font-size:11px;margin-right:4px">✎</button>' +
    (u.id === (CURRENT_USER && CURRENT_USER.id) ? '' : '<button class="btn btn-ghost us-del" data-id="' + u.id + '" style="padding:4px 10px;font-size:11px;color:var(--danger)">✕</button>') + '</td>' +
    '</tr>'
  ).join('');
  tbody.querySelectorAll('.us-edit').forEach(b => b.addEventListener('click', () => openEditUser(parseInt(b.dataset.id))));
  tbody.querySelectorAll('.us-del').forEach(b => b.addEventListener('click', async () => {
    if (!confirm('确认删除该用户？')) return;
    const res = await api('/api/users/' + b.dataset.id, { method: 'DELETE' });
    if (res.error) return toast(res.error, 'error');
    toast('✓ 已删除', 'ok'); loadUsers();
  }));
}
document.getElementById('us-search').addEventListener('click', () => {
  usState.keyword = document.getElementById('us-kw').value.trim(); loadUsers();
});
document.getElementById('us-kw').addEventListener('keydown', e => { if (e.key === 'Enter') loadUsers(); });
document.getElementById('us-add').addEventListener('click', () => openEditUser(null));
async function openEditUser(uid) {
  const isEdit = !!uid;
  const modal = document.getElementById('user-modal');
  document.getElementById('user-modal-title').textContent = isEdit ? '编辑用户' : '新建用户';
  // 重置表单
  document.getElementById('um-id').value = uid || '';
  document.getElementById('um-username').value = '';
  document.getElementById('um-display_name').value = '';
  document.getElementById('um-email').value = '';
  document.getElementById('um-role').value = 'user';
  document.getElementById('um-password').value = '';
  document.getElementById('um-pwd-label').textContent = isEdit ? '重置密码（留空则不修改）' : '密码 *（至少 6 位）';
  if (isEdit) {
    document.getElementById('um-username').disabled = true;
    // 拉取当前信息
    const params = new URLSearchParams({ page: 1, size: 200 });
    const res = await api('/api/users?' + params.toString());
    const u = res.items && res.items.find(x => x.id === uid);
    if (u) {
      document.getElementById('um-username').value = u.username;
      document.getElementById('um-display_name').value = u.display_name || '';
      document.getElementById('um-email').value = u.email || '';
      document.getElementById('um-role').value = u.role;
    }
  } else {
    document.getElementById('um-username').disabled = false;
  }
  modal.style.display = 'flex';
  document.getElementById('user-save').onclick = async () => {
    const data = {
      username: document.getElementById('um-username').value.trim(),
      display_name: document.getElementById('um-display_name').value.trim(),
      email: document.getElementById('um-email').value.trim(),
      role: document.getElementById('um-role').value,
      password: document.getElementById('um-password').value,
    };
    if (!isEdit) {
      if (!data.username || !data.password) return toast('用户名和密码必填', 'warn');
      const res = await api('/api/users', { method: 'POST', body: data });
      if (res.error) return toast(res.error, 'error');
      toast('✓ 用户已创建', 'ok');
    } else {
      const body = { display_name: data.display_name, email: data.email, role: data.role };
      if (data.password) body.password = data.password;
      const res = await api('/api/users/' + uid, { method: 'PUT', body });
      if (res.error) return toast(res.error, 'error');
      toast('✓ 用户已更新', 'ok');
    }
    modal.style.display = 'none';
    loadUsers();
  };
}

/* ============ PAGE · 系统设置 ============ */
function initSettings() {
  // 非管理员禁用保存按钮 + 输入框只读
  const admin = isAdmin();
  const saveBtn = document.getElementById('st-save');
  if (saveBtn) { saveBtn.disabled = !admin; saveBtn.title = admin ? '' : '仅管理员可修改'; }
  ['st-site_title', 'st-default_data_source', 'st-allow_guest_browse', 'st-allow_register', 'st-default_register_role', 'st-max_upload_size_mb', 'st-history_retention_days'].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.disabled = !admin;
  });
  loadSettings();
}
async function loadSettings() {
  const res = await api('/api/settings');
  if (res.error) return toast(res.error, 'error');
  const s = res.settings || {};
  ['site_title', 'default_data_source', 'allow_guest_browse', 'allow_register', 'default_register_role', 'max_upload_size_mb', 'history_retention_days'].forEach(k => {
    const el = document.getElementById('st-' + k);
    if (el && s[k] !== undefined) el.value = s[k];
  });
}
document.getElementById('st-save').addEventListener('click', async () => {
  const settings = {};
  ['site_title', 'default_data_source', 'allow_guest_browse', 'allow_register', 'default_register_role', 'max_upload_size_mb', 'history_retention_days'].forEach(k => {
    const el = document.getElementById('st-' + k);
    if (el) settings[k] = el.value;
  });
  const res = await api('/api/settings', { method: 'PUT', body: { settings } });
  if (res.error) return toast(res.error, 'error');
  toast('✓ 设置已保存', 'ok');
});

/* ============ INIT ============ */
/* 启动时先检查登录，再根据 hash 恢复页面 */
checkAuth().then(() => {
  const initialPage = (location.hash || '').replace('#', '');
  if (initialPage && document.getElementById('page-' + initialPage)) {
    navigate(initialPage);
  } else {
    navigate('dashboard');
  }
  toast('✓ FORGE 系统就绪 · 论文对齐版（11 页面）');
});
