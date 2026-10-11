<template>
  <div v-loading="loading">
    <el-alert
      v-if="task"
      :type="task.status === 'success' ? 'success' : task.status === 'failed' ? 'error' : 'warning'"
      :closable="false"
      class="task-alert"
    >
      任务 #{{ task.id }}（{{ task.file_name }}）—— 状态：{{ statusText(task.status) }}
      <template v-if="task.status === 'success'">
        ；共 {{ stats?.total_results ?? 0 }} 条结果；耗时
        {{ task.cost_seconds != null ? task.cost_seconds.toFixed(2) + ' 秒' : '—' }}
      </template>
      <template v-else-if="task.status === 'failed'">；错误：{{ task.error_msg }}</template>
    </el-alert>

    <el-row :gutter="16">
      <el-col :span="8">
        <el-card><div ref="pieRef" class="chart"></div></el-card>
      </el-col>
      <el-col :span="8">
        <el-card><div ref="barRef" class="chart"></div></el-card>
      </el-col>
      <el-col :span="8">
        <el-card><div ref="histRef" class="chart"></div></el-card>
      </el-col>
    </el-row>

    <el-card class="table-card">
      <template #header>检测结果明细（前 200 条）</template>
      <el-table :data="results" size="small" max-height="360">
        <el-table-column prop="row_no" label="行号" width="90" />
        <el-table-column prop="prediction" label="预测" width="110">
          <template #default="{ row }">
            <el-tag :type="row.prediction === 'Attack' ? 'danger' : 'success'">
              {{ row.prediction }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="attack_type" label="攻击类型" width="140">
          <template #default="{ row }">{{ row.attack_type ?? '—' }}</template>
        </el-table-column>
        <el-table-column label="置信度">
          <template #default="{ row }">
            {{ row.confidence != null ? (row.confidence * 100).toFixed(1) + '%' : '—' }}
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import * as echarts from 'echarts'
import { taskApi } from '../api'
import type { ResultItem, StatsData, TaskItem } from '../types'

const route = useRoute()
const taskId = Number(route.params.id)

const loading = ref(true)
const task = ref<TaskItem | null>(null)
const stats = ref<StatsData | null>(null)
const results = ref<ResultItem[]>([])

const pieRef = ref<HTMLDivElement>()
const barRef = ref<HTMLDivElement>()
const histRef = ref<HTMLDivElement>()
let charts: echarts.ECharts[] = []

const statusText = (s: string) =>
  ({ pending: '排队中', running: '检测中', success: '完成', failed: '失败' }[s] || s)

function renderCharts() {
  charts.forEach((c) => c.dispose())
  charts = []
  if (!stats.value) return
  const dist = stats.value.prediction_distribution
  const names = ['Normal', 'Attack']
  const zhNames: Record<string, string> = { Normal: '正常', Attack: '攻击' }

  // 图1：检测结果占比（饼图）
  const pie = echarts.init(pieRef.value!)
  pie.setOption({
    title: { text: '检测结果占比', left: 'center', textStyle: { fontSize: 14 } },
    tooltip: { trigger: 'item', formatter: '{b}: {c} 条 ({d}%)' },
    series: [
      {
        type: 'pie',
        radius: ['40%', '65%'],
        label: { formatter: '{b}\n{c} 条' },
        data: names
          .filter((n) => dist[n])
          .map((n) => ({
            name: zhNames[n] || n,
            value: dist[n].count,
            itemStyle: { color: n === 'Attack' ? '#f56c6c' : '#67c23a' },
          })),
      },
    ],
  })

  // 图2：平均置信度对比（柱状图）
  const bar = echarts.init(barRef.value!)
  bar.setOption({
    title: { text: '平均置信度对比', left: 'center', textStyle: { fontSize: 14 } },
    tooltip: { trigger: 'axis' },
    grid: { left: 50, right: 20, bottom: 30, top: 50 },
    xAxis: { type: 'category', data: names.filter((n) => dist[n]).map((n) => zhNames[n]) },
    yAxis: { type: 'value', max: 1, axisLabel: { formatter: (v: number) => (v * 100) + '%' } },
    series: [
      {
        type: 'bar',
        barWidth: 48,
        label: { show: true, position: 'top', formatter: (p: { value: number }) => (p.value * 100).toFixed(1) + '%' },
        data: names
          .filter((n) => dist[n])
          .map((n) => ({
            value: dist[n].avg_confidence ?? 0,
            itemStyle: { color: n === 'Attack' ? '#f56c6c' : '#409eff' },
          })),
      },
    ],
  })

  // 图3：置信度分布直方图（取明细样本）
  const buckets = new Array(10).fill(0)
  for (const r of results.value) {
    if (r.confidence == null) continue
    const idx = Math.min(9, Math.floor(r.confidence * 10))
    buckets[idx]++
  }
  const hist = echarts.init(histRef.value!)
  hist.setOption({
    title: { text: `置信度分布（样本 ${results.value.length} 条）`, left: 'center', textStyle: { fontSize: 14 } },
    tooltip: { trigger: 'axis' },
    grid: { left: 50, right: 20, bottom: 30, top: 50 },
    xAxis: {
      type: 'category',
      data: buckets.map((_, i) => `${i * 10}~${i * 10 + 10}%`),
      axisLabel: { fontSize: 10, rotate: 45 },
    },
    yAxis: { type: 'value', name: '条数' },
    series: [{ type: 'bar', data: buckets, itemStyle: { color: '#e6a23c' } }],
  })

  charts = [pie, bar, hist]
}

function onResize() {
  charts.forEach((c) => c.resize())
}

async function load() {
  loading.value = true
  try {
    const [tResp, sResp, rResp] = await Promise.all([
      taskApi.detail(taskId),
      taskApi.stats(taskId),
      taskApi.results(taskId, 1, 200),
    ])
    task.value = tResp.data
    stats.value = sResp.data
    results.value = rResp.data.items as ResultItem[]
    await nextTick()
    renderCharts()
  } catch {
    // 拦截器已提示（含后端不可达）
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  load()
  window.addEventListener('resize', onResize)
})
onBeforeUnmount(() => {
  window.removeEventListener('resize', onResize)
  charts.forEach((c) => c.dispose())
})
</script>

<style scoped>
.chart {
  height: 300px;
}
.task-alert {
  margin-bottom: 16px;
}
.table-card {
  margin-top: 16px;
}
</style>
