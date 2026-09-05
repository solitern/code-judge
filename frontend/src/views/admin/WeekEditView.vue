<template>
  <div class="admin-page">
    <AdminNav />
    <main class="admin-main">
      <div class="page-head">
        <h2>编辑周次 #{{ weekInfo?.week ?? weekId }} <span v-if="weekInfo" class="badge" :class="weekInfo.status.toLowerCase()">{{ statusLabel(weekInfo.status) }}</span></h2>
        <div class="actions">
          <label for="publish-at">定时发布（{{ tzLabel }}）</label>
          <div class="publish-picker">
            <input
              id="publish-at"
              ref="publishAtInput"
              v-model="publishAt"
              type="datetime-local"
              step="60"
              :min="minPublishAt"
              inputmode="none"
              autocomplete="off"
              aria-describedby="publish-at-help"
              @focus="refreshPublishMinimum"
              @click="refreshPublishMinimum"
              @change="validatePublishAt"
              @keydown="blockManualPublishInput"
              @paste.prevent
              @drop.prevent
            />
            <button class="picker-btn" type="button" @click="openPublishPicker">选择时间</button>
          </div>
          <span id="publish-at-help" class="sr-only">只能通过日期时间选择器选择未来的北京时间</span>
          <button class="btn" :disabled="scheduling" @click="schedulePublish">{{ scheduling ? '设置中…' : '设置定时发布' }}</button>
          <button class="btn" @click="publishNow">立即发布</button>
          <button class="btn" @click="cancelPublish">取消发布</button>
          <button class="btn" @click="archive">归档</button>
        </div>
      </div>

      <section class="week-editor-card">
        <div class="week-editor-head">
          <div>
            <h3>周次信息</h3>
            <p>标题可直接修改；也可以导入 week*.json，一次更新标题、题目和测试案例。</p>
          </div>
          <div class="week-import-actions">
            <input
              ref="weekJsonInput"
              class="sr-only"
              type="file"
              accept=".json,application/json"
              @change="selectWeekJson"
            />
            <button class="btn" type="button" :disabled="importingWeekJson" @click="openWeekJsonPicker">
              {{ importingWeekJson ? '导入中…' : '导入 JSON' }}
            </button>
          </div>
        </div>
        <div class="week-title-row">
          <div class="field week-title-field">
            <label for="week-title">周次标题</label>
            <input
              id="week-title"
              v-model="weekTitleDraft"
              maxlength="200"
              placeholder="例如：实验 1（表）"
              @input="weekTitleDirty = true"
            />
          </div>
          <button class="btn-primary" type="button" :disabled="savingWeekTitle || !weekTitleDirty" @click="saveWeekTitle">
            {{ savingWeekTitle ? '保存中…' : '保存标题' }}
          </button>
        </div>
        <p class="week-import-note">导入时，同 ID 题目及其测试案例会被覆盖，JSON 中新增的题目会被创建；未出现在 JSON 中的现有题目会保留。</p>
      </section>

      <section class="notice-editor-card">
        <div class="notice-editor-head">
          <div>
            <h3>学生页通知</h3>
            <p>支持 Markdown，可填写源文件提交链接、截止时间和补充说明；留空后学生页不显示通知按钮。</p>
          </div>
          <span class="notice-count">{{ noticeDraft.length }} / 20000</span>
        </div>
        <textarea
          v-model="noticeDraft"
          rows="4"
          maxlength="20000"
          @input="noticeDirty = true"
          placeholder="例如：请在 6 月 20 日前通过 [WPS 表单](https://example.com) 提交源文件。"
        ></textarea>
        <div class="notice-editor-actions">
          <span>保存后可通过草稿预览检查实际显示效果。</span>
          <button class="btn-primary" :disabled="savingNotice" @click="saveNotice">
            {{ savingNotice ? '保存中…' : '保存通知' }}
          </button>
        </div>
      </section>

      <div class="layout">
        <aside class="problem-list">
          <h3>题目</h3>
          <button v-for="p in problems" :key="p.stable_id" class="problem-item" :class="{ active: p.stable_id === selectedProblemId }" @click="selectProblem(p.stable_id)">
            {{ p.stable_id }}. {{ p.title }}
            <span v-if="p.has_solution && p.solution_verified" class="ok">✓已验证</span>
            <span v-else-if="p.has_solution" class="warn">未验证</span>
          </button>
          <div class="add-problem">
            <input v-model.number="newProblemId" type="number" min="1" max="99" placeholder="题目 ID" />
            <button class="btn" @click="addProblem">添加题目</button>
          </div>
        </aside>

        <section class="editor-area" v-if="selectedProblem">
          <div class="form-grid">
            <div class="field"><label>题目标题</label><input v-model="selectedProblem.title" /></div>
            <div class="field"><label>题目 ID</label><input v-model="selectedProblem.stable_id" disabled /></div>
            <div class="field"><label>时间限制 (ms)</label><input v-model.number="selectedProblem.time_limit_ms" type="number" /></div>
            <div class="field"><label>内存限制 (MB)</label><input v-model.number="selectedProblem.memory_limit_mb" type="number" /></div>
            <div class="field"><label>输出限制 (KB)</label><input v-model.number="selectedProblem.output_limit_kb" type="number" /></div>
            <div class="field"><label>显示顺序</label><input v-model.number="selectedProblem.sort_order" type="number" /></div>
          </div>
          <div class="field"><label>题目描述 (支持 Markdown)</label><textarea v-model="selectedProblem.description" rows="4"></textarea></div>
          <div class="field"><label>输入格式</label><textarea v-model="selectedProblem.input_format" rows="2"></textarea></div>
          <div class="field"><label>输出格式</label><textarea v-model="selectedProblem.output_format" rows="2"></textarea></div>
          <div class="field"><label>提示</label><textarea v-model="selectedProblem.hint" rows="2"></textarea></div>
          <div class="field"><label>C 语言代码模板</label><textarea v-model="selectedProblem.template" rows="8" class="code"></textarea></div>
          <button class="btn-primary" @click="saveProblem">保存题目（版本 +1）</button>

          <h3 class="section-h">测试案例</h3>
          <div class="tc-table">
            <div class="tc-row head"><span>ID</span><span>类型</span><span>输入</span><span>期望输出</span><span>顺序</span><span>启用</span><span>操作</span></div>
            <div v-for="tc in testCases" :key="tc.id" class="tc-row">
              <span>{{ tc.id }}</span>
              <span>{{ tc.is_public ? '公开样例' : '隐藏案例' }}</span>
              <span><pre class="tc-pre">{{ tc.input }}</pre></span>
              <span><pre class="tc-pre">{{ tc.output }}</pre></span>
              <span>{{ tc.sort_order }}</span>
              <span>{{ tc.enabled ? '是' : '否' }}</span>
              <span class="ops">
                <button class="op" @click="editTc(tc)">编辑</button>
                <button class="op" @click="toggleTc(tc)">{{ tc.enabled ? '禁用' : '启用' }}</button>
                <button class="op danger" @click="removeTc(tc)">删除</button>
              </span>
            </div>
          </div>
          <div class="tc-toolbar">
            <span class="tc-count">共 {{ testCases.length }} 个测试案例</span>
            <div class="btn-row tc-actions">
              <button class="btn" @click="addTc">添加测试案例</button>
              <button class="btn-primary" @click="openBulkImport">批量导入</button>
            </div>
          </div>

          <h3 class="section-h">标准答案</h3>
          <textarea v-model="solutionCode" rows="10" class="code" placeholder="C 语言标准答案，仅保存在服务器端"></textarea>
          <div class="btn-row">
            <button class="btn-primary" @click="saveSolution">保存标准答案</button>
            <button class="btn" :disabled="verifying" @click="verifySolution">{{ verifying ? '验证中…' : '验证标准答案' }}</button>
            <span v-if="solutionVerified" class="ok">已验证</span>
          </div>
          <div v-if="verifyResult" class="verify-result">
            <h4>验证结果</h4>
            <div class="summary" :class="verifyResult.status === 'ACCEPTED' ? 'pass' : 'fail'">{{ verifyResult.summary }}</div>
            <div v-if="verifyResult.compile_error" class="error-message">{{ verifyResult.compile_error }}</div>
            <div v-for="r in verifyResult.results" :key="r.case_id" class="case-item">
              <span class="case-badge" :class="r.passed ? 'pass' : 'fail'">{{ r.passed ? 'PASS' : 'FAIL' }}</span>
              <div>
                <div class="case-meta">#{{ r.case_id }} · {{ r.status }} · {{ r.time_ms }} ms</div>
                <div v-if="r.input !== null && r.input !== undefined"><label>输入</label><pre>{{ r.input }}</pre></div>
                <div v-if="r.expected !== null && r.expected !== undefined"><label>期望输出</label><pre>{{ r.expected }}</pre></div>
                <div v-if="r.actual !== null && r.actual !== undefined"><label>实际输出</label><pre>{{ r.actual }}</pre></div>
                <div v-if="r.stderr"><label>stderr</label><pre>{{ r.stderr }}</pre></div>
              </div>
            </div>
          </div>

          <h3 class="section-h">版本快照</h3>
          <div class="snap-list">
            <div v-for="s in snapshots" :key="s.id" class="snap-row">
              <span>版本 {{ s.version }}</span>
              <span>{{ formatShanghaiTime(s.created_at) }}</span>
              <button class="op" @click="rollback(s)">恢复此版本</button>
            </div>
          </div>
        </section>
      </div>
    </main>

    <div v-if="tcModal" class="modal-mask" @click.self="tcModal = false">
      <div class="modal">
        <h3>{{ editingTc ? '编辑测试案例' : '添加测试案例' }}</h3>
        <label><input type="checkbox" v-model="tcForm.is_public" /> 公开样例</label>
        <label>排序 <input v-model.number="tcForm.sort_order" type="number" /></label>
        <label>启用 <input type="checkbox" v-model="tcForm.enabled" /></label>
        <label>输入</label><textarea v-model="tcForm.input" rows="5" class="code"></textarea>
        <label>期望输出</label><textarea v-model="tcForm.output" rows="5" class="code"></textarea>
        <div class="modal-actions">
          <button class="btn" @click="tcModal = false">取消</button>
          <button class="btn-primary" @click="saveTc">保存</button>
        </div>
      </div>
    </div>

    <div v-if="bulkModal" class="modal-mask" @click.self="closeBulkImport">
      <div class="modal bulk-modal" role="dialog" aria-modal="true" aria-labelledby="bulk-import-title">
        <div class="bulk-head">
          <div>
            <h3 id="bulk-import-title">批量导入测试案例</h3>
            <p>一次导入会作为一个版本保存；任何一条校验失败时，整批都不会写入。</p>
          </div>
          <button class="modal-close" type="button" aria-label="关闭" @click="closeBulkImport">×</button>
        </div>

        <div class="bulk-tabs" role="tablist" aria-label="导入方式">
          <button type="button" :class="{ active: bulkMode === 'json' }" @click="switchBulkMode('json')">粘贴 JSON</button>
          <button type="button" :class="{ active: bulkMode === 'zip' }" @click="switchBulkMode('zip')">上传 ZIP</button>
        </div>

        <div v-if="bulkMode === 'json'" class="bulk-panel">
          <p class="bulk-help">粘贴一个案例数组，每项必须包含 <code>input</code> 和 <code>output</code>。换行请写成 <code>\n</code>。</p>
          <textarea
            v-model="bulkJson"
            class="code bulk-json"
            rows="12"
            spellcheck="false"
            placeholder='[{"input":"1 2\n","output":"3\n"}]'
          ></textarea>
          <details class="json-example">
            <summary>查看格式示例</summary>
            <pre>{{ jsonExample }}</pre>
          </details>
          <label class="check-row">
            <input v-model="bulkPublicDefault" type="checkbox" />
            未单独指定类型的案例默认为公开样例
          </label>
        </div>

        <div v-else class="bulk-panel">
          <label class="zip-picker" :class="{ selected: bulkZipFile }">
            <input type="file" accept=".zip,application/zip" @change="selectBulkZip" />
            <span class="zip-icon">ZIP</span>
            <strong>{{ bulkZipFile ? bulkZipFile.name : '选择 ZIP 文件' }}</strong>
            <small>{{ bulkZipFile ? formatFileSize(bulkZipFile.size) : '最大 10 MB' }}</small>
          </label>
          <div class="bulk-help zip-rules">
            <p>ZIP 内使用同名的输入/输出文件配对，例如：</p>
            <pre>001.in   001.out
