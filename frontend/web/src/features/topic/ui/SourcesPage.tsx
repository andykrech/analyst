import { useTopicStore } from '@/app/store/topicStore'
import { TopicSourcesTab } from '@/features/source'
import './SourcesPage.css'

export function SourcesPage() {
  const activeTopicId = useTopicStore((s) => s.activeTopicId)

  if (!activeTopicId) {
    return (
      <div className="sources-page">
        <p className="sources-page__placeholder">
          Выберите или создайте тему для управления источниками
        </p>
      </div>
    )
  }

  return <TopicSourcesTab themeId={activeTopicId} />
}
