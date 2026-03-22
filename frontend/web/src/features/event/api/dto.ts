export interface EventExtractResponseDto {
  processed_quanta: number
  created_events: number
}

export interface EventOutDto {
  id: string
  theme_id: string
  plot_code: string | null
  plot_name: string | null
  predicate_text: string
  predicate_normalized: string
  predicate_class: string | null
  display_text: string
  event_time: string | null
  created_at: string
  updated_at: string
}

export interface EventParticipantOutDto {
  role_code: string
  role_name: string | null
  entity_id: string
  entity_normalized_name: string
  entity_canonical_name: string | null
}

export interface EventAttributeOutDto {
  attribute_for: string
  entity_id: string | null
  entity_normalized_name: string | null
  attribute_text: string
  attribute_normalized: string | null
}

export interface EventDetailOutDto {
  event: EventOutDto
  participants: EventParticipantOutDto[]
  attributes: EventAttributeOutDto[]
}

