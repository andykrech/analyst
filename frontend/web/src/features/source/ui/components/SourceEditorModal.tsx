import { useEffect, useRef } from 'react'

interface SourceEditorModalProps {
  mode: 'create' | 'edit'
  domain: string
  domainReadOnly: boolean
  modeValue: 'include' | 'exclude' | 'prefer'
  statusValue: 'active' | 'muted' | 'pending_review'
  displayName: string
  description: string
  homepageUrl: string
  trustScore: string
  qualityTier: string
  error: string | null
  onDomainChange: (v: string) => void
  onModeChange: (v: 'include' | 'exclude' | 'prefer') => void
  onStatusChange: (v: 'active' | 'muted' | 'pending_review') => void
  onDisplayNameChange: (v: string) => void
  onDescriptionChange: (v: string) => void
  onHomepageUrlChange: (v: string) => void
  onTrustScoreChange: (v: string) => void
  onQualityTierChange: (v: string) => void
  onSave: () => void
  onCancel: () => void
  onClearError: () => void
}

export function SourceEditorModal({
  mode,
  domain,
  domainReadOnly,
  modeValue,
  statusValue,
  displayName,
  description,
  homepageUrl,
  trustScore,
  qualityTier,
  error,
  onDomainChange,
  onModeChange,
  onStatusChange,
  onDisplayNameChange,
  onDescriptionChange,
  onHomepageUrlChange,
  onTrustScoreChange,
  onQualityTierChange,
  onSave,
  onCancel,
  onClearError,
}: SourceEditorModalProps) {
  const domainInputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    if (mode === 'create' && domainInputRef.current) {
      domainInputRef.current.focus()
    }
  }, [mode])

  return (
    <div className="source-editor-overlay" onClick={onCancel}>
      <div
        className="source-editor-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="source-editor-title"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="source-editor-modal__header">
          <h2 id="source-editor-title">
            {mode === 'create' ? 'Добавить источник' : 'Редактировать источник'}
          </h2>
          <button
            type="button"
            className="source-editor-modal__close"
            onClick={onCancel}
            aria-label="Закрыть"
          >
            ×
          </button>
        </div>

        {error && (
          <div className="source-editor-modal__error">
            {error}
            <button
              type="button"
              onClick={onClearError}
              aria-label="Скрыть ошибку"
            >
              ×
            </button>
          </div>
        )}

        <div className="source-editor-modal__body">
          <div className="source-editor-modal__field">
            <label htmlFor="source-domain">Домен или URL</label>
            <input
              id="source-domain"
              ref={domainInputRef}
              type="text"
              value={domain}
              readOnly={domainReadOnly}
              onChange={(e) => onDomainChange(e.target.value)}
              placeholder="example.com или https://example.com/page"
            />
          </div>

          <div className="source-editor-modal__field">
            <label htmlFor="source-mode">Режим</label>
            <select
              id="source-mode"
              value={modeValue}
              onChange={(e) =>
                onModeChange(e.target.value as 'include' | 'exclude' | 'prefer')
              }
            >
              <option value="include">Включить</option>
              <option value="exclude">Исключить</option>
              <option value="prefer">Предпочитать</option>
            </select>
          </div>

          <div className="source-editor-modal__field">
            <label htmlFor="source-status">Статус</label>
            <select
              id="source-status"
              value={statusValue}
              onChange={(e) =>
                onStatusChange(
                  e.target.value as 'active' | 'muted' | 'pending_review'
                )
              }
            >
              <option value="active">Активен</option>
              <option value="muted">Выключен</option>
              <option value="pending_review">На проверке</option>
            </select>
          </div>

          <div className="source-editor-modal__field">
            <label htmlFor="source-display-name">Отображаемое имя</label>
            <input
              id="source-display-name"
              type="text"
              value={displayName}
              onChange={(e) => onDisplayNameChange(e.target.value)}
              placeholder="Название сайта"
            />
          </div>

          <div className="source-editor-modal__field">
            <label htmlFor="source-description">Описание</label>
            <textarea
              id="source-description"
              value={description}
              onChange={(e) => onDescriptionChange(e.target.value)}
              placeholder="Краткое описание тематики"
              rows={3}
            />
          </div>

          <div className="source-editor-modal__field">
            <label htmlFor="source-homepage">Домашняя страница</label>
            <input
              id="source-homepage"
              type="url"
              value={homepageUrl}
              onChange={(e) => onHomepageUrlChange(e.target.value)}
              placeholder="https://..."
            />
          </div>

          <div className="source-editor-modal__field">
            <label htmlFor="source-trust">Оценка доверия (0–1)</label>
            <input
              id="source-trust"
              type="text"
              value={trustScore}
              onChange={(e) => onTrustScoreChange(e.target.value)}
              placeholder="0.5"
            />
          </div>

          <div className="source-editor-modal__field">
            <label htmlFor="source-tier">Категория качества (1–5)</label>
            <input
              id="source-tier"
              type="text"
              value={qualityTier}
              onChange={(e) => onQualityTierChange(e.target.value)}
              placeholder="1"
            />
          </div>
        </div>

        <div className="source-editor-modal__footer">
          <button type="button" onClick={onCancel}>
            Отмена
          </button>
          <button type="button" onClick={onSave}>
            Сохранить
          </button>
        </div>
      </div>
    </div>
  )
}
