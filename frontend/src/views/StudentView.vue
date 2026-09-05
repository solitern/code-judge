<template>
  <div class="student-page" :class="{ mobile: isMobile }">
    <header class="topbar">
      <div class="topbar-left">
        <span class="logo">⌘</span>
        <div class="titles">
          <div class="course">数据结构实验</div>
          <div class="week-title">{{ weekTitle }}</div>
        </div>
      </div>
      <div class="topbar-actions">
        <button
          v-if="noticeContent"
          class="notice-toggle"
          type="button"
          aria-label="查看通知"
          aria-haspopup="dialog"
          @click="noticeOpen = true"
        >
          <span aria-hidden="true">🔔</span>
          <span class="notice-label">通知</span>
          <span class="notice-dot" aria-hidden="true"></span>
        </button>
        <span v-if="previewMode" class="preview-badge">草稿预览，尚未公开</span>
        <div v-else class="history-menu">
          <button
            class="history-toggle"
            type="button"
            aria-controls="history-week-list"
            :aria-expanded="historyOpen"
            @click="toggleHistory"
          >往期</button>
          <div v-if="historyOpen" id="history-week-list" class="history-dropdown">
            <div class="history-heading">
              <strong>往期内容</strong>
              <span>选择已发布周次</span>
            </div>
            <button v-if="historyMode" class="history-current" type="button" @click="goToCurrentWeek">
              ← 回到当前周次
            </button>
            <div v-if="historyLoading" class="history-state">正在加载…</div>
            <div v-else-if="historyError" class="history-state error">
              <span>{{ historyError }}</span>
              <button type="button" @click="loadHistoryWeeks">重试</button>
            </div>
            <div v-else-if="!historyChoices.length" class="history-state">暂无往期内容</div>
            <template v-else>
              <button
                v-for="item in historyChoices"
                :key="item.id"
                class="history-item"
                type="button"
                :disabled="item.id === week?.id"
                :aria-current="item.id === week?.id ? 'page' : undefined"
                @click="goToHistoryWeek(item.id)"
              >
                <span class="history-item-main">
                  <strong>第 {{ item.week }} 周</strong>
                  <span>{{ item.title }}</span>
                </span>
                <span class="history-item-meta">{{ item.problem_count }} 道题</span>
              </button>
            </template>
          </div>
        </div>
        <button class="theme-toggle" @click="toggleTheme">{{ theme === 'light' ? '🌙' : '☀️' }}</button>
      </div>
    </header>

    <nav class="problem-tabs" v-if="!isMobile">
      <button v-for="(p, i) in problems" :key="p.id" class="problem-tab" :class="{ active: i === currentIndex }" @click="switchProblem(i)">
        题目 {{ p.id }}：{{ p.title }}
      </button>
    </nav>

    <main v-if="!isMobile" class="desktop-main">
      <section class="panel problem-panel" :style="{ flexBasis: leftWidth + '%', maxWidth: leftWidth + '%' }">
        <div class="panel-header">
          <span>📖</span><span>{{ currentProblem?.title || '题目' }}</span>
        </div>
        <div class="panel-body">
          <ProblemPanel :problem="currentProblem" />
        </div>
      </section>
      <div class="divider" @mousedown="startDrag"></div>
      <section class="panel editor-panel">
        <div class="panel-header">
          <span>💻</span><span>代码编辑器</span>
          <button class="reset-btn" @click="resetCode">↺ 重置代码</button>
        </div>
        <div class="editor-wrap">
          <CodeEditor v-model="code" :theme="theme" />
        </div>
        <div class="action-bar">
          <div class="status-text">{{ statusText }}</div>
          <div class="actions">
            <button class="btn btn-dark" :disabled="running" @click="runSample">
              {{ running ? '运行中…' : '▶ 运行样例' }}
            </button>
            <button class="btn btn-outline" :disabled="running" @click="customInputOpen = true">✎ 自定义运行</button>
            <button class="btn btn-primary" :disabled="running" @click="runAll">
              {{ running ? '评测中…' : '⏩ 运行全部案例' }}
            </button>
          </div>
        </div>
        <ResultPanel :visible="resultVisible" :loading="running" :loading-text="runningText" :title="resultTitle"
          :response="runResponse" :reveal="revealResult" @close="closeResult" />
      </section>
    </main>

    <main v-else class="mobile-main">
      <div v-if="problems.length > 1" class="mobile-problem-picker">
        <label for="mobile-problem-select">当前题目</label>
        <select
          id="mobile-problem-select"
          :value="currentIndex"
          aria-label="选择题目"
          @change="onMobileProblemChange"
        >
          <option v-for="(p, i) in problems" :key="p.id" :value="i">
            题目 {{ p.id }}：{{ p.title }}
          </option>
        </select>
      </div>
      <div class="mobile-tabs">
        <button v-for="(t, i) in ['题目', '代码', '结果']" :key="t" class="mobile-tab" :class="{ active: mobileTab === i }" @click="switchMobileTab(i)">
          {{ t }}
        </button>
      </div>
      <section v-show="mobileTab === 0" class="mobile-pane">
        <ProblemPanel :problem="currentProblem" />
      </section>
      <section v-show="mobileTab === 1" class="mobile-pane code-pane">
        <CodeEditor v-model="code" :theme="theme" />
      </section>
      <section v-show="mobileTab === 2" class="mobile-pane result-pane">
        <ResultPanel :visible="true" :loading="running" :loading-text="runningText" :title="resultTitle"
          :response="runResponse" :reveal="revealResult" @close="mobileTab = 1" />
        <div v-if="!resultVisible" class="empty-result">暂无运行结果</div>
      </section>
    </main>

    <footer class="footer">
      <div>本网站仅用于代码自主评测，正式作业请按教师要求通过 WPS 表单提交源文件。</div>
    </footer>

    <div v-if="isMobile" class="mobile-actions">
      <button class="m-btn" :disabled="running" @click="runSample">运行样例</button>
      <button class="m-btn" :disabled="running" @click="customInputOpen = true">自定义运行</button>
      <button class="m-btn primary" :disabled="running" @click="runAll">运行全部案例</button>
      <button class="m-btn" :disabled="running" @click="resetCode">重置代码</button>
    </div>

    <div v-if="noticeOpen" class="modal-mask" @click.self="noticeOpen = false">
      <div class="modal notice-modal" role="dialog" aria-modal="true" aria-labelledby="notice-title">
        <div class="notice-modal-head">
          <div>
            <span class="notice-modal-icon" aria-hidden="true">🔔</span>
            <h3 id="notice-title">本周通知</h3>
          </div>
          <button class="notice-close" type="button" aria-label="关闭通知" @click="noticeOpen = false">×</button>
        </div>
        <MarkdownView :source="noticeContent" class="notice-content" />
      </div>
    </div>

    <div v-if="customInputOpen" class="modal-mask" @click.self="customInputOpen = false">
      <div class="modal">
        <h3>自定义运行</h3>
        <p class="modal-hint">输入将作为程序的标准输入（stdin）</p>
        <textarea v-model="customInput" rows="8" class="custom-textarea" placeholder="在此输入测试数据…"></textarea>
        <div class="modal-actions">
          <button class="btn btn-outline" @click="customInputOpen = false">取消</button>
          <button class="btn btn-primary" :disabled="running" @click="runCustom">运行</button>
        </div>
      </div>
    </div>

    <div v-if="newWeekAvailable" class="new-week-toast">
      <span>检测到新周次已发布</span>
      <button @click="reload">刷新</button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import CodeEditor from '../components/CodeEditor.vue'
