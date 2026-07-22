<template>
  <div>
    <PageHeader
      sub="系统管理"
      title="数据"
      em="管理"
      desc="对当前数据源做行级录入、查询、修改、删除、批量导入与导出。支持关键词搜索与按列排序。"
    />
    <div class="page-card">
      <div class="toolbar">
        <el-input v-model="keyword" placeholder="关键词搜索" style="width:200px" clearable @keyup.enter="search" />
        <el-select v-model="sort" clearable placeholder="排序列" style="width:160px">
          <el-option v-for="c in columns.filter((x) => x !== '_row_id')" :key="c" :label="c" :value="c" />
        </el-select>
        <el-select v-model="dir" style="width:100px">
          <el-option label="升序" value="asc" />
          <el-option label="降序" value="desc" />
        </el-select>
        <el-button type="primary" @click="search">查询</el-button>
        <el-button :disabled="auth.isGuest" @click="openEdit(null)">新增</el-button>
        <el-button :disabled="auth.isGuest" @click="batchRef?.click()">批量导入</el-button>
        <el-button @click="exportData('xlsx')">导出 XLSX</el-button>
        <el-button @click="exportData('csv')">导出 CSV</el-button>
        <el-button @click="runAnalysis">数据分析</el-button>
        <input ref="batchRef" type="file" accept=".xlsx,.xls,.csv" hidden @change="onBatch" />
      </div>
      <div style="color:var(--text-faint);font-size:12px;margin-bottom:8px">{{ info }}</div>
      <el-table :data="items" stripe border size="small" max-height="480" v-loading="loading">
        <el-table-column label="操作" width="120" fixed>
          <template #default="{ row }">
            <el-button link type="primary" :disabled="auth.isGuest" @click="openEdit(row)">编辑</el-button>
            <el-button link type="danger" :disabled="auth.isGuest" @click="remove(row)">删除</el-button>
          </template>
        </el-table-column>
        <el-table-column
          v-for="c in columns"
          :key="c"
          :prop="c"
          :label="c"
          min-width="100"
          show-overflow-tooltip
        />
      </el-table>
      <div class="toolbar" style="margin-top:12px;justify-content:flex-end">
        <el-button @click="prev" :disabled="page <= 1">上一页</el-button>
        <span>{{ page }} / {{ totalPages }}</span>
        <el-button @click="next" :disabled="page >= totalPages">下一页</el-button>
      </div>
    </div>

    <div v-if="showAnalysis" class="page-card">
      <div class="toolbar">
        <h3 style="margin:0;flex:1">数据分析</h3>
        <el-button text @click="showAnalysis = false">关闭</el-button>
      </div>
      <div class="scatter-grid">
        <div ref="histEl" class="chart-box sm"></div>
        <div ref="corrEl" class="chart-box sm"></div>
      </div>
      <el-table :data="featureStats" stripe border size="small" style="margin-top:12px" max-height="300">
        <el-table-column prop="feature" label="特征" width="120" />
        <el-table-column prop="count" label="count" width="80" />
        <el-table-column prop="min" label="min" />
        <el-table-column prop="max" label="max" />
        <el-table-column prop="mean" label="mean" />
        <el-table-column prop="std" label="std" />
        <el-table-column prop="median" label="median" />
      </el-table>
    </div>

    <el-dialog v-model="editVisible" :title="editRow ? `编辑行 (id=${editRow._row_id})` : '新增一行'" width="640px">
      <el-form label-position="top">
        <div class="form-grid">
          <el-form-item v-for="c in editableCols" :key="c" :label="c">
            <el-input v-model="editForm[c]" />
          </el-form-item>
        </div>
      </el-form>
      <template #footer>
        <el-button @click="editVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="saveRow">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { del, download, get, post, put, upload } from '@/api/http'
import { useAuthStore } from '@/stores/auth'
import { useEChart } from '@/utils/echarts'
import PageHeader from '@/components/PageHeader.vue'

const auth = useAuthStore()
const loading = ref(false)
const items = ref([])
const columns = ref([])
const page = ref(1)
const size = ref(20)
const total = ref(0)
const keyword = ref('')
const sort = ref('')
const dir = ref('asc')
const batchRef = ref(null)
const editVisible = ref(false)
const editRow = ref(null)
const editForm = reactive({})
const saving = ref(false)
const showAnalysis = ref(false)
const featureStats = ref([])
const { elRef: histEl, setOption: setHistOption } = useEChart()
const { elRef: corrEl, setOption: setCorrOption } = useEChart()

