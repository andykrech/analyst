export interface BillingUsageEventDto {
  id: string
  theme_id: string
  occurred_at: string

  service_type: string
  task_type: string
  service_impl?: string | null

  quantity: string
  quantity_unit_code: string
  extra?: unknown

  cost_tariff_currency: string
  tariff_currency_code: string
  cost_display_currency: string
  display_currency_code: string

  deleted: boolean
}

export interface BillingUsageEventsListDto {
  items: BillingUsageEventDto[]
  total: number
}

