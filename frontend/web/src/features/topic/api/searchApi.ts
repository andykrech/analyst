import { apiClient } from '@/shared/api/apiClient'

export interface LinkCandidate {
  url: string
  title?: string | null
  snippet?: string | null
  provider: string
  rank?: number | null
  normalized_url?: string | null
  url_hash?: string | null
}

export interface LinkCollectResult {
  items: LinkCandidate[]
  total_found: number
  total_returned: number
  plan?: unknown
  step_results?: unknown
}

export interface SearchCollectPayload {
  text: string | null
  keywords: string[]
  must_have: string[]
  exclude: string[]
  target_links?: number
}

export const searchApi = {
  collect: async (payload: SearchCollectPayload): Promise<LinkCollectResult> => {
    return apiClient.post<LinkCollectResult>('/api/v1/search/collect', payload)
  },
}