const totalPages = computed(() => Math.max(1, Math.ceil(total.value / size.value)))
const info = computed(() => `共 ${total.value} 条 · 第 ${page.value} 页`)
const editableCols = computed(() => columns.value.filter((c) => c !== '_row_id'))

async function loadRows() {
  loading.value = true
  const res = await get('/api/data/rows', {
    page: page.value,
    size: size.value,
    keyword: keyword.value,
    sort: sort.value,
    dir: dir.value,
  })
  loading.value = false
  if (res.error) {
    ElMessage.error(res.error)
    return
  }
  columns.value = res.columns || []
  items.value = res.items || []
  total.value = res.total || 0
  page.value = res.page || page.value
}

function search() {
  page.value = 1
  loadRows()
}
function prev() {
  if (page.value > 1) {
    page.value--
    loadRows()
  }
}
function next() {
  if (page.value < totalPages.value) {
    page.value++
    loadRows()
  }
}

function openEdit(row) {
  editRow.value = row
  editableCols.value.forEach((c) => {
    editForm[c] = row ? (row[c] ?? '') : ''
  })
  editVisible.value = true
}

async function saveRow() {
  saving.value = true
  const data = {}
  editableCols.value.forEach((c) => { data[c] = editForm[c] })
  let res
  if (editRow.value) res = await put(`/api/data/rows/${editRow.value._row_id}`, data)
  else res = await post('/api/data/rows', data)
  saving.value = false
  if (res.error) {
    ElMessage.error(res.error)
    return
  }
  ElMessage.success(editRow.value ? '已保存' : '新增成功')
  editVisible.value = false
  loadRows()
}

async function remove(row) {
  try {
    await ElMessageBox.confirm('确认删除该行？此操作不可恢复。', '提示', { type: 'warning' })
  } catch {
    return
  }
  const res = await del(`/api/data/rows/${row._row_id}`)
  if (res.error) {
    ElMessage.error(res.error)
    return
  }
  ElMessage.success('已删除')
  loadRows()
}

async function onBatch(e) {
  const file = e.target.files?.[0]
  if (!file) return
  const fd = new FormData()
  fd.append('file', file)
  const res = await upload('/api/data/batch_import', fd)
  e.target.value = ''
  if (res.error) {
    ElMessage.error(res.error)
    return
  }
  ElMessage.success(`导入成功：追加 ${res.appended_rows ?? res.appended ?? 0} 行`)
  loadRows()
}

function exportData(format) {
  download(`/api/data/export?format=${format}`, `data_export.${format === 'csv' ? 'csv' : 'xlsx'}`)
}

async function runAnalysis() {
  showAnalysis.value = true
  const res = await get('/api/data/analysis')
  if (res.error) {
    ElMessage.error(res.error)
    return
  }
  await nextTick()
  const ts = res.target_stats || {}
  if (ts.hist_counts) {
    const labels = (ts.hist_bins || []).slice(0, -1).map((v) => (+v).toFixed(0))
    setHistOption({
      title: { text: 'HV 直方图', textStyle: { fontSize: 13 } },
      tooltip: { trigger: 'axis' },
      xAxis: { type: 'category', data: labels },
      yAxis: { type: 'value' },
      series: [{ type: 'bar', data: ts.hist_counts, itemStyle: { color: 'rgba(10,132,255,.6)' } }],
    })
  }
  if (res.correlation_top?.length) {
    setCorrOption({
      title: { text: '相关性 Top', textStyle: { fontSize: 13 } },
      tooltip: { trigger: 'axis' },
      grid: { left: 80, right: 20, top: 40, bottom: 30 },
      xAxis: { type: 'value' },
      yAxis: { type: 'category', data: res.correlation_top.map((x) => x.element).reverse() },
      series: [{
        type: 'bar',
        data: res.correlation_top.map((x) => x.abs_corr).reverse(),
        itemStyle: { color: 'rgba(94,92,230,.55)' },
      }],
    })
  }
  featureStats.value = Object.entries(res.feature_stats || {}).slice(0, 10).map(([k, v]) => ({
    feature: k,
    count: v.count,
    min: (+v.min).toFixed(3),
    max: (+v.max).toFixed(3),
    mean: (+v.mean).toFixed(3),
    std: (+v.std).toFixed(3),
    median: (+v.median).toFixed(3),
  }))
}

onMounted(loadRows)
</script>
