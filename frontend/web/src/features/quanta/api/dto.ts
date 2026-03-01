/** DTO для квантов информации (theme_quanta). */

export interface QuantumOutDto {
  id: string
  theme_id: string
  run_id: string | null
  entity_kind: string
  title: string
  summary_text: string
  key_points: string[]
  /** Заголовок на основном языке темы; показывать вместо title если не null */
  title_translated: string | null
  /** Описание на основном языке темы; показывать вместо summary_text если не null */
  summary_text_translated: string | null
  /** Ключевые пункты на основном языке темы; показывать вместо key_points если не null */
  key_points_translated: string[] | null
  language: string | null
  date_at: string | null
  verification_url: string
  canonical_url: string | null
  dedup_key: string
  fingerprint: string
  identifiers: Array<{ scheme: string; value: string; is_primary?: boolean | null }>
  matched_terms: unknown[]
  matched_term_ids: unknown[]
  retriever_query: string | null
  /** Оценка сходства по эмбеддингу (0–1) */
  rank_score: number | null
  /** Мнения моделей ИИ о релевантности: [{ model, score }, ...]; первая — для отображения на карточке */
  opinion_score: Array<{ model: string; score: number }> | null
  /** Итоговая оценка релевантности (0–1): среднее rank_score и opinion_score */
  total_score: number | null
  source_system: string
  site_id: string | null
  retriever_name: string
  retriever_version: string | null
  retrieved_at: string
  attrs: Record<string, unknown>
  raw_payload_ref: string | null
  content_ref: string | null
  status: string
  duplicate_of_id: string | null
  created_at: string
  updated_at: string
}

export interface QuantumListOutDto {
  items: QuantumOutDto[]
  total: number
}

/** Запрос на запуск поиска по теме (POST /api/v1/search/collect-by-theme). */
export interface SearchCollectByThemeRequestDto {
  theme_id: string
  published_from?: string | null
  published_to?: string | null
  target_links?: number | null
  run_id?: string | null
}

/** Ответ поиска по теме (кванты возвращаются и сохраняются в БД). */
export interface SearchCollectByThemeResponseDto {
  items: unknown[]
  plan?: unknown
  step_results?: unknown
  total_found: number
  total_returned: number
}
