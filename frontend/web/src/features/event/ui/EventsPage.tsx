import { useTopicStore } from '@/app/store/topicStore'
import { EventsTab } from './EventsTab'
import { EventDetailModal } from './EventDetailModal'

export function EventsPage() {
  const activeTopicId = useTopicStore((s) => s.activeTopicId)

  if (!activeTopicId) {
    return (
      <div className="events-page">
        <p className="events-page__placeholder">
          Выберите или создайте тему для просмотра событий
        </p>
      </div>
    )
  }

  return (
    <>
      <EventsTab themeId={activeTopicId} />
      <EventDetailModal />
    </>
  )
}

