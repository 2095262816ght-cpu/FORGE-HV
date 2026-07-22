<template>
  <div>
    <PageHeader
      sub="第 2 章 · 数据准备与预处理"
      title="数据"
      em="可视化"
      desc="高温合金数据集：149 条实测样本。每条样本 = 70 维微观结构特征（DINOv2-Base + PCA）+ 22 维成分特征 + 1 维维氏硬度 HV。支持导入 Excel/CSV，数据会持久保存到服务端。"
    />
    <div class="metrics-row">
      <div class="metric-card">
        <div class="metric-label">样本数</div>
        <div class="metric-val">{{ sampleCount }}</div>
        <div class="metric-sub">论文：149 条</div>
      </div>
      <div class="metric-card">
        <div class="metric-label">微结构特征</div>
        <div class="metric-val">{{ stats.n_microstructure ?? 70 }}</div>
        <div class="metric-sub">DINOv2 + PCA</div>
      </div>
      <div class="metric-card">
        <div class="metric-label">成分特征</div>
        <div class="metric-val">{{ stats.n_elements ?? 22 }}</div>
        <div class="metric-sub">Al / Ti / Ni …</div>
      </div>
      <div class="metric-card">
        <div class="metric-label">目标 · HV 均值</div>
        <div class="metric-val">{{ fmt(stats.hv_mean) }}</div>
        <div class="metric-sub">{{ sourceLabel }}</div>
      </div>
    </div>

    <div class="page-card">
      <h3>数据导入与持久化</h3>
      <p style="color:var(--text-dim);font-size:12px;line-height:1.7;margin:0 0 12px">
        默认数据：项目内 <code>data_with_microstructure.xlsx</code>（149×93）。
        导入的 Excel/CSV 会保存到服务端 <code>generated_data/</code>，刷新页面或重启 ML 服务后仍会自动恢复，不会丢。
      </p>
      <div class="toolbar">
        <el-button type="primary" :disabled="auth.isGuest" :loading="uploading" @click="fileRef?.click()">
          导入数据文件
        </el-button>
        <el-button :disabled="auth.isGuest" :loading="resetting" @click="resetData">恢复默认数据</el-button>
        <el-button :loading="loading" @click="reloadAll">刷新数据</el-button>
        <span class="tag-pill" :class="usingUploaded ? 'success' : ''">{{ sourceLabel }}</span>
        <span style="color:var(--text-faint);font-size:12px">{{ uploadInfo }}</span>
        <input ref="fileRef" type="file" accept=".xlsx,.xls,.csv" hidden @change="onUpload" />
      </div>
    </div>

    <div class="page-card">
      <h3>元素含量分布</h3>
      <div class="chip-row">
        <span class="chip" :class="{ on: distType === 'median' }" @click="distType = 'median'">中位数柱状图</span>
        <span class="chip" :class="{ on: distType === 'range' }" @click="distType = 'range'">Q1–Q3 区间</span>
      </div>
      <div ref="distEl" class="chart-box"></div>
    </div>

    <div class="page-card">
      <h3>维氏硬度 HV 分布</h3>
      <div ref="histEl" class="chart-box sm"></div>
    </div>

    <div class="page-card">
      <h3>数据预览 · 结构分栏</h3>
      <div class="chip-row">
        <span class="chip" :class="{ on: previewTab === 'comp' }" @click="previewTab = 'comp'">22 维成分</span>
        <span class="chip" :class="{ on: previewTab === 'micro' }" @click="previewTab = 'micro'">70 维微结构</span>
        <span class="chip" :class="{ on: previewTab === 'hv' }" @click="previewTab = 'hv'">硬度 HV</span>
        <span class="chip" :class="{ on: previewTab === 'all' }" @click="previewTab = 'all'">全部列</span>
      </div>
      <el-table :data="previewRows" stripe border max-height="360" size="small" empty-text="暂无预览数据">
        <el-table-column
          v-for="col in previewColumns"
          :key="col"
          :prop="col"
          :label="col"
          min-width="90"
          show-overflow-tooltip
        />
      </el-table>
    </div>
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { get, post, upload } from '@/api/http'
import { useAuthStore } from '@/stores/auth'
import { ELEMENTS } from '@/utils/constants'
import { useEChart } from '@/utils/echarts'
import PageHeader from '@/components/PageHeader.vue'

defineOptions({ name: 'DashboardView' })

const CACHE_KEY = 'forge_dashboard_cache'

const auth = useAuthStore()
const stats = ref({})
const usingUploaded = ref(false)
const uploadInfo = ref('默认：data_with_microstructure.xlsx')
const uploading = ref(false)
const resetting = ref(false)
const loading = ref(false)
const fileRef = ref(null)
const distType = ref('median')
const previewTab = ref('comp')
const previewRaw = ref({ columns: [], rows: [] })

const { elRef: distEl, setOption: setDistOption } = useEChart()
const { elRef: histEl, setOption: setHistOption } = useEChart()

