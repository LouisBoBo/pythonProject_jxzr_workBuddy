import { createRouter, createWebHistory } from 'vue-router'
import ChatView from './views/ChatView.vue'
import FileManager from './views/FileManager.vue'

const routes = [
  { path: '/', name: 'chat', component: ChatView, meta: { title: '对话' } },
  { path: '/files', name: 'files', component: FileManager, meta: { title: '文件' } },
  { path: '/history', redirect: '/' },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

export default router
