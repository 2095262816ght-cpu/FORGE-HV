<template>
  <div>
    <PageHeader
      sub="系统管理"
      title="历史"
      em="预测记录"
      desc="所有训练/预测任务自动落库，支持按算法、数据源、时间范围筛选，并可导出 CSV。"
    />
    <div class="page-card">
      <div class="toolbar">
        <el-select v-model="algorithm" clearable placeholder="算法" style="width:160px">
          <el-option v-for="a in algs" :key="a" :label="a" :value="a" />
        </el-select>
        <el-select v-model="dataSource" clearable placeholder="数据源" style="width:140px">
          <el-option label="real" value="real" />
          <el-option label="gan" value="gan" />
        </el-select>
        <el-date-picker v-model="dateFrom" type="date" value-format="YYYY-MM-DD" placeholder="开始日期" />
        <el-date-picker v-model="dateTo" type="date" value-format="YYYY-MM-DD" placeholder="结束日期" />
        <el-button type="primary" @click="search">筛选</el-button>
        <el-button @click="exportCsv">导出 CSV</el-button>
      </div>
      <div style="color:var(--text-faint);font-size:12px;margin-bottom:8px">{{ info }}</div>
      <el-table :data="items" stripe border size="small" max-height="520" v-loading="loading">
        <el-table-column prop="id" label="ID" width="70" />
        <el-table-column label="时间" min-width="150">
          <template #default="{ row }">{{ fmtTime(row.created_at) }}</template>
        </el-table-column>
        <el-table-column prop="username" label="用户" width="100" />
        <el-table-column prop="task_type" label="任务" width="120" />
        <el-table-column prop="algorithm" label="算法" width="120" />
        <el-table-column prop="data_source" label="数据源" width="90" />
        <el-table-column prop="n_samples" label="样本" width="80" />
        <el-table-column label="R²" width="90">
          <template #default="{ row }">{{ metric(row, 'r2', 4) }}</template>
        </el-table-column>
        <el-table-column label="RMSE" width="90">
          <template #default="{ row }">{{ metric(row, 'rmse', 2) }}</template>
        </el-table-column>
        <el-table-column label="MAE" width="90">
          <template #default="{ row }">{{ metric(row, 'mae', 2) }}</template>
        </el-table-column>
        <el-table-column label="MAPE" width="90">
          <template #default="{ row }">
            <span v-if="metric(row, 'mape', 2) !== '—'">{{ metric(row, 'mape', 2) }}%</span>
            <span v-else>—</span>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="90" />
        <el-table-column v-if="auth.isAdmin" label="操作" width="80" fixed="right">
          <template #default="{ row }">
            <el-button link type="danger" @click="remove(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
      <div class="toolbar" style="margin-top:12px;justify-content:flex-end">
        <el-button :disabled="page <= 1" @click="page--; load()">上一页</el-button>
        <span>{{ page }} / {{ totalPages }}</span>
        <el-button :disabled="page >= totalPages" @click="page++; load()">下一页</el-button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { del, download, get } from '@/api/http'
import { useAuthStore } from '@/stores/auth'
import PageHeader from '@/components/PageHeader.vue'

const auth = useAuthStore()
const loading = ref(false)
const items = ref([])
const page = ref(1)
const size = ref(20)
const total = ref(0)
const algorithm = ref('')
const dataSource = ref('')
const dateFrom = ref('')
const dateTo = ref('')
const algs = ['DDPG', 'LinearRegression', 'PolynomialRegression', 'SVR', 'compare']

const totalPages = computed(() => Math.max(1, Math.ceil(total.value / size.value)))
const info = computed(() => `共 ${total.value} 条 · 第 ${page.value} 页`)

function fmtTime(t) {
  return (t || '').replace('T', ' ').slice(0, 19)
}

function parseMetrics(row) {
  let m = row.metrics
  if (typeof m === 'string') {
    try { m = JSON.parse(m) } catch { m = {} }
  }
  return m && typeof m === 'object' ? m : {}
}

/** 从多种落库结构中取出可用于展示的指标对象 */
function pickMetricBag(m) {
  if (!m || typeof m !== 'object') return {}
  if (m.test && typeof m.test === 'object') return m.test
  if (m.detail?.test && typeof m.detail.test === 'object') return m.detail.test
  if (m.detail && typeof m.detail === 'object' && (m.detail.r2 != null || m.detail.R2_value != null)) {
    return m.detail
  }
  // compare 落库：{ best, models:[{model,r2,rmse,...}] }
  if (Array.isArray(m.models) && m.models.length) {
    const bestName = m.best
    const best = m.models.find((x) => x && x.model === bestName && x.r2 != null)
      || m.models.find((x) => x && x.r2 != null)
    if (best) return best
  }
  return m
}

function metric(row, key, digits) {
  const bag = pickMetricBag(parseMetrics(row))
  const aliases = {
    r2: ['r2', 'R2', 'R2_value'],
    rmse: ['rmse', 'RMSE', 'RMSE_value'],
    mae: ['mae', 'MAE', 'MAE_value'],
    mape: ['mape', 'MAPE', 'MAPE_value'],
  }
  const keys = aliases[key] || [key]
  let v
  for (const k of keys) {
    if (bag[k] !== undefined && bag[k] !== null) { v = bag[k]; break }
  }
  return v !== undefined && v !== null && !Number.isNaN(+v) ? (+v).toFixed(digits) : '—'
}

async function load() {
  loading.value = true
  const params = { page: page.value, size: size.value }
  if (algorithm.value) params.algorithm = algorithm.value
  if (dataSource.value) params.data_source = dataSource.value
  if (dateFrom.value) params.date_from = dateFrom.value
  if (dateTo.value) params.date_to = dateTo.value
  const res = await get('/api/history', params)
  loading.value = false
  if (res.error) {
    ElMessage.error(res.error)
    return
  }
  items.value = res.items || []
  total.value = res.total || 0
  page.value = res.page || page.value
}

function search() {
  page.value = 1
  load()
}

async function remove(row) {
  try {
    await ElMessageBox.confirm('删除该历史记录？', '提示', { type: 'warning' })
  } catch {
    return
  }
  const res = await del(`/api/history/${row.id}`)
  if (res.error) {
    ElMessage.error(res.error)
    return
  }
  ElMessage.success('已删除')
  load()
}

function exportCsv() {
  download('/api/history/export', 'history.csv')
}

onMounted(load)
</script>
