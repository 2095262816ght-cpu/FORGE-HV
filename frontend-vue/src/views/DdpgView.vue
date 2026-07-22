<template>
  <div>
    <PageHeader
      sub="第 3-4 章 · 网络模型设计与训练策略"
      title="DDPG"
      em="模型训练"
      desc="深度确定性策略梯度（DDPG）回归框架：Actor-Critic 网络 + 优先经验回放 + 五段式奖励函数 + 高斯噪声探索。训练结果会自动保存，切换页面后仍可回看。"
    />
    <div class="page-card">
      <div class="form-grid">
        <div>
          <label class="field-label">数据源</label>
          <el-select v-model="form.data_source" style="width:100%">
            <el-option label="原始数据 (real)" value="real" />
            <el-option label="GAN 扩充 (gan)" value="gan" />
          </el-select>
        </div>
        <div>
          <label class="field-label">Epochs</label>
          <el-input-number v-model="form.epochs" :min="10" :max="5000" style="width:100%" />
        </div>
        <div>
          <label class="field-label">Batch Size</label>
          <el-input-number v-model="form.batch_size" :min="8" :max="256" style="width:100%" />
        </div>
        <div>
          <label class="field-label">Actor LR</label>
          <el-input-number v-model="form.lr_actor" :min="1e-6" :max="1e-2" :step="1e-5" :controls="false" style="width:100%" />
        </div>
        <div>
          <label class="field-label">Critic LR</label>
          <el-input-number v-model="form.lr_critic" :min="1e-6" :max="1e-2" :step="1e-5" :controls="false" style="width:100%" />
        </div>
        <div>
          <label class="field-label">Test Size</label>
          <el-input-number v-model="form.test_size" :min="0.05" :max="0.5" :step="0.05" style="width:100%" />
        </div>
      </div>
      <div class="toolbar" style="margin-top:14px">
        <el-button type="primary" :disabled="auth.isGuest" :loading="starting" @click="startTrain">开始训练</el-button>
        <el-button @click="pollOnce" :disabled="!taskId">刷新状态</el-button>
        <el-button plain :disabled="!metricsRows.length" @click="clearSaved">清除本页记录</el-button>
        <span class="tag-pill" :class="tagClass">{{ statusText }}</span>
        <span v-if="taskId" class="mono" style="color:var(--text-faint);font-size:11px">Task: {{ taskId }}</span>
        <span v-if="restoredHint" style="color:var(--text-faint);font-size:12px">{{ restoredHint }}</span>
      </div>
    </div>

    <div class="metrics-row">
      <div class="metric-card">
        <div class="metric-label">进度</div>
        <div class="metric-val" style="font-size:18px">{{ progressText }}</div>
      </div>
      <div class="metric-card">
        <div class="metric-label">设备</div>
        <div class="metric-val" style="font-size:18px">{{ device }}</div>
      </div>
      <div class="metric-card">
        <div class="metric-label">验证集 R²</div>
        <div class="metric-val good">{{ valR2 }}</div>
        <div class="metric-sub">{{ bestR2 }}</div>
      </div>
      <div class="metric-card">
        <div class="metric-label">数据划分</div>
        <div class="metric-val" style="font-size:13px">{{ dataInfo }}</div>
      </div>
    </div>

    <div class="scatter-grid">
      <div class="page-card">
        <h3>损失曲线</h3>
        <div ref="lossEl" class="chart-box sm"></div>
      </div>
      <div class="page-card">
        <h3>测试集散点</h3>
        <div ref="scatterEl" class="chart-box sm"></div>
      </div>
    </div>

    <div class="page-card">
      <h3>评估指标</h3>
      <el-table :data="metricsRows" stripe border size="small" empty-text="训练完成后显示（结果会自动保存）">
        <el-table-column prop="set" label="数据集" />
        <el-table-column prop="r2" label="R²" />
        <el-table-column prop="rmse" label="RMSE" />
        <el-table-column prop="mae" label="MAE" />
        <el-table-column prop="mape" label="MAPE(%)" />
      </el-table>
      <div v-if="summaryLines.length" style="margin-top:12px;color:var(--text-dim);line-height:1.7">
        <div v-for="(line, i) in summaryLines" :key="i">{{ line }}</div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, nextTick, onActivated, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { get, post } from '@/api/http'
import { useAuthStore } from '@/stores/auth'
import { useResultsStore } from '@/stores/results'
import { idealLine, useEChart } from '@/utils/echarts'
import PageHeader from '@/components/PageHeader.vue'

defineOptions({ name: 'DdpgView' })

const PAGE_KEY = 'ddpg'
const auth = useAuthStore()
const results = useResultsStore()

