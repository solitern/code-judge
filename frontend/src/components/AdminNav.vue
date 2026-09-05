<template>
  <header class="admin-topbar">
    <div class="brand">数据结构实验 · 管理后台</div>
    <nav>
      <router-link to="/admin">仪表盘</router-link>
      <router-link to="/admin/weeks">周次管理</router-link>
      <router-link to="/">学生页</router-link>
      <button class="logout" @click="doLogout">退出</button>
    </nav>
  </header>
</template>

<script setup lang="ts">
import { useRouter } from 'vue-router'
import { logout } from '../api/admin'
const router = useRouter()
async function doLogout() {
  try { await logout() } catch {}
  router.push('/admin/login')
}
</script>

<style scoped>
.admin-topbar { display: flex; align-items: center; justify-content: space-between; padding: 0 20px; height: 50px; background: linear-gradient(135deg, #667eea, #4350a0); color: #fff; }
.brand { font-weight: 700; }
nav { display: flex; gap: 14px; align-items: center; }
nav a { color: rgba(255,255,255,.85); text-decoration: none; font-size: 14px; }
nav a.router-link-exact-active { color: #fff; font-weight: 700; border-bottom: 2px solid #fff; }
.logout { background: rgba(255,255,255,.15); border: none; color: #fff; padding: 5px 12px; border-radius: 14px; cursor: pointer; }
</style>
