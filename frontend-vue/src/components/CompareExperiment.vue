<template>
  <div>
    <PageHeader
      :sub="headerSub"
      :title="headerTitle"
      :em="headerEm"
      :desc="headerDesc"
    />
    <div class="page-card">
      <div class="chip-row">
        <span
          v-for="m in COMPARE_MODELS"
          :key="m.key"
          class="chip"
          :class="{ on: picked.includes(m.key) }"
          @click="toggle(m.key)"
        >{{ m.label }}</span>
      </div>
      <div class="form-grid" style="max-width:360px">
        <div>
          <label class="field-label">测试集比例 {{ testSize.toFixed(2) }}</label>
          <el-slider v-model="testSize" :min="0.1" :max="0.4" :step="0.05" />
        </div>
      </div>
      <div class="toolbar" style="margin-top:12px">
        <el-button type="primary" :disabled="auth.isGuest" :loading="running" @click="run">
          运行对比实验
        </el-button>
        <span v-if="restoredHint" style="color:var(--text-faint);font-size:12px">{{ restoredHint }}</span>
      </div>
    </div>

    <div class="page-card" v-loading="running">
      <h3>{{ trainTableTitle }}</h3>
      <p style="color:var(--text-dim);font-size:12px;margin:0 0 12px;line-height:1.6">
        指标与论文一致：RMSE、MAE、R²、MAPE。模型：DDPG / LR / PR / SVR。
        <span v-if="resultSourceHint">{{ resultSourceHint }}</span>
      </p>
      <el-table :data="trainRows" stripe border size="small" empty-text="点击运行后显示结果">
        <el-table-column prop="model" label="模型" width="100" />
        <el-table-column prop="dataset" label="数据集类型" width="110" />
        <el-table-column prop="rmse" label="RMSE(HV)" />
        <el-table-column prop="mae" label="MAE(HV)" />
        <el-table-column prop="r2" label="R²" />
        <el-table-column prop="mape" label="MAPE(%)" />
      </el-table>
    </div>

    <div class="page-card">
      <h3>{{ testTableTitle }}</h3>
      <p style="color:var(--text-dim);font-size:12px;margin:0 0 12px;line-height:1.6">
        与上表同一实验划分；仅展示测试集指标，便于对照泛化性能。
      </p>
      <el-table :data="testRows" stripe border size="small" empty-text="点击运行后显示结果" v-loading="running">
        <el-table-column prop="model" label="模型" width="100" />
        <el-table-column prop="dataset" label="数据集类型" width="110" />
        <el-table-column prop="rmse" label="RMSE(HV)" />
        <el-table-column prop="mae" label="MAE(HV)" />
        <el-table-column prop="r2" label="R²" />
        <el-table-column prop="mape" label="MAPE(%)" />
      </el-table>
    </div>

    <div class="page-card">
      <h3>预测 vs 真实散点（测试集）</h3>
      <p style="color:var(--text-dim);font-size:12px;margin:0 0 12px;line-height:1.6">
        {{ scatterHint }}
      </p>
      <div class="scatter-grid">
        <div v-for="m in scatterModels" :key="m.key" class="page-card" style="margin:0;padding:12px">
          <div style="font-weight:600;margin-bottom:8px">{{ m.label }}</div>
          <div :ref="(el) => setChartEl(m.key, el)" class="chart-box sm"></div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import * as echarts from 'echarts'
