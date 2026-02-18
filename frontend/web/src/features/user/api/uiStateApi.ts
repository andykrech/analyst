import { apiClient, type RequestOptions } from '@/shared/api/apiClient'

export interface UiStateDto {
  active_theme_id?: string | null
  url?: string | null
  [key: string]: unknown
}

export interface UiStateGetResponseDto {
  state: UiStateDto
}

export interface UiStatePutRequestDto {
  active_theme_id?: string | null
  url?: string | null
}

export const uiStateApi = {
  getState: async (options?: RequestOptions): Promise<UiStateGetResponseDto> => {
    return apiClient.get<UiStateGetResponseDto>('/api/v1/ui-state', options)
  },

  setState: async (
    data: UiStatePutRequestDto,
    options?: RequestOptions
  ): Promise<UiStateGetResponseDto> => {
    return apiClient.put<UiStateGetResponseDto>('/api/v1/ui-state', data, options)
  },
}
