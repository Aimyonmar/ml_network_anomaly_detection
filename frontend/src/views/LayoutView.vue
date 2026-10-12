<template>
  <el-container class="layout">
    <el-header class="header">
      <div class="brand">网络异常检测系统</div>
      <el-menu mode="horizontal" :default-active="activeMenu" router class="menu">
        <el-menu-item index="/upload">上传检测</el-menu-item>
        <el-menu-item index="/tasks">任务列表</el-menu-item>
        <el-menu-item index="/alerts">
          <el-badge
            :value="alertStore.openCount"
            :hidden="alertStore.openCount === 0"
            :max="99"
            class="alert-badge"
          >
            告警中心
          </el-badge>
        </el-menu-item>
      </el-menu>
      <div class="user-area">
        <span class="username">{{ auth.username }}</span>
        <el-button link type="danger" @click="onLogout">退出</el-button>
      </div>
    </el-header>
    <el-main class="main">
      <RouterView />
    </el-main>
  </el-container>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import { useAlertStore } from '../stores/alerts'

const ALERT_POLL_MS = 15000

const auth = useAuthStore()
const alertStore = useAlertStore()
const route = useRoute()
const router = useRouter()

const activeMenu = computed(() => {
  if (route.path.startsWith('/tasks')) return '/tasks'
  if (route.path.startsWith('/alerts')) return '/alerts'
  return '/upload'
})

let alertTimer: number | undefined

onMounted(() => {
  alertStore.fetchCount()
  alertTimer = window.setInterval(() => alertStore.fetchCount(), ALERT_POLL_MS)
})

onBeforeUnmount(() => clearInterval(alertTimer))

function onLogout() {
  auth.logout()
  router.push('/login')
}
</script>

<style scoped>
.layout {
  min-height: 100vh;
}
.header {
  display: flex;
  align-items: center;
  background: #fff;
  border-bottom: 1px solid #e4e7ed;
  padding: 0 24px;
}
.brand {
  font-size: 18px;
  font-weight: 600;
  margin-right: 32px;
  white-space: nowrap;
}
.menu {
  flex: 1;
  border-bottom: none !important;
}
.alert-badge {
  display: inline-flex;
  align-items: center;
}
.user-area {
  display: flex;
  align-items: center;
  gap: 12px;
}
.username {
  color: #606266;
}
.main {
  padding: 24px;
}
</style>
