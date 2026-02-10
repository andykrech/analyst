import { useEffect, useState } from 'react'
import type { Term } from '@/shared/types/term'
import { useTopicStore } from '@/app/store/topicStore'
import { themesApi } from '@/features/topic/api/themesApi'
import { LanguagesBlock } from './LanguagesBlock'
import { TermEditModal } from './TermEditModal'
import './ThemePage.css'

function WordList({
  terms,
  onAdd,
  onRemove,
  onTermClick,
  placeholder,
}: {
  terms: Term[]
  onAdd: (text: string) => void
  onRemove: (id: string) => void
  onTermClick?: (id: string) => void
  placeholder: string
}) {
  const [input, setInput] = useState('')
  const handleAdd = () => {
    const trimmed = input.trim()
    if (trimmed) {
      onAdd(trimmed)
      setInput('')
    }
  }
  return (
    <div className="theme-page__word-list">
      <div className="theme-page__word-input-row">
        <input
          type="text"
          className="theme-page__input theme-page__input--inline"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && (e.preventDefault(), handleAdd())}
          placeholder={placeholder}
        />
        <button type="button" className="theme-page__btn-add" onClick={handleAdd}>
          +
        </button>
      </div>
      <ul className="theme-page__word-tags">
        {terms.map((t) => (
          <li key={t.id} className="theme-page__word-tag">
            <span
              className={`theme-page__word-tag-text ${onTermClick ? 'theme-page__word-tag-text--clickable' : ''}`}
              onClick={onTermClick ? () => onTermClick(t.id) : undefined}
            >
              {t.text}
              {t.needsTranslation && (
                <span className="theme-page__word-tag-badge" title="Нужен перевод">
                  🌐
                </span>
              )}
            </span>
            <button
              type="button"
              className="theme-page__word-tag-remove"
              onClick={(e) => {
                e.stopPropagation()
                onRemove(t.id)
              }}
              aria-label={`Удалить ${t.text}`}
            >
              ×
            </button>
          </li>
        ))}
      </ul>
    </div>
  )
}

// Локальный preview поисковых запросов (без API)
function buildSearchQueriesPreview(theme: {
  keywords: Term[]
  requiredWords: Term[]
  excludedWords: Term[]
}): string[] {
  const parts: string[] = []
  if (theme.keywords.length > 0) {
    parts.push(theme.keywords.map((t) => t.text).join(' OR '))
  }
  if (theme.requiredWords.length > 0) {
    parts.push(theme.requiredWords.map((t) => t.text).join(' '))
  }
  if (theme.excludedWords.length > 0) {
    parts.push('-' + theme.excludedWords.map((t) => t.text).join(' -'))
  }
  if (parts.length === 0) return ['Нет параметров — укажите ключевые слова']
  return parts.slice(0, 3)
}

