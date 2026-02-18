import { apiClient, type RequestOptions } from '@/shared/api/apiClient'

export interface ThemePrepareRequest {
  user_input: string
}

export interface TermDTO {
  text: string
  context?: string
}

export interface ThemePrepareResult {
  title: string
  keywords: TermDTO[]
  must_have: TermDTO[]
  excludes: TermDTO[]
}

export interface ThemePrepareLLMMeta {
  provider: string
  model?: string | null
  usage: { prompt_tokens: number; completion_tokens: number; total_tokens: number; source: string }
  cost: { currency: string; total_cost: number; [key: string]: unknown }
  warnings: string[]
}

export interface ThemePrepareResponse {
  result: ThemePrepareResult
  llm?: ThemePrepareLLMMeta | null
}

// --- Terms translate ---

export interface TermTranslateInDto {
  id: string
  text: string
  context: string
}

export interface TermsTranslateRequestDto {
  source_language: string
  target_language: string
  terms: TermTranslateInDto[]
}

export interface TermTranslationDto {
  id: string
  translation: string
}

export interface TermsTranslateResponseDto {
  translations: TermTranslationDto[]
  llm: ThemePrepareLLMMeta | null
}

// --- Сохранение темы и запросов ---

export interface ThemeSaveTermDto {
  id: string
  text: string
  context: string
  translations: Record<string, string>
}

export interface ThemeSaveThemeDto {
  title: string
  description: string
  keywords: ThemeSaveTermDto[]
  must_have: ThemeSaveTermDto[]
  exclude: ThemeSaveTermDto[]
  languages: string[]
  update_interval?: 'daily' | '3d' | 'weekly'
  status?: 'draft' | 'active' | 'paused' | 'archived'
  backfill_status?: 'not_started' | 'running' | 'done' | 'failed'
  backfill_horizon_months?: number
  region?: string | null
}

export interface ThemeSaveQueryModelDto {
  keywords: { groups: { id: string; op: 'OR' | 'AND'; termIds: string[] }[]; connectors: ('OR' | 'AND')[] }
  must: { mode: 'ALL' | 'ANY'; termIds: string[] }
  exclude: { termIds: string[] }
}

export interface ThemeSaveSearchQueryDto {
  order_index: number
  query_model: ThemeSaveQueryModelDto
  title?: string | null
  time_window_days?: number | null
  target_links?: number | null
  enabled_retrievers?: string[] | null
  is_enabled?: boolean
}

export interface ThemeSaveRequestDto {
  theme: ThemeSaveThemeDto
  search_queries: ThemeSaveSearchQueryDto[]
}

export interface ThemeSaveResponseDto {
  id: string
  message: string
}

// --- Загрузка темы по id (GET) ---

export interface ThemeGetTermDto {
  id: string
  text: string
  context: string
  translations: Record<string, string>
}

export interface ThemeGetThemeDto {
  id: string
  title: string
  description: string
  keywords: ThemeGetTermDto[]
  must_have: ThemeGetTermDto[]
  exclude: ThemeGetTermDto[]
  languages: string[]
}

export interface ThemeGetSearchQueryDto {
  order_index: number
  query_model: ThemeSaveQueryModelDto
}

export interface ThemeGetResponseDto {
  theme: ThemeGetThemeDto
  search_queries: ThemeGetSearchQueryDto[]
}

// --- Список тем пользователя ---

export interface ThemeListItemDto {
  id: string
  title: string
}

export interface ThemeListResponseDto {
  themes: ThemeListItemDto[]
}

export const themesApi = {
  prepare: async (data: ThemePrepareRequest): Promise<ThemePrepareResponse> => {
    return apiClient.post<ThemePrepareResponse>('/api/v1/themes/prepare', data)
  },

  translateTerms: async (
    data: TermsTranslateRequestDto
  ): Promise<TermsTranslateResponseDto> => {
    return apiClient.post<TermsTranslateResponseDto>(
      '/api/v1/themes/terms/translate',
      data
    )
  },

  saveTheme: async (
    data: ThemeSaveRequestDto,
    options?: RequestOptions
  ): Promise<ThemeSaveResponseDto> => {
    return apiClient.post<ThemeSaveResponseDto>('/api/v1/themes', data, options)
  },

  updateTheme: async (
    themeId: string,
    data: ThemeSaveRequestDto,
    options?: RequestOptions
  ): Promise<ThemeSaveResponseDto> => {
    return apiClient.put<ThemeSaveResponseDto>(
      `/api/v1/themes/${themeId}`,
      data,
      options
    )
  },

  getTheme: async (
    themeId: string,
    options?: RequestOptions
  ): Promise<ThemeGetResponseDto> => {
    return apiClient.get<ThemeGetResponseDto>(
      `/api/v1/themes/${themeId}`,
      options
    )
  },

  getThemes: async (
    options?: RequestOptions
  ): Promise<ThemeListResponseDto> => {
    return apiClient.get<ThemeListResponseDto>('/api/v1/themes', options)
  },
}