002.in   002.out</pre>
            <p>文件须为 UTF-8；ZIP 中如包含 <code>solution.c</code>，会同时更新标准答案。</p>
          </div>
        </div>

        <div v-if="bulkError" class="bulk-error" role="alert">{{ bulkError }}</div>
        <div class="modal-actions">
          <button class="btn" type="button" :disabled="bulkImporting" @click="closeBulkImport">取消</button>
          <button class="btn-primary" type="button" :disabled="bulkImporting" @click="importBulkCases">
            {{ bulkImporting ? '正在导入…' : '开始导入' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import AdminNav from '../../components/AdminNav.vue'
import * as adminApi from '../../api/admin'
import type { ProblemOut, RunResponse, TestCaseImportItem, TestCaseImportResult, TestCaseOut, WeekOut } from '../../types'
import {
  formatShanghaiTime,
  minimumShanghaiDateTimeLocal,
  shanghaiDateTimeLocalToUtc,
  utcToShanghaiDateTimeLocal,
} from '../../utils/time'

const route = useRoute()
const weekId = Number(route.params.id)
const weekInfo = ref<WeekOut | null>(null)
const weekTitleDraft = ref('')
const weekTitleDirty = ref(false)
const savingWeekTitle = ref(false)
const weekJsonInput = ref<HTMLInputElement | null>(null)
const importingWeekJson = ref(false)
const problems = ref<ProblemOut[]>([])
const selectedProblemId = ref<number | null>(null)
const selectedProblem = ref<ProblemOut | null>(null)
const testCases = ref<TestCaseOut[]>([])
const solutionCode = ref('')
const solutionVerified = ref(false)
const verifying = ref(false)
const verifyResult = ref<RunResponse | null>(null)
const snapshots = ref<{ id: number; week_id: number; version: number; created_at: string }[]>([])
const publishAt = ref('')
const publishAtInput = ref<HTMLInputElement | null>(null)
const minPublishAt = ref(minimumShanghaiDateTimeLocal())
const publishAtDirty = ref(false)
const scheduling = ref(false)
const tzLabel = '北京时间 UTC+8'
const newProblemId = ref(1)
const tcModal = ref(false)
const editingTc = ref<TestCaseOut | null>(null)
const tcForm = ref({ is_public: false, input: '', output: '', sort_order: 0, enabled: true })
const bulkModal = ref(false)
const bulkMode = ref<'json' | 'zip'>('json')
const bulkJson = ref('')
const bulkPublicDefault = ref(false)
const bulkZipFile = ref<File | null>(null)
const bulkError = ref('')
const bulkImporting = ref(false)
const noticeDraft = ref('')
const savingNotice = ref(false)
const noticeDirty = ref(false)
const jsonExample = JSON.stringify([
  { input: '3 5\n', output: '8\n' },
  { input: '10 20\n', output: '30\n', is_public: true },
], null, 2)

function statusLabel(s: string) {
  const map: Record<string, string> = { DRAFT: '草稿', SCHEDULED: '待发布', PUBLISHED: '已发布', ARCHIVED: '已归档' }
  return map[s] || s
}

async function loadAll() {
  try {
    const [loadedProblems, weeks, loadedSnapshots] = await Promise.all([
      adminApi.fetchProblems(weekId),
      adminApi.fetchWeeks(),
      adminApi.fetchSnapshots(weekId),
    ])
    problems.value = loadedProblems
    weekInfo.value = weeks.find(w => w.id === weekId) || null
    if (!weekTitleDirty.value) weekTitleDraft.value = weekInfo.value?.title || ''
    if (!noticeDirty.value) noticeDraft.value = weekInfo.value?.notice || ''
    if (!publishAtDirty.value) publishAt.value = utcToShanghaiDateTimeLocal(weekInfo.value?.publish_at || null)
    snapshots.value = loadedSnapshots
    if (problems.value.length) {
      const selectedStillExists = problems.value.some(p => p.stable_id === selectedProblemId.value)
      await selectProblem(selectedStillExists ? selectedProblemId.value! : problems.value[0].stable_id)
    }
  } catch (e: any) { alert(e.message || '加载失败') }
}

async function selectProblem(id: number) {
  selectedProblemId.value = id
  try {
    selectedProblem.value = problems.value.find(p => p.stable_id === id) || null
    const [cases, sol] = await Promise.all([
      adminApi.fetchTestCases(weekId, id),
      adminApi.fetchSolution(weekId, id),
    ])
    testCases.value = cases
    solutionCode.value = sol.code
    solutionVerified.value = sol.verified
    verifyResult.value = null
  } catch (e: any) { alert(e.message || '加载题目失败') }
}

async function addProblem() {
  if (!newProblemId.value) return
  try {
    await adminApi.saveProblem(weekId, newProblemId.value, {
      stable_id: newProblemId.value, title: `题目 ${newProblemId.value}`, description: '', input_format: '',
      output_format: '', hint: '', template: '#include <stdio.h>\n\nint main() {\n    return 0;\n}\n',
      time_limit_ms: 2000, memory_limit_mb: 256, output_limit_kb: 1024, sort_order: newProblemId.value
    })
    await loadAll()
  } catch (e: any) { alert(e.message || '添加失败') }
}

async function saveProblem() {
  if (!selectedProblem.value) return
  try {
    const p = selectedProblem.value
    await adminApi.saveProblem(weekId, p.stable_id, { ...p })
    alert('已保存，题目版本 +1')
    await loadAll()
  } catch (e: any) { alert(e.message || '保存失败') }
}

async function saveWeekTitle() {
  const title = weekTitleDraft.value.trim()
  if (!title) {
    alert('周次标题不能为空')
    return
  }
  savingWeekTitle.value = true
  try {
    const updated = await adminApi.updateWeek(weekId, { title })
    weekInfo.value = updated
    weekTitleDraft.value = updated.title
    weekTitleDirty.value = false
    snapshots.value = await adminApi.fetchSnapshots(weekId)
    alert('周次标题已保存')
  } catch (e: any) {
    alert(e.message || '保存标题失败')
  } finally {
    savingWeekTitle.value = false
  }
}

function openWeekJsonPicker() {
  weekJsonInput.value?.click()
}

async function selectWeekJson(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = ''
  if (!file) return
  if (file.size > 5 * 1024 * 1024) {
    alert('JSON 文件不能超过 5 MB')
    return
  }

  let parsed: any
  try {
    parsed = JSON.parse((await file.text()).replace(/^\uFEFF/, ''))
  } catch {
    alert('JSON 格式不正确，请检查文件内容')
    return
  }
  if (!parsed || typeof parsed !== 'object' || !Array.isArray(parsed.problems) || !parsed.problems.length) {
    alert('JSON 必须包含非空 problems 数组')
    return
  }
  if (Number(parsed.week) !== weekInfo.value?.week) {
    alert(`JSON 中的周次为 ${parsed.week ?? '未知'}，当前页面是周次 ${weekInfo.value?.week ?? '未知'}`)
    return
  }

  const title = typeof parsed.title === 'string' ? parsed.title : ''
  const sampleCount = parsed.problems.reduce(
    (sum: number, problem: any) => sum + (Array.isArray(problem?.samples) ? problem.samples.length : 0),
    0,
  )
  const hiddenCount = parsed.problems.reduce(
    (sum: number, problem: any) => sum + (
      Array.isArray(problem?.testCases)
        ? problem.testCases.length
        : (Array.isArray(problem?.test_cases) ? problem.test_cases.length : 0)
    ),
    0,
  )
  const confirmed = confirm(
    `准备导入“${title || '未命名周次'}”：${parsed.problems.length} 道题、${sampleCount} 个公开样例、${hiddenCount} 个隐藏案例。\n\n同 ID 题目及其测试案例将被覆盖，是否继续？`,
  )
  if (!confirmed) return

  importingWeekJson.value = true
  try {
    const result = await adminApi.importWeekJson(weekId, file)
    weekTitleDirty.value = false
    await loadAll()
    alert(
      `导入完成：${result.problems_imported} 道题、${result.samples_imported} 个公开样例、${result.hidden_cases_imported} 个隐藏案例`,
    )
  } catch (e: any) {
    alert(e.message || '导入 JSON 失败')
  } finally {
    importingWeekJson.value = false
  }
}

async function saveNotice() {
  savingNotice.value = true
  try {
    const updated = await adminApi.updateWeek(weekId, { notice: noticeDraft.value })
    weekInfo.value = updated
    noticeDraft.value = updated.notice
    noticeDirty.value = false
    alert(noticeDraft.value.trim() ? '通知已保存并显示在学生页' : '通知已清空，学生页按钮将隐藏')
  } catch (e: any) {
    alert(e.message || '保存通知失败')
  } finally {
    savingNotice.value = false
  }
}

async function addTc() {
  if (!selectedProblemId.value) return
  editingTc.value = null
  tcForm.value = { is_public: false, input: '', output: '', sort_order: testCases.value.length + 1, enabled: true }
  tcModal.value = true
}

function editTc(tc: TestCaseOut) {
  editingTc.value = tc
  tcForm.value = { is_public: tc.is_public, input: tc.input, output: tc.output, sort_order: tc.sort_order, enabled: tc.enabled }
  tcModal.value = true
}

async function saveTc() {
  if (!selectedProblemId.value) return
  try {
    if (editingTc.value) {
      await adminApi.updateTestCase(editingTc.value.id, { ...tcForm.value })
    } else {
      await adminApi.addTestCase(weekId, selectedProblemId.value, { ...tcForm.value })
    }
    tcModal.value = false
    testCases.value = await adminApi.fetchTestCases(weekId, selectedProblemId.value)
  } catch (e: any) { alert(e.message || '保存失败') }
}

function openBulkImport() {
  if (!selectedProblemId.value) return
  bulkMode.value = 'json'
  bulkJson.value = ''
  bulkPublicDefault.value = false
  bulkZipFile.value = null
  bulkError.value = ''
  bulkModal.value = true
}

function closeBulkImport() {
  if (bulkImporting.value) return
  bulkModal.value = false
}

function switchBulkMode(mode: 'json' | 'zip') {
  bulkMode.value = mode
  bulkError.value = ''
}

function selectBulkZip(event: Event) {
  const input = event.target as HTMLInputElement
  bulkZipFile.value = input.files?.[0] || null
  bulkError.value = ''
}

function formatFileSize(bytes: number) {
  return bytes < 1024 * 1024
    ? `${Math.max(1, Math.round(bytes / 1024))} KB`
    : `${(bytes / 1024 / 1024).toFixed(1)} MB`
}

async function importBulkCases() {
  if (!selectedProblemId.value) return
  bulkError.value = ''
  bulkImporting.value = true
  try {
    let result: TestCaseImportResult
    if (bulkMode.value === 'json') {
      if (!bulkJson.value.trim()) throw new Error('请先粘贴要导入的 JSON 内容')
      let parsed: unknown
      try {
        parsed = JSON.parse(bulkJson.value)
      } catch {
        throw new Error('JSON 格式不正确，请检查引号、逗号和换行转义')
      }
      const cases = Array.isArray(parsed)
        ? parsed
        : (parsed && typeof parsed === 'object' && Array.isArray((parsed as { cases?: unknown }).cases)
          ? (parsed as { cases: unknown[] }).cases
          : null)
      if (!cases?.length) throw new Error('JSON 必须是非空案例数组，或包含非空 cases 数组')
      result = await adminApi.importTestCasesJson(
        weekId,
        selectedProblemId.value,
        cases as TestCaseImportItem[],
        bulkPublicDefault.value,
      )
    } else {
      if (!bulkZipFile.value) throw new Error('请先选择 ZIP 文件')
      result = await adminApi.importTestCasesZip(weekId, selectedProblemId.value, bulkZipFile.value)
    }
    testCases.value = await adminApi.fetchTestCases(weekId, selectedProblemId.value)
    bulkModal.value = false
    const solutionNotice = result.solution_imported ? '，并已更新标准答案' : ''
    alert(`成功导入 ${result.imported} 个测试案例${solutionNotice}`)
  } catch (e: any) {
    bulkError.value = e.message || '批量导入失败'
  } finally {
    bulkImporting.value = false
  }
}

async function toggleTc(tc: TestCaseOut) {
  try {
    await adminApi.updateTestCase(tc.id, { is_public: tc.is_public, input: tc.input, output: tc.output, sort_order: tc.sort_order, enabled: !tc.enabled })
    testCases.value = await adminApi.fetchTestCases(weekId, selectedProblemId.value!)
  } catch (e: any) { alert(e.message || '操作失败') }
}

async function removeTc(tc: TestCaseOut) {
  if (!confirm('确认删除此测试案例？')) return
  try {
    await adminApi.deleteTestCase(tc.id)
    testCases.value = await adminApi.fetchTestCases(weekId, selectedProblemId.value!)
  } catch (e: any) { alert(e.message || '删除失败') }
}

async function saveSolution() {
  if (!selectedProblemId.value) return
  try {
    const r = await adminApi.saveSolution(weekId, selectedProblemId.value, solutionCode.value)
    solutionVerified.value = r.verified
    alert('已保存，尚未验证。请在发布前验证标准答案。')
  } catch (e: any) { alert(e.message || '保存失败') }
}

async function verifySolution() {
  if (!selectedProblemId.value) return
  verifying.value = true
  verifyResult.value = null
  try {
    const r = await adminApi.verifySolution(weekId, selectedProblemId.value)
    verifyResult.value = r
    solutionVerified.value = r.status === 'ACCEPTED'
    if (r.status === 'ACCEPTED') alert('标准答案通过全部案例')
  } catch (e: any) { alert(e.message || '验证失败') } finally { verifying.value = false }
}

async function schedulePublish() {
  if (!publishAt.value) { alert('请选择发布时间'); return }
  const publishAtUtc = shanghaiDateTimeLocalToUtc(publishAt.value)
  if (!publishAtUtc || Date.parse(publishAtUtc) <= Date.now()) {
    publishAt.value = ''
    refreshPublishMinimum()
    alert('定时发布时间必须晚于当前时间，请通过选择器重新选择')
    return
  }
  if (weekInfo.value?.has_unverified_solution && !confirm('该周次存在未验证的标准答案，仍要定时发布吗？')) return
  scheduling.value = true
  try {
    const updated = await adminApi.updateWeek(weekId, { status: 'SCHEDULED', publish_at: publishAtUtc })
    weekInfo.value = updated
    publishAt.value = utcToShanghaiDateTimeLocal(updated.publish_at)
    publishAtDirty.value = false
    await loadAll()
    alert('已设置定时发布')
  } catch (e: any) {
    alert(e.message || '设置失败')
  } finally {
    scheduling.value = false
  }
}

function refreshPublishMinimum() {
  minPublishAt.value = minimumShanghaiDateTimeLocal()
}

function openPublishPicker() {
  refreshPublishMinimum()
  publishAtInput.value?.showPicker?.()
}

function validatePublishAt() {
  publishAtDirty.value = true
  if (!publishAt.value) return
  const utc = shanghaiDateTimeLocalToUtc(publishAt.value)
  if (!utc || Date.parse(utc) <= Date.now()) {
    publishAt.value = ''
    refreshPublishMinimum()
    alert('不能选择已经过去的时间，请重新选择')
  }
}

function blockManualPublishInput(event: KeyboardEvent) {
  if (event.key !== 'Tab' && event.key !== 'Escape') event.preventDefault()
}

async function publishNow() {
  if (weekInfo.value?.has_unverified_solution && !confirm('该周次存在未验证的标准答案，仍要发布吗？')) return
  try { await adminApi.updateWeek(weekId, { status: 'PUBLISHED' }); alert('已立即发布'); await loadAll() }
  catch (e: any) { alert(e.message || '发布失败') }
}
async function cancelPublish() {
  try { await adminApi.updateWeek(weekId, { status: 'DRAFT' }); alert('已取消发布/回到草稿'); await loadAll() }
  catch (e: any) { alert(e.message || '操作失败') }
}
async function archive() {
  try { await adminApi.updateWeek(weekId, { status: 'ARCHIVED' }); alert('已归档'); await loadAll() }
  catch (e: any) { alert(e.message || '归档失败') }
}

async function rollback(s: { id: number; version: number }) {
  if (!confirm(`确认恢复到版本 ${s.version}？当前内容将被覆盖。`)) return
  try { await adminApi.rollbackSnapshot(weekId, s.id); alert('已恢复'); await loadAll() }
  catch (e: any) { alert(e.message || '恢复失败') }
}

onMounted(loadAll)
</script>

<style scoped>
.admin-page { min-height: 100dvh; background: var(--bg); }
.admin-main { padding: 20px; }
.page-head { display: flex; align-items: center; justify-content: space-between; gap: 10px; flex-wrap: wrap; }
.actions { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
.publish-picker { display: flex; align-items: stretch; min-width: 270px; }
.publish-picker input { min-width: 190px; border-radius: 6px 0 0 6px; cursor: pointer; caret-color: transparent; }
.picker-btn { border: 1px solid var(--border); border-left: 0; border-radius: 0 6px 6px 0; background: var(--bg); color: var(--text-secondary); padding: 0 10px; cursor: pointer; white-space: nowrap; }
.picker-btn:hover { color: var(--primary); }
.sr-only { position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px; overflow: hidden; clip: rect(0, 0, 0, 0); white-space: nowrap; border: 0; }
.week-editor-card { margin-top: 14px; padding: 14px 16px; border: 1px solid var(--border); border-radius: 10px; background: var(--card); }
.week-editor-head { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; }
.week-editor-head h3 { margin: 0 0 4px; font-size: 15px; }
.week-editor-head p { margin: 0; color: var(--text-muted); font-size: 12px; }
.week-import-actions { flex-shrink: 0; }
.week-title-row { display: flex; align-items: flex-end; gap: 10px; margin-top: 12px; }
.week-title-field { flex: 1; margin-bottom: 0; }
.week-title-row .btn-primary { flex-shrink: 0; }
.week-import-note { margin: 9px 0 0; color: var(--text-muted); font-size: 11px; line-height: 1.5; }
.notice-editor-card { margin-top: 14px; padding: 14px 16px; border: 1px solid var(--border); border-radius: 10px; background: var(--card); }
.notice-editor-head { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; margin-bottom: 9px; }
.notice-editor-head h3 { margin: 0 0 4px; font-size: 15px; }
.notice-editor-head p { margin: 0; color: var(--text-muted); font-size: 12px; }
.notice-count { flex-shrink: 0; color: var(--text-muted); font-size: 11px; }
.notice-editor-card textarea { min-height: 92px; resize: vertical; }
.notice-editor-actions { display: flex; align-items: center; justify-content: space-between; gap: 12px; margin-top: 8px; }
.notice-editor-actions span { color: var(--text-muted); font-size: 11px; }
.btn { border: 1px solid var(--border); background: var(--card); border-radius: 6px; padding: 7px 12px; cursor: pointer; font-size: 13px; }
.btn-primary { background: var(--primary); color: var(--on-primary); border: none; border-radius: 6px; padding: 8px 14px; cursor: pointer; font-size: 13px; }
.badge { padding: 2px 8px; border-radius: 10px; font-size: 12px; }
.badge.draft { background: #f0f0f0; color: #666; }
.badge.scheduled { background: #fff3e0; color: #b26a00; }
.badge.published { background: var(--green-bg); color: #157a52; }
.badge.archived { background: #f5f5f5; color: #999; }
.layout { display: flex; gap: 14px; margin-top: 14px; }
.problem-list { width: 240px; flex-shrink: 0; background: var(--card); border: 1px solid var(--border); border-radius: 10px; padding: 12px; }
.problem-item { display: flex; justify-content: space-between; width: 100%; text-align: left; padding: 8px; border: 1px solid transparent; background: none; cursor: pointer; border-radius: 6px; }
.problem-item.active { border-color: var(--primary); background: #f0f4ff; }
.problem-item .ok { color: var(--green); font-size: 11px; }
.problem-item .warn { color: var(--orange); font-size: 11px; }
.add-problem { display: flex; gap: 6px; margin-top: 10px; }
.add-problem input { width: 70px; }
.editor-area { flex: 1; min-width: 0; background: var(--card); border: 1px solid var(--border); border-radius: 10px; padding: 16px; }
.form-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 10px; }
.field { margin-bottom: 10px; }
.field label { display: block; font-size: 12px; color: var(--text-muted); margin-bottom: 4px; }
input, textarea { width: 100%; padding: 7px 9px; border: 1px solid var(--border); border-radius: 6px; font-size: 13px; font-family: inherit; }
textarea.code, input.code { font-family: var(--font-mono); }
.section-h { margin: 18px 0 8px; border-left: 3px solid var(--primary); padding-left: 8px; }
.tc-table { overflow-x: auto; }
.tc-row { display: grid; grid-template-columns: 50px 90px 1fr 1fr 50px 50px 130px; gap: 6px; align-items: center; padding: 6px 8px; border-bottom: 1px solid var(--border-light); font-size: 12px; }
.tc-row.head { font-weight: 700; color: var(--text-muted); }
.tc-pre { white-space: pre-wrap; word-break: break-all; margin: 0; font-size: 11px; font-family: var(--font-mono); }
.tc-toolbar { display: flex; align-items: center; justify-content: space-between; gap: 12px; margin-top: 10px; }
.tc-count { color: var(--text-muted); font-size: 12px; }
.tc-actions { margin-top: 0; }
.ops { display: flex; gap: 4px; flex-wrap: wrap; }
.op { border: 1px solid var(--border); background: var(--card); border-radius: 4px; padding: 2px 6px; font-size: 11px; cursor: pointer; }
.op.danger { color: var(--red); border-color: #f3c1c1; }
.btn-row { display: flex; gap: 8px; align-items: center; margin-top: 8px; }
.ok { color: var(--green); font-weight: 600; }
.verify-result { margin-top: 10px; }
.summary { padding: 8px 10px; border-radius: 6px; font-weight: 600; }
.summary.pass { background: var(--green-bg); color: #157a52; }
.summary.fail { background: var(--red-bg); color: #b33b3b; }
.error-message { font-family: var(--font-mono); color: var(--red); white-space: pre-wrap; }
.case-item { display: flex; gap: 8px; padding: 6px 0; border-bottom: 1px solid var(--border-light); }
.case-badge { flex-shrink: 0; padding: 1px 6px; border-radius: 3px; font-size: 11px; }
.case-badge.pass { background: var(--green-bg); color: #157a52; }
.case-badge.fail { background: var(--red-bg); color: #b33b3b; }
.case-meta { color: var(--text-muted); font-size: 12px; }
.case-item pre { white-space: pre-wrap; word-break: break-all; background: var(--bg); padding: 4px 6px; border-radius: 4px; font-size: 12px; }
.snap-list { display: flex; flex-direction: column; gap: 6px; }
.snap-row { display: flex; gap: 12px; align-items: center; padding: 6px 8px; border: 1px solid var(--border); border-radius: 6px; }
.modal-mask { position: fixed; inset: 0; background: rgba(0,0,0,.45); display: flex; align-items: center; justify-content: center; z-index: 100; }
.modal { background: var(--card); border-radius: 10px; padding: 18px; width: min(90vw, 640px); display: flex; flex-direction: column; gap: 8px; }
.modal-actions { display: flex; justify-content: flex-end; gap: 8px; }
.bulk-modal { width: min(92vw, 760px); max-height: 90dvh; overflow-y: auto; padding: 0; gap: 0; }
.bulk-head { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; padding: 20px 22px 14px; }
.bulk-head h3 { margin: 0 0 5px; }
.bulk-head p { margin: 0; color: var(--text-muted); font-size: 12px; }
.modal-close { border: 0; background: transparent; color: var(--text-muted); cursor: pointer; font-size: 24px; line-height: 1; padding: 0 2px; }
.bulk-tabs { display: flex; gap: 4px; padding: 0 22px; border-bottom: 1px solid var(--border); }
.bulk-tabs button { border: 0; border-bottom: 2px solid transparent; background: transparent; color: var(--text-muted); cursor: pointer; padding: 10px 15px; font: inherit; }
.bulk-tabs button.active { border-bottom-color: var(--primary); color: var(--primary); font-weight: 600; }
.bulk-panel { display: flex; flex-direction: column; gap: 10px; padding: 18px 22px; }
.bulk-help { margin: 0; color: var(--text-muted); font-size: 12px; line-height: 1.6; }
.bulk-help code { font-family: var(--font-mono); }
.bulk-json { min-height: 230px; resize: vertical; line-height: 1.55; }
.json-example { color: var(--text-muted); font-size: 12px; }
.json-example summary { cursor: pointer; user-select: none; }
.json-example pre, .zip-rules pre { margin: 8px 0 0; padding: 10px 12px; border: 1px solid var(--border); border-radius: 6px; background: var(--bg); color: var(--text); font-family: var(--font-mono); white-space: pre-wrap; }
.check-row { display: flex; align-items: center; gap: 8px; color: var(--text); font-size: 13px; }
.check-row input { width: auto; }
.zip-picker { position: relative; display: flex; min-height: 145px; flex-direction: column; align-items: center; justify-content: center; gap: 6px; border: 1px dashed var(--border); border-radius: 10px; background: var(--bg); cursor: pointer; }
.zip-picker:hover, .zip-picker.selected { border-color: var(--primary); }
.zip-picker input { position: absolute; inset: 0; width: 100%; opacity: 0; cursor: pointer; }
.zip-picker small { color: var(--text-muted); }
.zip-icon { border-radius: 5px; background: var(--primary); color: var(--on-primary); padding: 5px 8px; font-size: 11px; font-weight: 700; letter-spacing: .05em; }
.zip-rules p { margin: 0 0 6px; }
.zip-rules p:last-child { margin: 8px 0 0; }
.bulk-error { margin: 0 22px 14px; border: 1px solid #f3c1c1; border-radius: 6px; background: var(--red-bg); color: var(--red); padding: 9px 11px; font-size: 12px; }
.bulk-modal .modal-actions { border-top: 1px solid var(--border); padding: 14px 22px 18px; }
.btn:disabled, .btn-primary:disabled { cursor: not-allowed; opacity: .6; }
@media (max-width: 680px) {
  .week-editor-head, .week-title-row { align-items: stretch; flex-direction: column; }
  .week-import-actions .btn { width: 100%; }
  .notice-editor-head, .notice-editor-actions { align-items: flex-start; flex-direction: column; }
  .tc-toolbar { align-items: flex-start; flex-direction: column; }
  .bulk-head, .bulk-panel { padding-left: 16px; padding-right: 16px; }
  .bulk-tabs { padding: 0 16px; }
  .bulk-error { margin-left: 16px; margin-right: 16px; }
  .bulk-modal .modal-actions { padding-left: 16px; padding-right: 16px; }
}
</style>
