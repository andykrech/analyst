import { useTopicStore } from '@/app/store/topicStore'
import { EntitiesTab } from './EntitiesTab'

export function EntitiesPage() {
  const activeTopicId = useTopicStore((s) => s.activeTopicId)

  if (!activeTopicId) {
    return (
      <div className="entities-page">
        <p className="entities-page__placeholder">
          Выберите или создайте тему для просмотра сущностей
        </p>
      </div>
    )
  }

  return <EntitiesTab themeId={activeTopicId} />
}
