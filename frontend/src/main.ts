import { createApp } from 'vue'
import App from './App.vue'
import router from './router'
import { initTheme } from './stores/app'
import '@fontsource-variable/inter'
import '@fontsource-variable/noto-sans-sc'
import '@fontsource-variable/jetbrains-mono'
import './styles/main.css'

initTheme()
window.addEventListener('code-judge:unauthorized', () => {
  if (router.currentRoute.value.name !== 'admin-login') {
    void router.replace({ name: 'admin-login' })
  }
})
createApp(App).use(router).mount('#app')