import { computed, nextTick, onActivated, onBeforeUnmount, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { get, post } from '@/api/http'
import { useAuthStore } from '@/stores/auth'
import { useResultsStore } from '@/stores/results'
import { COMPARE_MODELS } from '@/utils/constants'
import { idealLine } from '@/utils/echarts'
import { SCATTER_DATA } from '@/data/scatter_data.js'
import PageHeader from '@/components/PageHeader.vue'

const props = defineProps({
  pageId: { type: String, required: true }, // '53' | '54'
  dataSource: { type: String, required: true }, // 'real' | 'gan'
})

const auth = useAuthStore()
const results = useResultsStore()
const pageKey = computed(() => `cmp${props.pageId}`)
const prefix = computed(() => `cmp${props.pageId}`)
const expLabel = computed(() =>
  props.pageId === '53' ? '材料硬度预测比较' : '数据扩充比较',
)
const headerSub = computed(() =>
  props.pageId === '53'
    ? '原始 149 条实测数据'
    : 'GAN 扩充数据 · 对算法性能影响分析',
)
const headerTitle = computed(() => (props.pageId === '53' ? '材料硬度' : '数据扩充'))
const headerEm = computed(() =>
  props.pageId === '53' ? '预测比较' : '比较',
)
const headerDesc = computed(() =>
  props.pageId === '53'
    ? '对比算法：LR、PR、SVR 与 DDPG。评估指标：RMSE / MAE / R² / MAPE。结果同时给出训练集与测试集，运行后自动保存。'
    : '在 GAN 扩充后的数据上，同样对比 LR / PR / SVR / DDPG。结果同时给出训练集与测试集，运行后自动保存。',
)

const MODEL_LABEL = {
  LinearRegression: 'LR',
  PolynomialRegression: 'PR',
  SVR: 'SVR',
  DDPG: 'DDPG',
}

const MODEL_SCATTER_KEY = {
  LinearRegression: 'lr',
  PolynomialRegression: 'pr',
  SVR: 'svr',
  DDPG: 'ddpg',
}

/** 论文表 1/2（原始数据）与表 3/4（GAN 数据）预置结果 */
const PAPER_TABLES = {
  '53': {
    train: [
      { model: 'DDPG', dataset: '训练集', rmse: '8.05', mae: '5.20', r2: '0.9904', mape: '1.42' },
      { model: 'LR', dataset: '训练集', rmse: '14.67', mae: '11.18', r2: '0.9733', mape: '2.73' },
      { model: 'PR', dataset: '训练集', rmse: '20.20', mae: '14.61', r2: '0.9494', mape: '3.79' },
      { model: 'SVR', dataset: '训练集', rmse: '44.97', mae: '22.50', r2: '0.7493', mape: '6.78' },
    ],
    test: [
      { model: 'DDPG', dataset: '测试集', rmse: '70.67', mae: '45.69', r2: '0.3304', mape: '14.88' },
      { model: 'LR', dataset: '测试集', rmse: '203.63', mae: '142.39', r2: '-4.6463', mape: '43.31' },
      { model: 'PR', dataset: '测试集', rmse: '201.46', mae: '125.38', r2: '-4.5262', mape: '40.42' },
      { model: 'SVR', dataset: '测试集', rmse: '88.22', mae: '65.16', r2: '-0.0597', mape: '20.57' },
    ],
  },
  '54': {
    train: [
      { model: 'DDPG', dataset: '训练集', rmse: '15.45', mae: '6.09', r2: '0.9641', mape: '1.47' },
      { model: 'LR', dataset: '训练集', rmse: '15.45', mae: '10.33', r2: '0.9526', mape: '2.56' },
      { model: 'PR', dataset: '训练集', rmse: '1.23', mae: '0.83', r2: '0.9997', mape: '0.20' },
      { model: 'SVR', dataset: '训练集', rmse: '16.93', mae: '9.51', r2: '0.9431', mape: '2.35' },
    ],
    test: [
      { model: 'DDPG', dataset: '测试集', rmse: '14.95', mae: '5.84', r2: '0.9665', mape: '1.41' },
      { model: 'LR', dataset: '测试集', rmse: '17.73', mae: '10.71', r2: '0.9386', mape: '2.61' },
      { model: 'PR', dataset: '测试集', rmse: '1498.13', mae: '191.37', r2: '-437.1577', mape: '46.88' },
      { model: 'SVR', dataset: '测试集', rmse: '19.33', mae: '9.95', r2: '0.9270', mape: '2.42' },
    ],
  },
}

const picked = ref(['LinearRegression', 'PolynomialRegression', 'SVR', 'DDPG'])
const testSize = ref(0.2)
const running = ref(false)
const tag = ref('论文预置')
const tableRows = ref([])
const scatterSource = ref('paper') // 'paper' | 'run'
const restoredHint = ref('')
const lastScatterByKey = ref({})
const scatterModels = [
  { key: 'ddpg', label: 'DDPG', color: '#2563EB' },
  { key: 'lr', label: 'LR', color: '#0EA5E9' },
  { key: 'pr', label: 'PR', color: '#0284C7' },
  { key: 'svr', label: 'SVR', color: '#F59E0B' },
]
const chartEls = {}
const charts = {}

const paperBundle = computed(() => PAPER_TABLES[props.pageId] || PAPER_TABLES['53'])
const trainTableTitle = computed(() =>
  props.pageId === '54'
    ? '表（训练集）使用 GAN 数据的结果及对比'
    : '表（训练集）原始数据结果对比',
)
const testTableTitle = computed(() =>
  props.pageId === '54'
    ? '表（测试集）使用 GAN 数据的结果及对比'
    : '表（测试集）原始数据结果对比',
)
const resultSourceHint = computed(() =>
  scatterSource.value === 'run'
    ? '当前为本次运行结果。'
    : '当前为论文预置结果，运行实验后将替换为实测值。',
)

function normalizeRows(rows) {
  let lastModel = ''
  return (rows || [])
    .filter((r) => r && (r.dataset === '训练集' || r.dataset === '测试集'))
    .map((r) => {
      const raw = String(r.model || '').trim()
      const mapped = MODEL_LABEL[raw] || raw || lastModel || '—'
      if (mapped && mapped !== '—') lastModel = mapped.replace(' [ERR]', '')
      return {
        model: mapped,
        dataset: r.dataset,
        rmse: r.rmse,
        mae: r.mae,
        r2: r.r2,
        mape: r.mape,
      }
    })
}

const displayRows = computed(() => {
  const rows = normalizeRows(tableRows.value)
  if (rows.length) return rows
  return [...paperBundle.value.train, ...paperBundle.value.test]
})
const trainRows = computed(() => displayRows.value.filter((r) => r.dataset === '训练集'))
const testRows = computed(() => displayRows.value.filter((r) => r.dataset === '测试集'))

const scatterHint = computed(() =>
  scatterSource.value === 'run'
    ? '下方散点来自本次运行的测试集预测结果（已本地保存）。'
    : '下方为论文预置散点（便于对照）；点击「运行对比实验」后将替换为本次训练结果并自动保存。',
)

function toggle(key) {
  const i = picked.value.indexOf(key)
  if (i >= 0) picked.value.splice(i, 1)
  else picked.value.push(key)
}

function setChartEl(key, el) {
  if (el) chartEls[key] = el
}

function fmtMetric(v, digits) {
  if (v == null || Number.isNaN(+v)) return '—'
  return (+v).toFixed(digits)
}

/** 兼容 snake_case / camelCase / 论文中文键名 */
function pickMetrics(block, fallback = null) {
  const src = block || fallback
  if (!src || typeof src !== 'object') return null
  const rmse = src.rmse ?? src.RMSE_value ?? src['RMSE (HV)'] ?? src['RMSE(HV)']
  const mae = src.mae ?? src.MAE_value ?? src['MAE (HV)'] ?? src['MAE(HV)']
  const r2 = src.r2 ?? src.R2_value ?? src['R²'] ?? src.R2
  const mape = src.mape ?? src.MAPE_value ?? src['MAPE (%)'] ?? src['MAPE(%)']
  if (rmse == null && mae == null && r2 == null && mape == null) return null
  return { rmse, mae, r2, mape }
}

function metricsFromModel(m, which) {
  if (!m) return null
  if (which === 'train') {
    return pickMetrics(
      m.train_metrics || m.trainMetrics || m.train,
      {
        r2: m.train_r2 ?? m.trainR2,
        rmse: m.train_rmse ?? m.trainRmse,
        mae: m.train_mae ?? m.trainMae,
        mape: m.train_mape ?? m.trainMape,
      },
    )
  }
  return pickMetrics(
    m.test_metrics || m.testMetrics || m.test,
    { r2: m.r2, rmse: m.rmse, mae: m.mae, mape: m.mape },
  )
}

function pushSplitRows(rows, modelName, trainM, testM, failed = false) {
  const label = MODEL_LABEL[modelName] || modelName
  const suffix = failed ? ' [ERR]' : ''
  // 论文表格式：每一行都写模型名（DDPG / LR / PR / SVR）
  if (trainM) {
    rows.push({
      model: label + suffix,
      dataset: '训练集',
      rmse: fmtMetric(trainM.rmse, 2),
      mae: fmtMetric(trainM.mae, 2),
      r2: fmtMetric(trainM.r2, 4),
      mape: fmtMetric(trainM.mape, 2),
    })
  }
  if (testM) {
    rows.push({
      model: label + suffix,
      dataset: '测试集',
      rmse: fmtMetric(testM.rmse, 2),
      mae: fmtMetric(testM.mae, 2),
      r2: fmtMetric(testM.r2, 4),
      mape: fmtMetric(testM.mape, 2),
    })
  }
}

function clearScatter(key) {
  const el = chartEls[key]
  if (!el) return
  if (charts[key]) charts[key].dispose()
  const chart = echarts.init(el)
  charts[key] = chart
  chart.setOption({
    title: {
      text: '暂无数据',
      left: 'center',
      top: 'middle',
      textStyle: { color: '#94A3B8', fontSize: 13, fontWeight: 400 },
    },
  })
}

function renderScatter(key, data, color, label) {
  const el = chartEls[key]
  if (!el) return
  if (!data?.length) {
    clearScatter(key)
    return
  }
  if (charts[key]) charts[key].dispose()
  const chart = echarts.init(el)
  charts[key] = chart
  const pts = data.map((p) => [p.x, p.y])
  const all = data.flatMap((p) => [p.x, p.y])
  const minV = Math.min(...all) - 10
  const maxV = Math.max(...all) + 10
  const symbolSize = data.length > 500 ? 4 : data.length > 100 ? 6 : 8
  chart.setOption({
    tooltip: { formatter: (p) => `真实: ${p.value[0].toFixed(1)} → 预测: ${p.value[1].toFixed(1)}` },
    grid: { left: 45, right: 12, top: 16, bottom: 36 },
    xAxis: { name: '真实 HV', min: minV, max: maxV, splitLine: { lineStyle: { color: 'rgba(15,23,42,.06)' } } },
    yAxis: { name: '预测 HV', min: minV, max: maxV, splitLine: { lineStyle: { color: 'rgba(15,23,42,.06)' } } },
    series: [
      { type: 'scatter', name: `${label} (${data.length})`, data: pts, symbolSize, itemStyle: { color } },
      idealLine(minV, maxV),
    ],
  })
}

function renderPaperScatters() {
  scatterSource.value = 'paper'
  const real = SCATTER_DATA?.[prefix.value] || {}
  scatterModels.forEach((m) => {
    renderScatter(m.key, real[m.key] || [], m.color, m.label)
  })
}

function renderRunScatters(byKey) {
  scatterSource.value = 'run'
  lastScatterByKey.value = byKey || {}
  scatterModels.forEach((m) => {
    renderScatter(m.key, byKey[m.key] || [], m.color, m.label)
  })
}

function persistResult() {
  const slimScatter = {}
  Object.entries(lastScatterByKey.value || {}).forEach(([k, pts]) => {
    slimScatter[k] = results.slimScatter(pts)
  })
  results.setPage(pageKey.value, {
    picked: [...picked.value],
    testSize: testSize.value,
    tag: tag.value,
    tableRows: tableRows.value,
    scatterSource: scatterSource.value,
    scatterByKey: slimScatter,
  })

  const ddpgTest = tableRows.value.find((r) => String(r.model).includes('DDPG') && r.dataset === '测试集')
  results.addHistory({
    type: expLabel.value,
    pageKey: pageKey.value,
    title: `${expLabel.value} · ${props.dataSource === 'gan' ? 'GAN 扩充' : '原始数据'}`,
    summary: ddpgTest
      ? `DDPG 测试集 R²=${ddpgTest.r2} · RMSE=${ddpgTest.rmse} · MAPE=${ddpgTest.mape}%`
      : `共 ${tableRows.value.length} 行结果 · ${tag.value}`,
    detail: {
      tableRows: tableRows.value,
      tag: tag.value,
      dataSource: props.dataSource,
    },
  })
}

function restoreResult() {
  const saved = results.getPage(pageKey.value)
  if (!saved?.tableRows?.length) return false
  if (saved.picked?.length) picked.value = [...saved.picked]
  if (saved.testSize != null) testSize.value = saved.testSize
  tag.value = saved.tag || '已完成'
  // 旧缓存可能含验证集 / 空模型名，过滤并规范化
  tableRows.value = normalizeRows(saved.tableRows)
  scatterSource.value = saved.scatterSource || 'run'
  lastScatterByKey.value = saved.scatterByKey || {}
  if (saved.savedAt) {
    restoredHint.value = `已恢复上次结果 · ${new Date(saved.savedAt).toLocaleString()}`
  }
  return true
}

function pollDdpg(taskId) {
  return new Promise((resolve) => {
    let elapsed = 0
    const timer = setInterval(async () => {
      elapsed++
      if (elapsed > 300) {
        clearInterval(timer)
        resolve(null)
        return
      }
      const res = await get(`/api/ddpg/status/${taskId}`)
      if (res.error || res.status === 'error') {
        clearInterval(timer)
        resolve(null)
        return
      }
      if (['done', 'completed', 'finished'].includes(res.status)) {
        clearInterval(timer)
        resolve(res)
        return
      }
      tag.value = `DDPG ${(res.progress || 0).toFixed?.(0) ?? res.progress ?? 0}%`
    }, 2000)
  })
}

async function run() {
  if (!picked.value.length) {
    ElMessage.warning('请至少选择一个算法')
    return
  }
  const traditional = picked.value.filter((m) => m !== 'DDPG')
  const wantDdpg = picked.value.includes('DDPG')
  running.value = true
  tag.value = '运行中'
  restoredHint.value = ''
  tableRows.value = []

  const rows = []
  const scatterByKey = {}
  let failed = false

  if (traditional.length) {
    const res = await post('/api/train/compare', {
      models: traditional,
      test_size: testSize.value,
      data_source: props.dataSource,
    })
    if (res.error) {
      running.value = false
      tag.value = '失败'
      ElMessage.error(res.error)
      return
    }
    ;(res.models || []).forEach((m) => {
      if (m.error) {
        failed = true
        rows.push({
          model: (MODEL_LABEL[m.model] || m.model) + ' [ERR]',
          dataset: '—',
          rmse: '—',
          mae: '—',
          r2: m.error,
          mape: '—',
        })
        return
      }
      const trainM = metricsFromModel(m, 'train')
      const testM = metricsFromModel(m, 'test')
      // 若训练集指标缺失但测试集有值，仍保证两行结构完整（避免只剩测试集）
      pushSplitRows(rows, m.model, trainM, testM)
      if (trainM == null && testM != null) {
        console.warn('[compare] missing train_metrics for', m.model, Object.keys(m || {}))
      }
      const sk = MODEL_SCATTER_KEY[m.model]
      if (sk && m.scatter?.length) scatterByKey[sk] = m.scatter
    })
    tableRows.value = [...rows]
  }

  if (wantDdpg) {
    tag.value = 'DDPG 训练中'
    const ddpgRes = await post('/api/ddpg/train', {
      data_source: props.dataSource,
      epochs: 500,
      batch_size: 32,
      lr_actor: 1e-4,
      lr_critic: 5e-4,
      test_size: testSize.value,
    })
    if (ddpgRes.error) {
      failed = true
      rows.push({ model: 'DDPG', dataset: '—', rmse: '—', mae: '—', r2: ddpgRes.error, mape: '—' })
    } else {
      const done = await pollDdpg(ddpgRes.task_id)
      if (done?.metrics) {
        const m = done.metrics
        // 与论文表一致：只展示训练集、测试集；每行都写 DDPG
        ;['train', 'test'].forEach((k) => {
          if (!m[k]) return
          const ds = { train: '训练集', test: '测试集' }[k]
          rows.push({
            model: 'DDPG',
            dataset: ds,
            rmse: (+m[k].rmse).toFixed(2),
            mae: (+m[k].mae).toFixed(2),
            r2: (+m[k].r2).toFixed(4),
            mape: (+(m[k].mape || 0)).toFixed(2),
          })
        })
        if (done.scatter?.length) scatterByKey.ddpg = done.scatter
      } else {
        failed = true
        rows.push({ model: 'DDPG', dataset: '—', rmse: '—', mae: '—', r2: '训练失败', mape: '—' })
      }
    }
    tableRows.value = [...rows]
  }

  if (Object.keys(scatterByKey).length) {
    renderRunScatters(scatterByKey)
  }

  // 按论文表顺序：DDPG → LR → PR → SVR
  const order = { DDPG: 0, LR: 1, PR: 2, SVR: 3 }
  rows.sort((a, b) => {
    const da = a.dataset === '训练集' ? 0 : 1
    const db = b.dataset === '训练集' ? 0 : 1
    if (da !== db) return da - db
    const ma = String(a.model).replace(' [ERR]', '')
    const mb = String(b.model).replace(' [ERR]', '')
    return (order[ma] ?? 9) - (order[mb] ?? 9)
  })
  tableRows.value = [...rows]
  scatterSource.value = 'run'

  running.value = false
  if (failed) {
    tag.value = '失败'
    ElMessage.warning(`${expLabel.value}部分失败，请查看结果表`)
  } else {
    tag.value = '已完成'
    ElMessage.success(`${expLabel.value}完成，结果已保存`)
  }
  if (tableRows.value.length) persistResult()
}

function onResize() {
  Object.values(charts).forEach((c) => c.resize())
}

async function boot() {
  await nextTick()
  const ok = restoreResult()
  setTimeout(() => {
    if (ok && Object.keys(lastScatterByKey.value || {}).length) {
      renderRunScatters(lastScatterByKey.value)
    } else {
      renderPaperScatters()
    }
  }, 50)
}

onMounted(() => {
  boot()
  window.addEventListener('resize', onResize)
})

onActivated(() => {
  setTimeout(() => {
    if (scatterSource.value === 'run' && Object.keys(lastScatterByKey.value || {}).length) {
      renderRunScatters(lastScatterByKey.value)
    } else if (tableRows.value.length === 0) {
      renderPaperScatters()
    } else {
      renderRunScatters(lastScatterByKey.value)
    }
  }, 30)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', onResize)
  Object.values(charts).forEach((c) => c.dispose())
})
</script>
