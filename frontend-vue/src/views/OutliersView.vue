<template>
  <div>
    <PageHeader
      sub="第 2 章 · 公式 (1)(2)(3)"
      title="异常值"
      em="检测"
      desc="论文采用分位数截断策略，保留 1%~99% 分位数范围内的有效数据，消除极端异常值对模型训练的干扰。"
    />
    <div class="page-card">
      <div class="form-grid">
        <div>
          <label class="field-label">检测方法</label>
          <el-select v-model="method" style="width:100%" disabled>
            <el-option v-for="m in OUTLIER_METHODS" :key="m.value" :label="m.label" :value="m.value" />
          </el-select>
        </div>
        <div>
          <label class="field-label">下分位 {{ lowQ.toFixed(2) }}</label>
          <el-slider v-model="lowQ" :min="0" :max="0.2" :step="0.01" />
        </div>
        <div>
          <label class="field-label">上分位 {{ highQ.toFixed(2) }}</label>
          <el-slider v-model="highQ" :min="0.8" :max="1" :step="0.01" />
        </div>
      </div>
      <div class="toolbar" style="margin-top:12px">
        <el-button type="primary" :disabled="auth.isGuest" :loading="running" @click="runDetect">
          运行异常值检测
        </el-button>
        <span class="tag-pill" :class="statusClass">{{ status }}</span>
      </div>
    </div>

    <div class="metrics-row">
      <div class="metric-card">
        <div class="metric-label">总样本</div>
        <div class="metric-val">{{ result.total ?? '—' }}</div>
      </div>
      <div class="metric-card">
        <div class="metric-label">异常数</div>
        <div class="metric-val warn">{{ result.n_outliers ?? '—' }}</div>
        <div class="metric-sub">{{ ratioText }}</div>
      </div>
      <div class="metric-card">
        <div class="metric-label">方法</div>
        <div class="metric-val" style="font-size:15px">{{ methodLabel }}</div>
      </div>
    </div>

    <div class="page-card">
      <h3>正常 vs 异常</h3>
      <div ref="chartEl" class="chart-box sm"></div>
    </div>

    <div class="page-card">
      <h3>异常样本 <span class="tag-pill">{{ (result.outliers || []).length }} 条</span></h3>
      <el-table :data="tableRows" stripe border size="small" max-height="400" empty-text="尚未运行检测">
        <el-table-column type="index" label="#" width="60" />
        <el-table-column prop="index" label="样本索引" width="120" />
        <el-table-column prop="detail" label="详情" min-width="280" show-overflow-tooltip />
      </el-table>
    </div>
  </div>
</template>

<script setup>
import { computed, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { post } from '@/api/http'
import { useAuthStore } from '@/stores/auth'
import { OUTLIER_METHODS } from '@/utils/constants'
import { useEChart } from '@/utils/echarts'
import PageHeader from '@/components/PageHeader.vue'

defineOptions({ name: 'OutliersView' })

const auth = useAuthStore()
const method = ref('quantile_clip')
const lowQ = ref(0.01)
const highQ = ref(0.99)
const contamination = ref(0.05)
const running = ref(false)
const status = ref('待运行')
const result = reactive({ total: null, n_outliers: null, outliers: [] })
const { elRef: chartEl, setOption } = useEChart()

const methodLabel = computed(() => OUTLIER_METHODS.find((m) => m.value === method.value)?.label || method.value)
const ratioText = computed(() => {
  if (!result.total || result.n_outliers == null) return ''
  return `占比 ${((result.n_outliers / result.total) * 100).toFixed(1)}%`
})
const statusClass = computed(() => (status.value === '完成' ? 'success' : status.value === '错误' ? 'danger' : ''))
const tableRows = computed(() =>
  (result.outliers || []).map((o) => ({
    index: o.index,
    detail: Object.entries(o.values || {})
      .slice(0, 6)
      .map(([k, v]) => `${k}=${(+v).toFixed(2)}`)
      .join(' · '),
  })),
)

function renderChart() {
  const total = result.total || 0
  const n = result.n_outliers || 0
  setOption({
    title: { text: '异常 vs 正常样本数', left: 0, textStyle: { fontSize: 13, color: '#0F172A' } },
    tooltip: { trigger: 'axis' },
    xAxis: { type: 'category', data: ['正常样本', '异常样本'], axisLabel: { color: '#64748B' } },
    yAxis: { type: 'value', axisLabel: { color: '#64748B' }, splitLine: { lineStyle: { color: 'rgba(15,23,42,.06)' } } },
    series: [{
      type: 'bar',
      data: [
        { value: Math.max(total - n, 0), itemStyle: { color: 'rgba(37,99,235,.55)' } },
        { value: n, itemStyle: { color: 'rgba(239,68,68,.7)' } },
      ],
      barWidth: 48,
    }],
  })
}

async function runDetect() {
  running.value = true
  status.value = '检测中'
  const payload = { method: method.value, contamination: contamination.value }
  if (method.value === 'quantile_clip') {
    payload.low_quantile = lowQ.value
    payload.high_quantile = highQ.value
  }
  const res = await post('/api/outliers/detect', payload)
  running.value = false
  if (res.error) {
    status.value = '错误'
    ElMessage.error(res.error)
    return
  }
  result.total = res.total
  result.n_outliers = res.n_outliers
  result.outliers = res.outliers || []
  status.value = '完成'
  renderChart()
  ElMessage.success(`检测完成 · 异常 ${res.n_outliers} 条`)
}
</script>
