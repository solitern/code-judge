<template>
  <div ref="container" class="markdown-body" v-html="rendered"></div>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { marked } from 'marked'
import DOMPurify from 'dompurify'
import renderMathInElement from 'katex/contrib/auto-render'
import 'katex/dist/katex.min.css'

const props = defineProps<{ source: string }>()
const container = ref<HTMLElement | null>(null)

const rendered = computed(() => {
  const html = marked.parse(props.source || '', { async: false }) as string
  const sanitized = DOMPurify.sanitize(html, {
    ALLOWED_TAGS: ['p', 'br', 'code', 'pre', 'strong', 'em', 'a', 'ul', 'ol', 'li', 'h1', 'h2', 'h3', 'h4', 'table', 'thead', 'tbody', 'tr', 'td', 'th', 'blockquote', 'hr'],
    ALLOWED_ATTR: ['href', 'title'],
  })
  const document = new DOMParser().parseFromString(sanitized, 'text/html')
  document.querySelectorAll('a').forEach((link) => {
    link.target = '_blank'
    link.rel = 'noopener noreferrer'
  })
  return document.body.innerHTML
})

function renderMath() {
  if (!container.value) return
  renderMathInElement(container.value, {
    delimiters: [
      { left: '$$', right: '$$', display: true },
      { left: '\\[', right: '\\]', display: true },
      { left: '\\(', right: '\\)', display: false },
      { left: '$', right: '$', display: false },
    ],
    throwOnError: false,
    trust: false,
  })
}

onMounted(renderMath)
watch(rendered, async () => {
  await nextTick()
  renderMath()
})
</script>

<style scoped>
.markdown-body {
  line-height: 1.75;
  overflow-wrap: anywhere;
}
.markdown-body :deep(p) {
  margin: 0 0 0.65em;
}
.markdown-body :deep(p:last-child) {
  margin-bottom: 0;
}
.markdown-body :deep(ul),
.markdown-body :deep(ol) {
  margin: 0.45em 0 0.75em;
  padding-inline-start: 1.8rem;
}
.markdown-body :deep(li) {
  margin: 0.18em 0;
  padding-inline-start: 0.18rem;
}
.markdown-body :deep(li::marker) {
  color: var(--text-muted);
  font-variant-numeric: tabular-nums;
}
.markdown-body :deep(li > ul),
.markdown-body :deep(li > ol) {
  margin: 0.25em 0;
}
.markdown-body :deep(pre) {
  background: var(--code-bg, #f6f8fa);
  margin: 0.65em 0;
  padding: 9px 11px;
  border-radius: 6px;
  overflow-x: auto;
}
.markdown-body :deep(code) {
  font-family: var(--font-mono);
  font-size: 0.9em;
  font-variant-ligatures: contextual;
}
.markdown-body :deep(a) {
  color: var(--primary);
  font-weight: 600;
  text-decoration: underline;
  text-underline-offset: 2px;
}
.markdown-body :deep(a:hover) {
  opacity: 0.82;
}
.markdown-body :deep(.katex-display) {
  margin: 0.7em 0;
  overflow-x: auto;
  overflow-y: hidden;
  padding: 0.15em 0;
}
</style>
