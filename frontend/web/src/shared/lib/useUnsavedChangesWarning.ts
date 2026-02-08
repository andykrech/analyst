import { useEffect } from 'react'
import { useTopicStore } from '@/app/store/topicStore'

/**
 * Подписывается на beforeunload: если topicStore.status === "dirty",
 * показывает стандартное предупреждение браузера при закрытии/перезагрузке.
 */
export function useUnsavedChangesWarning() {
  const status = useTopicStore((s) => s.status)

  useEffect(() => {
    if (status !== 'dirty') return

    const handler = (e: BeforeUnloadEvent) => {
      e.preventDefault()
    }

    window.addEventListener('beforeunload', handler)
    return () => window.removeEventListener('beforeunload', handler)
  }, [status])
}
