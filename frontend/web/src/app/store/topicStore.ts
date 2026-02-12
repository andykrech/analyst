import { create } from 'zustand'
import type {
  ThemePrepareResponse,
  TermDTO,
  TermTranslationDto,
} from '@/features/topic/api/themesApi'
import { themesApi } from '@/features/topic/api/themesApi'
import type { Term } from '@/shared/types/term'
import {
  type SavedQuery,
  type TermPools,
  type KeywordGroupData,
  createEmptyQuery,
  createTerm as createQueryTerm,
  getDefaultDraft,
} from '@/features/topic/types/queryBuilder'

export type TopicStatus = 'empty' | 'loaded' | 'dirty'

export interface TopicTheme {
  title: string
  description: string
  languages: string[]
  keywords: Term[]
  requiredWords: Term[]
  excludedWords: Term[]
}

function termFromDto(dto: TermDTO, hasAdditionalLangs: boolean): Term {
  return {
    id: crypto.randomUUID(),
    text: (dto.text ?? '').trim(),
    context: (dto.context ?? '').trim(),
    translations: {},
    needsTranslation: hasAdditionalLangs,
  }
}

function termsFromDtos(
  dtos: TermDTO[] | (string | TermDTO)[] | undefined | null,
  hasAdditionalLangs: boolean
): Term[] {
  if (dtos == null) return []
  const seen = new Set<string>()
  const result: Term[] = []
  for (const item of dtos) {
    const dto: TermDTO =
      typeof item === 'string'
        ? { text: item, context: '' }
        : { text: (item as TermDTO)?.text ?? '', context: (item as TermDTO)?.context ?? '' }
    const text = dto.text.trim()
    if (!text) continue
    const lower = text.toLowerCase()
    if (seen.has(lower)) continue
    seen.add(lower)
    result.push(termFromDto(dto, hasAdditionalLangs))
  }
  return result
}

function termsFromStrings(
  items: string[],
  hasAdditionalLangs: boolean
): Term[] {
  return termsFromDtos(
    items.map((s) => ({ text: s, context: '' })),
    hasAdditionalLangs
  )
}

/** Пул терминов + массив запросов: [0]=черновик, [1..3]=сохранённые. */
export interface SearchData {
  keywordTerms: Term[]
  mustTerms: Term[]
  excludeTerms: Term[]
  queries: [SavedQuery, SavedQuery | null, SavedQuery | null, SavedQuery | null]
  isEditingDraft: boolean
  editingQueryIndex: 1 | 2 | 3 | null
}

export interface TopicData {
  theme: TopicTheme
  search: SearchData
  sources: unknown[]
  entities: Record<string, unknown>
  events: Record<string, unknown>
}

export interface TopicUi {
  activeTab: 'theme' | 'sources'
}

const EMPTY_THEME: TopicTheme = {
  title: '',
  description: '',
  languages: [],
  keywords: [],
  requiredWords: [],
  excludedWords: [],
}

function getInitialSearch(): SearchData {
  return {
    keywordTerms: [],
    mustTerms: [],
    excludeTerms: [],
    queries: [
      createEmptyQuery(),
      null,
      null,
      null,
    ],
    isEditingDraft: false,
    editingQueryIndex: null,
  }
}

function createTerm(text: string, hasAdditionalLanguages: boolean): Term {
  return {
    id: crypto.randomUUID(),
    text,
    context: '',
    translations: {},
    needsTranslation: hasAdditionalLanguages,
  }
}

function hasTermWithText(list: Term[], text: string): boolean {
  const lower = text.toLowerCase()
  return list.some((t) => t.text.toLowerCase() === lower)
}

function addTermIfUnique(
  list: Term[],
  text: string,
  hasAdditionalLanguages: boolean
): Term[] {
  const trimmed = text.trim()
  if (!trimmed) return list
  if (hasTermWithText(list, trimmed)) return list
  return [...list, createTerm(trimmed, hasAdditionalLanguages)]
}

function removeTermById(list: Term[], id: string): Term[] {
  return list.filter((t) => t.id !== id)
}

interface TopicStore {
  activeTopicId: string | null
  status: TopicStatus
  data: TopicData
  ui: TopicUi
  aiSuggest: { isLoading: boolean; error: string | null }

