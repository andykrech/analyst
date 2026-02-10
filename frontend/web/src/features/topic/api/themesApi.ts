import { apiClient } from '@/shared/api/apiClient'

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
}
