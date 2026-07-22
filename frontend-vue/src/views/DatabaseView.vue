<template>
  <div>
    <PageHeader
      sub="数据可视化查询"
      title="数据库"
      em="管理"
      desc="通过可视化查询构建器筛选、排序、聚合合金数据集，无需手写 SQL。"
    />
    <div class="metrics-row">
      <div class="metric-card">
        <div class="metric-label">行数</div>
        <div class="metric-val">{{ schema.n_rows ?? '—' }}</div>
      </div>
      <div class="metric-card">
        <div class="metric-label">列数</div>
        <div class="metric-val">{{ (schema.columns || []).length || '—' }}</div>
      </div>
      <div class="metric-card">
        <div class="metric-label">查询状态</div>
        <div class="metric-val" style="font-size:16px">{{ status }}</div>
      </div>
    </div>

    <div class="page-card">
      <h3>可视化查询</h3>
      <div class="chip-row">
        <span class="chip" :class="{ on: mode === 'select' }" @click="mode = 'select'">选择查询</span>
        <span class="chip" :class="{ on: mode === 'aggregate' }" @click="mode = 'aggregate'">聚合查询</span>
      </div>

      <div v-if="mode === 'select'" class="form-grid">
        <div>
          <label class="field-label">选择列（可多选）</label>
          <el-select v-model="selectedCols" multiple filterable collapse-tags style="width:100%">
            <el-option v-for="c in allCols" :key="c" :label="c" :value="c" />
          </el-select>
        </div>
        <div>
          <label class="field-label">排序列</label>
          <el-select v-model="orderCol" clearable style="width:100%">
            <el-option v-for="c in allCols" :key="c" :label="c" :value="c" />
          </el-select>
        </div>
        <div>
          <label class="field-label">排序方向</label>
          <el-select v-model="orderDir" style="width:100%">
            <el-option label="降序" value="desc" />
            <el-option label="升序" value="asc" />
          </el-select>
        </div>
      </div>

      <div v-else class="form-grid">
        <div>
          <label class="field-label">聚合函数</label>
          <el-select v-model="aggFunc" style="width:100%">
            <el-option v-for="f in ['avg', 'sum', 'min', 'max', 'count']" :key="f" :label="f.toUpperCase()" :value="f" />
          </el-select>
        </div>
        <div>
          <label class="field-label">聚合列</label>
          <el-select v-model="aggCol" clearable style="width:100%">
            <el-option v-for="c in numCols" :key="c" :label="c" :value="c" />
          </el-select>
        </div>
        <div>
          <label class="field-label">分组列</label>
          <el-select v-model="aggGroup" multiple collapse-tags style="width:100%">
            <el-option v-for="c in allCols" :key="c" :label="c" :value="c" />
          </el-select>
        </div>
      </div>

      <div style="margin-top:14px">
        <label class="field-label">筛选条件</label>
        <div v-for="(f, i) in filters" :key="i" class="toolbar">
          <el-select v-model="f.col" style="width:180px">
            <el-option v-for="c in allCols" :key="c" :label="c" :value="c" />
          </el-select>
          <el-select v-model="f.op" style="width:110px">
            <el-option v-for="o in ops" :key="o" :label="o" :value="o" />
          </el-select>
          <el-input v-model="f.val" placeholder="数值（between 用 a,b）" style="width:180px" />
          <el-button text type="danger" @click="filters.splice(i, 1)">删除</el-button>
        </div>
        <el-button @click="filters.push({ col: allCols[0] || '', op: '>', val: '' })">添加筛选</el-button>
      </div>

      <div class="toolbar" style="margin-top:14px">
        <div style="min-width:200px">
          <label class="field-label">Limit {{ limit }}</label>
          <el-slider v-model="limit" :min="10" :max="500" :step="10" />
        </div>
        <el-button type="primary" :loading="running" @click="runQuery">执行查询</el-button>
      </div>

      <div class="chip-row" style="margin-top:8px">
        <span class="chip" @click="applyPreset('top10')">Top 10</span>
        <span class="chip" @click="applyPreset('hard')">HV &gt; 400</span>
        <span class="chip" @click="applyPreset('sorted_hv')">按 HV 降序</span>
        <span class="chip" @click="applyPreset('count')">COUNT</span>
      </div>
    </div>

    <div class="page-card">
      <h3>查询结果 <span class="tag-pill">{{ resultRows.length }} 行</span></h3>
      <el-table :data="resultRows" stripe border size="small" max-height="420" empty-text="尚未执行查询">
        <el-table-column type="index" label="#" width="55" />
        <el-table-column
          v-for="c in resultCols"
          :key="c"
          :prop="c"
          :label="c"
          min-width="100"
          show-overflow-tooltip
        />
      </el-table>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { get, post } from '@/api/http'
import PageHeader from '@/components/PageHeader.vue'

const schema = ref({ columns: [], n_rows: 0 })
const mode = ref('select')
const selectedCols = ref([])
const orderCol = ref('')
const orderDir = ref('desc')
const aggFunc = ref('avg')
const aggCol = ref('')
const aggGroup = ref([])
const filters = ref([])
const limit = ref(100)
const running = ref(false)
const status = ref('就绪')
const resultCols = ref([])
const resultRows = ref([])
const ops = ['>', '<', '>=', '<=', '=', '!=', 'between', 'contains']

const allCols = computed(() => (schema.value.columns || []).map((c) => c.name || c))
const numCols = computed(() =>
  (schema.value.columns || []).filter((c) => (c.type || '') === 'number').map((c) => c.name),
)

async function loadSchema() {
  const res = await get('/api/database/schema')
  if (res.error) {
    ElMessage.warning(res.error)
    return
  }
  schema.value = res
}

function applyPreset(name) {
  filters.value = []
  if (name === 'top10') {
    mode.value = 'select'
    limit.value = 10
  } else if (name === 'hard') {
    mode.value = 'select'
    filters.value = [{ col: 'Vickers Hardness (HV)', op: '>', val: '400' }]
    limit.value = 100
  } else if (name === 'sorted_hv') {
    mode.value = 'select'
    orderCol.value = 'Vickers Hardness (HV)'
    orderDir.value = 'desc'
    limit.value = 20
  } else if (name === 'count') {
    mode.value = 'aggregate'
    aggFunc.value = 'count'
    aggCol.value = ''
    limit.value = 10
  }
  runQuery()
}

async function runQuery() {
  const payload = { limit: limit.value }
  if (mode.value === 'select') {
    if (selectedCols.value.length) payload.columns = selectedCols.value
    const fs = filters.value.filter((f) => f.col && f.op && f.val)
    if (fs.length) payload.filters = fs
    if (orderCol.value) payload.order_by = { col: orderCol.value, desc: orderDir.value === 'desc' }
  } else {
    payload.aggregate = { func: aggFunc.value, col: aggCol.value, group_by: aggGroup.value }
  }
  running.value = true
  status.value = '执行中'
  const res = await post('/api/database/query', payload)
  running.value = false
  if (res.error) {
    status.value = '错误'
    ElMessage.error(res.error)
    return
  }
  status.value = '完成'
  resultCols.value = res.columns || []
  resultRows.value = (res.rows || []).map((row) => {
    if (Array.isArray(row)) {
      const obj = {}
      resultCols.value.forEach((c, i) => { obj[c] = row[i] })
      return obj
    }
    return row
  })
  ElMessage.success(`查询完成 · 返回 ${res.n ?? resultRows.value.length} 行`)
}

onMounted(loadSchema)
</script>
