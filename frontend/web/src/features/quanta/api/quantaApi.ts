import { apiClient } from '@/shared/api/apiClient'
import type {
  QuantumListOutDto,
  QuantumEntitiesOutDto,
  SearchCollectByThemeRequestDto,
  SearchCollectByThemeResponseDto,
} from './dto'

/** GET /api/v1/themes/{themeId}/quanta */
export function listThemeQuanta(
  themeId: string,
  params?: { entity_kind?: string; status?: string; limit?: number; offset?: number }
): Promise<QuantumListOutDto> {
  const search = new URLSearchParams()
  if (params?.entity_kind) search.set('entity_kind', params.entity_kind)
  if (params?.status) search.set('status', params.status)
  if (params?.limit != null) search.set('limit', String(params.limit))
  if (params?.offset != null) search.set('offset', String(params.offset))
  const q = search.toString()
  const url = `/api/v1/themes/${themeId}/quanta${q ? `?${q}` : ''}`
  return apiClient.get<QuantumListOutDto>(url)
}

/** GET /api/v1/quanta/{quantumId}/entities */
export function getQuantumEntities(quantumId: string): Promise<QuantumEntitiesOutDto> {
  const url = `/api/v1/quanta/${quantumId}/entities`
  return apiClient.get<QuantumEntitiesOutDto>(url)
}

/** Таймаут запроса поиска (поиск + перевод; на бэкенде таймаут = батчи × 60 с, здесь запас на ~10 батчей). */
const SEARCH_BY_THEME_TIMEOUT_MS = 600_000

/** POST /api/v1/search/collect-by-theme — запуск поиска по теме, кванты сохраняются в БД. */
export function runSearchByTheme(
  payload: SearchCollectByThemeRequestDto
): Promise<SearchCollectByThemeResponseDto> {
  const controller = new AbortController()
  const timeoutId = setTimeout(() => controller.abort(), SEARCH_BY_THEME_TIMEOUT_MS)
  return apiClient
    .post<SearchCollectByThemeResponseDto>(
      '/api/v1/search/collect-by-theme',
      payload,
      { signal: controller.signal }
    )
    .finally(() => clearTimeout(timeoutId))
}
