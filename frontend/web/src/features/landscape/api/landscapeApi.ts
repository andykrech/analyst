import { apiClient } from '@/shared/api/apiClient'
import type { LandscapeOutDto } from './dto'

const BUILD_LANDSCAPE_TIMEOUT_MS = 600_000

/** GET /api/v1/themes/{themeId}/landscape — последняя версия ландшафта. */
export function getLatestLandscape(themeId: string): Promise<LandscapeOutDto> {
  return apiClient.get<LandscapeOutDto>(`/api/v1/themes/${themeId}/landscape`)
}

/** POST /api/v1/themes/{themeId}/landscape/build — новая версия (LLM). */
export function buildLandscape(themeId: string): Promise<LandscapeOutDto> {
  const controller = new AbortController()
  const timeoutId = setTimeout(() => controller.abort(), BUILD_LANDSCAPE_TIMEOUT_MS)
  return apiClient
    .post<LandscapeOutDto>(
      `/api/v1/themes/${themeId}/landscape/build`,
      undefined,
      { signal: controller.signal },
    )
    .finally(() => clearTimeout(timeoutId))
}
