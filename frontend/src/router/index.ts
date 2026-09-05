import { createRouter, createWebHistory } from 'vue-router'
import StudentView from '../views/StudentView.vue'
import { getCookie } from '../api/client'

const routes = [
  { path: '/', name: 'student', component: StudentView },
  { path: '/weeks/:weekId(\\d+)', name: 'history-week', component: StudentView },
  { path: '/preview/:weekId', name: 'preview', component: StudentView, meta: { preview: true } },
  { path: '/admin/login', name: 'admin-login', component: () => import('../views/admin/LoginView.vue'), meta: { public: true } },
  { path: '/admin', name: 'admin-dashboard', component: () => import('../views/admin/DashboardView.vue') },
  { path: '/admin/weeks', name: 'admin-weeks', component: () => import('../views/admin/WeeksView.vue') },
  { path: '/admin/weeks/:id', name: 'admin-week-edit', component: () => import('../views/admin/WeekEditView.vue') },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

const chunkReloadKey = 'code-judge:chunk-reload-target'

function isStaleChunkError(error: unknown): boolean {
  const message = error instanceof Error ? error.message : String(error)
  return /Failed to fetch dynamically imported module|Importing a module script failed|error loading dynamically imported module|Loading chunk \d+ failed|Unable to preload CSS/i.test(message)
}

router.onError((error, to) => {
  if (!isStaleChunkError(error)) return
  const target = to.fullPath
  if (sessionStorage.getItem(chunkReloadKey) === target) return
  sessionStorage.setItem(chunkReloadKey, target)
  window.location.assign(target)
})

// A full-page recovery loaded the current deployment successfully.
// Clear the guard so a later deployment can recover in the same tab too.
void router.isReady().then(() => sessionStorage.removeItem(chunkReloadKey))

router.beforeEach((to) => {
  const isAdminRoute = to.path.startsWith('/admin')
  if (isAdminRoute && !to.meta.public) {
    // admin_session 是 HttpOnly Cookie，JS 无法读取；用可读的 csrf_token 仅作快速提示。
    // 服务端仍会校验真实会话，401 会清理此提示并跳回登录页。
    const hasSession = getCookie('csrf_token') !== null
    if (!hasSession) return { name: 'admin-login' }
  }
  if (to.name === 'admin-login' && getCookie('csrf_token') !== null) {
    return { name: 'admin-dashboard' }
  }
})

export default router
