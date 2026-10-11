<template>
  <div class="login-page">
    <el-card class="login-card">
      <h2 class="title">网络异常检测系统</h2>
      <el-tabs v-model="tab">
        <el-tab-pane label="登录" name="login" />
        <el-tab-pane label="注册" name="register" />
      </el-tabs>
      <el-form :model="form" label-width="0" @submit.prevent>
        <el-form-item>
          <el-input
            v-model="form.username"
            placeholder="用户名（3~50 字符）"
            :prefix-icon="User"
            clearable
          />
        </el-form-item>
        <el-form-item>
          <el-input
            v-model="form.password"
            type="password"
            placeholder="密码（至少 6 位）"
            :prefix-icon="Lock"
            show-password
            @keyup.enter="submit"
          />
        </el-form-item>
        <el-button
          class="submit-btn"
          type="primary"
          :loading="loading"
          @click="submit"
        >
          {{ tab === 'login' ? '登 录' : '注 册' }}
        </el-button>
      </el-form>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Lock, User } from '@element-plus/icons-vue'
import { authApi } from '../api'
import { useAuthStore } from '../stores/auth'

const router = useRouter()
const auth = useAuthStore()
const tab = ref<'login' | 'register'>('login')
const loading = ref(false)
const form = reactive({ username: '', password: '' })

async function submit() {
  if (!form.username || !form.password) {
    ElMessage.warning('请输入用户名和密码')
    return
  }
  loading.value = true
  try {
    if (tab.value === 'register') {
      await authApi.register(form.username, form.password)
      ElMessage.success('注册成功，请登录')
      tab.value = 'login'
    } else {
      const resp = await authApi.login(form.username, form.password)
      auth.setAuth({ ...resp.data, username: form.username })
      ElMessage.success('登录成功')
      router.push('/')
    }
  } catch {
    // 错误提示已由 axios 拦截器统一处理
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-page {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 100vh;
}
.login-card {
  width: 380px;
}
.title {
  margin: 0 0 8px;
  text-align: center;
  font-size: 20px;
}
.submit-btn {
  width: 100%;
}
</style>
