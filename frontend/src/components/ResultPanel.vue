<template>
  <div class="result-panel" v-if="visible">
    <div class="result-header">
      <span class="result-title">{{ title }}</span>
      <button class="icon-btn" @click="$emit('close')">×</button>
    </div>
    <div class="result-body">
      <div v-if="loading" class="status-line"><span class="spinner"></span>{{ loadingText }}</div>
      <template v-else-if="response">
        <div class="summary" :class="response.status === 'ACCEPTED' ? 'pass' : 'fail'">
          {{ response.summary }}
          <span v-if="response.compile_error" class="compile-badge">编译错误</span>
        </div>
        <div v-if="response.compile_error" class="error-message">{{ response.compile_error }}</div>
        <div v-for="r in visibleResults" :key="r.case_id" class="case-item">
          <span class="case-badge" :class="r.passed === true ? 'pass' : (r.passed === false ? 'fail' : 'neutral')">
            {{ statusLabel(r) }}
          </span>
          <div class="case-detail">
            <div class="case-meta">#{{ r.case_id }} · {{ statusText(r.status) }} · {{ r.time_ms?.toFixed(1) || '0' }} ms</div>
            <template v-if="r.input !== null && r.input !== undefined">
              <div class="case-row"><span class="label">输入</span><pre>{{ r.input }}</pre></div>
            </template>
            <template v-if="r.expected !== null && r.expected !== undefined">
              <div class="case-row"><span class="label">期望</span><pre>{{ r.expected }}</pre></div>
            </template>
            <template v-if="r.actual !== null && r.actual !== undefined">
              <div class="case-row"><span class="label">实际</span><pre>{{ r.actual }}</pre></div>
            </template>
            <template v-if="r.stderr">
              <div class="case-row"><span class="label">stderr</span><pre>{{ r.stderr }}</pre></div>
            </template>
          </div>
        </div>
      </template>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { RunResponse } from '../types'

const props = defineProps<{
  visible: boolean
  loading?: boolean
  loadingText?: string
  title?: string
  response?: RunResponse | null
  reveal?: boolean
}>()

defineEmits<{ (e: 'close'): void }>()

const visibleResults = computed(() => {
  if (!props.response) return []
  if (props.reveal) return props.response.results
  return props.response.results
})

function statusLabel(r: { passed: boolean | null; status: string }) {
  if (r.passed === true) return 'PASS'
  if (r.passed === false) return 'FAIL'
  const map: Record<string, string> = {
    ACCEPTED: 'OK', COMPILE_ERROR: 'CE', RUNTIME_ERROR: 'RE', TIME_LIMIT_EXCEEDED: 'TLE',
    MEMORY_LIMIT_EXCEEDED: 'MLE', OUTPUT_LIMIT_EXCEEDED: 'OLE', SYSTEM_ERROR: 'SE', WRONG_ANSWER: 'WA'
  }
  return map[r.status] || r.status
}

function statusText(s: string) {
  const map: Record<string, string> = {
    ACCEPTED: '通过', WRONG_ANSWER: '答案错误', COMPILE_ERROR: '编译错误',
    RUNTIME_ERROR: '运行时错误', TIME_LIMIT_EXCEEDED: '运行超时',
    MEMORY_LIMIT_EXCEEDED: '内存超限', OUTPUT_LIMIT_EXCEEDED: '输出超限', SYSTEM_ERROR: '系统错误'
  }
  return map[s] || s
}
</script>

<style scoped>
.result-panel { border-top: 1px solid var(--border); display: flex; flex-direction: column; max-height: 300px; overflow: hidden; background: var(--card); }
.result-header { display: flex; align-items: center; justify-content: space-between; padding: 8px 12px; border-bottom: 1px solid var(--border-light); }
.result-title { font-size: 13px; font-weight: 600; color: var(--text-secondary); }
.result-body { overflow-y: auto; padding: 10px 12px; }
.summary { padding: 8px 12px; border-radius: 6px; font-weight: 600; margin-bottom: 8px; font-size: 14px; }
.summary.pass { background: var(--green-bg); color: #157a52; }
.summary.fail { background: var(--red-bg); color: #b33b3b; }
.compile-badge { margin-left: 6px; font-size: 11px; padding: 1px 6px; border-radius: 3px; background: var(--red); color: #fff; }
.error-message { font-family: var(--font-mono); font-size: 13px; white-space: pre-wrap; color: var(--red); background: var(--red-bg); padding: 10px; border-radius: 6px; }
.case-item { display: flex; gap: 8px; padding: 7px 0; border-bottom: 1px solid var(--border-light); font-size: 13px; }
.case-badge { flex-shrink: 0; font-size: 11px; font-weight: 700; padding: 1px 7px; border-radius: 3px; height: max-content; }
.case-badge.pass { background: var(--green-bg); color: #157a52; }
.case-badge.fail { background: var(--red-bg); color: #b33b3b; }
.case-badge.neutral { background: var(--orange-bg); color: #a9711a; }
.case-detail { flex: 1; min-width: 0; }
.case-meta { color: var(--text-muted); font-size: 12px; margin-bottom: 4px; }
.case-row { display: flex; gap: 6px; margin-bottom: 3px; }
.case-row .label { flex-shrink: 0; width: 40px; text-align: right; color: var(--text-muted); font-size: 12px; }
.case-row pre { font-family: var(--font-mono); font-size: 12.5px; white-space: pre-wrap; word-break: break-all; margin: 0; color: var(--text-secondary); }
.status-line { color: var(--text-muted); font-size: 13px; }
.spinner { display: inline-block; width: 12px; height: 12px; border: 2px solid var(--border); border-top-color: var(--primary); border-radius: 50%; animation: spin .6s linear infinite; margin-right: 6px; vertical-align: middle; }
@keyframes spin { to { transform: rotate(360deg); } }
</style>
