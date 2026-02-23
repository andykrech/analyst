import { useTopicStore } from '@/app/store/topicStore'
import { QuantaTab } from './QuantaTab'
import './QuantaTab.css'

export function QuantaPage() {
  const activeTopicId = useTopicStore((s) => s.activeTopicId)

  if (!activeTopicId) {
    return (
      <div className="quanta-page">
        <p className="quanta-page__placeholder">
          Выберите или создайте тему для просмотра квантов
        </p>
      </div>
    )
  }

  return <QuantaTab themeId={activeTopicId} />
}
