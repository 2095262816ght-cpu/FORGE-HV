<template>
  <div class="login-overlay show login-page">
    <div class="login-box">
      <div class="login-brand">
        <svg width="32" height="32" viewBox="0 0 24 24" fill="none">
          <rect x="3" y="3" width="18" height="18" rx="5" fill="url(#fg2)" opacity=".9" />
          <path d="M8 12.5L11 15.5L16.5 9" stroke="#fff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" />
          <defs>
            <linearGradient id="fg2" x1="3" y1="3" x2="21" y2="21">
              <stop stop-color="#2563EB" />
              <stop offset="1" stop-color="#0EA5E9" />
            </linearGradient>
          </defs>
        </svg>
        <span>合金维氏硬度预测</span>
      </div>
      <div class="login-title">合金维氏硬度预测</div>
      <div class="login-sub">{{ subtitle }}</div>

      <div class="login-form">
        <div class="field">
          <label class="field-label">用户名</label>
          <input
            v-model="form.username"
            class="input"
            type="text"
            placeholder="admin"
            autocomplete="username"
            @keyup.enter="focusPwd"
          />
        </div>
        <div class="field">
          <label class="field-label">密码</label>
          <div class="pwd-wrap">
            <input
              ref="pwdRef"
              v-model="form.password"
              class="input"
              :type="showPwd ? 'text' : 'password'"
              placeholder="admin123"
              autocomplete="current-password"
              @keyup.enter="mode === 'login' ? doLogin() : doRegister()"
            />
            <button type="button" class="pwd-toggle" tabindex="-1" @click="showPwd = !showPwd">
              {{ showPwd ? '🙈' : '👁' }}
            </button>
          </div>
        </div>

        <template v-if="mode === 'register'">
          <div class="field">
            <label class="field-label">确认密码</label>
            <div class="pwd-wrap">
              <input
                v-model="form.confirm"
                class="input"
                :type="showConfirm ? 'text' : 'password'"
                placeholder="再次输入密码"
                autocomplete="new-password"
              />
              <button type="button" class="pwd-toggle" tabindex="-1" @click="showConfirm = !showConfirm">
                {{ showConfirm ? '🙈' : '👁' }}
              </button>
            </div>
          </div>
          <div class="field">
            <label class="field-label">显示名（可选）</label>
            <input v-model="form.display_name" class="input" type="text" placeholder="如：张三" />
          </div>
          <div class="field">
            <label class="field-label">邮箱（可选）</label>
            <input v-model="form.email" class="input" type="email" placeholder="user@example.com" />
          </div>
        </template>

        <div class="login-error">{{ error }}</div>

        <button
          v-if="mode === 'login'"
          type="button"
          class="btn btn-primary login-submit"
          :disabled="loading"
          @click="doLogin"
        >
          {{ loading ? '登录中…' : '登 录 →' }}
        </button>
        <button
          v-else
          type="button"
          class="btn btn-primary login-register"
          :disabled="loading"
          @click="doRegister"
        >
          {{ loading ? '注册中…' : '注 册 并 登 录 →' }}
        </button>

        <button
          v-if="mode === 'login' && allowGuest"
          type="button"
          class="btn btn-ghost login-guest"
          :disabled="guestLoading"
          style="width:100%;margin-top:8px;padding:10px 16px"
          @click="doGuest"
        >
          {{ guestLoading ? '进入中…' : '👤 以游客身份浏览' }}
        </button>

        <div v-if="mode === 'login' && allowRegister" class="login-switch">
          还没有账号？<a href="javascript:void(0)" @click.prevent="mode = 'register'">立即注册</a>
        </div>
        <div v-if="mode === 'register'" class="login-switch">
          已有账号？<a href="javascript:void(0)" @click.prevent="mode = 'login'">返回登录</a>
        </div>

        <div v-if="mode === 'login'" class="login-hint">默认账号 admin / admin123（管理员）</div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useAuthStore } from '@/stores/auth'
import { get } from '@/api/http'

const auth = useAuthStore()
const router = useRouter()
const route = useRoute()

const mode = ref('login')
const loading = ref(false)
const guestLoading = ref(false)
const error = ref('')
const allowGuest = ref(false)
const allowRegister = ref(true)
const showPwd = ref(false)
const showConfirm = ref(false)
const pwdRef = ref(null)

const form = reactive({
  username: '',
  password: '',
  confirm: '',
  display_name: '',
  email: '',
})

const subtitle = computed(() =>
  mode.value === 'register'
    ? '基于 DDPG 的合金维氏硬度预测 · 填写信息注册新账号'
    : '基于 DDPG 的合金维氏硬度预测 · 请登录后使用',
)

function focusPwd() {
  pwdRef.value?.focus?.()
}

function goHome() {
  const redirect = route.query.redirect || '/dashboard'
  router.replace(String(redirect))
}

async function doLogin() {
  error.value = ''
  if (!form.username || !form.password) {
    error.value = '请输入用户名和密码'
    return
  }
  loading.value = true
  const res = await auth.login(form.username.trim(), form.password)
  loading.value = false
  if (res.error) {
    error.value = res.error
    return
  }
  ElMessage.success(`欢迎回来，${res.user.display_name || res.user.username}`)
  goHome()
}

async function doGuest() {
  error.value = ''
  guestLoading.value = true
  const res = await auth.guestLogin()
  guestLoading.value = false
  if (res.error) {
    error.value = res.error
    return
  }
  ElMessage.success('已以游客身份进入（只读模式）')
  goHome()
}

async function doRegister() {
  error.value = ''
  const username = form.username.trim()
  const password = form.password
  if (!username || !password) {
    error.value = '用户名和密码不能为空'
    return
  }
  if (username.length < 3 || username.length > 20) {
    error.value = '用户名长度需 3-20 个字符'
    return
  }
  if (!/^[A-Za-z0-9_]+$/.test(username)) {
    error.value = '用户名只能含字母、数字、下划线'
    return
  }
  if (password.length < 6 || password.length > 64) {
    error.value = '密码长度需 6-64 个字符'
    return
  }
  if (password !== form.confirm) {
    error.value = '两次输入的密码不一致'
    return
  }
  loading.value = true
  const res = await auth.register({
    username,
    password,
    display_name: form.display_name.trim(),
    email: form.email.trim(),
  })
  loading.value = false
  if (res.error) {
    error.value = res.error
    return
  }
  ElMessage.success(`注册成功，欢迎加入，${res.user.display_name || res.user.username}`)
  goHome()
}

onMounted(async () => {
  const res = await get('/api/settings')
  const s = res.settings || {}
  allowGuest.value = s.allow_guest_browse === 'true'
  allowRegister.value = s.allow_register !== 'false'
})
</script>
