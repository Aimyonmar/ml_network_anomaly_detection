<template>
  <el-container class="layout">
    <el-header class="header">
      <div class="brand">网络异常检测系统</div>
      <el-menu mode="horizontal" :default-active="activeMenu" router class="menu">
        <el-menu-item index="/upload">上传检测</el-menu-item>
        <el-menu-item index="/tasks">任务列表</el-menu-item>
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
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()
const route = useRoute()
const router = useRouter()

const activeMenu = computed(() =>
  route.path.startsWith('/tasks') ? '/tasks' : '/upload',
)

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
