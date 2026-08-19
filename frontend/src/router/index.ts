import { createRouter, createWebHashHistory, type RouteRecordRaw } from 'vue-router'
import AppLayout from '@/components/layout/AppLayout.vue'

const routes: RouteRecordRaw[] = [
  {
    path: '/',
    component: AppLayout,
    children: [
      {
        path: '',
        name: 'dashboard',
        component: () => import('@/views/Dashboard.vue')
      },
      {
        path: 'upload',
        name: 'upload',
        component: () => import('@/views/Upload.vue')
      },
      {
        path: 'logs',
        name: 'logs',
        component: () => import('@/views/Logs.vue')
      },
      {
        path: 'config',
        name: 'config',
        component: () => import('@/views/Config.vue')
      },
      {
        path: 'risk',
        name: 'risk',
        component: () => import('@/views/Risk.vue')
      },
      {
        path: 'topology',
        name: 'topology',
        component: () => import('@/views/Topology.vue')
      },
      {
        path: 'manuals',
        name: 'manuals',
        component: () => import('@/views/Manuals.vue')
      },
      {
        path: 'rules',
        name: 'rules',
        component: () => import('@/views/Rules.vue')
      },
      {
        path: 'projects',
        name: 'projects',
        component: () => import('@/views/Projects.vue')
      },
      {
        path: 'reports',
        name: 'reports',
        component: () => import('@/views/Reports.vue')
      }
    ]
  }
]

const router = createRouter({
  history: createWebHashHistory(),
  routes
})

export default router
