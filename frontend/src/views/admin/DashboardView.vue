<template>
  <div class="admin-page">
    <AdminNav />
    <main class="admin-main">
      <h2>仪表盘</h2>
      <p v-if="error" class="error">{{ error }}</p>
      <div class="cards">
        <div class="card"><div class="card-label">当前公开周次</div><div class="card-value">{{ data?.current_public_week ? `第 ${data.current_public_week.week} 周 · ${data.current_public_week.title}` : '无' }}</div></div>
        <div class="card"><div class="card-label">下一个计划发布</div><div class="card-value">{{ data?.next_scheduled_publish ? formatShanghaiTime(data.next_scheduled_publish.publish_at, '无') : '无' }}</div></div>
        <div class="card"><div class="card-label">草稿 / 待发布 / 已发布 / 已归档</div><div class="card-value">{{ data?.draft_count }} / {{ data?.scheduled_count }} / {{ data?.published_count }} / {{ data?.archived_count }}</div></div>
        <div class="card"><div class="card-label">Judge Runner</div><div class="card-value">{{ data?.runner_status || 'unknown' }}</div></div>
        <div class="card"><div class="card-label">判题并发</div><div class="card-value">{{ data?.judge_max_concurrency }}</div></div>
        <div class="card"><div class="card-label">最近更新</div><div class="card-value">{{ formatShanghaiTime(data?.last_updated_at || null, '无') }}</div></div>
      </div>
    </main>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import AdminNav from '../../components/AdminNav.vue'
import { fetchDashboard } from '../../api/admin'
import type { DashboardOut } from '../../types'
import { formatShanghaiTime } from '../../utils/time'

const data = ref<DashboardOut | null>(null)
const error = ref('')

onMounted(async () => {
  try { data.value = await fetchDashboard() } catch (e: any) { error.value = e.message || '仪表盘加载失败' }
})
</script>

<style scoped>
.admin-page { min-height: 100dvh; background: var(--bg); }
.admin-main { padding: 20px; }
.error { color: var(--red); }
.cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 12px; margin-top: 14px; }
.card { background: var(--card); border: 1px solid var(--border); border-radius: 10px; padding: 16px; }
.card-label { font-size: 12px; color: var(--text-muted); }
.card-value { font-size: 18px; font-weight: 700; margin-top: 6px; }
</style>