const form = reactive({
  data_source: 'real',
  epochs: 500,
  batch_size: 32,
  lr_actor: 1e-4,
  lr_critic: 5e-4,
  test_size: 0.2,
})
const starting = ref(false)
const taskId = ref('')
const status = ref('')
const device = ref('—')
const dataInfo = ref('—')
const progress = ref(0)
const epoch = ref(0)
const totalEpochs = ref(0)
const valR2 = ref('—')
const bestR2 = ref('')
const metricsRows = ref([])
const summaryLines = ref([])
const restoredHint = ref('')
const lastLosses = ref(null)
const lastScatter = ref(null)
const { elRef: lossEl, setOption: setLossOption } = useEChart()
const { elRef: scatterEl, setOption: setScatterOption } = useEChart()
let timer = null

const statusText = computed(() => {
  const map = { pending: '排队中', running: '训练中', done: '完成', error: '错误', completed: '完成', finished: '完成' }
  return map[status.value] || (status.value || '待启动')
})
const tagClass = computed(() => {
  if (['done', 'completed', 'finished'].includes(status.value)) return 'success'
  if (status.value === 'error') return 'danger'
  if (status.value === 'running') return 'warn'
  return ''
})
const progressText = computed(() => {
  if (!totalEpochs.value) return '—'
  return `${epoch.value} / ${totalEpochs.value} · ${(+progress.value).toFixed(1)}%`
})

function stopPoll() {
  if (timer) {
    clearInterval(timer)
    timer = null
  }
}

function startPoll() {
  stopPoll()
  pollOnce()
  timer = setInterval(pollOnce, 2000)
}

function renderLoss(losses) {
  if (!losses) return
  lastLosses.value = losses
  const cl = losses.critic || []
  const al = losses.actor || []
  setLossOption({
    tooltip: { trigger: 'axis' },
    legend: { bottom: 0, textStyle: { color: '#64748B' } },
    grid: { left: 40, right: 16, top: 20, bottom: 40 },
    xAxis: { type: 'category', show: false, data: cl.map((_, i) => i) },
    yAxis: { type: 'value', splitLine: { lineStyle: { color: 'rgba(15,23,42,.06)' } } },
    series: [
      { name: 'Critic Loss', type: 'line', data: cl, showSymbol: false, lineStyle: { color: '#2563EB', width: 1.5 } },
      { name: 'Actor Loss', type: 'line', data: al, showSymbol: false, lineStyle: { color: '#D97706', width: 1.5 } },
    ],
  }, false)
}

function renderScatter(scatter) {
  if (!scatter?.length) return
  lastScatter.value = scatter
  const pts = scatter.map((p) => [p.x, p.y])
  const all = scatter.flatMap((p) => [p.x, p.y])
  const minV = Math.min(...all)
  const maxV = Math.max(...all)
  setScatterOption({
    tooltip: { formatter: (p) => `真实: ${p.value[0].toFixed(1)} → 预测: ${p.value[1].toFixed(1)}` },
    grid: { left: 50, right: 16, top: 20, bottom: 40 },
    xAxis: { name: '真实 HV', min: minV, max: maxV, splitLine: { lineStyle: { color: 'rgba(15,23,42,.06)' } } },
    yAxis: { name: '预测 HV', min: minV, max: maxV, splitLine: { lineStyle: { color: 'rgba(15,23,42,.06)' } } },
    series: [
      { type: 'scatter', data: pts, symbolSize: 8, itemStyle: { color: 'rgba(37,99,235,.55)' } },
      idealLine(minV, maxV),
    ],
  })
}

function persistResult() {
  const payload = {
    form: { ...form },
    taskId: taskId.value,
    status: status.value,
    device: device.value,
    dataInfo: dataInfo.value,
    progress: progress.value,
    epoch: epoch.value,
    totalEpochs: totalEpochs.value,
    valR2: valR2.value,
    bestR2: bestR2.value,
    metricsRows: metricsRows.value,
    summaryLines: summaryLines.value,
    losses: lastLosses.value,
    scatter: results.slimScatter(lastScatter.value),
  }
  results.setPage(PAGE_KEY, payload)

  const test = metricsRows.value.find((r) => r.set === '测试集')
  results.addHistory({
    type: 'DDPG',
    pageKey: 'ddpg',
    title: `DDPG · ${form.data_source}`,
    summary: test
      ? `测试集 R²=${test.r2} · RMSE=${test.rmse} · MAPE=${test.mape}%`
      : (summaryLines.value[0] || statusText.value),
    detail: {
      metrics: metricsRows.value,
      summary: summaryLines.value,
      form: { ...form },
      taskId: taskId.value,
    },
  })
}

