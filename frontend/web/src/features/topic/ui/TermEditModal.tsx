import { useCallback, useEffect, useRef, useState } from 'react'
import ISO6391 from 'iso-639-1'
import type { Term } from '@/shared/types/term'
import './TermEditModal.css'

function norm(s: string | undefined): string {
  return (s ?? '').trim()
}

function getLangLabel(code: string): string {
  const native = ISO6391.getNativeName(code)
  return `${native} (${code})`
}

export interface TermEditModalProps {
  isOpen: boolean
  term: Term | null
  additionalLanguages: string[]
  onClose: () => void
  onSave: (updated: {
    context: string
    translations: Record<string, string>
  }) => void
}

export function TermEditModal({
  isOpen,
  term,
  additionalLanguages,
  onClose,
  onSave,
}: TermEditModalProps) {
  const [draftContext, setDraftContext] = useState('')
  const [draftTranslations, setDraftTranslations] = useState<
    Record<string, string>
  >({})
  const prevTermRef = useRef<Term | null>(null)

  const originalContext = term?.context ?? ''
  const originalTranslations = term?.translations ?? {}

  const localDirty =
    norm(draftContext) !== norm(originalContext) ||
    additionalLanguages.some(
      (code) =>
        norm(draftTranslations[code]) !== norm(originalTranslations[code] ?? '')
    )

  const handleClose = useCallback(() => {
    if (!localDirty) {
      onClose()
      return
    }
    if (
      window.confirm(
        'Есть несохранённые изменения. Закрыть без сохранения?'
      )
    ) {
      onClose()
    }
  }, [localDirty, onClose])

  useEffect(() => {
    if (isOpen && term) {
      prevTermRef.current = term
      setDraftContext(term.context ?? '')
      setDraftTranslations({ ...(term.translations ?? {}) })
    }
  }, [isOpen, term])

  useEffect(() => {
    if (!isOpen) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') handleClose()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [isOpen, handleClose])

  const handleOverlayClick = (e: React.MouseEvent) => {
    if (e.target === e.currentTarget) handleClose()
  }

  const handleSave = () => {
    const trans: Record<string, string> = {}
    for (const code of additionalLanguages) {
      trans[code] = norm(draftTranslations[code]) ?? ''
    }
    onSave({ context: norm(draftContext), translations: trans })
    onClose()
  }

  if (!isOpen) return null

  return (
    <div
      className="term-edit-modal__overlay"
      onClick={handleOverlayClick}
      role="dialog"
      aria-modal="true"
      aria-labelledby="term-edit-modal-title"
    >
      <div className="term-edit-modal__panel">
        <h2 id="term-edit-modal-title" className="term-edit-modal__title">
          Слово
        </h2>

        <div className="term-edit-modal__field">
          <label className="term-edit-modal__label">Термин</label>
          <input
            type="text"
            className="term-edit-modal__input term-edit-modal__input--readonly"
            value={term?.text ?? ''}
            readOnly
            disabled
          />
        </div>

        <div className="term-edit-modal__field">
          <label className="term-edit-modal__label">Контекст</label>
          <textarea
            className="term-edit-modal__textarea"
            value={draftContext}
            onChange={(e) => setDraftContext(e.target.value)}
            rows={3}
          />
        </div>

        {additionalLanguages.length > 0 && (
          <div className="term-edit-modal__field">
            <label className="term-edit-modal__label">Переводы</label>
            {additionalLanguages.map((code) => (
              <div key={code} className="term-edit-modal__translation-row">
                <label className="term-edit-modal__sublabel">
                  {getLangLabel(code)}
                </label>
                <input
                  type="text"
                  className="term-edit-modal__input"
                  value={draftTranslations[code] ?? ''}
                  onChange={(e) =>
                    setDraftTranslations((prev) => ({
                      ...prev,
                      [code]: e.target.value,
                    }))
                  }
                />
              </div>
            ))}
          </div>
        )}

        <div className="term-edit-modal__actions">
          <button
            type="button"
            className="term-edit-modal__btn term-edit-modal__btn--primary"
            onClick={handleSave}
          >
            Сохранить
          </button>
          <button
            type="button"
            className="term-edit-modal__btn term-edit-modal__btn--secondary"
            onClick={handleClose}
          >
            Закрыть
          </button>
        </div>
      </div>
    </div>
  )
}
