import { useState } from 'react'
import type { EntityOutDto } from '@/features/entity/api/dto'
import { EntityList } from './EntityList'

const INITIAL_VISIBLE = 3

interface EntityGroupSectionProps {
  title: string
  items: EntityOutDto[]
}

export function EntityGroupSection({ title, items }: EntityGroupSectionProps) {
  const [expanded, setExpanded] = useState(false)
  const visibleCount = expanded ? items.length : INITIAL_VISIBLE
  const visibleItems = items.slice(0, visibleCount)
  const hasMore = items.length > INITIAL_VISIBLE
  const headingId = `entity-group-${title.replace(/\W+/g, '-').toLowerCase()}`

  return (
    <section className="entity-group" aria-labelledby={headingId}>
      <h2 id={headingId} className="entity-group__title">
        {title}
      </h2>
      <EntityList items={visibleItems} />
      {hasMore && (
        <div className="entity-group__expand">
          <button
            type="button"
            className="entity-group__expand-btn"
            onClick={() => setExpanded(!expanded)}
            aria-expanded={expanded}
          >
            {expanded ? 'Свернуть' : `Развернуть (ещё ${items.length - INITIAL_VISIBLE})`}
          </button>
        </div>
      )}
    </section>
  )
}