const sourceLabel = computed(() => (usingUploaded.value ? '使用上传数据' : '使用默认数据'))
const sampleCount = computed(() => {
  const n = stats.value.n_rows ?? stats.value.n_samples ?? stats.value.total
  return n == null || n === '' ? '—' : n
})

function fmt(v) {
  return v == null || Number.isNaN(+v) ? '—' : (+v).toFixed(1)
}

function applyStats(res) {
  if (!res || res.error) return
  stats.value = res
  usingUploaded.value = !!res.using_uploaded
  const n = res.n_rows ?? res.n_samples
  if (res.filename) {
    uploadInfo.value = `当前：${res.filename}${n != null ? ` · ${n} 行` : ''}`
  } else if (!res.using_uploaded) {
    uploadInfo.value = `默认：data_with_microstructure.xlsx${n != null ? ` · ${n} 行` : ''}`
  }
  try {
    localStorage.setItem(CACHE_KEY, JSON.stringify({
      stats: res,
      preview: previewRaw.value,
      savedAt: Date.now(),
    }))
  } catch {
    /* ignore quota */
  }
}

function restoreCache() {
  try {
    const raw = localStorage.getItem(CACHE_KEY)
    if (!raw) return false
    const cached = JSON.parse(raw)
    if (!cached?.stats) return false
    stats.value = cached.stats
    usingUploaded.value = !!cached.stats.using_uploaded
    if (cached.preview?.columns) previewRaw.value = cached.preview
    const n = cached.stats.n_rows ?? cached.stats.n_samples
    if (cached.stats.filename) {
      uploadInfo.value = `缓存：${cached.stats.filename}${n != null ? ` · ${n} 行` : ''}`
    }
    return true
  } catch {
    return false
  }
}

const previewColumns = computed(() => {
  const cols = previewRaw.value.columns || []
  if (previewTab.value === 'comp') {
    return cols.filter((c) => ELEMENTS.includes(c) || c === '_row_id' || /sample|id|image/i.test(c)).slice(0, 24)
  }
  if (previewTab.value === 'micro') {
    const micro = cols.filter((c) =>
      /micro|pca|feat|dino|struct|pc\d+|feature_?\d+/i.test(c) && !ELEMENTS.includes(c),
    )
    if (micro.length) return micro.slice(0, 20)
    return cols
      .filter((c) => !ELEMENTS.includes(c) && !/hv|hardness|vickers|image/i.test(c))
      .slice(0, 20)
  }
  if (previewTab.value === 'hv') return cols.filter((c) => /hv|hardness|vickers|_row_id|sample|id|image/i.test(c))
  return cols.slice(0, 20)
})

const previewRows = computed(() => {
  const cols = previewColumns.value
  const rows = previewRaw.value.rows || previewRaw.value.items || []
  return rows.map((r) => {
    if (Array.isArray(r)) {
      const obj = {}
      ;(previewRaw.value.columns || []).forEach((c, i) => { obj[c] = r[i] })
      const out = {}
      cols.forEach((c) => { out[c] = obj[c] })
      return out
    }
    const out = {}
    cols.forEach((c) => { out[c] = r[c] })
    return out
  })
})

function renderDist() {
  const elemStats = stats.value.element_stats || stats.value.elements || {}
  const labels = ELEMENTS.filter((e) => elemStats[e])
  const useLabels = labels.length ? labels : ELEMENTS
  if (distType.value === 'median') {
    const data = useLabels.map((e) => elemStats[e]?.median ?? elemStats[e]?.med ?? elemStats[e]?.mean ?? 0)
    setDistOption({
      title: { text: '元素含量中位数对比 (wt %)', left: 0, textStyle: { fontSize: 13, color: '#0F172A' } },
      tooltip: { trigger: 'axis' },
      grid: { left: 50, right: 20, top: 40, bottom: 30 },
      xAxis: { type: 'value', axisLabel: { color: '#64748B' }, splitLine: { lineStyle: { color: 'rgba(15,23,42,.06)' } } },
      yAxis: { type: 'category', data: useLabels, axisLabel: { color: '#475569', fontSize: 10 } },
      series: [{ type: 'bar', data, itemStyle: { color: 'rgba(37,99,235,.55)' }, barWidth: 10 }],
    })
  } else {
    const data = useLabels.map((e) => {
      const s = elemStats[e] || {}
      return [s.q1 ?? 0, s.q3 ?? 0]
    })
    setDistOption({
      title: { text: '元素含量 Q1–Q3 区间 (wt %)', left: 0, textStyle: { fontSize: 13, color: '#0F172A' } },
      tooltip: {
        trigger: 'axis',
        formatter: (params) => {
          const p = params[0]
          const [q1, q3] = p.value || [0, 0]
          return `${p.name}<br/>Q1: ${(+q1).toFixed(3)} · Q3: ${(+q3).toFixed(3)}`
        },
      },
      grid: { left: 50, right: 20, top: 40, bottom: 30 },
      xAxis: { type: 'value', axisLabel: { color: '#64748B' }, splitLine: { lineStyle: { color: 'rgba(15,23,42,.06)' } } },
      yAxis: { type: 'category', data: useLabels, axisLabel: { color: '#475569', fontSize: 10 } },
      series: [{
        type: 'custom',
        renderItem(params, api) {
          const catIndex = api.value(0)
          const q1 = api.value(1)
          const q3 = api.value(2)
          const y = api.coord([0, catIndex])[1]
          const x1 = api.coord([q1, catIndex])[0]
          const x2 = api.coord([q3, catIndex])[0]
          return {
            type: 'rect',
            shape: { x: x1, y: y - 5, width: Math.max(x2 - x1, 1), height: 10 },
            style: api.style({ fill: 'rgba(37,99,235,.28)', stroke: '#2563EB' }),
          }
        },
        data: data.map((d, i) => [i, d[0], d[1]]),
        encode: { x: [1, 2], y: 0 },
      }],
    })
  }
}

