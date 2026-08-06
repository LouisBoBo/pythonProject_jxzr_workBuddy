import { createRouter, createWebHistory } from 'vue-router'
import ChatView from './views/ChatView.vue'
import FileManager from './views/FileManager.vue'
import LoginView from './views/LoginView.vue'
import { isLoggedIn } from './auth.js'

const routes = [
  { path: '/login', name: 'login', component: LoginView, meta: { title: '登录', public: true } },
  { path: '/', name: 'chat', component: ChatView, meta: { title: '对话' } },
  { path: '/dev-agent', redirect: '/' },
  { path: '/files', name: 'files', component: FileManager, meta: { title: '文件' } },
  { path: '/history', redirect: '/' },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach((to) => {
  if (to.meta.public) {
    if (to.name === 'login' && isLoggedIn()) {
      return { path: '/', query: { thread: `session-${Date.now()}` } }
    }
    return true
  }
  if (!isLoggedIn()) {
    return { path: '/login', query: { redirect: to.fullPath } }
  }
  return true
})

export default router
