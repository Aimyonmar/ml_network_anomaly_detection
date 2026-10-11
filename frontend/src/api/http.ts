import axios from 'axios'
import { ElMessage } from 'element-plus'
import { useAuthStore } from '../stores/auth'
import router from '../router'

const http = axios.create({
  baseURL: '/api/v1',
  timeout: 15000,
})

// 请求拦截：附加 JWT
http.interceptors.request.use((config) => {
  const auth = useAuthStore()
  if (auth.token) {
    config.headers.Authorization = `Bearer ${auth.token}`
  }
  return config
})

// 响应拦截：拆 {code,msg,data}；401 跳登录；后端不可达提示错误
http.interceptors.response.use(
  (resp) => {
    const body = resp.data
    if (body && typeof body === 'object' && 'code' in body) {
      if (body.code >= 200 && body.code < 300) return body
      ElMessage.error(body.msg || '请求失败')
      return Promise.reject(new Error(body.msg))
    }
    return body
  },
  (error) => {
    const status = error.response?.status
    if (status === 401) {
      const auth = useAuthStore()
      auth.logout()
      ElMessage.warning('登录已过期，请重新登录')
      router.push('/login')
    } else if (!error.response) {
      ElMessage.error('无法连接后端服务，请确认服务已启动')
    } else {
      const data = error.response.data
      // dev 下 vite 代理连不上后端会返回 500/502/504 且无标准 {code,msg,data} 结构
      const isProxyDown =
        [500, 502, 503, 504].includes(status ?? 0) &&
        (!data || typeof data !== 'object' || !('code' in data))
      if (isProxyDown) {
        ElMessage.error('无法连接后端服务，请确认服务已启动')
      } else {
        ElMessage.error(data?.msg || `请求失败（${status}）`)
      }
    }
    return Promise.reject(error)
  },
)

export default http
