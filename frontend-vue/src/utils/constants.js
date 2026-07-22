/** 22 种合金元素列名（与后端 composition_columns 一致） */
export const ELEMENTS = [
  'Al', 'W', 'Ta', 'Ti', 'Cr', 'Ni', 'Mo', 'Hf', 'C', 'Co',
  'B', 'V', 'Si', 'Fe', 'Nb', 'Zr', 'Re', 'Cb', 'Ce', 'Mn', 'S', 'P',
]

/** 面包屑分类 — 只保留论文对应核心模块 */
export const CRUMB_CAT = {
  dashboard: '数据准备',
  outliers: '数据准备',
  correlation: '数据准备',
  ddpg: 'DDPG 模型',
  'ddpg-arch': 'DDPG 模型',
  'gan-process': '数据扩充',
  cmp53: '实验对比',
  cmp54: '实验对比',
  results: '实验记录',
  settings: '账户',
}

/** 页面中文名 — 严格对照论文术语 */
export const PAGE_NAMES = {
  dashboard: '数据可视化',
  outliers: '异常值检测',
  correlation: '元素相关性',
  ddpg: 'DDPG 训练',
  'ddpg-arch': 'DDPG 模型架构',
  'gan-process': '数据扩充过程',
  cmp53: '材料硬度预测比较',
  cmp54: '数据扩充比较',
  results: '训练结果记录',
  settings: '系统设置',
}

/**
 * 侧边栏导航 — 对应论文章节核心页面
 * 已删除：系统管理整组、数据库管理、重复的数据相关性页
 */
export const NAV_GROUPS = [
  {
    title: '数据准备 · 第 2 章',
    items: [
      { path: '/dashboard', name: 'dashboard', label: '数据可视化', icon: '◉' },
      { path: '/outliers', name: 'outliers', label: '异常值检测', icon: '⊙' },
      { path: '/correlation', name: 'correlation', label: '元素相关性', icon: '⌬' },
    ],
  },
  {
    title: 'DDPG 模型 · 第 3-4 章',
    items: [
      { path: '/ddpg-arch', name: 'ddpg-arch', label: 'DDPG 模型架构', icon: '⌬' },
      { path: '/ddpg', name: 'ddpg', label: 'DDPG 训练', icon: '⚡' },
    ],
  },
  {
    title: '数据扩充 · 第 5.4 章',
    items: [
      { path: '/gan-process', name: 'gan-process', label: '数据扩充过程', icon: '⊞' },
    ],
  },
  {
    title: '实验对比 · 第 5 章',
    items: [
      { path: '/cmp53', name: 'cmp53', label: '5.3 硬度预测比较', icon: '◆' },
      { path: '/cmp54', name: 'cmp54', label: '5.4 数据扩充比较', icon: '▦' },
      { path: '/results', name: 'results', label: '训练结果记录', icon: '⌚' },
    ],
  },
]

export const ROLE_LABELS = {
  admin: '管理员',
  user: '普通用户',
  guest: '游客',
}

/** 论文 5.1 节对比算法：LR / PR / SVR（+ 本文 DDPG） */
export const COMPARE_MODELS = [
  { key: 'LinearRegression', label: 'LR' },
  { key: 'PolynomialRegression', label: 'PR' },
  { key: 'SVR', label: 'SVR' },
  { key: 'DDPG', label: 'DDPG' },
]

/** 论文 5.2 节评估指标 */
export const EVAL_METRICS = ['RMSE', 'MAE', 'R²', 'MAPE']

/** 论文第 2 章：仅分位数截断 */
export const OUTLIER_METHODS = [
  { value: 'quantile_clip', label: '分位数截断（论文公式 1-3）' },
]

export const CORR_METHODS = [
  { value: 'pearson', label: 'Pearson' },
  { value: 'spearman', label: 'Spearman' },
  { value: 'kendall', label: 'Kendall' },
]
