<template>
  <div>
    <PageHeader
      sub="实验记录 · 本地持久化"
      title="训练"
      em="结果记录"
      desc="保存 DDPG 训练与硬度预测比较 / 数据扩充比较的最近结果。切换页面或刷新浏览器后仍可回看；数据保存在本机浏览器中。"
    />

    <div class="page-card">
      <div class="toolbar">
        <el-button type="danger" plain :disabled="!history.length" @click="clearAll">清空全部记录</el-button>
        <span class="tag-pill">共 {{ history.length }} 条</span>
      </div>
      <el-table :data="history" stripe border size="small" empty-text="暂无训练记录，去 DDPG / 材料硬度预测比较 / 数据扩充比较 页面跑一次实验即可自动保存">
        <el-table-column prop="savedAt" label="时间" width="170">
          <template #default="{ row }">{{ formatTime(row.savedAt) }}</template>
        </el-table-column>
        <el-table-column prop="type" label="类型" width="120" />
        <el-table-column prop="title" label="标题" min-width="180" />
        <el-table-column prop="summary" label="摘要" min-width="260" show-overflow-tooltip />
        <el-table-column label="操作" width="200">
          <template #default="{ row }">
            <el-button link type="primary" @click="goPage(row)">打开页面</el-button>
            <el-button link type="primary" @click="showDetail(row)">详情</el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <el-dialog v-model="detailVisible" title="结果详情" width="720px">
      <pre class="result-pre">{{ detailText }}</pre>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useResultsStore } from '@/stores/results'
import PageHeader from '@/components/PageHeader.vue'
import { ref } from 'vue'

defineOptions({ name: 'ResultsView' })

const router = useRouter()
const store = useResultsStore()
const history = computed(() => store.history)
const detailVisible = ref(false)
const detailText = ref('')

function formatTime(ts) {
  if (!ts) return '—'
  const d = new Date(ts)
  const pad = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`
}

function goPage(row) {
  const map = {
    ddpg: '/ddpg',
    cmp53: '/cmp53',
    cmp54: '/cmp54',
  }
  const path = map[row.pageKey] || map[row.type] || '/ddpg'
  router.push(path)
}

function showDetail(row) {
  detailText.value = JSON.stringify(row.detail || row, null, 2)
  detailVisible.value = true
}

async function clearAll() {
  try {
    await ElMessageBox.confirm('确定清空全部本地训练记录？此操作不可恢复。', '清空确认', {
      type: 'warning',
      confirmButtonText: '清空',
      cancelButtonText: '取消',
    })
  } catch {
    return
  }
  store.clearHistory()
  ;['ddpg', 'cmp53', 'cmp54'].forEach((k) => store.clearPage(k))
  ElMessage.success('已清空本地记录')
}
</script>

<style scoped>
.result-pre {
  max-height: 420px;
  overflow: auto;
  background: #F8FAFC;
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 12px 14px;
  font-size: 12px;
  line-height: 1.55;
  color: var(--text);
  white-space: pre-wrap;
  word-break: break-word;
}
</style>
