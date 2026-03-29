import { apiClient } from '@/shared/api/apiClient'
import type { BillingUsageEventsListDto } from './dto'

export interface ListBillingUsageEventsParams {
  limit?: number
  offset?: number
}

/**
 * GET /api/v1/themes/{themeId}/billing/usage-events
 * Только события с deleted=false (ещё не свёрнутые в дневную сводку).
 */
export function listBillingUsageEvents(
  themeId: string,
  params: ListBillingUsageEventsParams = {},
): Promise<BillingUsageEventsListDto> {
  const { limit = 100, offset = 0 } = params
  return apiClient.get<BillingUsageEventsListDto>(
    `/api/v1/themes/${themeId}/billing/usage-events`,
    {
      params: {
        limit: String(limit),
        offset: String(offset),
      },
    },
  )
}

