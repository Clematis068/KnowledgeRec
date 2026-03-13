import { ref } from 'vue'
import { ElMessage } from 'element-plus/es/components/message/index'

import { getDomains } from '../api/auth'

export function useDomains() {
  const domains = ref([])
  const loading = ref(false)

  async function fetchDomains() {
    loading.value = true
    try {
      const data = await getDomains()
      domains.value = data.domains || []
    } catch {
      ElMessage.error('加载领域列表失败')
    } finally {
      loading.value = false
    }
  }

  return {
    domains,
    loading,
    fetchDomains,
  }
}
