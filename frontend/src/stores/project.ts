import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { Project } from '@/types'
import { projectApi } from '@/api'

export const useProjectStore = defineStore('project', () => {
  const currentProject = ref<Project>({
    id: '',
    name: '',
    status: 'active',
    materialsCount: 0,
    risksCount: 0
  })

  const sidebarActive = ref<string>('dashboard')
  const initialized = ref(false)

  function setActive(key: string) {
    sidebarActive.value = key
  }

  function setProject(project: Project) {
    currentProject.value = project
  }

  function clearProject() {
    currentProject.value = {
      id: '',
      name: '',
      status: 'active',
      materialsCount: 0,
      risksCount: 0,
    }
  }

  async function init() {
    if (initialized.value) return
    try {
      const projects = await projectApi.list()
      if (projects.length > 0) {
        setProject(projects[0])
      }
      initialized.value = true
    } catch {
      // 后端不可用时不阻塞 UI
    }
  }

  return {
    currentProject,
    sidebarActive,
    initialized,
    setActive,
    setProject,
    clearProject,
    init
  }
})
