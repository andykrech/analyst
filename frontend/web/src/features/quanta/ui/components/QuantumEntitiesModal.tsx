import { useEffect, useState } from 'react'
import type {
  QuantumEntitiesOutDto,
  QuantumEntityRefDto,
  QuantumPhenomenonDto,
} from '@/features/quanta/api/dto'
import { getQuantumEntities } from '@/features/quanta/api/quantaApi'
import type { QuantumOutDto } from '@/features/quanta'

interface QuantumEntitiesModalProps {
  quantum: QuantumOutDto | null
  isOpen: boolean
  onClose: () => void
}

type LoadState =
  | { status: 'idle' }
  | { status: 'loading' }
  | { status: 'error'; message: string }
  | { status: 'success'; data: QuantumEntitiesOutDto }

export function QuantumEntitiesModal({ quantum, isOpen, onClose }: QuantumEntitiesModalProps) {
  const [state, setState] = useState<LoadState>({ status: 'idle' })

  useEffect(() => {
    if (!isOpen || !quantum) {
      setState({ status: 'idle' })
      return
    }

    let cancelled = false
    setState({ status: 'loading' })
    getQuantumEntities(quantum.id)
      .then((data) => {
        if (!cancelled) {
          setState({ status: 'success', data })
        }
      })
      .catch((e: unknown) => {
        if (!cancelled) {
          const message = e instanceof Error ? e.message : 'Не удалось загрузить сущности кванта'
          setState({ status: 'error', message })
        }
      })

    return () => {
      cancelled = true
    }
  }, [isOpen, quantum])

  if (!isOpen || !quantum) return null

  const handleOverlayClick = (e: React.MouseEvent<HTMLDivElement>) => {
    if (e.target === e.currentTarget) {
      onClose()
    }
  }

  const renderEntityList = (items: QuantumEntityRefDto[]) =>
    items.length === 0 ? (
      <p className="quantum-entities-modal__empty">Нет сущностей этого типа для кванта.</p>
    ) : (
      <ul className="quantum-entities-modal__list">
        {items.map((ent) => (
          <li key={ent.id} className="quantum-entities-modal__entity">
            <div className="quantum-entities-modal__entity-names">
              <div>
                <span className="quantum-entities-modal__label">Отображаемое имя:</span>{' '}
                <span>{ent.canonical_name}</span>
              </div>
              <div>
                <span className="quantum-entities-modal__label">Нормализованное имя:</span>{' '}
                <span>{ent.normalized_name}</span>
              </div>
            </div>
          </li>
        ))}
      </ul>
    )

  const renderPhenomena = (items: QuantumPhenomenonDto[]) =>
    items.length === 0 ? (
      <p className="quantum-entities-modal__empty">Нет явлений для кванта.</p>
    ) : (
      <ul className="quantum-entities-modal__list">
        {items.map((ent) => (
          <li key={ent.id} className="quantum-entities-modal__entity">
            <div className="quantum-entities-modal__entity-names">
              <div>
                <span className="quantum-entities-modal__label">Отображаемое имя:</span>{' '}
                <span>{ent.canonical_name}</span>
              </div>
              <div>
                <span className="quantum-entities-modal__label">Нормализованное имя:</span>{' '}
                <span>{ent.normalized_name}</span>
              </div>
            </div>
            <div className="quantum-entities-modal__claims">
              {ent.claims.length === 0 ? (
                <p className="quantum-entities-modal__empty">Нет модификаторов и условий.</p>
              ) : (
                <ul className="quantum-entities-modal__claims-list">
                  {ent.claims.map((c, idx) => (
                    <li key={idx} className="quantum-entities-modal__claim">
                      <div>
                        <span className="quantum-entities-modal__label">Модификатор:</span>{' '}
                        <span>{c.modifier || '—'}</span>
                      </div>
                      <div>
                        <span className="quantum-entities-modal__label">Условие:</span>{' '}
                        <span>{c.condition_text || '—'}</span>
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </li>
        ))}
      </ul>
    )

  const originalSummary = quantum.summary_text || ''

  return (
    <div
      className="quantum-entities-modal__overlay"
      onClick={handleOverlayClick}
      role="dialog"
      aria-modal="true"
      aria-labelledby="quantum-entities-modal-title"
    >
      <div className="quantum-entities-modal__panel">
        <h2 id="quantum-entities-modal-title" className="quantum-entities-modal__title">
          Сущности кванта
        </h2>

        <div className="quantum-entities-modal__section">
          <h3 className="quantum-entities-modal__section-title">Наименование кванта</h3>
          <p className="quantum-entities-modal__text">
            <span className="quantum-entities-modal__label">Отображаемое:</span>{' '}
            <span>{quantum.title_translated ?? quantum.title}</span>
          </p>
          <p className="quantum-entities-modal__text">
            <span className="quantum-entities-modal__label">Нормализованное:</span>{' '}
            <span>{quantum.title}</span>
          </p>
        </div>

        <div className="quantum-entities-modal__section">
          <h3 className="quantum-entities-modal__section-title">summary_text (язык кванта)</h3>
          <p className="quantum-entities-modal__summary">{originalSummary}</p>
        </div>

        <div className="quantum-entities-modal__section">
          <h3 className="quantum-entities-modal__section-title">Технологии</h3>
          {state.status === 'success' && renderEntityList(state.data.tech)}
        </div>

        <div className="quantum-entities-modal__section">
          <h3 className="quantum-entities-modal__section-title">Персоны</h3>
          {state.status === 'success' && renderEntityList(state.data.persons)}
        </div>

        <div className="quantum-entities-modal__section">
          <h3 className="quantum-entities-modal__section-title">Явления</h3>
          {state.status === 'success' && renderPhenomena(state.data.phenomena)}
        </div>

        {state.status === 'loading' && (
          <p className="quantum-entities-modal__status">Загрузка сущностей…</p>
        )}
        {state.status === 'error' && (
          <p className="quantum-entities-modal__status quantum-entities-modal__status--error">
            {state.message}
          </p>
        )}

        <div className="quantum-entities-modal__actions">
          <button
            type="button"
            className="quantum-entities-modal__btn quantum-entities-modal__btn--secondary"
            onClick={onClose}
          >
            Закрыть
          </button>
        </div>
      </div>
    </div>
  )
}

