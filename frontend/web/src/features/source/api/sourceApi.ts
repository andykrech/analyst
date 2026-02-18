import { apiClient } from '@/shared/api/apiClient'
import type {
  SourcesRecommendRequest,
  SourcesRecommendResponse,
  ThemeSiteDto,
  ThemeSiteUpdateRequest,
  ThemeSiteUpsertRequest,
} from './dto'

/** GET /api/v1/themes/{themeId}/sites */
export function listThemeSources(themeId: string): Promise<ThemeSiteDto[]> {
  return apiClient.get<ThemeSiteDto[]>(`/api/v1/themes/${themeId}/sites`)
}

/** POST /api/v1/themes/{themeId}/sites */
export function createThemeSource(
  themeId: string,
  payload: ThemeSiteUpsertRequest
): Promise<ThemeSiteDto> {
  return apiClient.post<ThemeSiteDto>(
    `/api/v1/themes/${themeId}/sites`,
    payload
  )
}

/**
 * PATCH /api/v1/themes/{themeId}/sites/{siteId}
 * Backend использует site_id (sites.id) в URL.
 */
export function updateThemeSource(
  themeId: string,
  siteId: string,
  payload: ThemeSiteUpdateRequest
): Promise<ThemeSiteDto> {
  return apiClient.patch<ThemeSiteDto>(
    `/api/v1/themes/${themeId}/sites/${siteId}`,
    payload
  )
}

/**
 * DELETE /api/v1/themes/{themeId}/sites/{siteId}
 * Мягкое удаление (mute). Backend использует site_id в URL.
 */
export function deleteThemeSource(
  themeId: string,
  siteId: string
): Promise<void> {
  return apiClient.delete<void>(`/api/v1/themes/${themeId}/sites/${siteId}`)
}

/**
 * POST /api/v1/themes/{themeId}/sites/recommend
 * Рекомендация источников по контексту темы (ИИ).
 */
export function recommendSources(
  themeId: string,
  payload: SourcesRecommendRequest
): Promise<SourcesRecommendResponse> {
  return apiClient.post<SourcesRecommendResponse>(
    `/api/v1/themes/${themeId}/sites/recommend`,
    payload
  )
}
