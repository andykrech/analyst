import { useState } from 'react'
import { NavLink } from 'react-router-dom'
import { useTopicStore } from '@/app/store/topicStore'
import { themesApi, type ThemeSaveRequestDto } from '@/features/topic/api/themesApi'
import { ApiError } from '@/shared/api/apiClient'
import './TopicTabs.css'

function termToDto(t: { id: string; text: string; context?: string; translations?: Record<string, string> }) {
  return {
    id: t.id,
    text: t.text,
    context: t.context ?? '',
    translations: t.translations ?? {},
  }
}

export function TopicTabs() {
  const setActiveTab = useTopicStore((s) => s.setActiveTab)
  const theme = useTopicStore((s) => s.data.theme)
  const search = useTopicStore((s) => s.data.search)
  const activeTopicId = useTopicStore((s) => s.activeTopicId)
  const loadTopicIntoStore = useTopicStore((s) => s.loadTopicIntoStore)

  const [saving, setSaving] = useState(false)
  const [successMessage, setSuccessMessage] = useState<string | null>(null)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)

  const handleSave = async () => {
    setErrorMessage(null)
    setSuccessMessage(null)
    setSaving(true)
    try {
      const payload: ThemeSaveRequestDto = {
        theme: {
          title: theme.title.trim() || 'Без названия',
          description: theme.description.trim() || 'Нет описания',
          keywords: search.keywordTerms.map(termToDto),
          must_have: search.mustTerms.map(termToDto),
          exclude: search.excludeTerms.map(termToDto),
          languages: theme.languages,
        },
        search_queries: ([1, 2, 3] as const)
          .map((orderIndex) => ({ orderIndex, query: search.queries[orderIndex] }))
          .filter(({ query }) => query != null)
          .map(({ orderIndex, query }) => ({
            order_index: orderIndex,
            query_model: {
              keywords: query!.keywords,
              must: query!.must,
              exclude: query!.exclude,
            },
          })),
      }

      const response = activeTopicId
        ? await themesApi.updateTheme(activeTopicId, payload)
        : await themesApi.saveTheme(payload)

      if (!activeTopicId && response.id) {
        loadTopicIntoStore({ id: response.id })
      }
      useTopicStore.getState().setStatusLoaded()
      setSuccessMessage('Тема сохранена')
      setTimeout(() => setSuccessMessage(null), 3000)
    } catch (e) {
      const msg = e instanceof ApiError ? e.message : 'Не удалось сохранить тему'
      setErrorMessage(msg)
      setTimeout(() => setErrorMessage(null), 5000)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="topic-tabs-bar">
      <nav className="topic-tabs" aria-label="Вкладки темы">
        <NavLink
          to="/topic/theme"
          className={({ isActive }) =>
            `topic-tabs__link ${isActive ? 'topic-tabs__link--active' : ''}`
          }
          onClick={() => setActiveTab('theme')}
        >
          Тема
        </NavLink>
        <NavLink
          to="/topic/sources"
          className={({ isActive }) =>
            `topic-tabs__link ${isActive ? 'topic-tabs__link--active' : ''}`
          }
          onClick={() => setActiveTab('sources')}
        >
          Источники
        </NavLink>
      </nav>
      <div className="topic-tabs__actions">
        {successMessage && (
          <span className="topic-tabs__message topic-tabs__message--success" role="status">
            {successMessage}
          </span>
        )}
        {errorMessage && (
          <span className="topic-tabs__message topic-tabs__message--error" role="alert">
            {errorMessage}
          </span>
        )}
        <button
          type="button"
          className="topic-tabs__save-btn"
          onClick={handleSave}
          disabled={saving}
        >
          {saving ? 'Сохранение…' : 'Сохранить тему'}
        </button>
      </div>
    </div>
  )
}
