import { create } from 'zustand'
import type {
  ThemeGetResponseDto,
  ThemeGetTermDto,
  ThemeListItemDto,
  ThemePrepareResponse,
  TermDTO,
  TermTranslationDto,
} from '@/features/topic/api/themesApi'
import type {
  RecommendedSiteItem,
  ThemeSiteDto,
  ThemeSiteMode,
  ThemeSiteStatus,
  ThemeSiteUpdateRequest,
} from '@/features/source/api/dto'
import {
  listThemeSources,
  createThemeSource,
  updateThemeSource,
  deleteThemeSource,
  recommendSources as recommendSourcesApi,
} from '@/features/source/api/sourceApi'
import { normalizeDomain } from '@/features/source/utils/normalizeDomain'
import { themesApi } from '@/features/topic/api/themesApi'
import type { Term } from '@/shared/types/term'
import {
  type GroupOp,
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

export interface TopicSourcesEditorForm {
  domain: string
  mode: 'include' | 'exclude' | 'prefer'
  status: 'active' | 'muted' | 'pending_review'
  display_name: string
  description: string
  homepage_url: string
  trust_score: string
  quality_tier: string
}

export interface TopicSourcesData {
  itemsById: Record<string, ThemeSiteDto>
  order: string[]
  selectedId: string | null
  isLoading: boolean
  error: string | null
  editor: {
    isOpen: boolean
    mode: 'create' | 'edit'
    themeSiteId: string | null
    form: TopicSourcesEditorForm
  }
}

export interface TopicData {
  theme: TopicTheme
  search: SearchData
  sources: unknown[]
  siteSources: TopicSourcesData
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

const EMPTY_SITE_SOURCES_FORM: TopicSourcesEditorForm = {
  domain: '',
  mode: 'include',
  status: 'active',
  display_name: '',
  description: '',
  homepage_url: '',
  trust_score: '',
  quality_tier: '',
}

function getInitialSiteSources(): TopicSourcesData {
  return {
    itemsById: {},
    order: [],
    selectedId: null,
    isLoading: false,
    error: null,
    editor: {
      isOpen: false,
      mode: 'create',
      themeSiteId: null,
      form: { ...EMPTY_SITE_SOURCES_FORM },
    },
  }
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
  /** Рекомендация источников по теме (ИИ). */
  sourcesRecommend: {
    isLoading: boolean
    error: string | null
    lastResult: RecommendedSiteItem[] | null
  }
  /** Список тем для навигации (заполняется провайдером TopicsNavProvider). */
  themesForNav: ThemeListItemDto[]

  setActiveTab: (tab: 'theme' | 'sources') => void
  setThemesForNav: (themes: ThemeListItemDto[]) => void
  applyThemeSuggestions: (payload: ThemePrepareResponse) => void
  suggestThemeFromDescription: () => Promise<void>
  resetToEmptyDraft: () => void
  loadTopicIntoStore: (payload: {
    id?: string
    theme?: Partial<TopicTheme>
    searchQueries?: [SavedQuery | null, SavedQuery | null, SavedQuery | null]
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
  /** Загрузить тему из ответа GET /themes/:id в стор. */
  loadThemeFromApi: (response: ThemeGetResponseDto) => void
  /** Сбросить статус на 'loaded' (например, после успешного сохранения). */
  setStatusLoaded: () => void

  // Site sources (theme_sites)
  loadSources: () => Promise<void>
  selectSource: (themeSiteId: string | null) => void
  openCreateSource: () => void
  openEditSource: (themeSiteId: string) => void
  closeSourceEditor: () => void
  setSourceEditorField: (
    key: keyof TopicSourcesEditorForm,
    value: string
  ) => void
  createSourceFromEditor: () => Promise<void>
  saveSourceEditor: () => Promise<void>
  muteSource: (themeSiteId: string) => Promise<void>
  unmuteSource: (themeSiteId: string) => Promise<void>
  updateSourceModeStatus: (
    themeSiteId: string,
    payload: { mode?: ThemeSiteMode; status?: ThemeSiteStatus }
  ) => Promise<void>
  clearSiteSourcesError: () => void
  recommendSources: () => Promise<void>
  clearSourcesRecommendError: () => void
  addRecommendedSource: (item: RecommendedSiteItem) => Promise<void>
}

export const useTopicStore = create<TopicStore>((set) => ({
  activeTopicId: null,
  status: 'empty',
  data: {
    theme: { ...EMPTY_THEME },
    search: getInitialSearch(),
    sources: [],
    siteSources: getInitialSiteSources(),
    entities: {},
    events: {},
  },
  ui: {
    activeTab: 'theme',
  },
  aiSuggest: { isLoading: false, error: null },
  sourcesRecommend: { isLoading: false, error: null, lastResult: null },
  themesForNav: [],

  setThemesForNav: (themes) => set({ themesForNav: themes }),

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
        siteSources: getInitialSiteSources(),
        entities: {},
        events: {},
      },
      ui: { activeTab: 'theme' },
      aiSuggest: { isLoading: false, error: null },
      sourcesRecommend: { isLoading: false, error: null, lastResult: null },
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
            siteSources: s.data.siteSources,
            entities: payload.entities ?? s.data.entities,
            events: payload.events ?? s.data.events,
          },
        }
      }
      const t = payload.theme as Record<string, unknown>
      const langs = t.languages as string[] | undefined
      const hasAdditional = (langs?.slice(1)?.length ?? 0) > 0
      const keywordTerms = toTerms(t.keywords, hasAdditional)
      const mustTerms = toTerms(t.requiredWords ?? t.must_have, hasAdditional)
      const excludeTerms = toTerms(t.excludedWords ?? t.exclude, hasAdditional)
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
      const savedSlots = payload.searchQueries ?? [
        s.data.search.queries[1],
        s.data.search.queries[2],
        s.data.search.queries[3],
      ]
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
              savedSlots[0] ?? null,
              savedSlots[1] ?? null,
              savedSlots[2] ?? null,
            ],
            isEditingDraft: false,
            editingQueryIndex: null,
          },
          sources: payload.sources ?? s.data.sources,
          siteSources: s.data.siteSources,
          entities: payload.entities ?? s.data.entities,
          events: payload.events ?? s.data.events,
        },
      }
    })
  },

  loadThemeFromApi: (response) => {
    const theme = response.theme
    const additionalLangs = theme.languages?.slice(1) ?? []
    const toTerm = (dto: ThemeGetTermDto): Term => {
      const translations = dto.translations ?? {}
      const hasAllTranslations =
        additionalLangs.length === 0 ||
        additionalLangs.every(
          (lang) => typeof translations[lang] === 'string' && translations[lang].trim().length > 0
        )
      return {
        id: dto.id,
        text: dto.text,
        context: dto.context ?? '',
        translations,
        needsTranslation: !hasAllTranslations,
      }
    }
    const searchQueries: [SavedQuery | null, SavedQuery | null, SavedQuery | null] = [
      null,
      null,
      null,
    ]
    for (const q of response.search_queries) {
      if (q.order_index >= 1 && q.order_index <= 3 && q.query_model) {
        searchQueries[q.order_index - 1] = {
          keywords: q.query_model.keywords ?? { groups: [], connectors: [] },
          must: q.query_model.must ?? { mode: 'ALL', termIds: [] },
          exclude: q.query_model.exclude ?? { termIds: [] },
        }
      }
    }
    useTopicStore.getState().loadTopicIntoStore({
      id: theme.id,
      theme: {
        title: theme.title,
        description: theme.description,
        languages: theme.languages ?? [],
        keywords: theme.keywords.map(toTerm),
        requiredWords: theme.must_have.map(toTerm),
        excludedWords: theme.exclude.map(toTerm),
      },
      searchQueries,
    })
  },

  setStatusLoaded: () => set((s) => ({ ...s, status: 'loaded' as const })),

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
      const idx = search.editingQueryIndex
      const wasEditingSaved = idx !== null
      if (wasEditingSaved && idx != null) {
        targetIndex = idx
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
      const connectors: GroupOp[] =
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

  loadSources: async () => {
    const state = useTopicStore.getState()
    const themeId = state.activeTopicId
    if (!themeId) return

    set((s) => ({
      ...s,
      data: {
        ...s.data,
        siteSources: {
          ...s.data.siteSources,
          isLoading: true,
          error: null,
        },
      },
    }))

    try {
      const list = await listThemeSources(themeId)
      const sorted = [...list].sort((a, b) => {
        const na =
          (a.site.effective_display_name ?? a.site.domain ?? '').toLowerCase()
        const nb =
          (b.site.effective_display_name ?? b.site.domain ?? '').toLowerCase()
        return na.localeCompare(nb)
      })
      const itemsById: Record<string, ThemeSiteDto> = {}
      const order: string[] = []
      for (const dto of sorted) {
        itemsById[dto.id] = dto
        order.push(dto.id)
      }

      const prev = useTopicStore.getState().data.siteSources
      const selectedId =
        prev.selectedId && itemsById[prev.selectedId]
          ? prev.selectedId
          : order[0] ?? null

      set((s) => ({
        ...s,
        data: {
          ...s.data,
          siteSources: {
            ...s.data.siteSources,
            itemsById,
            order,
            selectedId,
            isLoading: false,
            error: null,
          },
        },
      }))
    } catch (e) {
      const msg = e instanceof Error ? e.message : 'Ошибка загрузки источников'
      set((s) => ({
        ...s,
        data: {
          ...s.data,
          siteSources: {
            ...s.data.siteSources,
            isLoading: false,
            error: msg,
          },
        },
      }))
    }
  },

  selectSource: (themeSiteId) =>
    set((s) => ({
      ...s,
      data: {
        ...s.data,
        siteSources: {
          ...s.data.siteSources,
          selectedId: themeSiteId,
        },
      },
    })),

  openCreateSource: () =>
    set((s) => ({
      ...s,
      data: {
        ...s.data,
        siteSources: {
          ...s.data.siteSources,
          error: null,
          editor: {
            isOpen: true,
            mode: 'create',
            themeSiteId: null,
            form: { ...EMPTY_SITE_SOURCES_FORM },
          },
        },
      },
    })),

  openEditSource: (themeSiteId) => {
    const state = useTopicStore.getState()
    const dto = state.data.siteSources.itemsById[themeSiteId]
    if (!dto) return

    set((s) => ({
      ...s,
      data: {
        ...s.data,
        siteSources: {
          ...s.data.siteSources,
          error: null,
          editor: {
            isOpen: true,
            mode: 'edit',
            themeSiteId,
            form: {
              domain: dto.site.domain ?? '',
              mode: dto.mode,
              status: dto.status,
              display_name: dto.site.effective_display_name ?? '',
              description: dto.site.effective_description ?? '',
              homepage_url: dto.site.effective_homepage_url ?? '',
              trust_score:
                dto.site.effective_trust_score != null
                  ? String(dto.site.effective_trust_score)
                  : '',
              quality_tier:
                dto.site.effective_quality_tier != null
                  ? String(dto.site.effective_quality_tier)
                  : '',
            },
          },
        },
      },
    }))
  },

  closeSourceEditor: () =>
    set((s) => ({
      ...s,
      data: {
        ...s.data,
        siteSources: {
          ...s.data.siteSources,
          editor: {
            ...s.data.siteSources.editor,
            isOpen: false,
          },
        },
      },
    })),

  setSourceEditorField: (key, value) =>
    set((s) => ({
      ...s,
      data: {
        ...s.data,
        siteSources: {
          ...s.data.siteSources,
          editor: {
            ...s.data.siteSources.editor,
            form: {
              ...s.data.siteSources.editor.form,
              [key]: value,
            },
          },
        },
      },
    })),

  createSourceFromEditor: async () => {
    const state = useTopicStore.getState()
    const themeId = state.activeTopicId
    const editor = state.data.siteSources.editor
    const items = state.data.siteSources.itemsById

    if (!themeId) return

    const norm = normalizeDomain(editor.form.domain)
    if (!norm) {
      set((s) => ({
        ...s,
        data: {
          ...s.data,
          siteSources: {
            ...s.data.siteSources,
            error: 'Некорректный домен или URL',
          },
        },
      }))
      return
    }

    for (const dto of Object.values(items)) {
      if (dto.status === 'muted') continue
      const existingNorm = normalizeDomain(dto.site.domain)
      if (existingNorm && existingNorm === norm) {
        set((s) => ({
          ...s,
          data: {
            ...s.data,
            siteSources: {
              ...s.data.siteSources,
              error: 'Этот источник уже добавлен в тему',
            },
          },
        }))
        return
      }
    }

    try {
      const payload = {
        domain: editor.form.domain.trim(),
        mode: editor.form.mode,
        status: editor.form.status,
        display_name: editor.form.display_name.trim() || undefined,
        description: editor.form.description.trim() || undefined,
        homepage_url: editor.form.homepage_url.trim() || undefined,
        trust_score: parseFloat(editor.form.trust_score) || undefined,
        quality_tier: parseInt(editor.form.quality_tier, 10) || undefined,
      }
      const dto = await createThemeSource(themeId, payload)

      set((s) => {
        const by = { ...s.data.siteSources.itemsById, [dto.id]: dto }
        const order = s.data.siteSources.order.includes(dto.id)
          ? s.data.siteSources.order
          : [...s.data.siteSources.order, dto.id].sort((ia, ib) => {
              const a = by[ia]?.site.effective_display_name ?? by[ia]?.site.domain ?? ''
              const b = by[ib]?.site.effective_display_name ?? by[ib]?.site.domain ?? ''
              return a.localeCompare(b)
            })
        return {
          ...s,
          data: {
            ...s.data,
            siteSources: {
              ...s.data.siteSources,
              itemsById: by,
              order,
              selectedId: dto.id,
              error: null,
              editor: { ...s.data.siteSources.editor, isOpen: false },
            },
          },
        }
      })
    } catch (e) {
      const apiErr = e as { status?: number; message?: string }
      const is409 = apiErr?.status === 409
      const msg = is409
        ? 'Этот источник уже добавлен в тему'
        : (apiErr.message ?? 'Ошибка при добавлении источника')

      set((s) => ({
        ...s,
        data: {
          ...s.data,
          siteSources: {
            ...s.data.siteSources,
            error: msg,
          },
        },
      }))
    }
  },

  saveSourceEditor: async () => {
    const state = useTopicStore.getState()
    const themeId = state.activeTopicId
    const editor = state.data.siteSources.editor
    const dto = editor.themeSiteId
      ? state.data.siteSources.itemsById[editor.themeSiteId]
      : null

    if (!themeId || !dto) return

    try {
      const payload: ThemeSiteUpdateRequest = {
        mode: editor.form.mode,
        status: editor.form.status,
        display_name: editor.form.display_name.trim() || undefined,
        description: editor.form.description.trim() || undefined,
        homepage_url: editor.form.homepage_url.trim() || undefined,
        trust_score: parseFloat(editor.form.trust_score) || undefined,
        quality_tier: parseInt(editor.form.quality_tier, 10) || undefined,
      }
      const updated = await updateThemeSource(themeId, dto.site_id, payload)

      set((s) => {
        const by = { ...s.data.siteSources.itemsById, [updated.id]: updated }
        return {
          ...s,
          data: {
            ...s.data,
            siteSources: {
              ...s.data.siteSources,
              itemsById: by,
              error: null,
              editor: { ...s.data.siteSources.editor, isOpen: false },
            },
          },
        }
      })
    } catch (e) {
      const msg =
        e instanceof Error ? e.message : 'Ошибка при сохранении'
      set((s) => ({
        ...s,
        data: {
          ...s.data,
          siteSources: {
            ...s.data.siteSources,
            error: msg,
          },
        },
      }))
    }
  },

  muteSource: async (themeSiteId) => {
    const state = useTopicStore.getState()
    const themeId = state.activeTopicId
    const dto = state.data.siteSources.itemsById[themeSiteId]
    if (!themeId || !dto) return

    try {
      await deleteThemeSource(themeId, dto.site_id)
      const wasSelected = useTopicStore.getState().data.siteSources.selectedId === themeSiteId
      await useTopicStore.getState().loadSources()
      if (wasSelected) {
        set((s) => ({
          ...s,
          data: {
            ...s.data,
            siteSources: {
              ...s.data.siteSources,
              selectedId: null,
            },
          },
        }))
      }
    } catch (e) {
      const msg = e instanceof Error ? e.message : 'Ошибка при выключении'
      set((s) => ({
        ...s,
        data: {
          ...s.data,
          siteSources: {
            ...s.data.siteSources,
            error: msg,
          },
        },
      }))
    }
  },

  unmuteSource: async (themeSiteId) => {
    const state = useTopicStore.getState()
    const themeId = state.activeTopicId
    const dto = state.data.siteSources.itemsById[themeSiteId]
    if (!themeId || !dto) return

    try {
      const updated = await updateThemeSource(themeId, dto.site_id, {
        status: 'active',
      })
      set((s) => {
        const by = { ...s.data.siteSources.itemsById, [updated.id]: updated }
        return {
          ...s,
          data: {
            ...s.data,
            siteSources: {
              ...s.data.siteSources,
              itemsById: by,
              error: null,
            },
          },
        }
      })
    } catch (e) {
      const msg = e instanceof Error ? e.message : 'Ошибка при включении'
      set((s) => ({
        ...s,
        data: {
          ...s.data,
          siteSources: {
            ...s.data.siteSources,
            error: msg,
          },
        },
      }))
    }
  },

  updateSourceModeStatus: async (themeSiteId, payload) => {
    const state = useTopicStore.getState()
    const themeId = state.activeTopicId
    const dto = state.data.siteSources.itemsById[themeSiteId]
    if (!themeId || !dto) return
    const patch: ThemeSiteUpdateRequest = {}
    if (payload.mode !== undefined) patch.mode = payload.mode
    if (payload.status !== undefined) patch.status = payload.status
    if (Object.keys(patch).length === 0) return
    try {
      const updated = await updateThemeSource(themeId, dto.site_id, patch)
      set((s) => ({
        ...s,
        data: {
          ...s.data,
          siteSources: {
            ...s.data.siteSources,
            itemsById: { ...s.data.siteSources.itemsById, [updated.id]: updated },
            error: null,
          },
        },
      }))
    } catch (e) {
      const msg = e instanceof Error ? e.message : 'Ошибка при обновлении'
      set((s) => ({
        ...s,
        data: {
          ...s.data,
          siteSources: { ...s.data.siteSources, error: msg },
        },
      }))
    }
  },

  clearSiteSourcesError: () =>
    set((s) => ({
      ...s,
      data: {
        ...s.data,
        siteSources: {
          ...s.data.siteSources,
          error: null,
        },
      },
    })),

  recommendSources: async () => {
    const state = useTopicStore.getState()
    const themeId = state.activeTopicId
    const theme = state.data.theme
    if (!themeId) return
    const title = theme.title?.trim() ?? ''
    const description = theme.description?.trim() ?? ''
    const keywords = theme.keywords?.map((t) => t.text) ?? []
    if (!title && !description) {
      set((s) => ({
        ...s,
        sourcesRecommend: {
          ...s.sourcesRecommend,
          error: 'Укажите название или описание темы на вкладке «Тема»',
        },
      }))
      return
    }
    set((s) => ({
      ...s,
      sourcesRecommend: { isLoading: true, error: null, lastResult: null },
    }))
    try {
      const response = await recommendSourcesApi(themeId, {
        title: title || undefined,
        description: description || undefined,
        keywords: keywords.length > 0 ? keywords : undefined,
      })
      set((s) => ({
        ...s,
        sourcesRecommend: {
          isLoading: false,
          error: null,
          lastResult: response.result ?? [],
        },
      }))
    } catch (e) {
      const message =
        e instanceof Error ? e.message : 'Ошибка при получении рекомендаций'
      set((s) => ({
        ...s,
        sourcesRecommend: {
          isLoading: false,
          error: message,
          lastResult: null,
        },
      }))
    }
  },

  clearSourcesRecommendError: () =>
    set((s) => ({
      ...s,
      sourcesRecommend: {
        ...s.sourcesRecommend,
        error: null,
      },
    })),

  addRecommendedSource: async (item) => {
    const state = useTopicStore.getState()
    const themeId = state.activeTopicId
    if (!themeId) return
    const items = state.data.siteSources.itemsById
    const norm = normalizeDomain(item.domain)
    if (!norm) return
    for (const dto of Object.values(items)) {
      if (dto.status === 'muted') continue
      const existingNorm = normalizeDomain(dto.site.domain)
      if (existingNorm === norm) return
    }
    try {
      const payload = {
        domain: item.domain.trim(),
        mode: 'include' as const,
        status: 'active' as const,
        source: 'ai_recommended' as const,
        display_name: item.display_name?.trim() || undefined,
        reason: item.reason?.trim() || undefined,
      }
      const dto = await createThemeSource(themeId, payload)
      set((s) => {
        const by = { ...s.data.siteSources.itemsById, [dto.id]: dto }
        const order = s.data.siteSources.order.includes(dto.id)
          ? s.data.siteSources.order
          : [...s.data.siteSources.order, dto.id].sort((ia, ib) => {
              const a = by[ia]?.site.effective_display_name ?? by[ia]?.site.domain ?? ''
              const b = by[ib]?.site.effective_display_name ?? by[ib]?.site.domain ?? ''
              return a.localeCompare(b)
            })
        return {
          ...s,
          data: {
            ...s.data,
            siteSources: {
              ...s.data.siteSources,
              itemsById: by,
              order,
              selectedId: dto.id,
              error: null,
            },
          },
        }
      })
    } catch {
      // 409 или другая ошибка — не перезаписываем sourcesRecommend
    }
  },

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
