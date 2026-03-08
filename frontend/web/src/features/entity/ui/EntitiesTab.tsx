import { useEffect, useMemo } from 'react'
import type { EntityOutDto } from '@/features/entity/api/dto'
import { useTopicStore } from '@/app/store/topicStore'
import { EntityGroupSection } from './components/EntityGroupSection'
import './EntitiesTab.css'

const GROUP_ORDER: { type: string; title: string }[] = [
  { type: 'tech', title: 'Технологии' },
  { type: 'person', title: 'Персоны' },
  { type: '__other__', title: 'Другое' },
]

function sortEntities(items: EntityOutDto[]): EntityOutDto[] {
  return [...items].sort((a, b) => {
    if (b.mention_count !== a.mention_count) return b.mention_count - a.mention_count
    const aTime = a.last_seen_at ? new Date(a.last_seen_at).getTime() : 0
    const bTime = b.last_seen_at ? new Date(b.last_seen_at).getTime() : 0
    return bTime - aTime
  })
}

function groupByType(items: EntityOutDto[]): Map<string, EntityOutDto[]> {
  const map = new Map<string, EntityOutDto[]>()
  for (const e of items) {
    const key = e.entity_type === 'tech' || e.entity_type === 'person' ? e.entity_type : '__other__'
    if (!map.has(key)) map.set(key, [])
    map.get(key)!.push(e)
  }
  for (const [key, arr] of map) {
    map.set(key, sortEntities(arr))
  }
  return map
}

interface EntitiesTabProps {
  themeId: string
}

export function EntitiesTab({ themeId }: EntitiesTabProps) {
  const entities = useTopicStore((s) => s.data.entities)
  const loadEntities = useTopicStore((s) => s.loadEntities)
  const clearEntitiesError = useTopicStore((s) => s.clearEntitiesError)

  const groups = useMemo(() => groupByType(entities.items), [entities.items])

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
        <div className="entities-tab__groups">
          {GROUP_ORDER.map(({ type, title }) => {
            const items = groups.get(type)
            if (!items?.length) return null
            return <EntityGroupSection key={type} title={title} items={items} />
          })}
        </div>
      )}
    </div>
  )
}
