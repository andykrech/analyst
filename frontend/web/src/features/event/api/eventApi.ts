import { apiClient } from '@/shared/api/apiClient'
import type { EventDetailOutDto, EventExtractResponseDto, EventOutDto } from './dto'

/** Таймаут извлечения событий (батчи LLM могут быть долгими). */
const EXTRACT_EVENTS_TIMEOUT_MS = 600_000

/** POST /api/v1/themes/{themeId}/events/extract — запуск извлечения событий. */
export function extractThemeEvents(themeId: string): Promise<EventExtractResponseDto> {
  const controller = new AbortController()
  const timeoutId = setTimeout(() => controller.abort(), EXTRACT_EVENTS_TIMEOUT_MS)
  return apiClient
    .post<EventExtractResponseDto>(`/api/v1/themes/${themeId}/events/extract`, undefined, {
      signal: controller.signal,
    })
    .finally(() => clearTimeout(timeoutId))
}

/** GET /api/v1/themes/{themeId}/events — список событий по теме. */
export function listThemeEvents(themeId: string): Promise<EventOutDto[]> {
  return apiClient.get<EventOutDto[]>(`/api/v1/themes/${themeId}/events`)
}

/** GET /api/v1/events/{eventId} — детали события. */
export function getEventDetail(eventId: string): Promise<EventDetailOutDto> {
  return apiClient.get<EventDetailOutDto>(`/api/v1/events/${eventId}`)
}


