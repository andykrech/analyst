import { useEffect } from 'react'
import { useTopicStore } from '@/app/store/topicStore'
import { EntityList } from './components/EntityList'
import './EntitiesTab.css'

interface EntitiesTabProps {
  themeId: string
}

export function EntitiesTab({ themeId }: EntitiesTabProps) {
  const entities = useTopicStore((s) => s.data.entities)
  const loadEntities = useTopicStore((s) => s.loadEntities)
  const clearEntitiesError = useTopicStore((s) => s.clearEntitiesError)

  useEffect(() => {
    if (themeId) {
      loadEntities()
    }
  }, [themeId, loadEntities])

  return (
    <div className="entities-tab">
      {entities.error && (
        <div className="entities-tab__error">
          {entities.error}
          <button type="button" onClick={clearEntitiesError} aria-label="Скрыть">
            ×
          </button>
        </div>
      )}

      {entities.isLoading ? (
        <p className="entities-tab__loading">Загрузка…</p>
      ) : entities.items.length === 0 ? (
        <p className="entities-tab__empty">
          Нет сущностей. Нажмите «Найти сущности» на панели выше, чтобы извлечь
          сущности из квантов темы.
        </p>
      ) : (
        <EntityList items={entities.items} />
      )}
    </div>
  )
}
