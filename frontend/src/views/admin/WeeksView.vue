<template>
  <div class="admin-page">
    <AdminNav />
    <main class="admin-main">
      <div class="page-head">
        <h2>周次管理</h2>
        <div class="actions">
          <input v-model.number="newWeekNo" type="number" min="1" max="52" placeholder="新周次编号" />
          <input v-model="newWeekTitle" type="text" placeholder="标题，如：数组和链表" />
          <button class="btn-primary" @click="createWeek">新建周次</button>
        </div>
      </div>
      <div class="table">
        <div class="row head">
          <span>周次</span><span>标题</span><span>状态</span><span>题目数</span><span>发布时间</span><span>操作</span>
        </div>
        <div v-for="w in weeks" :key="w.id" class="row">
          <span>第 {{ w.week }} 周</span>
          <span>{{ w.title }}</span>
          <span><span class="badge" :class="w.status.toLowerCase()">{{ statusLabel(w.status) }}</span></span>
          <span>{{ w.problem_count }}</span>
          <span>{{ formatShanghaiTime(w.publish_at) }}</span>
          <span class="ops">
            <router-link :to="`/admin/weeks/${w.id}`" class="op">编辑</router-link>
            <button class="op" @click="preview(w)">预览</button>
            <button v-if="w.status === 'DRAFT'" class="op" @click="publish(w, true)">立即发布</button>
            <button v-if="w.status === 'PUBLISHED'" class="op" @click="publish(w, false)">取消发布</button>
            <button v-if="w.status === 'DRAFT' || w.status === 'SCHEDULED'" class="op danger" @click="remove(w)">删除</button>
          </span>
        </div>
      </div>
    </main>
  </div>
</template>

<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import AdminNav from '../../components/AdminNav.vue'
import { createWeek as apiCreateWeek, deleteWeek as apiDeleteWeek, fetchWeeks, updateWeek } from '../../api/admin'
import type { WeekOut } from '../../types'
import { formatShanghaiTime, parseUtcDateTime } from '../../utils/time'

const router = useRouter()
const weeks = ref<WeekOut[]>([])
const newWeekNo = ref<number>(1)
const newWeekTitle = ref('')
let scheduledRefresh: ReturnType<typeof setTimeout> | null = null

function statusLabel(s: string) {
  const map: Record<string, string> = { DRAFT: '草稿', SCHEDULED: '待发布', PUBLISHED: '已发布', ARCHIVED: '已归档' }
  return map[s] || s
}
async function load() {
  weeks.value = await fetchWeeks()
  planScheduledRefresh()
}
function planScheduledRefresh() {
  if (scheduledRefresh) clearTimeout(scheduledRefresh)
  const nextPublishAt = weeks.value
    .filter(week => week.status === 'SCHEDULED' && week.publish_at)
    .map(week => parseUtcDateTime(week.publish_at!).getTime())
    .filter(timestamp => timestamp > Date.now())
    .sort((a, b) => a - b)[0]
  if (!nextPublishAt) return
  const delay = Math.min(nextPublishAt - Date.now() + 1000, 2_147_000_000)
  scheduledRefresh = setTimeout(() => void load(), delay)
}
async function createWeek() {
  if (!newWeekNo.value || !newWeekTitle.value.trim()) { alert('请填写周次编号和标题'); return }
  try {
    await apiCreateWeek(newWeekNo.value, newWeekTitle.value.trim())
    newWeekTitle.value = ''
    await load()
  } catch (e: any) { alert(e.message || '创建失败') }
}
async function publish(w: WeekOut, immediate: boolean) {
  if (w.has_unverified_solution && !confirm('该周次存在未验证的标准答案，仍要发布吗？')) return
  try {
    if (immediate) {
      await updateWeek(w.id, { status: 'PUBLISHED' })
    } else {
      await updateWeek(w.id, { status: 'DRAFT' })
    }
    await load()
  } catch (e: any) { alert(e.message || '操作失败') }
}
async function remove(w: WeekOut) {
  if (!confirm(`确认删除第 ${w.week} 周草稿？`)) return
  try { await apiDeleteWeek(w.id); await load() } catch (e: any) { alert(e.message || '删除失败') }
}
function preview(w: WeekOut) {
  window.open(`/preview/${w.id}`, '_blank')
}
onMounted(load)
onBeforeUnmount(() => {
  if (scheduledRefresh) clearTimeout(scheduledRefresh)
})
</script>

<style scoped>
.admin-page { min-height: 100dvh; background: var(--bg); }
.admin-main { padding: 20px; }
.page-head { display: flex; align-items: center; justify-content: space-between; gap: 10px; flex-wrap: wrap; }
.actions { display: flex; gap: 8px; }
.actions input { padding: 7px 10px; border: 1px solid var(--border); border-radius: 6px; }
.btn-primary { background: var(--primary); color: var(--on-primary); border: none; padding: 8px 14px; border-radius: 6px; cursor: pointer; }
.table { margin-top: 14px; background: var(--card); border: 1px solid var(--border); border-radius: 10px; overflow: auto; }
.row { display: grid; grid-template-columns: 80px 1fr 80px 70px 180px 260px; gap: 8px; align-items: center; padding: 9px 12px; border-bottom: 1px solid var(--border-light); font-size: 13px; }
.row.head { background: var(--bg); font-weight: 700; color: var(--text-muted); }
.row:last-child { border-bottom: none; }
.badge { padding: 2px 8px; border-radius: 10px; font-size: 12px; }
.badge.draft { background: #f0f0f0; color: #666; }
.badge.scheduled { background: #fff3e0; color: #b26a00; }
.badge.published { background: var(--green-bg); color: #157a52; }
.badge.archived { background: #f5f5f5; color: #999; }
.ops { display: flex; gap: 6px; flex-wrap: wrap; }
.op { border: 1px solid var(--border); background: var(--card); border-radius: 5px; padding: 3px 8px; font-size: 12px; cursor: pointer; color: var(--text-secondary); text-decoration: none; }
.op.danger { color: var(--red); border-color: #f3c1c1; }
</style>
