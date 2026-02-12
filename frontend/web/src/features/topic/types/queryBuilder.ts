import type { Term } from '@/shared/types/term'

export type GroupOp = 'OR' | 'AND'
export type MustMode = 'ALL' | 'ANY'

/** Группа ключевых слов в запросе (только id терминов). */
export interface KeywordGroupData {
  id: string
  op: GroupOp
  termIds: string[]
}

/** Один сохранённый или черновой запрос — только id, без дублирования терминов. */
export interface SavedQuery {
  keywords: {
    groups: KeywordGroupData[]
    connectors: GroupOp[]
  }
  must: { mode: MustMode; termIds: string[] }
  exclude: { termIds: string[] }
}

/** Пулы терминов темы (общие для всех запросов). */
export interface TermPools {
  keywordTerms: Term[]
  mustTerms: Term[]
  excludeTerms: Term[]
}

export function createTerm(text: string): Term {
  return {
    id: crypto.randomUUID(),
    text,
    context: '',
    translations: {},
    needsTranslation: false,
  }
}

/** Пустой запрос. */
export function createEmptyQuery(): SavedQuery {
  return {
    keywords: { groups: [], connectors: [] },
    must: { mode: 'ALL', termIds: [] },
    exclude: { termIds: [] },
  }
}

/** Черновик по умолчанию: все ключевые в одной группе OR, все обязательные и минус в группах. */
export function getDefaultDraft(pools: TermPools): SavedQuery {
  const keywordIds = pools.keywordTerms.map((t) => t.id)
  const mustIds = pools.mustTerms.map((t) => t.id)
  const excludeIds = pools.excludeTerms.map((t) => t.id)

  const groups =
    keywordIds.length > 0
      ? [
          {
            id: crypto.randomUUID(),
            op: 'OR' as GroupOp,
            termIds: keywordIds,
          },
        ]
      : []

  return {
    keywords: { groups, connectors: [] },
    must: { mode: 'ALL', termIds: mustIds },
    exclude: { termIds: excludeIds },
  }
}

function getTermById(pools: TermPools, termId: string): Term | undefined {
  return (
    pools.keywordTerms.find((t) => t.id === termId) ??
    pools.mustTerms.find((t) => t.id === termId) ??
    pools.excludeTerms.find((t) => t.id === termId)
  )
}

function quoteTerm(text: string): string {
  const t = text.trim()
  if (!t) return ''
  return t.includes(' ') ? `"${t}"` : t
}

/** Текст запроса по SavedQuery и пулам. */
export function compileQueryPreviewFromSaved(
  pools: TermPools,
  query: SavedQuery
): string {
  const parts: string[] = []

  if (query.keywords.groups.length > 0) {
    const groupStrs = query.keywords.groups
      .map((g) => {
        const terms = g.termIds
          .map((id) => getTermById(pools, id)?.text)
          .filter((t): t is string => Boolean(t))
          .map(quoteTerm)
          .filter(Boolean)
        if (terms.length === 0) return ''
        const op = g.op === 'AND' ? ' AND ' : ' OR '
        return `(${terms.join(op)})`
      })
      .filter(Boolean)
    if (groupStrs.length > 0) {
      const conn = query.keywords.connectors.map((c) => ` ${c} `)
      let expr = groupStrs[0]
      for (let i = 1; i < groupStrs.length; i++) {
        expr += (conn[i - 1] ?? ' ') + groupStrs[i]
      }
      parts.push(expr)
    }
  }

  if (query.must.termIds.length > 0) {
    const mustTexts = query.must.termIds
      .map((id) => getTermById(pools, id)?.text)
      .filter((t): t is string => Boolean(t))
      .map(quoteTerm)
      .filter(Boolean)
    const mustOp = query.must.mode === 'ALL' ? ' AND ' : ' OR '
    parts.push(`MUST(${mustTexts.join(mustOp)})`)
  }

  if (query.exclude.termIds.length > 0) {
    const exTexts = query.exclude.termIds
      .map((id) => getTermById(pools, id)?.text)
      .filter((t): t is string => Boolean(t))
      .map(quoteTerm)
      .filter(Boolean)
    parts.push(`NOT(${exTexts.join(' OR ')})`)
  }

  if (parts.length === 0)
    return 'Нет параметров — добавьте ключевые слова'
  return parts.join(' ')
}

/** Id ключевых слов, используемых в запросе (в любой группе). */
export function getUsedKeywordIds(query: SavedQuery): Set<string> {
  const set = new Set<string>()
  for (const g of query.keywords.groups) {
    for (const id of g.termIds) set.add(id)
  }
  return set
}

/** Неиспользуемые ключевые = пул минус используемые в запросе. */
export function getUnusedKeywordTerms(
  pools: TermPools,
  query: SavedQuery
): Term[] {
  const used = getUsedKeywordIds(query)
  return pools.keywordTerms.filter((t) => !used.has(t.id))
}

export function getUnusedMustTerms(pools: TermPools, query: SavedQuery): Term[] {
  const used = new Set(query.must.termIds)
  return pools.mustTerms.filter((t) => !used.has(t.id))
}

export function getUnusedExcludeTerms(
  pools: TermPools,
  query: SavedQuery
): Term[] {
  const used = new Set(query.exclude.termIds)
  return pools.excludeTerms.filter((t) => !used.has(t.id))
}
