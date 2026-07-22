import { defineStore } from 'pinia'
import { ref } from 'vue'

const STORAGE_KEY = 'forge_experiment_results'
const HISTORY_MAX = 40

function loadAll() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return { pages: {}, history: [] }
    const data = JSON.parse(raw)
    return {
      pages: data.pages || {},
      history: Array.isArray(data.history) ? data.history : [],
    }
  } catch {
    return { pages: {}, history: [] }
  }
}

function saveAll(pages, history) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify({ pages, history, savedAt: Date.now() }))
  } catch (e) {
    // 散点过大时降级：去掉 scatter 再存
    try {
      const slimPages = {}
      Object.entries(pages || {}).forEach(([k, v]) => {
        if (!v || typeof v !== 'object') {
          slimPages[k] = v
          return
        }
        const copy = { ...v }
        delete copy.scatter
        delete copy.scatterByKey
        delete copy.losses
        slimPages[k] = copy
      })
      localStorage.setItem(STORAGE_KEY, JSON.stringify({ pages: slimPages, history, savedAt: Date.now() }))
    } catch {
      /* ignore */
    }
  }
}

/** 散点过多时抽样，避免撑爆 localStorage */
function slimScatter(points, max = 300) {
  if (!Array.isArray(points) || points.length <= max) return points || []
  const step = Math.ceil(points.length / max)
  return points.filter((_, i) => i % step === 0).slice(0, max)
}

export const useResultsStore = defineStore('results', () => {
  const initial = loadAll()
  const pages = ref(initial.pages)
  const history = ref(initial.history)

  function persist() {
    saveAll(pages.value, history.value)
  }

  function getPage(key) {
    return pages.value[key] || null
  }

  function setPage(key, payload) {
    pages.value = {
      ...pages.value,
      [key]: {
        ...payload,
        savedAt: Date.now(),
      },
    }
    persist()
  }

  function clearPage(key) {
    const next = { ...pages.value }
    delete next[key]
    pages.value = next
    persist()
  }

  function addHistory(entry) {
    const item = {
      id: `${Date.now()}_${Math.random().toString(36).slice(2, 8)}`,
      savedAt: Date.now(),
      ...entry,
    }
    history.value = [item, ...history.value].slice(0, HISTORY_MAX)
    persist()
    return item
  }

  function clearHistory() {
    history.value = []
    persist()
  }

  return {
    pages,
    history,
    getPage,
    setPage,
    clearPage,
    addHistory,
    clearHistory,
    slimScatter,
  }
})
