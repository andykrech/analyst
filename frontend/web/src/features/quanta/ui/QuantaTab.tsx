import { useEffect } from 'react'
import { useTopicStore } from '@/app/store/topicStore'
import { QuantaList } from './components/QuantaList'
import './QuantaTab.css'
import './QuantumEntitiesModal.css'

interface QuantaTabProps {
  themeId: string
}

export function QuantaTab({ themeId }: QuantaTabProps) {
  const quanta = useTopicStore((s) => s.data.quanta)
  const loadQuanta = useTopicStore((s) => s.loadQuanta)
  const clearQuantaError = useTopicStore((s) => s.clearQuantaError)

  useEffect(() => {
    if (themeId) {
      loadQuanta()
    }
  }, [themeId, loadQuanta])

  return (
    <div className="quanta-tab">
      {quanta.error && (
        <div className="quanta-tab__error">
          {quanta.error}
          <button type="button" onClick={clearQuantaError} aria-label="Скрыть">
            ×
          </button>
        </div>
      )}

      {quanta.isLoading ? (
        <p className="quanta-tab__loading">Загрузка…</p>
      ) : quanta.items.length === 0 ? (
        <p className="quanta-tab__empty">
          Нет квантов. Нажмите «Поиск информации» на панели выше, чтобы запустить поиск по теме.
        </p>
      ) : (
        <QuantaList items={quanta.items} />
      )}
    </div>
  )
}