import MarkdownView from '../components/MarkdownView.vue'
import ProblemPanel from '../components/ProblemPanel.vue'
import ResultPanel from '../components/ResultPanel.vue'
import * as publicApi from '../api/public'
import * as adminApi from '../api/admin'
import { loadCode, saveCode, resetCode as clearStoredCode, setTheme } from '../stores/app'
import type { PublicProblem, PublicWeek, PublicWeekSummary, RunResponse } from '../types'

const route = useRoute()
const router = useRouter()
const previewMode = computed(() => !!route.meta.preview || route.path.startsWith('/preview'))
const previewWeekId = computed(() => Number(route.params.weekId || 0))
const historyMode = computed(() => route.name === 'history-week')
const historyWeekId = computed(() => Number(route.params.weekId || 0))

const week = ref<PublicWeek | null>(null)
const problems = computed(() => week.value?.problems || [])
const currentIndex = ref(0)
const currentProblem = computed(() => problems.value[currentIndex.value] || null)
const noticeContent = computed(() => week.value?.notice?.trim() || '')
const code = ref('')
const theme = ref<'light' | 'dark'>(document.documentElement.dataset.theme === 'dark' ? 'dark' : 'light')
const isMobile = ref(window.innerWidth <= 900)
const mobileTab = ref(0)
const leftWidth = ref(42)
const dragging = ref(false)

