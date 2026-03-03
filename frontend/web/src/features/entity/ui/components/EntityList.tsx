import type { EntityOutDto } from '@/features/entity/api/dto'

function formatDate(s: string | null): string {
  if (!s) return '—'
  try {
    const d = new Date(s)
    return d.toLocaleDateString(undefined, {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    })
  } catch {
    return '—'
  }
}

const ENTITY_TYPE_LABELS: Record<string, string> = {
  tech: 'Технология',
  person: 'Персона',
  org: 'Организация',
  product: 'Продукт',
  country: 'Страна',
  document: 'Документ',
  regulation: 'Регуляция',
  other: 'Другое',
}

interface EntityListProps {
  items: EntityOutDto[]
}

export function EntityList({ items }: EntityListProps) {
  return (
    <ul className="entity-list" role="list" aria-label="Список сущностей">
      {items.map((e) => {
        const aliasValues = e.aliases?.map((a) => a.alias_value).filter(Boolean) ?? []
        const uniqueAliases = [...new Set(aliasValues)]
        const canonicalLower = (e.canonical_name ?? '').toLowerCase()
        const normalizedLower = (e.normalized_name ?? '').toLowerCase()
        const displayAliases = uniqueAliases.filter(
          (a) => a.toLowerCase() !== canonicalLower && a.toLowerCase() !== normalizedLower
        )
        return (
          <li key={e.id} className="entity-list__card">
            <div className="entity-list__card-header">
              <span className="entity-list__kind">
                {ENTITY_TYPE_LABELS[e.entity_type] ?? e.entity_type}
              </span>
              {e.mention_count > 0 && (
                <span className="entity-list__meta">
                  Упоминаний: {e.mention_count}
                </span>
              )}
            </div>
            <h3 className="entity-list__title">{e.canonical_name}</h3>
            {e.normalized_name && e.normalized_name !== e.canonical_name && (
              <p className="entity-list__normalized">{e.normalized_name}</p>
            )}
            {displayAliases.length > 0 && (
              <div className="entity-list__aliases">
                <span className="entity-list__aliases-label">Алиасы: </span>
                {displayAliases.join(', ')}
              </div>
            )}
            <div className="entity-list__meta">
              <span>Первое появление: {formatDate(e.first_seen_at)}</span>
              <span>Последнее: {formatDate(e.last_seen_at)}</span>
            </div>
          </li>
        )
      })}
    </ul>
  )
}
