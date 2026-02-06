import { useState } from 'react'
import { themesApi } from '../api/themesApi'
import { searchApi, type LinkCollectResult } from '../api/searchApi'
import { ApiError } from '@/shared/api/apiClient'
import './NewTopicPage.css'

export function NewTopicPage() {
  const [themeTitle, setThemeTitle] = useState('Новая тема')
  const [userInput, setUserInput] = useState('')
  const [keywords, setKeywords] = useState<string[]>([])
  const [mustHave, setMustHave] = useState<string[]>([])
  const [excludes, setExcludes] = useState<string[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [searchLoading, setSearchLoading] = useState(false)
  const [searchError, setSearchError] = useState<string | null>(null)
  const [linksResult, setLinksResult] = useState<LinkCollectResult | null>(null)

  const handleProcess = async () => {
    const input = userInput.trim()
    if (!input) {
      setError('Введите текст для обработки.')
      return
    }
    setError(null)
    setLoading(true)
    try {
      const response = await themesApi.prepare({ user_input: input })
      setThemeTitle(response.result.title || themeTitle)
      setKeywords(response.result.keywords ?? [])
      setMustHave(response.result.must_have ?? [])
      setExcludes(response.result.excludes ?? [])
    } catch (e) {
      const message =
        e instanceof ApiError
          ? e.message
          : e instanceof Error
            ? e.message
            : 'Не удалось обработать тему. Попробуйте позже.'
      setError(message)
    } finally {
      setLoading(false)
    }
  }

  const handleSearchSources = async () => {
    const text = userInput.trim()
    if (keywords.length === 0 && !text) return

    setSearchError(null)
    setLinksResult(null)
    setSearchLoading(true)
    try {
      const payload = {
        text: text || null,
        keywords,
        must_have: mustHave,
        exclude: excludes,
        target_links: 50,
      }
      const res = await searchApi.collect(payload)
      setLinksResult(res)
    } catch (e) {
      const message =
        e instanceof ApiError
          ? e.message
          : e instanceof Error
            ? e.message
            : 'Не удалось выполнить поиск. Попробуйте позже.'
      setSearchError(message)
    } finally {
      setSearchLoading(false)
    }
  }

  const canSearch = keywords.length > 0 || userInput.trim() !== ''
  const searchDisabled = loading || searchLoading || !canSearch

  return (
    <div className="new-topic-page">
      <h1 className="new-topic-page__title">{themeTitle}</h1>
      <textarea
        className="new-topic-page__textarea"
        placeholder="Опишите аналитическую тему или запрос..."
        rows={5}
        value={userInput}
        onChange={(e) => setUserInput(e.target.value)}
        disabled={loading}
      />
      <div className="new-topic-page__actions">
        <button
          type="button"
          className="new-topic-page__button"
          onClick={handleProcess}
          disabled={loading}
        >
          {loading ? 'Обработка...' : 'Обработать'}
        </button>
        <button
          type="button"
          className="new-topic-page__button new-topic-page__button--secondary"
          onClick={handleSearchSources}
          disabled={searchDisabled}
        >
          {searchLoading ? 'Поиск...' : 'Поиск источников'}
        </button>
      </div>
      {error && (
        <div className="new-topic-page__error" role="alert">
          {error}
        </div>
      )}
      {!error && (keywords.length > 0 || mustHave.length > 0 || excludes.length > 0) && (
        <div className="new-topic-page__result">
          <div className="new-topic-page__result-row">
            <span className="new-topic-page__result-label">Ключевые слова:</span>
            <span className="new-topic-page__result-value">
              {keywords.length > 0 ? keywords.join(', ') : '—'}
            </span>
          </div>
          <div className="new-topic-page__result-row">
            <span className="new-topic-page__result-label">Обязательные слова:</span>
            <span className="new-topic-page__result-value">
              {mustHave.length > 0 ? mustHave.join(', ') : '—'}
            </span>
          </div>
          <div className="new-topic-page__result-row">
            <span className="new-topic-page__result-label">Минус-слова:</span>
            <span className="new-topic-page__result-value">
              {excludes.length > 0 ? excludes.join(', ') : '—'}
            </span>
          </div>
        </div>
      )}
      {searchError && (
        <div className="new-topic-page__search-error" role="alert">
          {searchError}
        </div>
      )}
      {linksResult && (
        <div className="new-topic-page__links">
          <h2 className="new-topic-page__links-title">Найденные источники</h2>
          <p className="new-topic-page__links-stats">
            Найдено: {linksResult.total_found}, показано: {linksResult.total_returned}
          </p>
          <div className="new-topic-page__links-list">
            {linksResult.items.map((item, idx) => (
              <div key={item.url_hash ?? `${item.url}-${idx}`} className="new-topic-page__link-card">
                <a
                  href={item.url}
                  target="_blank"
                  rel="noreferrer"
                  className="new-topic-page__link-title"
                >
                  {item.title ?? item.url}
                </a>
                {item.title && (
                  <p className="new-topic-page__link-url">{item.url}</p>
                )}
                {item.snippet && (
                  <p className="new-topic-page__link-snippet">{item.snippet}</p>
                )}
                <span className="new-topic-page__link-provider">{item.provider}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