const running = ref(false)
const runningText = ref('')
const resultVisible = ref(false)
const resultTitle = ref('运行结果')
const runResponse = ref<RunResponse | null>(null)
const revealResult = computed(() => previewMode.value)
const statusText = ref('')
const customInputOpen = ref(false)
const customInput = ref('')
const newWeekAvailable = ref(false)
const weekLoaded = ref(false)
const historyOpen = ref(false)
const noticeOpen = ref(false)
const historyLoading = ref(false)
const historyError = ref('')
const publishedWeeks = ref<PublicWeekSummary[]>([])
const historyChoices = computed(() => {
  const currentPublishedId = publishedWeeks.value[0]?.id
  return publishedWeeks.value.filter(item => item.id !== currentPublishedId)
})
let pollTimer: number | undefined

const weekTitle = computed(() => {
  if (!week.value) return weekLoaded.value ? '暂无已发布周次' : '加载中…'
  const prefix = historyMode.value ? '往期 · ' : ''
  return `${prefix}第 ${week.value.week} 周 · ${week.value.title}`
})

function weekFingerprint(value: PublicWeek | null): string {
  if (!value) return 'none'
  return JSON.stringify([
    value.id,
    value.title,
    value.problems.map(problem => [problem.id, problem.version]),
  ])
}

function toggleTheme() {
  theme.value = theme.value === 'light' ? 'dark' : 'light'
  setTheme(theme.value)
}

async function loadHistoryWeeks() {
  historyLoading.value = true
  historyError.value = ''
  try {
    publishedWeeks.value = await publicApi.fetchPublishedWeeks()
  } catch (e: any) {
    historyError.value = e.message || '加载失败'
  } finally {
    historyLoading.value = false
  }
}

function toggleHistory() {
  historyOpen.value = !historyOpen.value
  if (historyOpen.value) loadHistoryWeeks()
}

function goToHistoryWeek(weekId: number) {
  historyOpen.value = false
  if (weekId !== week.value?.id) router.push({ name: 'history-week', params: { weekId } })
}

function goToCurrentWeek() {
  historyOpen.value = false
  router.push({ name: 'student' })
}

function switchProblem(i: number) {
  if (currentProblem.value && week.value) {
    saveCode(week.value.id, currentProblem.value.id, currentProblem.value.version, code.value)
  }
  currentIndex.value = i
  restoreCode()
}

function onMobileProblemChange(event: Event) {
  const index = Number((event.target as HTMLSelectElement).value)
  if (Number.isInteger(index) && index >= 0 && index < problems.value.length) {
    switchProblem(index)
  }
}

function restoreCode() {
  if (!currentProblem.value || !week.value) return
  code.value = loadCode(week.value.id, currentProblem.value.id, currentProblem.value.version, currentProblem.value.template)
  closeResult()
}

function resetCode() {
  if (!currentProblem.value || !week.value) return
  if (confirm('确定要重置代码为初始模板吗？')) {
    clearStoredCode(week.value.id, currentProblem.value.id, currentProblem.value.version)
    code.value = currentProblem.value.template
    closeResult()
  }
}

