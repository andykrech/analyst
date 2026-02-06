import { apiClient } from '@/shared/api/apiClient'

export interface ThemePrepareRequest {
  user_input: string
}

export interface ThemePrepareResult {
  title: string
  keywords: string[]
  must_have: string[]
  excludes: string[]
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

export const themesApi = {
  prepare: async (data: ThemePrepareRequest): Promise<ThemePrepareResponse> => {
    return apiClient.post<ThemePrepareResponse>('/api/v1/themes/prepare', data)
  },
}
