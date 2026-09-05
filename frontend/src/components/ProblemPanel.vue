<template>
  <div v-if="problem" class="problem-panel-inner">
    <section class="problem-section">
      <div class="section-title">题目描述</div>
      <MarkdownView :source="problem.description" class="problem-text" />
    </section>
    <section class="problem-section">
      <div class="section-title">输入格式</div>
      <MarkdownView :source="problem.input_format" class="problem-text" />
    </section>
    <section class="problem-section">
      <div class="section-title">输出格式</div>
      <MarkdownView :source="problem.output_format" class="problem-text" />
    </section>
    <section class="problem-section">
      <div class="section-title">样例</div>
      <div v-for="(s, i) in problem.samples" :key="s.id || i" class="sample-group">
        <div class="sample-label">输入样例 {{ problem.samples.length > 1 ? i + 1 : '' }}</div>
        <pre class="code-block">{{ s.input }}</pre>
        <div class="sample-label">输出样例 {{ problem.samples.length > 1 ? i + 1 : '' }}</div>
        <pre class="code-block">{{ s.output }}</pre>
      </div>
      <div v-if="!problem.samples.length" class="muted">暂无公开样例</div>
    </section>
    <section class="problem-section" v-if="problem.hint">
      <div class="section-title">提示</div>
      <div class="hint-box">{{ problem.hint }}</div>
    </section>
    <section class="problem-section muted">
      限制：{{ problem.time_limit_ms }} ms / {{ problem.memory_limit_mb }} MB / 输出 {{ problem.output_limit_kb }} KB
    </section>
  </div>
  <div v-else class="muted">加载中…</div>
</template>

<script setup lang="ts">
import type { PublicProblem } from '../types'
import MarkdownView from './MarkdownView.vue'
defineProps<{ problem: PublicProblem | null }>()
</script>

<style scoped>
.problem-panel-inner { line-height: 1.65; }
.problem-section { margin-bottom: 14px; }
.section-title { font-size: 15px; font-weight: 700; color: var(--primary); margin-bottom: 6px; }
.problem-text { font-size: 14px; color: var(--text-secondary); }
.sample-group { margin-bottom: 10px; }
.sample-label { font-size: 12px; font-weight: 600; color: var(--text-muted); margin: 5px 0 3px; }
.code-block { background: var(--bg); border: 1px solid var(--border); border-radius: 6px; padding: 8px 10px; font-family: var(--font-mono); font-size: 13px; white-space: pre-wrap; margin: 0; overflow-x: auto; }
.hint-box { background: var(--warning-bg); border-left: 3px solid var(--warning-border); color: var(--warning-text); padding: 8px 10px; border-radius: 6px; font-size: 13px; }
.muted { color: var(--text-muted); font-size: 12px; }
</style>