async function loadWeek() {
  try {
    if (previewMode.value) {
      const data = await adminApi.fetchWeekPreview(previewWeekId.value)
      week.value = {
        id: data.id,
        week: data.week,
        title: data.title,
        notice: data.notice,
        problems: data.problems.map(p => ({
          id: p.stable_id,
          title: p.title,
          description: p.description,
          input_format: p.input_format,
          output_format: p.output_format,
          hint: p.hint,
          template: p.template,
          time_limit_ms: p.time_limit_ms,
          memory_limit_mb: p.memory_limit_mb,
          output_limit_kb: p.output_limit_kb,
          version: p.version,
          samples: p.samples.map(s => ({ id: s.id, input: s.input, output: s.output })),
        })),
      }
    } else if (historyMode.value) {
      week.value = await publicApi.fetchPublicWeek(historyWeekId.value)
    } else {
      const data = await publicApi.fetchCurrentWeek()
      week.value = data
    }
    currentIndex.value = 0
    restoreCode()
  } catch (e: any) {
    statusText.value = '加载失败：' + (e.message || '请刷新重试')
  } finally {
    weekLoaded.value = true
  }
}

async function runSample() {
  if (!currentProblem.value || !week.value || running.value) return
  if (!currentProblem.value.samples.length) {
    alert('该题目暂无公开样例')
    return
  }
  running.value = true
  runningText.value = '编译运行中…'
  resultVisible.value = true
  resultTitle.value = '样例运行'
  runResponse.value = null
  try {
    const w = week.value
    const p = currentProblem.value
    if (previewMode.value) {
      runResponse.value = await adminApi.runPreviewSample(w.id, p.id, code.value, 0)
    } else {
      runResponse.value = await publicApi.runSample(w.id, p.id, code.value, 0)
    }
  } catch (e: any) {
    alert(e.message || '运行失败')
  } finally {
    running.value = false
    runningText.value = ''
    if (isMobile.value) mobileTab.value = 2
  }
}

async function runCustom() {
  if (!currentProblem.value || !week.value || running.value) return
  running.value = true
  runningText.value = '编译运行中…'
  resultVisible.value = true
  resultTitle.value = '自定义运行'
  runResponse.value = null
  customInputOpen.value = false
  try {
    const w = week.value
    const p = currentProblem.value
    if (previewMode.value) {
      runResponse.value = await adminApi.runPreviewCustom(w.id, p.id, code.value, customInput.value)
    } else {
      runResponse.value = await publicApi.runCustom(w.id, p.id, code.value, customInput.value)
    }
  } catch (e: any) {
    alert(e.message || '运行失败')
  } finally {
    running.value = false
    runningText.value = ''
    if (isMobile.value) mobileTab.value = 2
  }
}

async function runAll() {
  if (!currentProblem.value || !week.value || running.value) return
  running.value = true
  runningText.value = '编译并评测全部案例中…'
  resultVisible.value = true
  resultTitle.value = '全部案例'
  runResponse.value = null
  try {
    const w = week.value
    const p = currentProblem.value
    if (previewMode.value) {
      runResponse.value = await adminApi.runPreviewAll(w.id, p.id, code.value)
    } else {
      runResponse.value = await publicApi.runAll(w.id, p.id, code.value)
    }
  } catch (e: any) {
    alert(e.message || '运行失败')
  } finally {
    running.value = false
    runningText.value = ''
    if (isMobile.value) mobileTab.value = 2
  }
}

function closeResult() {
  resultVisible.value = false
  runResponse.value = null
}

function startDrag(e: MouseEvent) {
  dragging.value = true
  document.addEventListener('mousemove', onDrag)
  document.addEventListener('mouseup', stopDrag)
  e.preventDefault()
}

function onDrag(e: MouseEvent) {
  if (!dragging.value) return
  const total = document.querySelector('.desktop-main')?.clientWidth || 1
  const x = e.clientX - (document.querySelector('.desktop-main')?.getBoundingClientRect().left || 0)
  leftWidth.value = Math.min(60, Math.max(25, (x / total) * 100))
}

