import { apiClient } from '@/shared/api/apiClient'
import type { EntityListOutDto } from './dto'

/** GET /api/v1/themes/{themeId}/entities */
export function listThemeEntities(themeId: string): Promise<EntityListOutDto> {
  return apiClient.get<EntityListOutDto>(`/api/v1/themes/${themeId}/entities`)
}

/** Таймаут запроса извлечения сущностей (батчи LLM могут быть долгими). */
const EXTRACT_ENTITIES_TIMEOUT_MS = 600_000

/** POST /api/v1/themes/{themeId}/entities/extract — запуск извлечения, возвращает список сущностей. */
export function extractThemeEntities(themeId: string): Promise<EntityListOutDto> {
  const controller = new AbortController()
  const timeoutId = setTimeout(() => controller.abort(), EXTRACT_ENTITIES_TIMEOUT_MS)
  return apiClient
    .post<EntityListOutDto>(`/api/v1/themes/${themeId}/entities/extract`, undefined, {
      signal: controller.signal,
    })
    .finally(() => clearTimeout(timeoutId))
}
