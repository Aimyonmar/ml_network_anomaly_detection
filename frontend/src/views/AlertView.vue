<template>
  <el-card>
    <template #header>
      <div class="card-header">
        <span>告警中心</span>
        <el-radio-group v-model="status" @change="onFilterChange">
          <el-radio-button value="all">全部</el-radio-button>
          <el-radio-button value="open">待处置</el-radio-button>
          <el-radio-button value="acked">已确认</el-radio-button>
          <el-radio-button value="dismissed">已忽略</el-radio-button>
        </el-radio-group>
      </div>
    </template>
    <el-alert
      v-if="status === 'open'"
      type="info"
      :closable="false"
      class="rule-alert"
      title="处置建议命令仅供人工审核后手动执行，系统绝不自动阻断（CONTEXT.md §10.2）"
    />
    <el-table :data="items" v-loading="loading" empty-text="暂无告警">
      <el-table-column prop="id" label="ID" width="70" />
      <el-table-column label="攻击源" min-width="140">
        <template #default="{ row }">
          <code class="mono">{{ row.src_key }}</code>
        </template>
      </el-table-column>
      <el-table-column label="置信度" width="130" sortable :sort-by="'confidence'" :sort-method="sortByConfidence">
        <template #default="{ row }">
          <el-progress
            :percentage="Math.round(row.confidence * 100)"
            :stroke-width="10"
            :color="confColor(row.confidence)"
          />
        </template>
      </el-table-column>
      <el-table-column label="状态" width="90">
        <template #default="{ row }">
          <el-tag :type="statusType(row.status)">{{ statusText(row.status) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="处置建议（人工执行）" min-width="260">
        <template #default="{ row }">
          <div v-if="row.rule_cmd" class="rule-cell">
            <code class="mono rule-text">{{ row.rule_cmd }}</code>
            <el-button link type="primary" size="small" @click="copyCmd(row.rule_cmd)">
              复制
            </el-button>
          </div>
          <span v-else>—</span>
        </template>
      </el-table-column>
      <el-table-column label="触发任务" width="90">
        <template #default="{ row }">
          <el-link type="primary" @click="goReport(row.task_id)">#{{ row.task_id }}</el-link>
        </template>
      </el-table-column>
      <el-table-column label="时间" width="170">
        <template #default="{ row }">{{ fmtTime(row.created_at) }}</template>
      </el-table-column>
      <el-table-column label="操作" width="130" fixed="right">
        <template #default="{ row }">
          <template v-if="row.status === 'open'">
            <el-button link type="success" @click="ack(row.id)">确认</el-button>
            <el-button link type="info" @click="dismiss(row.id)">忽略</el-button>
          </template>
          <span v-else class="done-mark">—</span>
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
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { alertApi } from '../api'
import { useAlertStore } from '../stores/alerts'
import type { AlertItem } from '../types'

const router = useRouter()
const alertStore = useAlertStore()

const items = ref<AlertItem[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = 20
const status = ref('all')
const loading = ref(false)

async function load() {
  loading.value = true
  try {
    const resp = await alertApi.list(status.value, page.value, pageSize)
    items.value = resp.data.items as AlertItem[]
    total.value = resp.data.total
  } catch {
    // 拦截器已提示
  } finally {
    loading.value = false
  }
}

function onFilterChange() {
  page.value = 1
  load()
}

function onPageChange(p: number) {
  page.value = p
  load()
}

async function ack(id: number) {
  try {
    await alertApi.ack(id)
    ElMessage.success('已确认处置')
    await Promise.all([load(), alertStore.fetchCount()])
  } catch {
    // 拦截器已提示
  }
}

async function dismiss(id: number) {
  try {
    await alertApi.dismiss(id)
    ElMessage.success('已忽略')
    await Promise.all([load(), alertStore.fetchCount()])
  } catch {
    // 拦截器已提示
  }
}

async function copyCmd(cmd: string) {
  try {
    await navigator.clipboard.writeText(cmd)
    ElMessage.success('命令已复制，请在防火墙侧人工审核后执行')
  } catch {
    ElMessage.error('复制失败，请手动选择文本复制')
  }
}

function goReport(taskId: number) {
  router.push(`/tasks/${taskId}/report`)
}

function sortByConfidence(a: AlertItem, b: AlertItem) {
  return a.confidence - b.confidence
}

function confColor(c: number) {
  return c >= 0.95 ? '#f56c6c' : '#e6a23c'
}

function statusText(s: string) {
  return { open: '待处置', acked: '已确认', dismissed: '已忽略' }[s] || s
}

function statusType(s: string) {
  return { open: 'danger', acked: 'success', dismissed: 'info' }[s as 'open'] as 'info'
}

function fmtTime(iso: string) {
  return new Date(iso).toLocaleString('zh-CN', { hour12: false })
}

onMounted(load)
</script>

<style scoped>
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.rule-alert {
  margin-bottom: 12px;
}
.mono {
  font-family: Consolas, 'Courier New', monospace;
  font-size: 12px;
}
.rule-cell {
  display: flex;
  align-items: center;
  gap: 8px;
}
.rule-text {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  display: block;
}
.done-mark {
  color: #c0c4cc;
}
.pager {
  margin-top: 16px;
  justify-content: flex-end;
}
</style>
