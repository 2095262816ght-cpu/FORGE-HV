<template>
  <div>
    <PageHeader
      sub="系统管理"
      title="系统"
      em="设置"
      desc="站点标题、默认数据源、上传大小限制、历史保留天数等系统级配置。仅管理员可修改。"
    />
    <div class="page-card">
      <p v-if="!auth.isAdmin" style="color:var(--amber);margin-bottom:12px">仅管理员可修改设置（当前为只读）</p>
      <el-form label-position="top" style="max-width:560px" v-loading="loading">
        <el-form-item label="站点标题">
          <el-input v-model="form.site_title" :disabled="!auth.isAdmin" />
        </el-form-item>
        <el-form-item label="默认数据源">
          <el-select v-model="form.default_data_source" :disabled="!auth.isAdmin" style="width:100%">
            <el-option label="real" value="real" />
            <el-option label="gan" value="gan" />
          </el-select>
        </el-form-item>
        <el-form-item label="允许游客浏览">
          <el-select v-model="form.allow_guest_browse" :disabled="!auth.isAdmin" style="width:100%">
            <el-option label="true" value="true" />
            <el-option label="false" value="false" />
          </el-select>
        </el-form-item>
        <el-form-item label="允许注册">
          <el-select v-model="form.allow_register" :disabled="!auth.isAdmin" style="width:100%">
            <el-option label="true" value="true" />
            <el-option label="false" value="false" />
          </el-select>
        </el-form-item>
        <el-form-item label="默认注册角色">
          <el-select v-model="form.default_register_role" :disabled="!auth.isAdmin" style="width:100%">
            <el-option label="user" value="user" />
            <el-option label="guest" value="guest" />
          </el-select>
        </el-form-item>
        <el-form-item label="最大上传大小 (MB)">
          <el-input v-model="form.max_upload_size_mb" :disabled="!auth.isAdmin" />
        </el-form-item>
        <el-form-item label="历史保留天数">
          <el-input v-model="form.history_retention_days" :disabled="!auth.isAdmin" />
        </el-form-item>
        <el-button type="primary" :disabled="!auth.isAdmin" :loading="saving" @click="save">保存设置</el-button>
      </el-form>
    </div>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { get, put } from '@/api/http'
import { useAuthStore } from '@/stores/auth'
import PageHeader from '@/components/PageHeader.vue'

const auth = useAuthStore()
const loading = ref(false)
const saving = ref(false)
const form = reactive({
  site_title: 'FORGE-HV',
  default_data_source: 'real',
  allow_guest_browse: 'true',
  allow_register: 'true',
  default_register_role: 'user',
  max_upload_size_mb: '20',
  history_retention_days: '365',
})

const keys = Object.keys(form)

async function load() {
  loading.value = true
  const res = await get('/api/settings')
  loading.value = false
  if (res.error) {
    ElMessage.error(res.error)
    return
  }
  const s = res.settings || {}
  keys.forEach((k) => {
    if (s[k] !== undefined && s[k] !== null) form[k] = String(s[k])
  })
}

async function save() {
  const settings = {}
  keys.forEach((k) => { settings[k] = form[k] })
  saving.value = true
  const res = await put('/api/settings', { settings })
  saving.value = false
  if (res.error) {
    ElMessage.error(res.error)
    return
  }
  ElMessage.success('设置已保存')
  if (res.settings) {
    keys.forEach((k) => {
      if (res.settings[k] !== undefined) form[k] = String(res.settings[k])
    })
  }
}

onMounted(load)
</script>
