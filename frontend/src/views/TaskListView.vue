<template>
  <el-card>
    <template #header>
      <div class="card-header">
        <span>我的检测任务</span>
        <el-button :icon="Refresh" circle @click="load" />
      </div>
    </template>
    <el-table :data="items" v-loading="loading" empty-text="暂无任务，请先上传文件">
      <el-table-column prop="id" label="ID" width="70" />
      <el-table-column prop="file_name" label="文件名" min-width="180" show-overflow-tooltip />
      <el-table-column label="状态" width="110">
        <template #default="{ row }">
          <el-tag :type="statusType(row.status)">{{ statusText(row.status) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="total_rows" label="总行数" width="90" />
      <el-table-column prop="attack_rows" label="攻击行" width="80" />
      <el-table-column prop="normal_rows" label="正常行" width="80" />
      <el-table-column label="耗时" width="90">
        <template #default="{ row }">
          {{ row.cost_seconds != null ? row.cost_seconds.toFixed(2) + 's' : '—' }}
        </template>
      </el-table-column>
      <el-table-column prop="created_at" label="创建时间" width="170">
        <template #default="{ row }">{{ fmtTime(row.created_at) }}</template>
      </el-table-column>
      <el-table-column label="操作" width="110" fixed="right">
        <template #default="{ row }">
          <el-button
            link
            type="primary"
            :disabled="row.status !== 'success'"
            @click="goReport(row.id)"
          >
            查看报告
          </el-button>
        </template>
      </el-table-column>
    </el-table>
    <el-pagination
      class="pager"
      layout="total, prev, pager, next"
      :total="total"
      :page-size="pageSize"
      :current-page="page"
      @current-change="onPageChange"
    />
  </el-card>
</template>

<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { Refresh } from '@element-plus/icons-vue'
import { taskApi } from '../api'
import type { TaskItem } from '../types'

const POLL_MS = 2000

const router = useRouter()
const items = ref<TaskItem[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = 20
const loading = ref(false)
let timer: number | undefined

async function load() {
  loading.value = true
  try {
    const resp = await taskApi.list(page.value, pageSize)
    items.value = resp.data.items as TaskItem[]
    total.value = resp.data.total
    schedulePoll()
  } catch {
    // 拦截器已提示
  } finally {
    loading.value = false
  }
}

// 仅轮询当前页未完成任务的状态（pending/running → success/failed）
function schedulePoll() {
  clearTimeout(timer)
  const pending = items.value.filter(
    (t) => t.status === 'pending' || t.status === 'running',
  )
  if (pending.length === 0) return
  timer = window.setTimeout(async () => {
    for (const t of pending) {
      try {
        const resp = await taskApi.detail(t.id)
        const d = resp.data
        t.status = d.status
        t.total_rows = d.total_rows
        t.attack_rows = d.attack_rows
        t.normal_rows = d.normal_rows
        t.cost_seconds = d.cost_seconds
      } catch {
        break // 后端不可达，停止本轮
      }
    }
    schedulePoll()
  }, POLL_MS)
}

function onPageChange(p: number) {
  page.value = p
  load()
}

function goReport(id: number) {
  router.push(`/tasks/${id}/report`)
}

function statusText(s: string) {
  return { pending: '排队中', running: '检测中', success: '完成', failed: '失败' }[s] || s
}

function statusType(s: string) {
  return { pending: 'info', running: 'warning', success: 'success', failed: 'danger' }[
    s as 'pending'
  ] as 'info'
}

function fmtTime(iso: string) {
  return new Date(iso).toLocaleString('zh-CN', { hour12: false })
}

onMounted(load)
onBeforeUnmount(() => clearTimeout(timer))
</script>

<style scoped>
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.pager {
  margin-top: 16px;
  justify-content: flex-end;
}
</style>