  setActiveTab: (tab: 'theme' | 'sources') => void
  applyThemeSuggestions: (payload: ThemePrepareResponse) => void
  suggestThemeFromDescription: () => Promise<void>
  resetToEmptyDraft: () => void
  loadTopicIntoStore: (payload: {
    id?: string
    theme?: Partial<TopicTheme>
    sources?: unknown[]
    entities?: Record<string, unknown>
    events?: Record<string, unknown>
  }) => void
  setThemeTitle: (title: string) => void
  setThemeDescription: (description: string) => void
  setPrimaryLanguage: (code: string) => void
  addAdditionalLanguage: (code: string) => void
  removeAdditionalLanguage: (code: string) => void
  applyTranslations: (
    targetLanguage: string,
    translations: TermTranslationDto[]
  ) => void
  updateThemeTerm: (
    listName: 'keywords' | 'requiredWords' | 'excludedWords',
    termId: string,
    patch: { context?: string; translations?: Record<string, string> }
  ) => void
  addThemeKeyword: (text: string) => void
  removeThemeKeyword: (id: string) => void
  addThemeRequiredWord: (text: string) => void
  removeThemeRequiredWord: (id: string) => void
  addThemeExcludedWord: (text: string) => void
  removeThemeExcludedWord: (id: string) => void

  // Search (конструктор запросов): пулы + 4 слота запросов
  setSearchDraft: (updater: (prev: SavedQuery) => SavedQuery) => void
  setSearchEditingDraft: (value: boolean) => void
  setSearchEditingQueryIndex: (index: 1 | 2 | 3 | null) => void
  saveCurrentQuery: () => void
  newQueryAfterConfirm: (saveChanges: boolean) => void
  startEditingQuery: (index: 1 | 2 | 3) => void
  deleteSavedQuery: (index: 1 | 2 | 3) => void
  addSearchKeyword: (text: string) => void
  addSearchMustTerm: (text: string) => void
  addSearchExcludeTerm: (text: string) => void
  updateSearchTermInPool: (
    pool: 'keyword' | 'must' | 'exclude',
    termId: string,
    patch: { context?: string; translations?: Record<string, string> }
  ) => void
  moveKeywordToGroup: (termId: string, groupIndex: number) => void
  moveKeywordToUnused: (termId: string) => void
  setDraftKeywordGroupOp: (groupIndex: number, op: 'OR' | 'AND') => void
  setDraftConnector: (connectorIndex: number, op: 'OR' | 'AND') => void
  addDraftKeywordGroup: () => void
  removeDraftKeywordGroup: (groupIndex: number) => void
  setDraftMustMode: (mode: 'ALL' | 'ANY') => void
  moveMustToGroup: (termId: string) => void
  moveMustToUnused: (termId: string) => void
  moveExcludeToGroup: (termId: string) => void
  moveExcludeToUnused: (termId: string) => void
  /** Для теста конструктора: заполнить пулы и черновик при загрузке страницы (потом убрать). */
  seedSearchPoolsForTesting: () => void
}