export function ThemePage() {
  const theme = useTopicStore((s) => s.data.theme)
  const aiSuggest = useTopicStore((s) => s.aiSuggest)
  const setThemeTitle = useTopicStore((s) => s.setThemeTitle)
  const setThemeDescription = useTopicStore((s) => s.setThemeDescription)
  const addThemeKeyword = useTopicStore((s) => s.addThemeKeyword)
  const removeThemeKeyword = useTopicStore((s) => s.removeThemeKeyword)
  const updateThemeTerm = useTopicStore((s) => s.updateThemeTerm)
  const addThemeRequiredWord = useTopicStore((s) => s.addThemeRequiredWord)
  const removeThemeRequiredWord = useTopicStore((s) => s.removeThemeRequiredWord)
  const addThemeExcludedWord = useTopicStore((s) => s.addThemeExcludedWord)
  const removeThemeExcludedWord = useTopicStore((s) => s.removeThemeExcludedWord)
  const suggestThemeFromDescription = useTopicStore(
    (s) => s.suggestThemeFromDescription
  )
  const applyTranslations = useTopicStore((s) => s.applyTranslations)

  type TermListName = 'keywords' | 'requiredWords' | 'excludedWords'

  const [selectedTermId, setSelectedTermId] = useState<string | null>(null)
  const [selectedListName, setSelectedListName] =
    useState<TermListName | null>(null)
  const [isTranslating, setIsTranslating] = useState(false)

  const selectedTerm =
    selectedTermId != null && selectedListName != null
      ? theme[selectedListName].find((t) => t.id === selectedTermId) ?? null
      : null
  const isModalOpen = selectedTermId !== null && selectedTerm !== null
  const additionalLanguages = theme.languages.slice(1)

  const openTermModal = (id: string, listName: TermListName) => {
    setSelectedTermId(id)
    setSelectedListName(listName)
  }

  useEffect(() => {
    if (selectedTermId !== null && selectedTerm === null) {
      setSelectedTermId(null)
      setSelectedListName(null)
    }
  }, [selectedTermId, selectedTerm])

  const handleCloseModal = () => {
    setSelectedTermId(null)
    setSelectedListName(null)
  }

  const handleSaveTerm = (updated: {
    context: string
    translations: Record<string, string>
  }) => {
    if (selectedTermId && selectedListName) {
      updateThemeTerm(selectedListName, selectedTermId, updated)
      handleCloseModal()
    }
  }

  const allTerms: Term[] = [
    ...theme.keywords,
    ...theme.requiredWords,
    ...theme.excludedWords,
  ]

  const queriesPreview = buildSearchQueriesPreview(theme)

  const hasTitle = theme.title.trim().length > 0
  const hasAnyTerms =
    theme.keywords.length > 0 ||
    theme.requiredWords.length > 0 ||
    theme.excludedWords.length > 0

  const hasAdditionalLanguages = additionalLanguages.length > 0
  const allAlreadyTranslated =
    hasAdditionalLanguages &&
    allTerms.length > 0 &&
    allTerms.every((t) => !t.needsTranslation)

  const canTranslate =
    !isTranslating &&
    hasAdditionalLanguages &&
    allTerms.length > 0 &&
    !allAlreadyTranslated

  const handleTranslateAll = async () => {
    if (!canTranslate) return
    const sourceLang = theme.languages[0]
    const targetLangs = theme.languages.slice(1)
    if (!sourceLang || targetLangs.length === 0) return

    const termsPayload = allTerms.map((t) => ({
      id: t.id,
      text: t.text,
      context: t.context,
    }))

    if (termsPayload.length === 0) return

    setIsTranslating(true)
    try {
      for (const targetLanguage of targetLangs) {
        const response = await themesApi.translateTerms({
          source_language: sourceLang,
          target_language: targetLanguage,
          terms: termsPayload,
        })
        applyTranslations(targetLanguage, response.translations)
      }
    } catch (e) {
      const message =
        e instanceof Error
          ? e.message
          : 'Ошибка при переводе ключевых слов'
      // eslint-disable-next-line no-alert
      alert(message)
    } finally {
      setIsTranslating(false)
    }
  }

  return (
    <div className="theme-page">
      <h1 className="theme-page__heading">Тема</h1>

      <section className="theme-page__block">
        <label className="theme-page__label">Название темы</label>
        <input
          type="text"
          className="theme-page__input"
          value={theme.title}
          onChange={(e) => setThemeTitle(e.target.value)}
          placeholder="Введите название"
        />
      </section>

      <section className="theme-page__block">
        <label className="theme-page__label">Описание темы</label>
        <textarea
          className="theme-page__textarea"
          value={theme.description}
          onChange={(e) => setThemeDescription(e.target.value)}
          placeholder="Опишите тему..."
          rows={4}
        />
      </section>

      <section className="theme-page__block">
        <LanguagesBlock />
      </section>

      <section className="theme-page__block">
        <div className="theme-page__suggest-row">
          <button
            type="button"
            className="theme-page__suggest-btn"
            onClick={() => suggestThemeFromDescription()}
            disabled={
              aiSuggest.isLoading ||
              theme.description.trim().length < 3 ||
              (hasTitle && hasAnyTerms)
            }
          >
            {aiSuggest.isLoading
              ? 'Загрузка...'
              : 'Предложить название темы, ключевые слова'}
          </button>
          {aiSuggest.error && (
            <span className="theme-page__suggest-error" role="alert">
              {aiSuggest.error}
            </span>
          )}
        </div>
      </section>

      <section className="theme-page__block">
        <label className="theme-page__label">Ключевые слова</label>
        <WordList
          terms={theme.keywords}
          onAdd={addThemeKeyword}
          onRemove={removeThemeKeyword}
          onTermClick={(id) => openTermModal(id, 'keywords')}
          placeholder="Добавить ключевое слово"
        />
      </section>

      <TermEditModal
        isOpen={isModalOpen}
        term={selectedTerm}
        additionalLanguages={additionalLanguages}
        onClose={handleCloseModal}
        onSave={handleSaveTerm}
      />

      <section className="theme-page__block">
        <label className="theme-page__label">Обязательные слова</label>
        <WordList
          terms={theme.requiredWords}
          onAdd={addThemeRequiredWord}
          onRemove={removeThemeRequiredWord}
          onTermClick={(id) => openTermModal(id, 'requiredWords')}
          placeholder="Добавить обязательное слово"
        />
      </section>

      <section className="theme-page__block">
        <label className="theme-page__label">Минус-слова</label>
        <WordList
          terms={theme.excludedWords}
          onAdd={addThemeExcludedWord}
          onRemove={removeThemeExcludedWord}
          onTermClick={(id) => openTermModal(id, 'excludedWords')}
          placeholder="Добавить минус-слово"
        />
      </section>

      <section className="theme-page__block">
        <button
          type="button"
          className="theme-page__suggest-btn"
          disabled={!canTranslate}
          onClick={handleTranslateAll}
        >
          {isTranslating ? 'Перевод...' : 'Перевести ключевые слова'}
        </button>
      </section>

      <section className="theme-page__block">
        <label className="theme-page__label">Построение поисковых запросов</label>
        <div className="theme-page__queries-preview">
          {queriesPreview.map((q, i) => (
            <div key={i} className="theme-page__query-line">
              {q}
            </div>
          ))}
        </div>
        {/* TODO: Replace with API for search queries generation */}
      </section>
    </div>
  )
}
