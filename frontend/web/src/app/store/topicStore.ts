import { create } from 'zustand'
import type {
  ThemePrepareResponse,
  TermDTO,
  TermTranslationDto,
} from '@/features/topic/api/themesApi'
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
      const hasAdditionalLangs =
        s.data.theme.languages.length > 1
      return {
        ...s,
        status: 'dirty',
        data: {
          ...s.data,
          theme: {
            ...s.data.theme,
            title: r.title?.trim() ?? s.data.theme.title,
            keywords: termsFromDtos(r.keywords, hasAdditionalLangs),
            requiredWords: termsFromDtos(r.must_have, hasAdditionalLangs),
            excludedWords: termsFromDtos(r.excludes, hasAdditionalLangs),
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
