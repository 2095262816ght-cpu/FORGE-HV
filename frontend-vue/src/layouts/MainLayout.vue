<template>
  <div class="app-shell" :class="{ collapsed }">
    <aside class="sidebar">
      <div class="brand">
        <div class="brand-mark">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" style="vertical-align:-3px;margin-right:8px">
            <rect x="3" y="3" width="18" height="18" rx="5" fill="url(#fg1)" opacity=".9" />
            <path d="M8 12.5L11 15.5L16.5 9" stroke="#fff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" />
            <defs>
              <linearGradient id="fg1" x1="3" y1="3" x2="21" y2="21">
                <stop stop-color="#2563EB" />
                <stop offset="1" stop-color="#0EA5E9" />
              </linearGradient>
            </defs>
          </svg>FORGE
        </div>
        <div class="brand-sub">合金维氏硬度预测</div>
        <div class="brand-meta"><span class="dot"></span><span>v3.2 · 论文对齐</span></div>
      </div>

      <div class="sidebar-toggle" title="折叠/展开侧边栏" @click="collapsed = !collapsed">
        {{ collapsed ? '⟩' : '⟨' }}
      </div>

      <nav class="nav nav-scroll">
        <div
          v-for="g in visibleGroups"
          :key="g.title"
          class="nav-group"
          :class="{ collapsed: collapsedGroups[g.title] }"
        >
          <div class="nav-cat" @click="toggleGroup(g.title)">
            {{ g.title }} <span class="arrow">▼</span>
          </div>
          <template v-if="!collapsedGroups[g.title] || collapsed">
            <router-link
              v-for="item in g.items"
              :key="item.path"
              :to="item.path"
              class="nav-item"
              :title="item.label"
            >
              <span class="ic">{{ item.icon }}</span>
              <span>{{ item.label }}</span>
            </router-link>
          </template>
        </div>
      </nav>

      <div class="sidebar-foot">
        <span>HGMX-22E</span>
        <span>RTX 3060</span>
      </div>
    </aside>

    <main class="main-area">
      <header class="topbar">
        <div class="crumb">
          <span>FORGE</span><span class="sep">/</span>
          <span>{{ crumbCat }}</span><span class="sep">/</span>
          <b>{{ crumbPage }}</b>
        </div>
        <div class="topbar-r">
          <span class="kbd">⌘K</span>
          <div class="gpu-badge"><span class="gd"></span>CUDA 12.6 · 6GB</div>
          <div ref="userMenuRef" class="user-menu" @click.stop="userOpen = !userOpen">
            <div class="user-avatar">{{ avatarLetter }}</div>
            <span class="user-name">{{ displayName }}</span>
            <div class="user-dropdown" :class="{ show: userOpen }">
              <div class="user-info">
                <div class="user-info-name">{{ displayName }}</div>
                <div class="user-info-role">{{ roleLabel }}</div>
              </div>
              <div v-if="!auth.isGuest" class="user-dropdown-item" @click="openPassword">🔑 修改密码</div>
              <div class="user-dropdown-item danger" @click="doLogout">⏻ 退出登录</div>
            </div>
          </div>
        </div>
      </header>

      <section class="content">
        <router-view v-slot="{ Component, route }">
          <keep-alive :include="['DdpgView', 'Cmp53View', 'Cmp54View', 'OutliersView', 'DashboardView']">
            <component :is="Component" :key="route.name" />
          </keep-alive>
        </router-view>
      </section>
    </main>

    <div
      v-if="pwdVisible"
      class="modal-overlay"
      style="display: flex"
      @click.self="pwdVisible = false"
    >
      <div class="modal-box">
        <div class="modal-head">
          <div class="modal-title">🔑 修改密码</div>
          <button type="button" class="modal-close" @click="pwdVisible = false">✕</button>
        </div>
        <div class="modal-body">
          <div class="field">
            <label class="field-label">原密码</label>
            <input v-model="pwdForm.old" class="input" type="password" autocomplete="current-password" />
          </div>
          <div class="field">
            <label class="field-label">新密码（至少 6 位）</label>
            <input v-model="pwdForm.next" class="input" type="password" autocomplete="new-password" />
          </div>
          <div class="field">
            <label class="field-label">确认新密码</label>
            <input v-model="pwdForm.confirm" class="input" type="password" autocomplete="new-password" />
          </div>
        </div>
        <div class="modal-foot">
          <button type="button" class="btn btn-ghost" @click="pwdVisible = false">取消</button>
          <button type="button" class="btn btn-primary" :disabled="pwdLoading" @click="savePassword">
            {{ pwdLoading ? '保存中…' : '确认修改' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useAuthStore } from '@/stores/auth'
import { CRUMB_CAT, NAV_GROUPS, PAGE_NAMES, ROLE_LABELS } from '@/utils/constants'

const auth = useAuthStore()
const route = useRoute()
const router = useRouter()

const collapsed = ref(false)
const collapsedGroups = reactive({})
const pwdVisible = ref(false)
const pwdLoading = ref(false)
const userOpen = ref(false)
const userMenuRef = ref(null)
const pwdForm = reactive({ old: '', next: '', confirm: '' })

const pageKey = computed(() => route.name || 'dashboard')
const crumbCat = computed(() => CRUMB_CAT[pageKey.value] || '')
const crumbPage = computed(() => PAGE_NAMES[pageKey.value] || '')
const avatarLetter = computed(() => (auth.user?.username || 'U').charAt(0).toUpperCase())
const displayName = computed(() => auth.user?.display_name || auth.user?.username || '未登录')
const roleLabel = computed(() => ROLE_LABELS[auth.user?.role] || '未知')

const visibleGroups = computed(() =>
  NAV_GROUPS.map((g) => ({
    ...g,
    items: g.items.filter((it) => !it.adminOnly || auth.isAdmin),
  })).filter((g) => g.items.length),
)

function toggleGroup(title) {
  collapsedGroups[title] = !collapsedGroups[title]
}

function closeUserMenu() {
  userOpen.value = false
}

function onDocClick(e) {
  if (userMenuRef.value && !userMenuRef.value.contains(e.target)) {
    closeUserMenu()
  }
}

function openPassword() {
  closeUserMenu()
  pwdForm.old = ''
  pwdForm.next = ''
  pwdForm.confirm = ''
  pwdVisible.value = true
}

function doLogout() {
  closeUserMenu()
  auth.logout()
  router.push('/login')
  ElMessage.success('已退出登录')
}

async function savePassword() {
  if (!pwdForm.old || !pwdForm.next) {
    ElMessage.warning('原密码和新密码不能为空')
    return
  }
  if (pwdForm.next !== pwdForm.confirm) {
    ElMessage.warning('两次新密码不一致')
    return
  }
  if (pwdForm.next.length < 6) {
    ElMessage.warning('新密码至少 6 位')
    return
  }
  pwdLoading.value = true
  const res = await auth.changePassword(pwdForm.old, pwdForm.next)
  pwdLoading.value = false
  if (res.error) {
    ElMessage.error(res.error)
    return
  }
  ElMessage.success('密码修改成功')
  pwdVisible.value = false
}

function onUnauthorized() {
  ElMessage.warning('登录已过期，请重新登录')
  auth.logout()
  router.push('/login')
}

onMounted(() => {
  window.addEventListener('auth:unauthorized', onUnauthorized)
  document.addEventListener('click', onDocClick)
})
onUnmounted(() => {
  window.removeEventListener('auth:unauthorized', onUnauthorized)
  document.removeEventListener('click', onDocClick)
})
</script>