function renderHist() {
  const hist = stats.value.hv_hist || stats.value.target_hist || {}
  let labels = hist.bins || hist.labels || []
  let counts = hist.counts || hist.values || []
  if (!labels.length || !counts.length) {
    setHistOption({
      title: {
        text: '维氏硬度 HV 分布（暂无数据）',
        left: 'center',
        top: 'middle',
        textStyle: { color: '#94A3B8', fontSize: 13, fontWeight: 400 },
      },
      xAxis: { show: false },
      yAxis: { show: false },
      series: [],
    })
    return
  }
  if (labels.length === counts.length + 1) {
    labels = labels.slice(0, -1).map((v, i) => `${(+v).toFixed(0)}–${(+labels[i + 1]).toFixed(0)}`)
  }
  setHistOption({
    title: { text: '维氏硬度 HV 分布', left: 0, textStyle: { fontSize: 13, color: '#0F172A' } },
    tooltip: { trigger: 'axis' },
    grid: { left: 40, right: 16, top: 40, bottom: 50 },
    xAxis: { type: 'category', data: labels, axisLabel: { color: '#64748B', rotate: 45, fontSize: 10 } },
    yAxis: { type: 'value', axisLabel: { color: '#64748B' }, splitLine: { lineStyle: { color: 'rgba(15,23,42,.06)' } } },
    series: [{
      type: 'bar',
      data: counts,
      itemStyle: {
        color: (p) => (p.dataIndex > 7 && p.dataIndex < 13 ? '#2563EB' : 'rgba(37,99,235,.35)'),
      },
    }],
  })
}

async function loadStats() {
  const res = await get('/api/data/stats')
  if (res.error) {
    ElMessage.warning(res.error)
    await nextTick()
    renderDist()
    renderHist()
    return
  }
  applyStats(res)
  await nextTick()
  renderDist()
  renderHist()
}

async function loadPreview() {
  const res = await get('/api/data/preview', { limit: 20, n: 20 })
  if (res.error) return
  if (res.columns && res.rows) {
    previewRaw.value = res
  } else if (res.items) {
    const cols = res.columns || Object.keys(res.items[0] || {})
    previewRaw.value = { columns: cols, rows: res.items }
  }
  // 同步写入缓存
  try {
    const raw = localStorage.getItem(CACHE_KEY)
    const cached = raw ? JSON.parse(raw) : { stats: stats.value }
    cached.preview = previewRaw.value
    cached.savedAt = Date.now()
    localStorage.setItem(CACHE_KEY, JSON.stringify(cached))
  } catch {
    /* ignore */
  }
}

async function reloadAll() {
  loading.value = true
  try {
    await loadStats()
    await loadPreview()
    ElMessage.success('数据已刷新')
  } finally {
    loading.value = false
  }
}

async function onUpload(e) {
  const file = e.target.files?.[0]
  if (!file) return
  uploading.value = true
  const fd = new FormData()
  fd.append('file', file)
  const res = await upload('/api/data/upload', fd)
  uploading.value = false
  e.target.value = ''
  if (res.error) {
    ElMessage.error(`上传失败：${res.error}`)
    return
  }
  usingUploaded.value = true
  const n = res.n_rows ?? res.n_samples
  uploadInfo.value = `当前：${res.filename} · ${n} 行 × ${res.n_cols} 列`
  ElMessage.success(`数据导入成功：${res.filename}（已持久保存）`)
  await loadStats()
  await loadPreview()
}

async function resetData() {
  resetting.value = true
  const res = await post('/api/data/reset', {})
  resetting.value = false
  if (res.error) {
    ElMessage.error(res.error)
    return
  }
  usingUploaded.value = false
  uploadInfo.value = '默认：data_with_microstructure.xlsx'
  ElMessage.success('已恢复默认数据')
  await loadStats()
  await loadPreview()
}

watch(distType, () => nextTick().then(renderDist))

onMounted(async () => {
  const hadCache = restoreCache()
  if (hadCache) {
    await nextTick()
    renderDist()
    renderHist()
  }
  await loadStats()
  await loadPreview()
})
</script>
