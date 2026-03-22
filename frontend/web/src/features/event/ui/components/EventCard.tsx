import type { EventOutDto } from '@/features/event'
import './EventCard.css'

interface EventCardProps {
  event: EventOutDto
  onOpenDetail: (event: EventOutDto) => void
}

export function EventCard({ event, onOpenDetail }: EventCardProps) {
  const subtitleParts: string[] = []
  if (event.plot_name) subtitleParts.push(event.plot_name)
  if (event.predicate_class) subtitleParts.push(event.predicate_class)
  const subtitle = subtitleParts.join(' · ')

  return (
    <div className="event-card">
      {subtitle && <div className="event-card__subtitle">{subtitle}</div>}
      <div className="event-card__text">{event.display_text}</div>
      {event.event_time && <div className="event-card__time">{event.event_time}</div>}
      <div className="event-card__footer">
        <button
          type="button"
          className="event-card__btn"
          onClick={() => onOpenDetail(event)}
        >
          Подробно
        </button>
      </div>
    </div>
  )
}

