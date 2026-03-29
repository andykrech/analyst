import { useEffect, useState } from 'react'
import { ApiError } from '@/shared/api/apiClient'
import { listBillingUsageEvents } from '../api/billingApi'
import type { BillingUsageEventDto, BillingUsageEventsListDto } from '../api/dto'
import './BillingUsageModal.css'

/** service_impl (ключ тарифа); для старых событий без поля — черпаем из extra. */
function billingImplementationLabel(it: BillingUsageEventDto): string {
  const raw = it.service_impl?.trim()
  if (raw) return raw
  const ex = it.extra
  if (!ex || typeof ex !== 'object' || Array.isArray(ex)) return '—'
  const o = ex as Record<string, unknown>
  if (typeof o.translator === 'string' && o.translator.trim()) return o.translator.trim()
  if (typeof o.retriever === 'string' && o.retriever.trim()) return o.retriever.trim()
  const provider = typeof o.provider === 'string' ? o.provider.trim() : ''
  const model = typeof o.model === 'string' ? o.model.trim() : ''
  if (provider && model) return `${provider}/${model}`
  if (provider) return provider
  if (model) return model
  return '—'
}

interface BillingUsageModalProps {
  themeId: string | null
  isOpen: boolean
  onClose: () => void
}

type LoadState =
  | { status: 'idle' }
  | { status: 'loading' }
  | { status: 'error'; message: string }
  | { status: 'success'; data: BillingUsageEventsListDto }

export function BillingUsageModal({ themeId, isOpen, onClose }: BillingUsageModalProps) {
  const [state, setState] = useState<LoadState>({ status: 'idle' })

  useEffect(() => {
    if (!isOpen) {
      setState({ status: 'idle' })
      return
    }
    if (!themeId) {
      setState({ status: 'error', message: 'Тема не выбрана.' })
      return
    }

    let cancelled = false
    setState({ status: 'loading' })
    listBillingUsageEvents(themeId, { limit: 200, offset: 0 })
      .then((data) => {
        if (!cancelled) setState({ status: 'success', data })
      })
      .catch((e: unknown) => {
        if (cancelled) return
        if (e instanceof ApiError && (e.status === 404 || e.status === 501)) {
          setState({
            status: 'error',
            message:
              'API детального биллинга ещё не доступно на бэкенде. Нужно добавить эндпоинт для выдачи billing_usage_events.',
          })
          return
        }
        const message = e instanceof Error ? e.message : 'Не удалось загрузить детальный биллинг'
        setState({ status: 'error', message })
      })

    return () => {
      cancelled = true
    }
  }, [isOpen, themeId])

  if (!isOpen) return null

  const handleOverlayClick = (e: React.MouseEvent<HTMLDivElement>) => {
    if (e.target === e.currentTarget) onClose()
  }

  return (
    <div className="billing-usage-overlay" role="dialog" aria-modal="true" onClick={handleOverlayClick}>
      <div className="billing-usage-modal" onClick={(e) => e.stopPropagation()}>
        <div className="billing-usage-modal__header">
          <h2 className="billing-usage-modal__title">Детальный биллинг</h2>
          <button type="button" className="billing-usage-modal__close" onClick={onClose} aria-label="Закрыть">
            ×
          </button>
        </div>

        <div className="billing-usage-modal__body">
          <p className="billing-usage-modal__hint">
            Только несвёрнутые события (ещё не учтённые в дневной сводке). Пока без пагинации в UI.
            Колонка «Реализация» — ключ из тарифа (модель LLM, переводчик, ретривер и т.п.); у записей до
            появления поля в БД может подставляться краткая строка из доп. полей.
          </p>

          {state.status === 'loading' && (
            <div className="billing-usage-modal__state">Загрузка…</div>
          )}

          {state.status === 'error' && (
            <div className="billing-usage-modal__error">{state.message}</div>
          )}

          {state.status === 'success' && (
            <table className="billing-usage-table">
              <thead>
                <tr>
                  <th>Время</th>
                  <th>Сервис</th>
                  <th title="Совпадает с billing_tariffs.service_impl (ключ тарифа)">Реализация</th>
                  <th>Задача</th>
                  <th>Объём</th>
                  <th>Ед.</th>
                  <th>Стоимость (тариф)</th>
                  <th>Вал.</th>
                  <th>Стоимость (показ)</th>
                  <th>Вал.</th>
                </tr>
              </thead>
              <tbody>
                {state.data.items.length === 0 ? (
                  <tr>
                    <td colSpan={10} className="billing-usage-table__wide">
                      Нет данных.
                    </td>
                  </tr>
                ) : (
                  state.data.items.map((it) => (
                    <tr key={it.id}>
                      <td>{new Date(it.occurred_at).toLocaleString()}</td>
                      <td>{it.service_type}</td>
                      <td>{billingImplementationLabel(it)}</td>
                      <td>{it.task_type}</td>
                      <td>{it.quantity}</td>
                      <td>{it.quantity_unit_code}</td>
                      <td>{it.cost_tariff_currency}</td>
                      <td>{it.tariff_currency_code}</td>
                      <td>{it.cost_display_currency}</td>
                      <td>{it.display_currency_code}</td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </div>
  )
}

