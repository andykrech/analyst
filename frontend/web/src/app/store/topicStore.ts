import { create } from 'zustand'
import type { ThemePrepareResponse } from '@/features/topic/api/themesApi'
import { themesApi } from '@/features/topic/api/themesApi'
import type { Term } from '@/shared/types/term'

export type TopicStatus = 'empty' | 'loaded' | 'dirty'

export interface TopicTheme {
  title: string
  description: string
  languages: string[]
  keywords: Term[]
  requiredWords: Term[]
  excludedWords: Term[]
}

function termsFromStrings(
  items: string[],
  hasAdditionalLanguages: boolean
): Term[] {
  const seen = new Set<string>()
  return items
    .map((s) => s.trim())
    .filter((s) => s.length > 0)
    .filter((s) => {
      const lower = s.toLowerCase()
      if (seen.has(lower)) return false
      seen.add(lower)
      return true
    })
    .map((text) => ({
      id: crypto.randomUUID(),
      text,
      context: '',
      translations: {},
      needsTranslation: hasAdditionalLanguages,
    }))
}

export interface TopicData {
  theme: TopicTheme
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
}

export const useTopicStore = create<TopicStore>((set) => ({
  activeTopicId: null,
  status: 'empty',
  data: {
    theme: { ...EMPTY_THEME },
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
      const hasAdditional =
        s.data.theme.languages.slice(1).length > 0
      return {
        ...s,
        status: 'dirty',
        data: {
          ...s.data,
          theme: {
            ...s.data.theme,
            title: r.title?.trim() ?? s.data.theme.title,
            keywords: termsFromStrings(r.keywords ?? [], hasAdditional),
            requiredWords: termsFromStrings(r.must_have ?? [], hasAdditional),
            excludedWords: termsFromStrings(r.excludes ?? [], hasAdditional),
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
      const theme: TopicTheme = {
        ...EMPTY_THEME,
        ...payload.theme,
        keywords: toTerms(t.keywords, hasAdditional),
        requiredWords: toTerms(t.requiredWords, hasAdditional),
        excludedWords: toTerms(t.excludedWords, hasAdditional),
      }
      return {
        ...s,
        activeTopicId: payload.id ?? null,
        status: 'loaded',
        data: {
          ...s.data,
          theme,
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
}))