function stopDrag() {
  dragging.value = false
  document.removeEventListener('mousemove', onDrag)
  document.removeEventListener('mouseup', stopDrag)
}

function switchMobileTab(i: number) {
  mobileTab.value = i
  if (i === 1) resultVisible.value = false
  if (i === 2 && runResponse.value) resultVisible.value = true
}

function reload() {
  newWeekAvailable.value = false
  loadWeek()
}

function onResize() {
  isMobile.value = window.innerWidth <= 900
}

watch(() => route.fullPath, () => {
  historyOpen.value = false
  noticeOpen.value = false
  week.value = null
  weekLoaded.value = false
  statusText.value = ''
  newWeekAvailable.value = false
  loadWeek()
}, { immediate: true })

onMounted(() => {
  window.addEventListener('resize', onResize)
  pollTimer = window.setInterval(async () => {
    if (previewMode.value || historyMode.value) return
    try {
      const current = await publicApi.fetchCurrentWeek()
      if (weekFingerprint(current) !== weekFingerprint(week.value)) {
        newWeekAvailable.value = true
      }
    } catch { /* ignore */ }
  }, 60000)
})

onBeforeUnmount(() => {
  stopDrag()
  window.removeEventListener('resize', onResize)
  if (pollTimer) clearInterval(pollTimer)
})

watch(code, (v) => {
  if (currentProblem.value && week.value) {
    saveCode(week.value.id, currentProblem.value.id, currentProblem.value.version, v)
  }
})
</script>

