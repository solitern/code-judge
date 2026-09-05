<template>
  <div class="login-page">
    <form class="login-card" @submit.prevent="doLogin">
      <h2>管理员登录</h2>
      <p class="hint">请使用服务器环境变量中配置的管理员账号</p>
      <input v-model="username" type="text" placeholder="用户名" autocomplete="username" />
      <input v-model="password" type="password" placeholder="密码" autocomplete="current-password" />
      <button class="btn-primary" :disabled="loading">{{ loading ? '登录中…' : '登录' }}</button>
      <p v-if="error" class="error">{{ error }}</p>
    </form>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { login } from '../../api/admin'

const username = ref('admin')
const password = ref('')
const loading = ref(false)
const error = ref('')
const router = useRouter()

async function doLogin() {
  loading.value = true
  error.value = ''
  try {
    await login(username.value, password.value)
    router.push('/admin')
  } catch (e: any) {
    error.value = e.message || '登录失败'
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-page { display: flex; align-items: center; justify-content: center; min-height: 100dvh; background: var(--bg); }
.login-card { background: var(--card); border: 1px solid var(--border); border-radius: 12px; padding: 28px; width: min(90vw, 380px); display: flex; flex-direction: column; gap: 12px; }
.login-card h2 { margin: 0; }
.hint { color: var(--text-muted); font-size: 12px; margin: 0; }
input { padding: 9px 10px; border: 1px solid var(--border); border-radius: 6px; font-size: 14px; }
.btn-primary { background: var(--primary); color: var(--on-primary); border: none; padding: 10px; border-radius: 6px; cursor: pointer; font-size: 14px; }
.error { color: var(--red); font-size: 13px; }
</style>
