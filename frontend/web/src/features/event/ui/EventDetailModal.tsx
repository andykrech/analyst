import { useTopicStore } from '@/app/store/topicStore'
import './EventDetailModal.css'

export function EventDetailModal() {
  const detail = useTopicStore((s) => s.data.events.detail)
  const closeEventDetail = useTopicStore((s) => s.closeEventDetail)

  if (!detail.eventId) return null

  const { data, isLoading, error } = detail

  return (
    <div className="event-detail-modal">
      <div className="event-detail-modal__backdrop" onClick={() => closeEventDetail()} />
      <div className="event-detail-modal__content" role="dialog" aria-modal="true">
        <button
          type="button"
          className="event-detail-modal__close"
          onClick={() => closeEventDetail()}
          aria-label="Закрыть"
        >
          ×
        </button>

        {isLoading && <p>Загрузка деталей события…</p>}
        {error && <p className="event-detail-modal__error">{error}</p>}
        {data && (
          <>
            <h2 className="event-detail-modal__title">{data.event.display_text}</h2>

            <section className="event-detail-modal__section">
              <h3>Предикат</h3>
              <p>
                <strong>Текст:</strong> {data.event.predicate_text}
              </p>
              <p>
                <strong>Нормализованный:</strong> {data.event.predicate_normalized}
              </p>
              {data.event.predicate_class && (
                <p>
                  <strong>Класс:</strong> {data.event.predicate_class}
                </p>
              )}
            </section>

            <section className="event-detail-modal__section">
              <h3>Участники</h3>
              {data.participants.length === 0 ? (
                <p>Нет участников.</p>
              ) : (
                <ul className="event-detail-modal__list">
                  {data.participants.map((p) => (
                    <li key={`${p.role_code}-${p.entity_id}`} className="event-detail-modal__list-item">
                      <strong>{p.role_name ?? p.role_code}</strong>:{' '}
                      {p.entity_normalized_name}
                      {p.entity_canonical_name && ` (${p.entity_canonical_name})`}
                    </li>
                  ))}
                </ul>
              )}
            </section>

            <section className="event-detail-modal__section">
              <h3>Атрибуты</h3>
              {data.attributes.length === 0 ? (
                <p>Нет атрибутов.</p>
              ) : (
                <ul className="event-detail-modal__list">
                  {data.attributes.map((a, idx) => (
                    <li key={idx} className="event-detail-modal__list-item">
                      <div>
                        <strong>Цель:</strong> {a.attribute_for}
                        {a.entity_normalized_name && ` (${a.entity_normalized_name})`}
                      </div>
                      <div>
                        <strong>Текст:</strong> {a.attribute_text}
                      </div>
                      {a.attribute_normalized && (
                        <div>
                          <strong>Нормализовано:</strong> {a.attribute_normalized}
                        </div>
                      )}
                    </li>
                  ))}
                </ul>
              )}
            </section>
          </>
        )}
      </div>
    </div>
  )
}

