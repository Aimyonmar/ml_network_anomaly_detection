<template>
  <div class="upload-page">
    <el-card class="live-card">
      <template #header>
        <span>一键体检（推荐 · 零门槛）</span>
      </template>
      <el-alert
        type="info"
        :closable="false"
        class="live-boundary"
        title="无需准备任何文件：系统在本机自动抓取网络流量并检测。检测对象是本系统所在电脑的网络流量；检测为初筛，不拦截不阻断。"
      />
      <div v-if="!liveTaskId" class="live-form">
        <span class="live-label">体检时长：</span>
        <el-radio-group v-model="liveDuration" :disabled="liveLoading">
          <el-radio-button :value="30">30 秒</el-radio-button>
          <el-radio-button :value="60">60 秒（推荐）</el-radio-button>
          <el-radio-button :value="120">2 分钟</el-radio-button>
        </el-radio-group>
        <el-button
          type="primary"
          :loading="liveLoading"
          class="live-btn"
          @click="doLiveScan"
        >
          开始体检
        </el-button>
      </div>
      <div v-else>
        <el-alert
          v-if="liveStatus === 'pending' || liveStatus === 'running'"
          type="success"
          :closable="false"
        >
          <template #title>
            正在体检：请正常使用网络（如浏览网页、聊天），结束后自动出报告。
            {{ liveCountdownText }}
          </template>
        </el-alert>
        <el-alert v-else-if="liveStatus === 'success'" type="success" :closable="false">
          <template #title>
            体检完成（task_id={{ liveTaskId }}）。
            <el-link type="primary" @click="goReport(liveTaskId)">查看报告</el-link>
            或
            <el-link type="primary" @click="goTasks">前往任务列表</el-link>
          </template>
        </el-alert>
        <el-alert v-else-if="liveStatus === 'failed'" type="error" :closable="false">
          <template #title>
            体检失败：{{ liveErrorMsg || '未知原因' }}
            <el-link type="primary" @click="resetLive">重新体检</el-link>
          </template>
        </el-alert>
      </div>
    </el-card>

    <el-card>
      <template #header>上传流量文件</template>
      <el-upload
        drag
        :auto-upload="false"
        :limit="1"
        accept=".csv,.pcap"
        :file-list="fileList"
        :on-change="onFileChange"
        :on-exceed="onExceed"
        :on-remove="onRemove"
      >
        <el-icon class="upload-icon"><UploadFilled /></el-icon>
        <div class="el-upload__text">
          将 .csv / .pcap 文件拖到此处，或<em>点击选择</em>
        </div>
        <template #tip>
          <div class="el-upload__tip">
            支持 .csv（NSL-KDD 41 列 / CIC-IDS2017 78 列，表头自动识别）与 .pcap
            原始抓包（服务端解析流特征），大小不超过 50MB
          </div>
        </template>
      </el-upload>
      <div class="actions">
        <el-button
          type="primary"
          :disabled="!currentFile"
          :loading="uploading"
          @click="doUpload"
        >
          开始检测
        </el-button>
      </div>
      <el-alert
        v-if="createdTaskId"
        type="success"
        :closable="false"
        class="result-alert"
      >
        任务已创建（task_id={{ createdTaskId }}），后台检测中。
        <el-link type="primary" @click="goReport(createdTaskId)">查看报告</el-link>
        或
        <el-link type="primary" @click="goTasks">前往任务列表</el-link>
      </el-alert>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { computed, onUnmounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, type UploadFile, type UploadUserFile } from 'element-plus'
import { UploadFilled } from '@element-plus/icons-vue'
import { taskApi } from '../api'
import type { TaskStatus } from '../types'

const MAX_MB = 50
const router = useRouter()

// ---------- V3 一键体检 ----------
const liveDuration = ref(60)
const liveLoading = ref(false)
const liveTaskId = ref<number | null>(null)
const liveStatus = ref<TaskStatus>('pending')
const liveErrorMsg = ref<string | null>(null)
const liveEndsAt = ref(0) // 抓包窗口结束时间戳（ms）
const nowTs = ref(Date.now())

