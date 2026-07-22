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
      <div class="form-grid" style="max-width:520px">
        <div>
          <label class="field-label">测试集比例 {{ testSize.toFixed(2) }}</label>
          <el-slider v-model="testSize" :min="0.1" :max="0.4" :step="0.05" />
        </div>
        <div>
          <label class="field-label">交叉验证折数 {{ cvFolds }}</label>
          <el-slider v-model="cvFolds" :min="3" :max="10" :step="1" />
        </div>
      </div>
      <div class="toolbar" style="margin-top:12px">
        <el-button type="primary" :disabled="auth.isGuest" :loading="running" @click="run">
          运行 {{ section }} 节对比实验
        </el-button>
        <el-button plain :disabled="!tableRows.length" @click="clearSaved">清除本页记录</el-button>
        <span class="tag-pill" :class="tagClass">{{ tag }}</span>
        <span v-if="restoredHint" style="color:var(--text-faint);font-size:12px">{{ restoredHint }}</span>
      </div>
    </div>

    <div class="page-card">
      <h3>对比结果</h3>
      <el-table :data="tableRows" stripe border size="small" empty-text="点击运行后显示结果" v-loading="running">
        <el-table-column prop="model" label="模型" width="180" />
        <el-table-column prop="dataset" label="数据集" width="100" />
        <el-table-column prop="rmse" label="RMSE (HV)" />
        <el-table-column prop="mae" label="MAE (HV)" />
        <el-table-column prop="r2" label="R²" />
        <el-table-column prop="mape" label="MAPE (%)" />
      </el-table>
    </div>

    <div class="page-card">
      <h3>预测 vs 真实散点</h3>
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
const section = computed(() => `5.${props.pageId}`)
const headerSub = computed(() =>
  props.pageId === '53'
    ? '第 5.3 节 · 材料维氏硬度预测比较（原始数据）'
    : '第 5.4 节 · 数据扩充对算法性能影响分析',
)
const headerTitle = computed(() => (props.pageId === '53' ? '5.3' : '5.4'))
const headerEm = computed(() =>
  props.pageId === '53' ? '材料硬度预测比较' : '数据扩充比较',
)
const headerDesc = computed(() =>
  props.pageId === '53'
    ? '原始 149 条实测数据上，对比算法仅保留论文 5.1 节的 LR / PR / SVR 与本文 DDPG；评估指标为论文 5.2 节的 RMSE / MAE / R² / MAPE（表 1-2）。运行结果会自动保存。'
    : 'GAN 扩充后 10149 条数据上，同样仅对比 LR / PR / SVR / DDPG（表 3-4）。运行结果会自动保存，切换页面后仍可回看。',
)

const MODEL_SCATTER_KEY = {
  LinearRegression: 'lr',
  PolynomialRegression: 'pr',
  SVR: 'svr',
  DDPG: 'ddpg',
}

const picked = ref(['LinearRegression', 'PolynomialRegression', 'SVR', 'DDPG'])
const testSize = ref(0.2)
const cvFolds = ref(5)
const running = ref(false)
const tag = ref('待运行')
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

const tagClass = computed(() => (tag.value === '已完成' ? 'success' : tag.value === '失败' ? 'danger' : ''))
const scatterHint = computed(() =>
  scatterSource.value === 'run'
    ? '下方散点来自本次运行的测试集预测结果（已本地保存）。'
    : '下方为论文预置散点（便于对照复现）；点击「运行对比实验」后将替换为本次训练结果并自动保存。',
)

function toggle(key) {
  const i = picked.value.indexOf(key)
  if (i >= 0) picked.value.splice(i, 1)
  else picked.value.push(key)
}

function setChartEl(key, el) {
  if (el) chartEls[key] = el
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
    cvFolds: cvFolds.value,
    tag: tag.value,
    tableRows: tableRows.value,
    scatterSource: scatterSource.value,
    scatterByKey: slimScatter,
  })

  const ddpgTest = tableRows.value.find((r) => (r.model === 'DDPG' || r.model === '') && r.dataset === '测试集')
    || tableRows.value.find((r) => String(r.model).includes('DDPG'))
  results.addHistory({
    type: section.value,
    pageKey: pageKey.value,
    title: `${section.value} · ${props.dataSource === 'gan' ? 'GAN 扩充' : '原始数据'}`,
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
  if (saved.cvFolds != null) cvFolds.value = saved.cvFolds
  tag.value = saved.tag || '已完成'
  tableRows.value = saved.tableRows || []
  scatterSource.value = saved.scatterSource || 'run'
  lastScatterByKey.value = saved.scatterByKey || {}
  if (saved.savedAt) {
    restoredHint.value = `已恢复上次结果 · ${new Date(saved.savedAt).toLocaleString()}`
  }
  return true
}

function clearSaved() {
  results.clearPage(pageKey.value)
  tableRows.value = []
  tag.value = '待运行'
  restoredHint.value = ''
  lastScatterByKey.value = {}
  renderPaperScatters()
  ElMessage.success('已清除本页保存的对比结果')
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
      cv_folds: cvFolds.value,
      data_source: props.dataSource,
    })
    if (res.error) {
      running.value = false
      tag.value = '失败'
      ElMessage.error(res.error)
      return
    }
    ;(res.models || []).forEach((m) => {
      rows.push({
        model: m.model + (m.error ? ' [ERR]' : ''),
        dataset: '测试集',
        rmse: m.rmse != null ? (+m.rmse).toFixed(2) : '—',
        mae: m.mae != null ? (+m.mae).toFixed(2) : '—',
        r2: m.r2 != null ? (+m.r2).toFixed(4) : '—',
        mape: m.mape != null ? (+m.mape).toFixed(2) : '—',
      })
      const sk = MODEL_SCATTER_KEY[m.model]
      if (sk && m.scatter?.length) scatterByKey[sk] = m.scatter
      if (m.error) failed = true
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
        ;['train', 'val', 'test'].forEach((k) => {
          rows.push({
            model: k === 'train' ? 'DDPG' : '',
            dataset: { train: '训练集', val: '验证集', test: '测试集' }[k],
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

  running.value = false
  if (failed) {
    tag.value = '失败'
    ElMessage.warning(`${section.value} 节对比实验部分失败，请查看结果表`)
  } else {
    tag.value = '已完成'
    ElMessage.success(`${section.value} 节对比实验完成，结果已保存`)
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
