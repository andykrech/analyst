/** DTO для сущностей по теме (entities + entity_aliases). */

export interface EntityAliasDto {
  alias_value: string
  kind: string
  source: string
  lang: string | null
  confidence: number | null
}

export interface EntityOutDto {
  id: string
  theme_id: string
  entity_type: string
  canonical_name: string
  normalized_name: string
  mention_count: number
  first_seen_at: string | null
  last_seen_at: string | null
  importance: number | null
  confidence: number | null
  status: string
  is_user_pinned: boolean
  aliases: EntityAliasDto[]
  created_at: string | null
  updated_at: string | null
}

export interface EntityListOutDto {
  items: EntityOutDto[]
  total: number
}
