import './NewTopicPage.css'

export function NewTopicPage() {
  return (
    <div className="new-topic-page">
      <textarea
        className="new-topic-page__textarea"
        placeholder="Опишите аналитическую тему или запрос..."
        rows={5}
      />
    </div>
  )
}