function restoreResult() {
  const saved = results.getPage(PAGE_KEY)
  if (!saved) return false
  Object.assign(form, saved.form || {})
  taskId.value = saved.taskId || ''
  status.value = saved.status || ''
  device.value = saved.device || '—'
  dataInfo.value = saved.dataInfo || '—'
  progress.value = saved.progress || 0
  epoch.value = saved.epoch || 0
  totalEpochs.value = saved.totalEpochs || 0
  valR2.value = saved.valR2 || '—'
  bestR2.value = saved.bestR2 || ''
  metricsRows.value = saved.metricsRows || []
  summaryLines.value = saved.summaryLines || []
  lastLosses.value = saved.losses || null
  lastScatter.value = saved.scatter || null
  if (saved.savedAt) {
    restoredHint.value = `已恢复上次结果 · ${new Date(saved.savedAt).toLocaleString()}`
  }
  return true
}

function clearSaved() {
  results.clearPage(PAGE_KEY)
  metricsRows.value = []
  summaryLines.value = []
  lastLosses.value = null
  lastScatter.value = null
  status.value = ''
  taskId.value = ''
  restoredHint.value = ''
  ElMessage.success('已清除本页保存的训练结果')
}

async function startTrain() {
  starting.value = true
  const res = await post('/api/ddpg/train', { ...form })
  starting.value = false
  if (res.error) {
    ElMessage.error(`启动失败: ${res.error}`)
    return
  }
  taskId.value = res.task_id
  status.value = 'running'
  metricsRows.value = []
  summaryLines.value = []
  restoredHint.value = ''
  ElMessage.success('DDPG 训练已启动（异步），完成后会自动保存记录')
  startPoll()
}

async function pollOnce() {
  if (!taskId.value) return
  const res = await get(`/api/ddpg/status/${taskId.value}`)
  if (res.error) {
    ElMessage.warning(res.error)
    stopPoll()
    return
  }
  status.value = res.status || ''
  if (res.device) device.value = String(res.device).includes('cuda') ? 'GPU' : 'CPU'
  if (res.n_train != null) {
    dataInfo.value = `${res.n_train}/${res.n_val}/${res.n_test} (训/验/测) · ${res.n_features}维`
  }
  epoch.value = res.epoch || 0
  totalEpochs.value = res.total_epochs || 0
  progress.value = res.progress || 0
  if (res.val_r2 != null) valR2.value = (+res.val_r2).toFixed(4)
  if (res.best_val_r2 != null) bestR2.value = `最佳 ${(+res.best_val_r2).toFixed(4)}`

  if (res.losses) renderLoss(res.losses)

  if (['done', 'completed', 'finished'].includes(res.status)) {
    stopPoll()
    if (res.metrics) {
      const m = res.metrics
      metricsRows.value = ['train', 'val', 'test'].map((k) => ({
        set: { train: '训练集', val: '验证集', test: '测试集' }[k],
        r2: (+m[k].r2).toFixed(4),
        rmse: (+m[k].rmse).toFixed(2),
        mae: (+m[k].mae).toFixed(2),
        mape: (+(m[k].mape || 0)).toFixed(2),
      }))
      summaryLines.value = [
        `训练完成 · 共 ${res.epoch} 轮` + (res.early_stopped ? ' · 早停触发' : ''),
        `最佳验证集 R²: ${res.best_val_r2?.toFixed?.(4) ?? '—'}`,
        `测试集 R²: ${(+m.test.r2).toFixed(4)} · RMSE: ${(+m.test.rmse).toFixed(2)} HV`,
      ]
    }
    if (res.scatter?.length) renderScatter(res.scatter)
    persistResult()
    ElMessage.success(`DDPG 训练完成！结果已保存 · 测试集 R²=${res.metrics?.test?.r2?.toFixed?.(4) ?? '—'}`)
  }

  if (res.status === 'error') {
    stopPoll()
    ElMessage.error(`训练失败: ${res.error || '未知错误'}`)
  }
}

function redrawCharts() {
  if (lastLosses.value) renderLoss(lastLosses.value)
  if (lastScatter.value) renderScatter(lastScatter.value)
}

function onVisibility() {
  if (document.hidden) stopPoll()
  else if (taskId.value && !['done', 'error', 'completed', 'finished'].includes(status.value)) startPoll()
}

onMounted(async () => {
  document.addEventListener('visibilitychange', onVisibility)
  const ok = restoreResult()
  await nextTick()
  if (ok) redrawCharts()
  if (taskId.value && !['done', 'error', 'completed', 'finished'].includes(status.value)) {
    startPoll()
  }
})

onActivated(async () => {
  await nextTick()
  redrawCharts()
})

onBeforeUnmount(() => {
  stopPoll()
  document.removeEventListener('visibilitychange', onVisibility)
})
</script>
