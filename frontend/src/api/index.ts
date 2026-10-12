import http from './http'
import type {
  AlertCountData,
  AlertItem,
  ApiResponse,
  PageData,
  ResultItem,
  StatsData,
  TaskCreatedData,
  TaskItem,
  TokenData,
  UserInfo,
} from '../types'

export const authApi = {
  login: (username: string, password: string) =>
    http.post<never, ApiResponse<TokenData>>('/auth/login', { username, password }),
  register: (username: string, password: string) =>
    http.post<never, ApiResponse<UserInfo>>('/auth/register', { username, password }),
  me: () => http.get<never, ApiResponse<UserInfo>>('/auth/me'),
}

export const taskApi = {
  create: (file: File) => {
    const fd = new FormData()
    fd.append('file', file)
    return http.post<never, ApiResponse<TaskCreatedData>>('/tasks', fd)
  },
  list: (page: number, pageSize: number) =>
    http.get<never, ApiResponse<PageData<TaskItem>>>('/tasks', {
      params: { page, page_size: pageSize },
    }),
  detail: (id: number) => http.get<never, ApiResponse<TaskItem>>(`/tasks/${id}`),
  results: (id: number, page: number, pageSize: number) =>
    http.get<never, ApiResponse<PageData<ResultItem>>>(`/tasks/${id}/results`, {
      params: { page, page_size: pageSize },
    }),
  stats: (id: number) => http.get<never, ApiResponse<StatsData>>(`/tasks/${id}/stats`),
}

export const alertApi = {
  list: (status: string, page: number, pageSize: number) =>
    http.get<never, ApiResponse<PageData<AlertItem>>>('/alerts', {
      params: { status, page, page_size: pageSize },
    }),
  // 高频轮询静默失败（菜单红点），避免后端不可达时刷屏
  count: () =>
    http.get<never, ApiResponse<AlertCountData>>('/alerts/count', { _silent: true }),
  ack: (id: number) => http.put<never, ApiResponse<AlertItem>>(`/alerts/${id}/ack`),
  dismiss: (id: number) => http.put<never, ApiResponse<AlertItem>>(`/alerts/${id}/dismiss`),
}
