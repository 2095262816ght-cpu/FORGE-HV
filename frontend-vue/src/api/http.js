import axios from 'axios'
import { ElMessage } from 'element-plus'

const TOKEN_KEY = 'forge_token'

const http = axios.create({
  baseURL: import.meta.env.VITE_API_BASE || '',
  timeout: 60000,
})

http.interceptors.request.use((config) => {
  const token = localStorage.getItem(TOKEN_KEY)
  if (token) {
    config.headers = config.headers || {}
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

http.interceptors.response.use(
  (res) => res,
  (err) => {
    const status = err.response?.status
    // 仅 401 视为会话失效；403 为权限不足，不强制登出
    if (status === 401) {
      const detail = err.response?.data || { error: '未登录或登录已过期' }
      window.dispatchEvent(new CustomEvent('auth:unauthorized', { detail }))
    } else if (status === 403) {
      const msg = err.response?.data?.error || '权限不足'
      ElMessage.warning(msg)
    }
    return Promise.reject(err)
  },
)

function unwrap(res) {
  return res.data
}

function toError(err) {
  if (err.response?.data) return err.response.data
  if (err.code === 'ECONNABORTED') return { error: '请求超时' }
  return { error: err.message || '网络错误' }
}

export async function get(url, params, config = {}) {
  try {
    return unwrap(await http.get(url, { params, ...config }))
  } catch (e) {
    return toError(e)
  }
}

export async function post(url, data, config = {}) {
  try {
    return unwrap(await http.post(url, data, config))
  } catch (e) {
    return toError(e)
  }
}

export async function put(url, data, config = {}) {
  try {
    return unwrap(await http.put(url, data, config))
  } catch (e) {
    return toError(e)
  }
}

export async function del(url, config = {}) {
  try {
    return unwrap(await http.delete(url, config))
  } catch (e) {
    return toError(e)
  }
}

/** FormData 上传（不手动设 Content-Type，交由浏览器带 boundary） */
export async function upload(url, formData, config = {}) {
  try {
    const headers = { ...(config.headers || {}) }
    delete headers['Content-Type']
    delete headers['content-type']
    return unwrap(
      await http.post(url, formData, {
        ...config,
        headers,
      }),
    )
  } catch (e) {
    return toError(e)
  }
}

/** 带鉴权下载文件 */
export async function download(url, filename) {
  try {
    const res = await http.get(url, { responseType: 'blob' })
    const blob = res.data
    const objectUrl = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = objectUrl
    a.download = filename
    a.click()
    URL.revokeObjectURL(objectUrl)
    return { ok: true }
  } catch (e) {
    ElMessage.error('导出失败')
    return toError(e)
  }
}

export { http, TOKEN_KEY }
export default http
