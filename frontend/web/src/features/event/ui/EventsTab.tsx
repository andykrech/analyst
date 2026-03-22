import { useEffect } from 'react'
import { useTopicStore } from '@/app/store/topicStore'
import type { EventOutDto } from '@/features/event'
import { EventCard } from './components/EventCard'
import './EventsTab.css'

interface EventsTabProps {
  themeId: string
}

export function EventsTab({ themeId }: EventsTabProps) {
  const events = useTopicStore((s) => s.data.events)
  const loadEvents = useTopicStore((s) => s.loadEvents)
  const openEventDetail = useTopicStore((s) => s.openEventDetail)

  useEffect(() => {
    if (themeId) {
      loadEvents()
    }
  }, [themeId, loadEvents])

  const handleOpenDetail = (event: EventOutDto) => {
    void openEventDetail(event.id)
  }

  return (
    <div className="events-tab">
      {events.error && (
        <div className="events-tab__error">
          {events.error}
        </div>
      )}

      {events.isLoading ? (
        <p className="events-tab__loading">Загрузка…</p>
      ) : events.items.length === 0 ? (
        <p className="events-tab__empty">
          Пока нет извлечённых событий. Нажмите «Извлечь события» на панели выше.
        </p>
      ) : (
        <div className="events-tab__list">
          {events.items.map((ev) => (
            <EventCard key={ev.id} event={ev} onOpenDetail={handleOpenDetail} />
          ))}
        </div>
      )}
    </div>
  )
}