<style scoped>
.student-page { display: flex; flex-direction: column; height: 100dvh; background: var(--bg); color: var(--text-primary); }
.topbar { background: linear-gradient(135deg, #667eea, #4350a0); color: #fff; padding: 0 16px; height: 48px; display: flex; align-items: center; justify-content: space-between; flex-shrink: 0; }
.topbar-left { display: flex; align-items: center; gap: 10px; min-width: 0; }
.titles { min-width: 0; }
.logo { font-size: 18px; opacity: .85; }
.course { font-size: 15px; font-weight: 700; }
.week-title { font-size: 12px; opacity: .8; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.topbar-actions { display: flex; align-items: center; gap: 8px; }
.preview-badge { background: #ff9800; color: #fff; font-size: 12px; padding: 2px 8px; border-radius: 12px; }
.history-menu { position: relative; }
.history-toggle, .notice-toggle, .theme-toggle { background: rgba(255,255,255,.15); border: 1px solid rgba(255,255,255,.22); color: #fff; border-radius: 16px; padding: 4px 11px; cursor: pointer; }
.history-toggle:hover, .notice-toggle:hover, .theme-toggle:hover { background: rgba(255,255,255,.24); }
.notice-toggle { position: relative; display: inline-flex; align-items: center; gap: 5px; }
.notice-dot { position: absolute; top: 2px; right: 4px; width: 6px; height: 6px; border: 1px solid rgba(255,255,255,.75); border-radius: 50%; background: #ffb020; }
.history-dropdown { position: absolute; z-index: 120; top: calc(100% + 9px); right: 0; width: min(86vw, 330px); max-height: min(70vh, 480px); overflow-y: auto; padding: 8px; border: 1px solid var(--border); border-radius: 10px; background: var(--card); color: var(--text-primary); box-shadow: 0 14px 35px rgba(15,23,42,.22); }
.history-heading { display: flex; align-items: baseline; justify-content: space-between; gap: 12px; padding: 5px 7px 9px; border-bottom: 1px solid var(--border-light); }
.history-heading strong { font-size: 14px; }
.history-heading span { color: var(--text-muted); font-size: 11px; }
.history-current { width: 100%; margin-top: 6px; padding: 8px; border: 1px solid var(--border); border-radius: 7px; background: var(--bg); color: var(--primary); text-align: left; cursor: pointer; }
.history-state { padding: 20px 8px; color: var(--text-muted); font-size: 13px; text-align: center; }
.history-state.error { display: flex; align-items: center; justify-content: center; gap: 8px; color: var(--red); }
.history-state.error button { border: 1px solid var(--border); border-radius: 5px; background: var(--card); color: var(--text-secondary); padding: 3px 7px; cursor: pointer; }
.history-item { width: 100%; display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 9px 8px; border: none; border-bottom: 1px solid var(--border-light); background: transparent; color: var(--text-primary); text-align: left; cursor: pointer; }
.history-item:last-child { border-bottom: none; }
.history-item:hover { background: var(--bg); }
.history-item:disabled { background: var(--bg); cursor: default; opacity: .65; }
.history-item-main { display: grid; gap: 2px; min-width: 0; }
.history-item-main strong { font-size: 13px; color: var(--primary); }
.history-item-main span { overflow: hidden; color: var(--text-secondary); font-size: 12px; text-overflow: ellipsis; white-space: nowrap; }
.history-item-meta { flex-shrink: 0; color: var(--text-muted); font-size: 11px; }
.theme-toggle { background: rgba(255,255,255,.15); border: none; color: #fff; border-radius: 16px; padding: 4px 10px; cursor: pointer; }
.problem-tabs { display: flex; gap: 4px; padding: 0 14px; background: var(--card); border-bottom: 1px solid var(--border); flex-shrink: 0; overflow-x: auto; }
.problem-tab { padding: 9px 14px; border: none; background: none; font-size: 14px; color: var(--text-muted); cursor: pointer; border-bottom: 2px solid transparent; white-space: nowrap; }
.problem-tab.active { color: var(--primary); font-weight: 600; border-bottom-color: var(--primary); }
.desktop-main { flex: 1; display: flex; gap: 0; min-height: 0; overflow: hidden; }
.panel { display: flex; flex-direction: column; min-height: 0; background: var(--card); }
.problem-panel { flex-shrink: 0; min-width: 260px; }
.editor-panel { flex: 1; border-left: 1px solid var(--border); }
.divider { width: 6px; cursor: col-resize; background: transparent; flex-shrink: 0; }
.panel-header { display: flex; align-items: center; gap: 6px; padding: 8px 12px; border-bottom: 1px solid var(--border); font-size: 14px; font-weight: 600; color: var(--text-secondary); background: var(--bg); flex-shrink: 0; }
.panel-body { flex: 1; overflow-y: auto; padding: 14px 16px; }
.editor-wrap { flex: 1; min-height: 0; }
.action-bar { display: flex; align-items: center; gap: 8px; padding: 6px 10px; border-top: 1px solid var(--border); background: var(--bg); flex-shrink: 0; }
.status-text { flex: 1; font-size: 12px; color: var(--text-muted); }
.actions { display: flex; gap: 6px; }
.reset-btn { margin-left: auto; font-size: 11px; color: var(--text-muted); background: var(--card); border: 1px solid var(--border); border-radius: 5px; padding: 3px 8px; cursor: pointer; }
.btn { border: none; border-radius: 6px; padding: 7px 14px; font-size: 13px; font-weight: 500; cursor: pointer; }
.btn:disabled { opacity: .5; cursor: not-allowed; }
.btn-dark { background: var(--neutral-control-bg); color: var(--neutral-control-text); }
.btn-primary { background: var(--primary); color: var(--on-primary); }
.btn-outline { background: var(--card); color: var(--text-secondary); border: 1px solid var(--border); }
.footer { text-align: center; padding: 5px 16px; font-size: 11px; color: var(--text-muted); flex-shrink: 0; }

.mobile-main { flex: 1; display: flex; flex-direction: column; min-height: 0; padding-bottom: calc(58px + env(safe-area-inset-bottom)); }
.mobile-problem-picker { display: flex; align-items: center; gap: 10px; padding: 8px 12px; border-bottom: 1px solid var(--border); background: var(--card); flex-shrink: 0; }
.mobile-problem-picker label { flex-shrink: 0; color: var(--text-muted); font-size: 12px; }
.mobile-problem-picker select { min-width: 0; flex: 1; padding: 7px 30px 7px 9px; border: 1px solid var(--border); border-radius: 7px; background: var(--bg); color: var(--text-primary); font-size: 13px; }
.mobile-tabs { display: flex; background: var(--card); border-bottom: 1px solid var(--border); flex-shrink: 0; }
.mobile-tab { flex: 1; padding: 10px; border: none; background: none; font-size: 14px; color: var(--text-muted); cursor: pointer; border-bottom: 2px solid transparent; }
.mobile-tab.active { color: var(--primary); font-weight: 600; border-bottom-color: var(--primary); }
.mobile-pane { flex: 1; overflow-y: auto; min-height: 0; padding: 12px; }
.code-pane { padding: 0; }
.result-pane { padding: 0; }
.empty-result { color: var(--text-muted); text-align: center; padding: 30px; }

.modal-mask { position: fixed; inset: 0; background: rgba(0,0,0,.45); display: flex; align-items: center; justify-content: center; z-index: 100; }
.modal { background: var(--card); border-radius: 10px; padding: 18px; width: min(90vw, 600px); }
.modal h3 { margin: 0 0 6px; }
.notice-modal { width: min(92vw, 680px); max-height: min(84dvh, 720px); overflow-y: auto; padding: 0; border: 1px solid var(--border); box-shadow: 0 18px 55px rgba(15,23,42,.28); }
.notice-modal-head { position: sticky; z-index: 1; top: 0; display: flex; align-items: center; justify-content: space-between; gap: 14px; padding: 16px 18px; border-bottom: 1px solid var(--border); background: var(--card); }
.notice-modal-head > div { display: flex; align-items: center; gap: 9px; }
.notice-modal-head h3 { margin: 0; font-size: 17px; }
.notice-modal-icon { display: grid; width: 30px; height: 30px; place-items: center; border-radius: 8px; background: var(--warning-bg); }
.notice-close { border: 0; background: transparent; color: var(--text-muted); cursor: pointer; font-size: 25px; line-height: 1; padding: 2px 5px; }
.notice-close:hover { color: var(--text-primary); }
.notice-content { padding: 18px 20px 22px; color: var(--text-secondary); font-size: 14px; }
.modal-hint { color: var(--text-muted); font-size: 12px; }
.custom-textarea { width: 100%; border: 1px solid var(--border); border-radius: 6px; padding: 8px; font-family: var(--font-mono); font-size: 13px; resize: vertical; }
.modal-actions { display: flex; justify-content: flex-end; gap: 8px; margin-top: 10px; }
.new-week-toast { position: fixed; bottom: 48px; left: 50%; transform: translateX(-50%); background: var(--neutral-control-bg); color: var(--neutral-control-text); padding: 8px 14px; border-radius: 20px; display: flex; gap: 10px; align-items: center; z-index: 90; }
.new-week-toast button { background: var(--primary); color: var(--on-primary); border: none; border-radius: 12px; padding: 3px 10px; cursor: pointer; }
.mobile-actions { position: fixed; bottom: 0; left: 0; right: 0; display: flex; gap: 6px; padding: 8px 10px calc(8px + env(safe-area-inset-bottom)); background: var(--card); border-top: 1px solid var(--border); z-index: 80; }
.m-btn { flex: 1; border: 1px solid var(--border); background: var(--card); color: var(--text-primary); border-radius: 6px; padding: 9px 4px; font-size: 12px; cursor: pointer; }
.m-btn.primary { background: var(--primary); color: var(--on-primary); border-color: var(--primary); }
.m-btn:disabled { opacity: .5; }

@media (max-width: 540px) {
  .topbar { padding: 0 10px; }
  .topbar-left { gap: 7px; }
  .logo { display: none; }
  .course { font-size: 13px; }
  .week-title { max-width: 48vw; }
  .topbar-actions { gap: 5px; }
  .history-toggle, .notice-toggle, .theme-toggle { padding: 4px 9px; }
  .notice-label { display: none; }
  .notice-modal-head { padding: 14px 15px; }
  .notice-content { padding: 15px 16px 19px; }
}
</style>
