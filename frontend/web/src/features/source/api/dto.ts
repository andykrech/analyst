/** DTO для источников темы (theme_sites + site). */

export type ThemeSiteMode = 'include' | 'exclude' | 'prefer'
export type ThemeSiteStatus = 'active' | 'muted' | 'pending_review'
export type ThemeSiteSource = 'ai_recommended' | 'user_added' | 'discovered' | 'admin_seed'

export interface ThemeSiteSiteDto {
  id: string
  domain: string
  effective_display_name?: string | null
  effective_description?: string | null
  effective_homepage_url?: string | null
  effective_trust_score?: number | null
  effective_quality_tier?: number | null
}

export interface ThemeSiteDto {
  id: string
  theme_id: string
  site_id: string
  mode: ThemeSiteMode
  status: ThemeSiteStatus
  source: ThemeSiteSource
  confidence?: number | null
  reason?: string | null
  site: ThemeSiteSiteDto
  created_by_user_id?: string | null
}

export interface ThemeSiteUpsertRequest {
  domain: string
  mode: ThemeSiteMode
  status?: ThemeSiteStatus
  display_name?: string | null
  description?: string | null
  homepage_url?: string | null
  trust_score?: number | null
  quality_tier?: number | null
  source?: ThemeSiteSource
  confidence?: number | null
  reason?: string | null
}

export type ThemeSiteUpdateRequest = Partial<
  Omit<ThemeSiteUpsertRequest, 'domain'>
>

/** Рекомендация источников (ИИ) */

export interface SourcesRecommendRequest {
  title?: string | null
  description?: string | null
  keywords?: string[] | null
}

export interface RecommendedSiteItem {
  domain: string
  display_name?: string | null
  reason?: string | null
}

export interface SourcesRecommendResponse {
  result: RecommendedSiteItem[]
  llm?: { provider: string; model?: string | null; usage: unknown; cost: unknown; warnings: string[] } | null
}
