import { ref } from 'vue'
import { defineStore } from 'pinia'
import { alertApi } from '../api'

/** 菜单红点共享状态：Layout 定时轮询，告警页处置后主动刷新 */
export const useAlertStore = defineStore('alerts', () => {
  const openCount = ref(0)

  async function fetchCount() {
    try {
      const resp = await alertApi.count()
      openCount.value = resp.data.open_count
    } catch {
      // _silent 请求，静默失败
    }
  }

  return { openCount, fetchCount }
})