let liveTimer: number | null = null

const liveCountdownText = computed(() => {
  const remain = Math.ceil((liveEndsAt.value - nowTs.value) / 1000)
  if (remain > 0) return `抓包中，剩余约 ${remain} 秒…`
  return '抓包结束，正在分析检测…'
})

async function doLiveScan() {
  liveLoading.value = true
  try {
    const resp = await taskApi.live(liveDuration.value)
    liveTaskId.value = resp.data.task_id
    liveStatus.value = 'pending'
    liveErrorMsg.value = null
    liveEndsAt.value = Date.now() + liveDuration.value * 1000
    startLivePolling()
    ElMessage.success('体检已开始，请正常使用网络')
  } catch {
    // 拦截器已提示（含 409 重复体检、400 时长不合法）
  } finally {
    liveLoading.value = false
  }
}

function startLivePolling() {
  stopLivePolling()
  liveTimer = window.setInterval(async () => {
    nowTs.value = Date.now()
    const id = liveTaskId.value
    if (id == null) return stopLivePolling()
    try {
      const resp = await taskApi.detail(id)
      liveStatus.value = resp.data.status
      liveErrorMsg.value = resp.data.error_msg
      if (liveStatus.value === 'success' || liveStatus.value === 'failed') {
        stopLivePolling()
      }
    } catch {
      // 轮询失败静默重试（后端不可达时拦截器已有全局提示）
    }
  }, 3000)
}

function stopLivePolling() {
  if (liveTimer != null) {
    window.clearInterval(liveTimer)
    liveTimer = null
  }
}

function resetLive() {
  liveTaskId.value = null
  liveStatus.value = 'pending'
  liveErrorMsg.value = null
}

onUnmounted(() => stopLivePolling())

// ---------- 上传检测（V1/V2 原有链路） ----------
const fileList = ref<UploadUserFile[]>([])
const currentFile = ref<File | null>(null)
const uploading = ref(false)
const createdTaskId = ref<number | null>(null)

function onFileChange(file: UploadFile) {
  createdTaskId.value = null
  const raw = file.raw
  if (!raw) return
  const ok = ['.csv', '.pcap'].some((ext) =>
    file.name.toLowerCase().endsWith(ext),
  )
  if (!ok) {
    ElMessage.error('仅支持 .csv 或 .pcap 文件')
    fileList.value = []
    currentFile.value = null
    return
  }
  if (raw.size > MAX_MB * 1024 * 1024) {
    ElMessage.error(`文件大小超过 ${MAX_MB}MB 限制`)
    fileList.value = []
    currentFile.value = null
    return
  }
  fileList.value = [file]
  currentFile.value = raw
}

function onRemove() {
  fileList.value = []
  currentFile.value = null
}

function onExceed(files: File[]) {
  // 超出 limit=1 时替换为最新选择
  const f = files[0]
  if (f) onFileChange({ name: f.name, raw: f } as unknown as UploadFile)
}

async function doUpload() {
  if (!currentFile.value) return
  uploading.value = true
  try {
    const resp = await taskApi.create(currentFile.value)
    createdTaskId.value = resp.data.task_id
    ElMessage.success('上传成功，任务已创建')
  } catch {
    // 拦截器已提示
  } finally {
    uploading.value = false
  }
}

function goReport(id: number) {
  router.push(`/tasks/${id}/report`)
}

function goTasks() {
  router.push('/tasks')
}
</script>

<style scoped>
.upload-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.live-boundary {
  margin-bottom: 16px;
}
.live-form {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}
.live-label {
  color: #606266;
}
.live-btn {
  margin-left: auto;
}
.upload-icon {
  font-size: 60px;
  color: #c0c4cc;
}
.actions {
  margin-top: 16px;
}
.result-alert {
  margin-top: 16px;
}
</style>
