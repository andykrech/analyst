import { useEffect, useState } from 'react'
import { useBlocker } from 'react-router-dom'
import type { Term } from '@/shared/types/term'
import { useTopicStore } from '@/app/store/topicStore'
import { themesApi } from '@/features/topic/api/themesApi'
import {
  type GroupOp,
  type TermPools,
  compileQueryPreviewFromSaved,
  getUnusedExcludeTerms,
  getUnusedKeywordTerms,
  getUnusedMustTerms,
} from '@/features/topic/types/queryBuilder'
import { LanguagesBlock } from './LanguagesBlock'
import { TermEditModal } from './TermEditModal'
import './ThemePage.css'

function getTermFromPools(
  pools: TermPools,
  poolKey: 'keyword' | 'must' | 'exclude',
  termId: string
): Term | null {
  const list =
    poolKey === 'keyword'
      ? pools.keywordTerms
      : poolKey === 'must'
        ? pools.mustTerms
        : pools.excludeTerms
  return list.find((t) => t.id === termId) ?? null
}

/** Неиспользуемые ключевые слова: только добавление и «В группу»; без удаления. */
function UnusedKeywordsBlock({
  terms,
  onAdd,
  onMoveToGroup,
  onTermClick,
  groupCount,
  inputOnly,
  listOnly,
}: {
  terms: Term[]
  onAdd: (text: string) => void
  onMoveToGroup: (termId: string, groupIndex: number) => void
  onTermClick?: (id: string) => void
  groupCount: number
  inputOnly?: boolean
  listOnly?: boolean
}) {
  const [input, setInput] = useState('')
  const handleAdd = () => {
    const trimmed = input.trim()
    if (trimmed) {
      onAdd(trimmed)
      setInput('')
    }
  }
  const showInput = !listOnly
  const showList = !inputOnly
  return (
    <div className="theme-page__word-list">
      {showInput && (
        <div className="theme-page__word-input-row">
          <input
            type="text"
            className="theme-page__input theme-page__input--inline"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && (e.preventDefault(), handleAdd())}
            placeholder="Добавить ключевое слово"
          />
          <button type="button" className="theme-page__btn-add" onClick={handleAdd}>
            +
          </button>
        </div>
      )}
      {showList && (
        <ul className="theme-page__word-tags">
          {terms.map((t) => (
            <li key={t.id} className="theme-page__word-tag theme-page__word-tag--free">
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
              {groupCount > 0 && (
                <select
                  className="theme-page__word-tag-move"
                  value=""
                  onChange={(e) => {
                    const idx = Number(e.target.value)
                    if (!Number.isNaN(idx) && idx >= 0) onMoveToGroup(t.id, idx)
                    e.target.value = ''
                  }}
                  aria-label={`Переместить ${t.text} в группу`}
                >
                  <option value="">В группу →</option>
                  {Array.from({ length: groupCount }, (_, i) => (
                    <option key={i} value={i}>
                      Группа {i + 1}
                    </option>
                  ))}
                </select>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

/** Группа ключевых слов: оператор OR/AND, теги со стрелкой вверх (в неиспользуемые). */
function KeywordGroupBlock({
  index,
  op,
  terms,
  connectorLeft,
  onOpChange,
  onConnectorChange,
  onMoveToUnused,
  onTermClick,
  onRemoveGroup,
  canRemoveGroup,
}: {
  index: number
  op: GroupOp
  terms: Term[]
  connectorLeft: GroupOp | null
  onOpChange: (op: GroupOp) => void
  onConnectorChange: (op: GroupOp) => void
  onMoveToUnused: (termId: string) => void
  onTermClick?: (termId: string) => void
  onRemoveGroup: () => void
  canRemoveGroup: boolean
}) {
  return (
    <div className="theme-page__keyword-group">
      {connectorLeft !== null && (
        <div className="theme-page__group-connector">
          <select
            value={connectorLeft}
            onChange={(e) => onConnectorChange(e.target.value as GroupOp)}
            aria-label="Связь с предыдущей группой"
          >
            <option value="AND">AND</option>
            <option value="OR">OR</option>
          </select>
        </div>
      )}
      <div className="theme-page__group-card">
        <div className="theme-page__group-header">
          <span className="theme-page__group-title">Группа {index + 1}</span>
          <div className="theme-page__group-controls">
            <select
              value={op}
              onChange={(e) => onOpChange(e.target.value as GroupOp)}
              aria-label="Оператор внутри группы"
            >
              <option value="OR">OR</option>
              <option value="AND">AND</option>
            </select>
            {canRemoveGroup && (
              <button
                type="button"
                className="theme-page__group-remove"
                onClick={onRemoveGroup}
                aria-label="Удалить группу"
              >
                Удалить группу
              </button>
            )}
          </div>
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
                className="theme-page__word-tag-move-up"
                onClick={() => onMoveToUnused(t.id)}
                aria-label={`В неиспользуемые: ${t.text}`}
                title="В неиспользуемые слова"
              >
                ↑
              </button>
            </li>
          ))}
        </ul>
      </div>
    </div>
  )
}

/** Один список терминов: только «В запрос» (в группу) и клик по термину для модалки. */
function UnusedTermsList({
  terms,
  onAdd,
  onMoveToGroup,
  onTermClick,
  placeholder,
  moveLabel,
  inputOnly,
  listOnly,
}: {
  terms: Term[]
  onAdd: (text: string) => void
  onMoveToGroup: (termId: string) => void
  onTermClick?: (id: string) => void
  placeholder: string
  moveLabel: string
  inputOnly?: boolean
  listOnly?: boolean
}) {
  const [input, setInput] = useState('')
  const handleAdd = () => {
    const trimmed = input.trim()
    if (trimmed) {
      onAdd(trimmed)
      setInput('')
    }
  }
  const showInput = !listOnly
  const showList = !inputOnly
  return (
    <div className="theme-page__word-list">
      {showInput && (
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
      )}
      {showList && (
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
                className="theme-page__btn-to-query"
                onClick={() => onMoveToGroup(t.id)}
                aria-label={`${moveLabel}: ${t.text}`}
              >
                {moveLabel}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

/** Термины в группе запроса (MUST или NOT): стрелка вверх в неиспользуемые. */
function UsedTermsList({
  terms,
  onMoveToUnused,
  onTermClick,
}: {
  terms: Term[]
  onMoveToUnused: (termId: string) => void
  onTermClick?: (id: string) => void
}) {
  return (
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
            className="theme-page__word-tag-move-up"
            onClick={() => onMoveToUnused(t.id)}
            aria-label={`В неиспользуемые: ${t.text}`}
            title="В неиспользуемые"
          >
            ↑
          </button>
        </li>
      ))}
    </ul>
  )
}

export function ThemePage() {
  const theme = useTopicStore((s) => s.data.theme)
  const search = useTopicStore((s) => s.data.search)
  const aiSuggest = useTopicStore((s) => s.aiSuggest)
  const setThemeTitle = useTopicStore((s) => s.setThemeTitle)
  const setThemeDescription = useTopicStore((s) => s.setThemeDescription)
  const suggestThemeFromDescription = useTopicStore(
    (s) => s.suggestThemeFromDescription
  )
  const addSearchKeyword = useTopicStore((s) => s.addSearchKeyword)
  const moveKeywordToGroup = useTopicStore((s) => s.moveKeywordToGroup)
  const moveKeywordToUnused = useTopicStore((s) => s.moveKeywordToUnused)
  const setDraftKeywordGroupOp = useTopicStore((s) => s.setDraftKeywordGroupOp)
  const setDraftConnector = useTopicStore((s) => s.setDraftConnector)
  const addDraftKeywordGroup = useTopicStore((s) => s.addDraftKeywordGroup)
  const removeDraftKeywordGroup = useTopicStore((s) => s.removeDraftKeywordGroup)
  const setDraftMustMode = useTopicStore((s) => s.setDraftMustMode)
  const addSearchMustTerm = useTopicStore((s) => s.addSearchMustTerm)
  const moveMustToGroup = useTopicStore((s) => s.moveMustToGroup)
  const moveMustToUnused = useTopicStore((s) => s.moveMustToUnused)
  const addSearchExcludeTerm = useTopicStore((s) => s.addSearchExcludeTerm)
  const moveExcludeToGroup = useTopicStore((s) => s.moveExcludeToGroup)
  const moveExcludeToUnused = useTopicStore((s) => s.moveExcludeToUnused)
  const saveCurrentQuery = useTopicStore((s) => s.saveCurrentQuery)
  const newQueryAfterConfirm = useTopicStore((s) => s.newQueryAfterConfirm)
  const startEditingQuery = useTopicStore((s) => s.startEditingQuery)
  const deleteSavedQuery = useTopicStore((s) => s.deleteSavedQuery)
  const updateSearchTermInPool = useTopicStore((s) => s.updateSearchTermInPool)
  const seedSearchPoolsForTesting = useTopicStore((s) => s.seedSearchPoolsForTesting)

  useEffect(() => {
    seedSearchPoolsForTesting()
  }, [seedSearchPoolsForTesting])

  const draft = search.queries[0]
  const pools: TermPools = {
    keywordTerms: search.keywordTerms,
    mustTerms: search.mustTerms,
    excludeTerms: search.excludeTerms,
  }
  const unusedKeywords = getUnusedKeywordTerms(pools, draft)
  const unusedMust = getUnusedMustTerms(pools, draft)
  const unusedExclude = getUnusedExcludeTerms(pools, draft)
  const mustTermsInQuery = draft.must.termIds
    .map((id) => pools.mustTerms.find((t) => t.id === id))
    .filter((t): t is Term => t != null)
  const excludeTermsInQuery = draft.exclude.termIds
    .map((id) => pools.excludeTerms.find((t) => t.id === id))
    .filter((t): t is Term => t != null)
  const keywordGroupsTerms = draft.keywords.groups.map((g) =>
    g.termIds
      .map((id) => pools.keywordTerms.find((t) => t.id === id))
      .filter((t): t is Term => t != null)
  )

  const [selectedTermId, setSelectedTermId] = useState<string | null>(null)
  const [selectedPoolKey, setSelectedPoolKey] = useState<
    'keyword' | 'must' | 'exclude' | null
  >(null)
  const selectedTerm =
    selectedTermId && selectedPoolKey
      ? getTermFromPools(pools, selectedPoolKey, selectedTermId)
      : null
  const isModalOpen = selectedTermId !== null && selectedTerm !== null
  const additionalLanguages = theme.languages.slice(1)

  const [showNewQueryConfirm, setShowNewQueryConfirm] = useState(false)
  const [showDeleteConfirm, setShowDeleteConfirm] = useState<1 | 2 | 3 | null>(
    null
  )
  const [isTranslating, setIsTranslating] = useState(false)

  useEffect(() => {
    if (selectedTermId !== null && selectedTerm === null) {
      setSelectedTermId(null)
      setSelectedPoolKey(null)
    }
  }, [selectedTermId, selectedTerm])

  const leaveBlocker = useBlocker(search.isEditingDraft)
  const showLeaveConfirm =
    leaveBlocker.state === 'blocked' && leaveBlocker.location != null

  useEffect(() => {
    const handleBeforeUnload = (e: BeforeUnloadEvent) => {
      if (search.isEditingDraft) {
        e.preventDefault()
      }
    }
    window.addEventListener('beforeunload', handleBeforeUnload)
    return () => window.removeEventListener('beforeunload', handleBeforeUnload)
  }, [search.isEditingDraft])

  const handleLeaveConfirm = (save: boolean) => {
    if (save) saveCurrentQuery()
    else newQueryAfterConfirm(false)
    if (typeof leaveBlocker.proceed === 'function') leaveBlocker.proceed()
  }

  const handleCloseModal = () => {
    setSelectedTermId(null)
    setSelectedPoolKey(null)
  }

  const openTermModal = (termId: string, poolKey: 'keyword' | 'must' | 'exclude') => {
    setSelectedTermId(termId)
    setSelectedPoolKey(poolKey)
  }

  const handleSaveTerm = (updated: {
    context: string
    translations: Record<string, string>
  }) => {
    if (selectedTermId && selectedPoolKey) {
      updateSearchTermInPool(selectedPoolKey, selectedTermId, updated)
      handleCloseModal()
    }
  }

  const handleSaveQuery = () => {
    saveCurrentQuery()
  }

  const handleNewQuery = () => {
    if (search.isEditingDraft) {
      setShowNewQueryConfirm(true)
      return
    }
    newQueryAfterConfirm(false)
  }

  const handleNewQueryConfirm = (save: boolean) => {
    setShowNewQueryConfirm(false)
    newQueryAfterConfirm(save)
  }

  const handleDeleteQuery = (index: 1 | 2 | 3) => {
    setShowDeleteConfirm(index)
  }

  const handleDeleteQueryConfirm = (confirmed: boolean) => {
    if (confirmed && showDeleteConfirm !== null) {
      deleteSavedQuery(showDeleteConfirm)
    }
    setShowDeleteConfirm(null)
  }

  const savedQueries: { index: 1 | 2 | 3; text: string }[] = []
  for (let i = 1; i <= 3; i++) {
    const q = search.queries[i as 1 | 2 | 3]
    if (q !== null) {
      savedQueries.push({
        index: i as 1 | 2 | 3,
        text: compileQueryPreviewFromSaved(pools, q),
      })
    }
  }

  const canSaveQuery =
    savedQueries.length < 3 || search.editingQueryIndex !== null
  const queryPreview = compileQueryPreviewFromSaved(pools, draft)

  const hasTitle = theme.title.trim().length > 0
  const hasAnyTerms =
    pools.keywordTerms.length > 0 ||
    pools.mustTerms.length > 0 ||
    pools.excludeTerms.length > 0

  const allTermsFromSearch: Term[] = [
    ...pools.keywordTerms,
    ...pools.mustTerms,
    ...pools.excludeTerms,
  ]
  const hasAdditionalLanguages = additionalLanguages.length > 0
  const allAlreadyTranslated =
    hasAdditionalLanguages &&
    allTermsFromSearch.length > 0 &&
    allTermsFromSearch.every((t) => !t.needsTranslation)
  const canTranslate =
    !isTranslating &&
    hasAdditionalLanguages &&
    allTermsFromSearch.length > 0 &&
    !allAlreadyTranslated

  const handleTranslateAll = async () => {
    if (!canTranslate) return
    const sourceLang = theme.languages[0]
    const targetLangs = theme.languages.slice(1)
    if (!sourceLang || targetLangs.length === 0) return
    const termsPayload = allTermsFromSearch.map((t) => ({
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
        useTopicStore.getState().applyTranslations(
          targetLanguage,
          response.translations
        )
      }
    } catch (e) {
      const message =
        e instanceof Error ? e.message : 'Ошибка при переводе ключевых слов'
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

      <section className="theme-page__block theme-page__block--query">
        <h2 className="theme-page__subheading">Конструктор запроса</h2>

        {/* Ключевые слова: поле добавления → неиспользуемые → группы */}
        <div className="theme-page__block">
          <h3 className="theme-page__section-title">Ключевые слова</h3>
          <UnusedKeywordsBlock
            terms={unusedKeywords}
            onAdd={addSearchKeyword}
            onMoveToGroup={moveKeywordToGroup}
            onTermClick={(id) => openTermModal(id, 'keyword')}
            groupCount={draft.keywords.groups.length}
            inputOnly
          />
          <label className="theme-page__label">Неиспользуемые ключевые слова</label>
          <p className="theme-page__hint">
            Добавлять слова можно только здесь. «В группу» — переместить в выбранную группу.
          </p>
          <UnusedKeywordsBlock
            terms={unusedKeywords}
            onAdd={addSearchKeyword}
            onMoveToGroup={moveKeywordToGroup}
            onTermClick={(id) => openTermModal(id, 'keyword')}
            groupCount={draft.keywords.groups.length}
            listOnly
          />
          <label className="theme-page__label">Группы ключевых слов</label>
          <div className="theme-page__groups">
            {draft.keywords.groups.map((group, i) => (
              <KeywordGroupBlock
                key={group.id}
                index={i}
                op={group.op}
                terms={keywordGroupsTerms[i] ?? []}
                connectorLeft={
                  i === 0 ? null : draft.keywords.connectors[i - 1] ?? 'AND'
                }
                onOpChange={(op) => setDraftKeywordGroupOp(i, op)}
                onConnectorChange={(op) => setDraftConnector(i - 1, op)}
                onMoveToUnused={moveKeywordToUnused}
                onTermClick={(termId) => openTermModal(termId, 'keyword')}
                onRemoveGroup={() => removeDraftKeywordGroup(i)}
                canRemoveGroup={draft.keywords.groups.length > 1}
              />
            ))}
          </div>
          <button
            type="button"
            className="theme-page__btn-add-group"
            onClick={addDraftKeywordGroup}
          >
            Добавить группу
          </button>
        </div>

        {/* Обязательные слова (MUST): поле → неиспользуемые → режим → группа */}
        <div className="theme-page__block">
          <h3 className="theme-page__section-title">Обязательные слова (MUST)</h3>
          <UnusedTermsList
            terms={unusedMust}
            onAdd={addSearchMustTerm}
            onMoveToGroup={moveMustToGroup}
            onTermClick={(id) => openTermModal(id, 'must')}
            placeholder="Добавить обязательное слово"
            moveLabel="В запрос"
            inputOnly
          />
          <label className="theme-page__label">Неиспользуемые обязательные слова</label>
          <UnusedTermsList
            terms={unusedMust}
            onAdd={addSearchMustTerm}
            onMoveToGroup={moveMustToGroup}
            onTermClick={(id) => openTermModal(id, 'must')}
            placeholder="Добавить обязательное слово"
            moveLabel="В запрос"
            listOnly
          />
          <div className="theme-page__must-mode">
            <span className="theme-page__must-mode-label">Режим:</span>
            <label className="theme-page__radio-label">
              <input
                type="radio"
                name="mustMode"
                checked={draft.must.mode === 'ALL'}
                onChange={() => setDraftMustMode('ALL')}
              />
              Все (ALL)
            </label>
            <label className="theme-page__radio-label">
              <input
                type="radio"
                name="mustMode"
                checked={draft.must.mode === 'ANY'}
                onChange={() => setDraftMustMode('ANY')}
              />
              Любые (ANY)
            </label>
          </div>
          <UsedTermsList
            terms={mustTermsInQuery}
            onMoveToUnused={moveMustToUnused}
            onTermClick={(id) => openTermModal(id, 'must')}
          />
        </div>

        {/* Минус-слова (NOT): поле → неиспользуемые → группа */}
        <div className="theme-page__block">
          <h3 className="theme-page__section-title">Минус-слова (NOT)</h3>
          <UnusedTermsList
            terms={unusedExclude}
            onAdd={addSearchExcludeTerm}
            onMoveToGroup={moveExcludeToGroup}
            onTermClick={(id) => openTermModal(id, 'exclude')}
            placeholder="Добавить минус-слово"
            moveLabel="В запрос"
            inputOnly
          />
          <label className="theme-page__label">Неиспользуемые минус-слова</label>
          <UnusedTermsList
            terms={unusedExclude}
            onAdd={addSearchExcludeTerm}
            onMoveToGroup={moveExcludeToGroup}
            onTermClick={(id) => openTermModal(id, 'exclude')}
            placeholder="Добавить минус-слово"
            moveLabel="В запрос"
            listOnly
          />
          <UsedTermsList
            terms={excludeTermsInQuery}
            onMoveToUnused={moveExcludeToUnused}
            onTermClick={(id) => openTermModal(id, 'exclude')}
          />
        </div>

        <div className="theme-page__block">
          <button
            type="button"
            className="theme-page__suggest-btn"
            disabled={!canTranslate}
            onClick={handleTranslateAll}
          >
            {isTranslating ? 'Перевод...' : 'Перевести ключевые слова'}
          </button>
        </div>

        <div className="theme-page__block">
          <label className="theme-page__label">Редактируемый запрос</label>
          <div className="theme-page__queries-preview theme-page__queries-preview--single">
            <div className="theme-page__query-line">{queryPreview}</div>
          </div>
        </div>

        <div className="theme-page__block theme-page__query-actions">
          <button
            type="button"
            className="theme-page__suggest-btn"
            disabled={!canSaveQuery}
            onClick={handleSaveQuery}
          >
            Сохранить этот запрос
          </button>
          <button
            type="button"
            className="theme-page__btn-secondary"
            disabled={savedQueries.length === 0}
            onClick={handleNewQuery}
          >
            Новый запрос
          </button>
        </div>

        <div className="theme-page__block">
          <label className="theme-page__label">Используемые запросы</label>
          {savedQueries.length === 0 ? (
            <p className="theme-page__hint">Нет сохранённых запросов. Сохраните черновик выше.</p>
          ) : (
            <ul className="theme-page__saved-queries">
              {savedQueries.map(({ index, text }) => (
                <li
                  key={index}
                  className={`theme-page__saved-query ${search.editingQueryIndex === index ? 'theme-page__saved-query--editing' : ''}`}
                >
                  <span className="theme-page__saved-query-text">{text}</span>
                  <div className="theme-page__saved-query-actions">
                    <button
                      type="button"
                      className="theme-page__btn-icon"
                      onClick={() => startEditingQuery(index)}
                      aria-label="Редактировать запрос"
                      title="Редактировать"
                    >
                      ✎
                    </button>
                    <button
                      type="button"
                      className="theme-page__btn-icon theme-page__btn-icon--danger"
                      onClick={() => handleDeleteQuery(index)}
                      aria-label="Удалить запрос"
                      title="Удалить"
                    >
                      ×
                    </button>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>
      </section>

      {showNewQueryConfirm && (
        <div className="theme-page__dialog-backdrop" role="dialog" aria-modal="true">
          <div className="theme-page__dialog">
            <p>Один из запросов был изменён. Сохранить изменения?</p>
            <div className="theme-page__dialog-actions">
              <button
                type="button"
                className="theme-page__suggest-btn"
                onClick={() => handleNewQueryConfirm(true)}
              >
                Да
              </button>
              <button
                type="button"
                className="theme-page__btn-secondary"
                onClick={() => handleNewQueryConfirm(false)}
              >
                Нет
              </button>
            </div>
          </div>
        </div>
      )}

      {showDeleteConfirm !== null && (
        <div className="theme-page__dialog-backdrop" role="dialog" aria-modal="true">
          <div className="theme-page__dialog">
            <p>Удалить этот запрос?</p>
            <div className="theme-page__dialog-actions">
              <button
                type="button"
                className="theme-page__btn-icon--danger"
                onClick={() => handleDeleteQueryConfirm(true)}
              >
                Удалить
              </button>
              <button
                type="button"
                className="theme-page__btn-secondary"
                onClick={() => handleDeleteQueryConfirm(false)}
              >
                Отмена
              </button>
            </div>
          </div>
        </div>
      )}

      {showLeaveConfirm && (
        <div className="theme-page__dialog-backdrop" role="dialog" aria-modal="true">
          <div className="theme-page__dialog">
            <p>Один из запросов был изменён. Сохранить изменения?</p>
            <div className="theme-page__dialog-actions">
              <button
                type="button"
                className="theme-page__suggest-btn"
                onClick={() => handleLeaveConfirm(true)}
              >
                Да
              </button>
              <button
                type="button"
                className="theme-page__btn-secondary"
                onClick={() => handleLeaveConfirm(false)}
              >
                Нет
              </button>
            </div>
          </div>
        </div>
      )}

      <TermEditModal
        isOpen={isModalOpen}
        term={selectedTerm}
        additionalLanguages={additionalLanguages}
        onClose={handleCloseModal}
        onSave={handleSaveTerm}
      />
    </div>
  )
}
