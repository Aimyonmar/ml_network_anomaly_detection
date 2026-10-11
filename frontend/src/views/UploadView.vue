<template>
  <el-card>
    <template #header>上传流量 CSV 文件</template>
    <el-upload
      drag
      :auto-upload="false"
      :limit="1"
      accept=".csv"
      :file-list="fileList"
      :on-change="onFileChange"
      :on-exceed="onExceed"
      :on-remove="onRemove"
    >
      <el-icon class="upload-icon"><UploadFilled /></el-icon>
      <div class="el-upload__text">
        将 .csv 文件拖到此处，或<em>点击选择</em>
      </div>
      <template #tip>
        <div class="el-upload__tip">仅支持 .csv 文件，大小不超过 50MB</div>
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
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, type UploadFile, type UploadUserFile } from 'element-plus'
import { UploadFilled } from '@element-plus/icons-vue'
import { taskApi } from '../api'

const MAX_MB = 50
const router = useRouter()
const fileList = ref<UploadUserFile[]>([])
const currentFile = ref<File | null>(null)
const uploading = ref(false)
const createdTaskId = ref<number | null>(null)

function onFileChange(file: UploadFile) {
  createdTaskId.value = null
  const raw = file.raw
  if (!raw) return
  if (!file.name.toLowerCase().endsWith('.csv')) {
    ElMessage.error('仅支持 .csv 文件')
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
