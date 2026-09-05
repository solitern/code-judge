<template>
  <div ref="editorHost" class="code-editor-host"></div>
</template>

<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { EditorView, keymap, lineNumbers, highlightActiveLine, highlightActiveLineGutter } from '@codemirror/view'
import { EditorState, Compartment } from '@codemirror/state'
import { defaultKeymap, indentWithTab } from '@codemirror/commands'
import { cpp } from '@codemirror/lang-cpp'
import { oneDark } from '@codemirror/theme-one-dark'
import { syntaxHighlighting, defaultHighlightStyle } from '@codemirror/language'

const props = defineProps<{
  modelValue: string
  theme?: 'light' | 'dark'
}>()
const emit = defineEmits<{ (e: 'update:modelValue', v: string): void }>()

const editorHost = ref<HTMLElement | null>(null)
let view: EditorView | null = null
const themeCompartment = new Compartment()

function themeExtension(theme: 'light' | 'dark') {
  return theme === 'dark' ? oneDark : []
}

onMounted(() => {
  if (!editorHost.value) return
  view = new EditorView({
    state: EditorState.create({
      doc: props.modelValue,
      extensions: [
        lineNumbers(),
        highlightActiveLineGutter(),
        highlightActiveLine(),
        cpp(),
        syntaxHighlighting(defaultHighlightStyle, { fallback: true }),
        keymap.of([...defaultKeymap, indentWithTab]),
        EditorView.updateListener.of((update) => {
          if (update.docChanged) {
            emit('update:modelValue', update.state.doc.toString())
          }
        }),
        themeCompartment.of(themeExtension(props.theme || 'light')),
      ],
    }),
    parent: editorHost.value,
  })
})

watch(() => props.modelValue, (v) => {
  if (view && v !== view.state.doc.toString()) {
    view.dispatch({ changes: { from: 0, to: view.state.doc.length, insert: v } })
  }
})

watch(() => props.theme, (t) => {
  if (view) {
    view.dispatch({ effects: themeCompartment.reconfigure(themeExtension(t || 'light')) })
  }
})

onBeforeUnmount(() => {
  view?.destroy()
  view = null
})
</script>

<style scoped>
.code-editor-host {
  height: 100%;
  min-height: 0;
  overflow: hidden;
  font-size: 14px;
}
.code-editor-host :deep(.cm-editor) {
  height: 100%;
}
.code-editor-host :deep(.cm-scroller) {
  overflow: auto;
  font-family: var(--font-mono);
  font-variant-ligatures: contextual;
  line-height: 1.6;
}
</style>
