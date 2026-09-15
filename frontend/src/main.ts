import { createApp } from 'vue'
import { createPinia } from 'pinia'
import { createRouter, createWebHashHistory } from 'vue-router'
import { QueryClient, VueQueryPlugin } from '@tanstack/vue-query'
import App from './App.vue'
import AuthPage from './pages/AuthPage.vue'
import Dashboard from './pages/Dashboard.vue'
import PublicPage from './pages/PublicPage.vue'
import './styles.css'
import './workspace.css'

const router = createRouter({
  history: createWebHashHistory(),
  routes: [
    { path: '/', component: PublicPage },
    { path: '/u/:owner', component: PublicPage },
    { path: '/login', component: AuthPage },
    { path: '/setup', component: AuthPage },
    { path: '/signup', component: AuthPage },
    { path: '/join', component: AuthPage },
    { path: '/reset', component: AuthPage },
    { path: '/account-reset', component: AuthPage },
    { path: '/w/:workspace', component: PublicPage },
    { path: '/:view(team|personal|favorites|recent)', component: Dashboard },
    { path: '/:pathMatch(.*)*', redirect: '/' },
  ],
})
export const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: false, staleTime: 15000, refetchOnWindowFocus: true } },
})
createApp(App).use(createPinia()).use(router).use(VueQueryPlugin, { queryClient }).mount('#app')