export const useTopicStore = create<TopicStore>((set) => ({
  activeTopicId: null,
  status: 'empty',
  data: {
    theme: { ...EMPTY_THEME },
    search: getInitialSearch(),
    sources: [],
    entities: {},
    events: {},
  },
  ui: {
    activeTab: 'theme',
  },
  aiSuggest: { isLoading: false, error: null },

  setActiveTab: (tab) =>
    set((s) => ({
      ...s,
      ui: { ...s.ui, activeTab: tab },
    })),

  resetToEmptyDraft: () =>
    set({
      activeTopicId: null,
      status: 'empty',
      data: {
        theme: { ...EMPTY_THEME },
        search: getInitialSearch(),
        sources: [],
        entities: {},
        events: {},
      },
      ui: { activeTab: 'theme' },
      aiSuggest: { isLoading: false, error: null },
    }),

  applyThemeSuggestions: (payload) =>
    set((s) => {
      const r = payload.result
      const hasAdditionalLangs = s.data.theme.languages.length > 1
      const keywordTerms = termsFromDtos(r.keywords, hasAdditionalLangs)
      const mustTerms = termsFromDtos(r.must_have, hasAdditionalLangs)
      const excludeTerms = termsFromDtos(r.excludes, hasAdditionalLangs)
      const pools: TermPools = {
        keywordTerms,
        mustTerms,
        excludeTerms,
      }
      const draft = getDefaultDraft(pools)
      return {
        ...s,
        status: 'dirty',
        data: {
          ...s.data,
          theme: {
            ...s.data.theme,
            title: r.title?.trim() ?? s.data.theme.title,
            keywords: keywordTerms,
            requiredWords: mustTerms,
            excludedWords: excludeTerms,
          },
          search: {
            ...s.data.search,
            keywordTerms,
            mustTerms,
            excludeTerms,
            queries: [
              draft,
              s.data.search.queries[1],
              s.data.search.queries[2],
              s.data.search.queries[3],
            ],
            isEditingDraft: false,
            editingQueryIndex: null,
          },
        },
      }
    }),

  suggestThemeFromDescription: async () => {
    const state = useTopicStore.getState()
    const description = state.data.theme.description?.trim() ?? ''
    if (description.length < 3) return

    set((s) => ({
      ...s,
      aiSuggest: { isLoading: true, error: null },
    }))

    try {
      const response = await themesApi.prepare({ user_input: description })
      useTopicStore.getState().applyThemeSuggestions(response)
    } catch (e) {
      const message =
        e instanceof Error ? e.message : 'Ошибка при получении предложений'
      set((s) => ({
        ...s,
        aiSuggest: { isLoading: false, error: message },
      }))
      return
    }

    set((s) => ({
      ...s,
      aiSuggest: { isLoading: false, error: null },
    }))
  },


  loadTopicIntoStore: (payload) => {
    // TODO: Replace with API call for load topic into store
    const toTerms = (v: unknown, hasAdditional: boolean): Term[] => {
      if (Array.isArray(v) && v.every((x) => typeof x === 'string')) {
        return termsFromStrings(v, hasAdditional)
      }
      if (Array.isArray(v)) {
        return (v as Term[]).map((t) => ({
          ...t,
          needsTranslation: t.needsTranslation ?? false,
        }))
      }
      return []
    }
    set((s) => {
      if (!payload.theme) {
        return {
          ...s,
          activeTopicId: payload.id ?? null,
          status: 'loaded',
          data: {
            ...s.data,
            sources: payload.sources ?? s.data.sources,
            entities: payload.entities ?? s.data.entities,
            events: payload.events ?? s.data.events,
          },
        }
      }
      const t = payload.theme as Record<string, unknown>
      const langs = t.languages as string[] | undefined
      const hasAdditional = (langs?.slice(1)?.length ?? 0) > 0
      const keywordTerms = toTerms(t.keywords, hasAdditional)
      const mustTerms = toTerms(t.requiredWords, hasAdditional)
      const excludeTerms = toTerms(t.excludedWords, hasAdditional)
      const theme: TopicTheme = {
        ...EMPTY_THEME,
        ...payload.theme,
        keywords: keywordTerms,
        requiredWords: mustTerms,
        excludedWords: excludeTerms,
      }
      const pools: TermPools = { keywordTerms, mustTerms, excludeTerms }
      const draft =
        keywordTerms.length > 0 || mustTerms.length > 0 || excludeTerms.length > 0
          ? getDefaultDraft(pools)
          : s.data.search.queries[0]
      return {
        ...s,
        activeTopicId: payload.id ?? null,
        status: 'loaded',
        data: {
          ...s.data,
          theme,
          search: {
            ...s.data.search,
            keywordTerms,
            mustTerms,
            excludeTerms,
            queries: [
              draft,
              s.data.search.queries[1],
              s.data.search.queries[2],
              s.data.search.queries[3],
            ],
            isEditingDraft: false,
            editingQueryIndex: null,
          },
          sources: payload.sources ?? s.data.sources,
          entities: payload.entities ?? s.data.entities,
          events: payload.events ?? s.data.events,
        },
      }
    })
  },

  setThemeTitle: (title) =>
    set((s) => ({
      ...s,
      status: 'dirty',
      data: {
        ...s.data,
        theme: { ...s.data.theme, title },
      },
    })),

  setThemeDescription: (description) =>
    set((s) => ({
      ...s,
      status: 'dirty',
      data: {
        ...s.data,
        theme: { ...s.data.theme, description },
      },
    })),

  setPrimaryLanguage: (code) =>
    set((s) => {
      const languages = s.data.theme.languages
      const lower = code.toLowerCase()
      const additional = languages.slice(1).filter((l) => l.toLowerCase() !== lower)
      const newLanguages = [code, ...additional]
      return {
        ...s,
        status: 'dirty',
        data: {
          ...s.data,
          theme: { ...s.data.theme, languages: newLanguages },
        },
      }
    }),

  addAdditionalLanguage: (code) => {
    const lower = code.toLowerCase()
    set((s) => {
      const languages = s.data.theme.languages
      const primary = languages[0]?.toLowerCase()
      if (primary === lower) return s
      if (languages.slice(1).some((l) => l.toLowerCase() === lower)) return s
      return {
        ...s,
        status: 'dirty',
        data: {
          ...s.data,
          theme: {
            ...s.data.theme,
            languages: [...languages, code],
          },
        },
      }
    })
  },

  removeAdditionalLanguage: (code) =>
    set((s) => {
      const languages = s.data.theme.languages
      const lower = code.toLowerCase()
      const additional = languages.slice(1).filter((l) => l.toLowerCase() !== lower)
      const newLanguages = languages[0] ? [languages[0], ...additional] : []
      return {
        ...s,
        status: 'dirty',
        data: {
          ...s.data,
          theme: { ...s.data.theme, languages: newLanguages },
        },
      }
    }),

  applyTranslations: (targetLanguage, translations) =>
    set((s) => {
      const theme = s.data.theme
      const additionalLangs = theme.languages.slice(1)
      if (additionalLangs.length === 0) return s

      const map = new Map<string, string>()
      for (const t of translations) {
        if (t.id && t.translation) {
          map.set(t.id, t.translation)
        }
      }
      if (map.size === 0) return s

      const updateList = (list: Term[]): Term[] =>
        list.map((term) => {
          const translated = map.get(term.id)
          if (!translated) return term
          const translationsForTerm = {
            ...term.translations,
            [targetLanguage]: translated,
          }
          const hasAllTranslations =
            additionalLangs.length > 0 &&
            additionalLangs.every((lang) => {
              const v = translationsForTerm[lang]
              return typeof v === 'string' && v.trim().length > 0
            })

          return {
            ...term,
            translations: translationsForTerm,
            needsTranslation: !hasAllTranslations,
          }
        })

      const search = s.data.search
      return {
        ...s,
        status: 'dirty',
        data: {
          ...s.data,
          theme: {
            ...theme,
            keywords: updateList(theme.keywords),
            requiredWords: updateList(theme.requiredWords),
            excludedWords: updateList(theme.excludedWords),
          },
          search: {
            ...search,
            keywordTerms: updateList(search.keywordTerms),
            mustTerms: updateList(search.mustTerms),
            excludeTerms: updateList(search.excludeTerms),
          },
        },
      }
    }),

  updateThemeTerm: (listName, termId, patch) =>
    set((s) => {
      const list = s.data.theme[listName]
      const idx = list.findIndex((t) => t.id === termId)
      if (idx < 0) return s
      const term = list[idx]
      const hasAdditional = s.data.theme.languages.slice(1).length > 0
      const contextChanged =
        (patch.context ?? term.context) !== term.context
      const needsTranslation =
        term.needsTranslation ||
        (contextChanged && hasAdditional)
      const updated: Term = {
        ...term,
        ...patch,
        context: patch.context ?? term.context,
        translations: patch.translations ?? term.translations,
        needsTranslation,
      }
      const newList = [...list]
      newList[idx] = updated
      return {
        ...s,
        status: 'dirty',
        data: {
          ...s.data,
          theme: { ...s.data.theme, [listName]: newList },
        },
      }
    }),

  addThemeKeyword: (text) =>
    set((s) => {
      const hasAdditional = s.data.theme.languages.slice(1).length > 0
      return {
        ...s,
        status: 'dirty',
        data: {
          ...s.data,
          theme: {
            ...s.data.theme,
            keywords: addTermIfUnique(
              s.data.theme.keywords,
              text,
              hasAdditional
            ),
          },
        },
      }
    }),

  removeThemeKeyword: (id) =>
    set((s) => ({
      ...s,
      status: 'dirty',
      data: {
        ...s.data,
        theme: {
          ...s.data.theme,
          keywords: removeTermById(s.data.theme.keywords, id),
        },
      },
    })),

  addThemeRequiredWord: (text) =>
    set((s) => {
      const hasAdditional = s.data.theme.languages.slice(1).length > 0
      return {
        ...s,
        status: 'dirty',
        data: {
          ...s.data,
          theme: {
            ...s.data.theme,
            requiredWords: addTermIfUnique(
              s.data.theme.requiredWords,
              text,
              hasAdditional
            ),
          },
        },
      }
    }),

  removeThemeRequiredWord: (id) =>
    set((s) => ({
      ...s,
      status: 'dirty',
      data: {
        ...s.data,
        theme: {
          ...s.data.theme,
          requiredWords: removeTermById(s.data.theme.requiredWords, id),
        },
      },
    })),

  addThemeExcludedWord: (text) =>
    set((s) => {
      const hasAdditional = s.data.theme.languages.slice(1).length > 0
      return {
        ...s,
        status: 'dirty',
        data: {
          ...s.data,
          theme: {
            ...s.data.theme,
            excludedWords: addTermIfUnique(
              s.data.theme.excludedWords,
              text,
              hasAdditional
            ),
          },
        },
      }
    }),

  removeThemeExcludedWord: (id) =>
    set((s) => ({
      ...s,
      status: 'dirty',
      data: {
        ...s.data,
        theme: {
          ...s.data.theme,
          excludedWords: removeTermById(s.data.theme.excludedWords, id),
        },
      },
    })),

  setSearchDraft: (updater) =>
    set((s) => {
      const search = s.data.search
      const nextDraft = updater(search.queries[0])
      const isEditing = search.editingQueryIndex !== null
      return {
        ...s,
        status: 'dirty',
        data: {
          ...s.data,
          search: {
            ...search,
            queries: [nextDraft, search.queries[1], search.queries[2], search.queries[3]],
            isEditingDraft: isEditing ? true : search.isEditingDraft,
          },
        },
      }
    }),

  setSearchEditingDraft: (value) =>
    set((s) => ({
      ...s,
      data: {
        ...s.data,
        search: { ...s.data.search, isEditingDraft: value },
      },
    })),

  setSearchEditingQueryIndex: (index) =>
    set((s) => ({
      ...s,
      data: {
        ...s.data,
        search: { ...s.data.search, editingQueryIndex: index },
      },
    })),

  saveCurrentQuery: () =>
    set((s) => {
      const search = s.data.search
      const draft = search.queries[0]
      let targetIndex: 1 | 2 | 3
      const wasEditingSaved = search.editingQueryIndex !== null
      if (wasEditingSaved) {
        targetIndex = search.editingQueryIndex
      } else {
        const firstFree = ([1, 2, 3] as const).find((i) => search.queries[i] === null)
        if (firstFree === undefined) return s
        targetIndex = firstFree
      }
      const next = [...search.queries] as SearchData['queries']
      next[targetIndex] = JSON.parse(JSON.stringify(draft))
      return {
        ...s,
        status: 'dirty',
        data: {
          ...s.data,
          search: {
            ...search,
            queries: next,
            isEditingDraft: false,
            editingQueryIndex: wasEditingSaved ? search.editingQueryIndex : targetIndex,
          },
        },
      }
    }),

  newQueryAfterConfirm: (saveChanges) =>
    set((s) => {
      const search = s.data.search
      let nextQueries = search.queries
      if (saveChanges && search.editingQueryIndex !== null) {
        const draft = search.queries[0]
        nextQueries = [...search.queries] as SearchData['queries']
        nextQueries[search.editingQueryIndex] = { ...draft }
      }
      const pools: TermPools = {
        keywordTerms: search.keywordTerms,
        mustTerms: search.mustTerms,
        excludeTerms: search.excludeTerms,
      }
      const defaultDraft = getDefaultDraft(pools)
      return {
        ...s,
        status: 'dirty',
        data: {
          ...s.data,
          search: {
            ...search,
            queries: [defaultDraft, nextQueries[1], nextQueries[2], nextQueries[3]],
            isEditingDraft: false,
            editingQueryIndex: null,
          },
        },
      }
    }),

  startEditingQuery: (index) =>
    set((s) => {
      const q = s.data.search.queries[index]
      if (q === null) return s
      const next = [...s.data.search.queries] as SearchData['queries']
      next[0] = JSON.parse(JSON.stringify(q))
      return {
        ...s,
        data: {
          ...s.data,
          search: {
            ...s.data.search,
            queries: next,
            editingQueryIndex: index,
            isEditingDraft: false,
          },
        },
      }
    }),

  deleteSavedQuery: (index) =>
    set((s) => {
      const search = s.data.search
      const next: SearchData['queries'] = [
        search.queries[0],
        null,
        null,
        null,
      ]
      let j = 1
      for (let i = 1; i <= 3; i++) {
        if (i !== index && search.queries[i] !== null) {
          next[j] = search.queries[i]
          j++
        }
      }
      const newEditing =
        search.editingQueryIndex === index
          ? null
          : search.editingQueryIndex === null
            ? null
            : search.editingQueryIndex > index
              ? ((search.editingQueryIndex - 1) as 1 | 2 | 3)
              : search.editingQueryIndex
      return {
        ...s,
        status: 'dirty',
        data: {
          ...s.data,
          search: {
            ...search,
            queries: next,
            editingQueryIndex: newEditing,
          },
        },
      }
    }),

  addSearchKeyword: (text) =>
    set((s) => {
      const trimmed = text.trim()
      if (!trimmed) return s
      const hasAdditional = s.data.theme.languages.length > 1
      const list = s.data.search.keywordTerms
      if (list.some((t) => t.text.toLowerCase() === trimmed.toLowerCase())) return s
      const term = createQueryTerm(trimmed)
      if (hasAdditional) term.needsTranslation = true
      return {
        ...s,
        status: 'dirty',
        data: {
          ...s.data,
          search: {
            ...s.data.search,
            keywordTerms: [...list, term],
          },
        },
      }
    }),

  addSearchMustTerm: (text) =>
    set((s) => {
      const trimmed = text.trim()
      if (!trimmed) return s
      const hasAdditional = s.data.theme.languages.length > 1
      const list = s.data.search.mustTerms
      if (list.some((t) => t.text.toLowerCase() === trimmed.toLowerCase())) return s
      const term = createQueryTerm(trimmed)
      if (hasAdditional) term.needsTranslation = true
      return {
        ...s,
        status: 'dirty',
        data: {
          ...s.data,
          search: {
            ...s.data.search,
            mustTerms: [...list, term],
          },
        },
      }
    }),

  addSearchExcludeTerm: (text) =>
    set((s) => {
      const trimmed = text.trim()
      if (!trimmed) return s
      const hasAdditional = s.data.theme.languages.length > 1
      const list = s.data.search.excludeTerms
      if (list.some((t) => t.text.toLowerCase() === trimmed.toLowerCase())) return s
      const term = createQueryTerm(trimmed)
      if (hasAdditional) term.needsTranslation = true
      return {
        ...s,
        status: 'dirty',
        data: {
          ...s.data,
          search: {
            ...s.data.search,
            excludeTerms: [...list, term],
          },
        },
      }
    }),

  updateSearchTermInPool: (pool, termId, patch) =>
    set((s) => {
      const key =
        pool === 'keyword'
          ? 'keywordTerms'
          : pool === 'must'
            ? 'mustTerms'
            : 'excludeTerms'
      const list = s.data.search[key]
      const idx = list.findIndex((t) => t.id === termId)
      if (idx < 0) return s
      const term = list[idx]
      const hasAdditional = s.data.theme.languages.slice(1).length > 0
      const contextChanged = (patch.context ?? term.context) !== term.context
      const needsTranslation =
        term.needsTranslation || (contextChanged && hasAdditional)
      const updated: Term = {
        ...term,
        ...patch,
        context: patch.context ?? term.context,
        translations: patch.translations ?? term.translations,
        needsTranslation,
      }
      const newList = [...list]
      newList[idx] = updated
      return {
        ...s,
        status: 'dirty',
        data: {
          ...s.data,
          search: { ...s.data.search, [key]: newList },
        },
      }
    }),

  moveKeywordToGroup: (termId, groupIndex) =>
    set((s) => {
      const draft = s.data.search.queries[0]
      if (groupIndex < 0 || groupIndex >= draft.keywords.groups.length) return s
      const groups = draft.keywords.groups.map((g) => ({
        ...g,
        termIds: g.termIds.filter((id) => id !== termId),
      }))
      groups[groupIndex] = {
        ...groups[groupIndex],
        termIds: [...groups[groupIndex].termIds, termId],
      }
      const search = s.data.search
      return {
        ...s,
        status: 'dirty',
        data: {
          ...s.data,
          search: {
            ...search,
            queries: [
              {
                ...draft,
                keywords: {
                  ...draft.keywords,
                  groups,
                },
              },
              search.queries[1],
              search.queries[2],
              search.queries[3],
            ],
            isEditingDraft: search.editingQueryIndex !== null ? true : search.isEditingDraft,
          },
        },
      }
    }),

  moveKeywordToUnused: (termId) =>
    set((s) => {
      const draft = s.data.search.queries[0]
      const groups = draft.keywords.groups.map((g) => ({
        ...g,
        termIds: g.termIds.filter((id) => id !== termId),
      }))
      const connectors =
        groups.length <= 1
          ? []
          : draft.keywords.connectors.slice(0, groups.length - 1)
      const search = s.data.search
      return {
        ...s,
        status: 'dirty',
        data: {
          ...s.data,
          search: {
            ...search,
            queries: [
              {
                ...draft,
                keywords: { groups, connectors },
              },
              search.queries[1],
              search.queries[2],
              search.queries[3],
            ],
            isEditingDraft: search.editingQueryIndex !== null ? true : search.isEditingDraft,
          },
        },
      }
    }),

  setDraftKeywordGroupOp: (groupIndex, op) =>
    set((s) => {
      const draft = s.data.search.queries[0]
      const search = s.data.search
      const groups = draft.keywords.groups.map((g, i) =>
        i === groupIndex ? { ...g, op } : g
      )
      return {
        ...s,
        status: 'dirty',
        data: {
          ...s.data,
          search: {
            ...search,
            queries: [
              {
                ...draft,
                keywords: { ...draft.keywords, groups },
              },
              search.queries[1],
              search.queries[2],
              search.queries[3],
            ],
            isEditingDraft: search.editingQueryIndex !== null ? true : search.isEditingDraft,
          },
        },
      }
    }),

  setDraftConnector: (connectorIndex, op) =>
    set((s) => {
      const draft = s.data.search.queries[0]
      const search = s.data.search
      const connectors = draft.keywords.connectors.map((c, i) =>
        i === connectorIndex ? op : c
      )
      return {
        ...s,
        status: 'dirty',
        data: {
          ...s.data,
          search: {
            ...search,
            queries: [
              {
                ...draft,
                keywords: { ...draft.keywords, connectors },
              },
              search.queries[1],
              search.queries[2],
              search.queries[3],
            ],
            isEditingDraft: search.editingQueryIndex !== null ? true : search.isEditingDraft,
          },
        },
      }
    }),

  addDraftKeywordGroup: () =>
    set((s) => {
      const draft = s.data.search.queries[0]
      const search = s.data.search
      const newGroup: KeywordGroupData = {
        id: crypto.randomUUID(),
        op: 'OR',
        termIds: [],
      }
      const groups = [...draft.keywords.groups, newGroup]
      const connectors =
        draft.keywords.connectors.length === groups.length - 1
          ? [...draft.keywords.connectors, 'AND']
          : [...draft.keywords.connectors, 'AND']
      return {
        ...s,
        status: 'dirty',
        data: {
          ...s.data,
          search: {
            ...search,
            queries: [
              {
                ...draft,
                keywords: { groups, connectors },
              },
              search.queries[1],
              search.queries[2],
              search.queries[3],
            ],
            isEditingDraft: search.editingQueryIndex !== null ? true : search.isEditingDraft,
          },
        },
      }
    }),

  removeDraftKeywordGroup: (groupIndex) =>
    set((s) => {
      const draft = s.data.search.queries[0]
      if (draft.keywords.groups.length <= 1) return s
      const groups = draft.keywords.groups.filter((_, i) => i !== groupIndex)
      const connectors =
        groupIndex === 0
          ? draft.keywords.connectors.slice(1)
          : [
              ...draft.keywords.connectors.slice(0, groupIndex - 1),
              ...draft.keywords.connectors.slice(groupIndex),
            ]
      const movedTermIds = draft.keywords.groups[groupIndex]?.termIds ?? []
      const nextDraft = { ...draft, keywords: { groups, connectors } }
      if (movedTermIds.length > 0 && groups.length > 0) {
        nextDraft.keywords.groups[0] = {
          ...nextDraft.keywords.groups[0],
          termIds: [
            ...nextDraft.keywords.groups[0].termIds,
            ...movedTermIds,
          ],
        }
      }
      const search = s.data.search
      return {
        ...s,
        status: 'dirty',
        data: {
          ...s.data,
          search: {
            ...search,
            queries: [
              nextDraft,
              search.queries[1],
              search.queries[2],
              search.queries[3],
            ],
            isEditingDraft: search.editingQueryIndex !== null ? true : search.isEditingDraft,
          },
        },
      }
    }),

  setDraftMustMode: (mode) =>
    set((s) => {
      const search = s.data.search
      return {
        ...s,
        status: 'dirty',
        data: {
          ...s.data,
          search: {
            ...search,
            queries: [
              { ...search.queries[0], must: { ...search.queries[0].must, mode } },
              search.queries[1],
              search.queries[2],
              search.queries[3],
            ],
            isEditingDraft: search.editingQueryIndex !== null ? true : search.isEditingDraft,
          },
        },
      }
    }),

  moveMustToGroup: (termId) =>
    set((s) => {
      const draft = s.data.search.queries[0]
      const search = s.data.search
      const ids = draft.must.termIds.includes(termId)
        ? draft.must.termIds
        : [...draft.must.termIds, termId]
      return {
        ...s,
        status: 'dirty',
        data: {
          ...s.data,
          search: {
            ...search,
            queries: [
              { ...draft, must: { ...draft.must, termIds: ids } },
              search.queries[1],
              search.queries[2],
              search.queries[3],
            ],
            isEditingDraft: search.editingQueryIndex !== null ? true : search.isEditingDraft,
          },
        },
      }
    }),

  moveMustToUnused: (termId) =>
    set((s) => {
      const draft = s.data.search.queries[0]
      const search = s.data.search
      const ids = draft.must.termIds.filter((id) => id !== termId)
      return {
        ...s,
        status: 'dirty',
        data: {
          ...s.data,
          search: {
            ...search,
            queries: [
              { ...draft, must: { ...draft.must, termIds: ids } },
              search.queries[1],
              search.queries[2],
              search.queries[3],
            ],
            isEditingDraft: search.editingQueryIndex !== null ? true : search.isEditingDraft,
          },
        },
      }
    }),

  moveExcludeToGroup: (termId) =>
    set((s) => {
      const draft = s.data.search.queries[0]
      const search = s.data.search
      const ids = draft.exclude.termIds.includes(termId)
        ? draft.exclude.termIds
        : [...draft.exclude.termIds, termId]
      return {
        ...s,
        status: 'dirty',
        data: {
          ...s.data,
          search: {
            ...search,
            queries: [
              { ...draft, exclude: { ...draft.exclude, termIds: ids } },
              search.queries[1],
              search.queries[2],
              search.queries[3],
            ],
            isEditingDraft: search.editingQueryIndex !== null ? true : search.isEditingDraft,
          },
        },
      }
    }),

  moveExcludeToUnused: (termId) =>
    set((s) => {
      const draft = s.data.search.queries[0]
      const search = s.data.search
      const ids = draft.exclude.termIds.filter((id) => id !== termId)
      return {
        ...s,
        status: 'dirty',
        data: {
          ...s.data,
          search: {
            ...search,
            queries: [
              { ...draft, exclude: { termIds: ids } },
              search.queries[1],
              search.queries[2],
              search.queries[3],
            ],
            isEditingDraft: search.editingQueryIndex !== null ? true : search.isEditingDraft,
          },
        },
      }
    }),

  seedSearchPoolsForTesting: () =>
    set((s) => {
      const search = s.data.search
      if (
        search.keywordTerms.length > 0 ||
        search.mustTerms.length > 0 ||
        search.excludeTerms.length > 0
      ) {
        return s
      }
      const keywordTerms = [
        'ультразвук',
        'акустическая эмиссия',
        'пластическая деформация',
        'повреждённость',
        'контроль качества',
        'дефектоскопия',
        'напряжение',
        'трещина',
        'металлоконструкция',
        'диагностика',
      ].map((text) => createQueryTerm(text))
      const mustTerms = ['норматив', 'безопасность', 'стандарт'].map((text) =>
        createQueryTerm(text)
      )
      const excludeTerms = ['реклама', 'вакансия', 'курс'].map((text) =>
        createQueryTerm(text)
      )
      const pools: TermPools = {
        keywordTerms,
        mustTerms,
        excludeTerms,
      }
      const draft = getDefaultDraft(pools)
      return {
        ...s,
        data: {
          ...s.data,
          search: {
            ...search,
            keywordTerms,
            mustTerms,
            excludeTerms,
            queries: [
              draft,
              search.queries[1],
              search.queries[2],
              search.queries[3],
            ],
          },
        },
      }
    }),
}))
