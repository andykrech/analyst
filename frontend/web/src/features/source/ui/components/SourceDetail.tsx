import type { ThemeSiteDto } from '@/features/source/api/dto'

interface SourceDetailProps {
  dto: ThemeSiteDto
  onEdit: () => void
  onMute: () => void
  onUnmute: () => void
  onDelete: () => void
}

export function SourceDetail({
  dto,
  onEdit,
  onMute,
  onUnmute,
  onDelete,
}: SourceDetailProps) {
  const title = dto.site.effective_display_name ?? dto.site.domain ?? '—'
  const isMuted = dto.status === 'muted'

  return (
    <div className="source-detail">
      <h3 className="source-detail__title">{title}</h3>
      <p className="source-detail__domain">{dto.site.domain}</p>
      {dto.site.effective_description && (
        <p className="source-detail__desc">{dto.site.effective_description}</p>
      )}
      {dto.site.effective_homepage_url && (
        <p className="source-detail__url">
          <a
            href={dto.site.effective_homepage_url}
            target="_blank"
            rel="noopener noreferrer"
          >
            {dto.site.effective_homepage_url}
          </a>
        </p>
      )}
      <dl className="source-detail__meta">
        <dt>Режим</dt>
        <dd>{dto.mode}</dd>
        <dt>Статус</dt>
        <dd>{dto.status}</dd>
        <dt>Источник</dt>
        <dd>{dto.source}</dd>
      </dl>
      <div className="source-detail__actions">
        <button type="button" onClick={onEdit}>
          Редактировать
        </button>
        {isMuted ? (
          <button type="button" onClick={onUnmute}>
            Включить
          </button>
        ) : (
          <button type="button" onClick={onMute}>
            Выключить
          </button>
        )}
        <button type="button" onClick={onDelete}>
          Удалить
        </button>
      </div>
    </div>
  )
}
