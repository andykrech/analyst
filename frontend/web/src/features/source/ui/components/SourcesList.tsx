import type {
  ThemeSiteDto,
  ThemeSiteMode,
  ThemeSiteSource,
  ThemeSiteStatus,
} from '@/features/source/api/dto'

const SOURCE_ICON: Record<ThemeSiteSource, string> = {
  ai_recommended: '🤖',
  user_added: '👤',
  discovered: '🔎',
  admin_seed: '🧩',
}

const MODE_LABELS: Record<ThemeSiteMode, string> = {
  include: 'Используется',
  prefer: 'Предпочитается',
  exclude: 'Запрещен',
}

const STATUS_LABELS: Record<ThemeSiteStatus, string> = {
  active: 'Активен',
  muted: 'Временно отключен',
  pending_review: 'Требует подтверждения',
}

interface SourcesListProps {
  items: ThemeSiteDto[]
  onEdit: (themeSiteId: string) => void
  onDelete: (themeSiteId: string) => void
  onModeChange: (themeSiteId: string, mode: ThemeSiteMode) => void
  onStatusChange: (themeSiteId: string, status: ThemeSiteStatus) => void
}

export function SourcesList({
  items,
  onEdit,
  onDelete,
  onModeChange,
  onStatusChange,
}: SourcesListProps) {
  return (
    <ul className="sources-list" role="list" aria-label="Список источников">
      {items.map((dto) => {
        const title =
          dto.site.effective_display_name ?? dto.site.domain ?? '—'
        const domain = dto.site.domain ?? ''
        const desc = dto.site.effective_description ?? ''
        const icon = SOURCE_ICON[dto.source] ?? '📄'

        return (
          <li key={dto.id} className="sources-list__card">
            <div className="sources-list__card-header">
              <span className="sources-list__icon" title={dto.source}>
                {icon}
              </span>
              <span className="sources-list__title">{title}</span>
              <div className="sources-list__actions">
                <button
                  type="button"
                  className="sources-list__btn sources-list__btn--edit"
                  onClick={(e) => {
                    e.stopPropagation()
                    onEdit(dto.id)
                  }}
                  aria-label="Редактировать"
                  title="Редактировать"
                >
                  ✎
                </button>
                <button
                  type="button"
                  className="sources-list__btn sources-list__btn--delete"
                  onClick={(e) => {
                    e.stopPropagation()
                    onDelete(dto.id)
                  }}
                  aria-label="Удалить"
                  title="Удалить"
                >
                  ×
                </button>
              </div>
            </div>
            <span className="sources-list__domain">{domain}</span>
            {desc && (
              <span className="sources-list__desc">{desc}</span>
            )}
            <div className="sources-list__selects">
              <select
                className="sources-list__select"
                value={dto.mode}
                onChange={(e) =>
                  onModeChange(dto.id, e.target.value as ThemeSiteMode)
                }
                onClick={(e) => e.stopPropagation()}
                aria-label="Режим источника"
              >
                {(Object.keys(MODE_LABELS) as ThemeSiteMode[]).map((m) => (
                  <option key={m} value={m}>
                    {MODE_LABELS[m]}
                  </option>
                ))}
              </select>
              <select
                className="sources-list__select"
                value={dto.status}
                onChange={(e) =>
                  onStatusChange(dto.id, e.target.value as ThemeSiteStatus)
                }
                onClick={(e) => e.stopPropagation()}
                aria-label="Статус источника"
              >
                {(Object.keys(STATUS_LABELS) as ThemeSiteStatus[]).map((s) => (
                  <option key={s} value={s}>
                    {STATUS_LABELS[s]}
                  </option>
                ))}
              </select>
            </div>
          </li>
        )
      })}
    </ul>
  )
}
