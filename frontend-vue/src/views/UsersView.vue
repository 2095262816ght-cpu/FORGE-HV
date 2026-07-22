<template>
  <div>
    <PageHeader
      sub="系统管理 · 仅管理员"
      title="用户"
      em="管理"
      desc="管理系统用户账号，支持角色分配（admin/user）、重置密码、删除账号。"
    />
    <div class="page-card">
      <div class="toolbar">
        <el-input v-model="keyword" placeholder="搜索用户名/显示名" style="width:220px" clearable @keyup.enter="search" />
        <el-button type="primary" @click="search">搜索</el-button>
        <el-button type="success" @click="openEdit(null)">新建用户</el-button>
      </div>
      <el-table :data="items" stripe border size="small" v-loading="loading" empty-text="暂无用户">
        <el-table-column prop="id" label="ID" width="70" />
        <el-table-column prop="username" label="用户名" width="140" />
        <el-table-column prop="display_name" label="显示名" width="140" />
        <el-table-column prop="email" label="邮箱" min-width="160" />
        <el-table-column label="角色" width="100">
          <template #default="{ row }">
            <span class="tag-pill" :class="{ success: row.role === 'admin' }">{{ row.role }}</span>
          </template>
        </el-table-column>
        <el-table-column label="创建时间" min-width="150">
          <template #default="{ row }">{{ fmt(row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="最近登录" min-width="150">
          <template #default="{ row }">{{ fmt(row.last_login) || '—' }}</template>
        </el-table-column>
        <el-table-column label="操作" width="140" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
            <el-button
              v-if="row.id !== auth.user?.id && row.id !== auth.user?.user_id"
              link
              type="danger"
              @click="remove(row)"
            >删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <el-dialog v-model="visible" :title="editId ? '编辑用户' : '新建用户'" width="480px" destroy-on-close>
      <el-form label-position="top">
        <el-form-item label="用户名">
          <el-input v-model="form.username" :disabled="!!editId" />
        </el-form-item>
        <el-form-item label="显示名">
          <el-input v-model="form.display_name" />
        </el-form-item>
        <el-form-item label="邮箱">
          <el-input v-model="form.email" />
        </el-form-item>
        <el-form-item label="角色">
          <el-select v-model="form.role" style="width:100%">
            <el-option label="admin" value="admin" />
            <el-option label="user" value="user" />
          </el-select>
        </el-form-item>
        <el-form-item :label="editId ? '重置密码（留空则不修改）' : '密码 *（至少 6 位）'">
          <el-input v-model="form.password" type="password" show-password />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="visible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="save">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { del, get, post, put } from '@/api/http'
import { useAuthStore } from '@/stores/auth'
import PageHeader from '@/components/PageHeader.vue'

const auth = useAuthStore()
const loading = ref(false)
const items = ref([])
const keyword = ref('')
const visible = ref(false)
const editId = ref(null)
const saving = ref(false)
const form = reactive({
  username: '',
  display_name: '',
  email: '',
  role: 'user',
  password: '',
})

function fmt(t) {
  return t ? String(t).replace('T', ' ').slice(0, 19) : ''
}

async function load() {
  loading.value = true
  const res = await get('/api/users', { page: 1, size: 50, keyword: keyword.value })
  loading.value = false
  if (res.error) {
    ElMessage.error(res.error)
    return
  }
  items.value = res.items || []
}

function search() {
  load()
}

function openEdit(row) {
  editId.value = row?.id || null
  form.username = row?.username || ''
  form.display_name = row?.display_name || ''
  form.email = row?.email || ''
  form.role = row?.role || 'user'
  form.password = ''
  visible.value = true
}

async function save() {
  if (!editId.value) {
    if (!form.username || !form.password) {
      ElMessage.warning('用户名和密码必填')
      return
    }
    saving.value = true
    const res = await post('/api/users', { ...form })
    saving.value = false
    if (res.error) {
      ElMessage.error(res.error)
      return
    }
    ElMessage.success('用户已创建')
  } else {
    const body = {
      display_name: form.display_name,
      email: form.email,
      role: form.role,
    }
    if (form.password) body.password = form.password
    saving.value = true
    const res = await put(`/api/users/${editId.value}`, body)
    saving.value = false
    if (res.error) {
      ElMessage.error(res.error)
      return
    }
    ElMessage.success('用户已更新')
  }
  visible.value = false
  load()
}

async function remove(row) {
  try {
    await ElMessageBox.confirm('确认删除该用户？', '提示', { type: 'warning' })
  } catch {
    return
  }
  const res = await del(`/api/users/${row.id}`)
  if (res.error) {
    ElMessage.error(res.error)
    return
  }
  ElMessage.success('已删除')
  load()
}

onMounted(load)
</script>
