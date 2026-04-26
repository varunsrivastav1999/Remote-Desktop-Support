import { createApp } from 'vue'
import { createRouter, createWebHistory } from 'vue-router'
import App from './App.vue'
import './style.css'

// ─── Routes ─────────────────────────────────────────────────
const routes = [
  {
    path: '/',
    name: 'Home',
    component: () => import('./views/HomeView.vue'),
  },
  {
    path: '/session/:code',
    name: 'Session',
    component: () => import('./views/SessionView.vue'),
    props: true,
  },
  {
    path: '/ssh/:code',
    name: 'Terminal',
    component: () => import('./views/TerminalView.vue'),
    props: true,
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

// ─── App ────────────────────────────────────────────────────
const app = createApp(App)
app.use(router)
app.mount('#app')
