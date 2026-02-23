import type { QuantumOutDto } from '@/features/quanta/api/dto'

const ENTITY_KIND_LABELS: Record<string, string> = {
  publication: 'Публикация',
  patent: 'Патент',
  webpage: 'Веб-страница',
}

const SUMMARY_MAX_LENGTH = 400

/** Для отображения: переведённое значение, если есть, иначе оригинал */
function displayTitle(q: QuantumOutDto): string {
  return (q.title_translated ?? q.title) || ''
}

function displaySummary(q: QuantumOutDto): string {
  return (q.summary_text_translated ?? q.summary_text) || ''
}

function displayKeyPoints(q: QuantumOutDto): string[] {
  const list = q.key_points_translated ?? q.key_points
  return Array.isArray(list) ? list : []
}

interface QuantaListProps {
  items: QuantumOutDto[]
}

function truncateSummary(text: string, maxLen: number): string {
  const s = (text || '').trim()
  if (s.length <= maxLen) return s
  return s.slice(0, maxLen).trim() + '…'
}

export function QuantaList({ items }: QuantaListProps) {
  return (
    <ul className="quanta-list" role="list" aria-label="Список квантов">
      {items.map((q) => {
        const summary = displaySummary(q)
        const keyPoints = displayKeyPoints(q)
        return (
          <li key={q.id} className="quanta-list__card">
            <div className="quanta-list__card-header">
              <span className="quanta-list__kind" title={q.source_system}>
                {ENTITY_KIND_LABELS[q.entity_kind] ?? q.entity_kind}
              </span>
              <span className="quanta-list__source">{q.source_system}</span>
            </div>
            <h3 className="quanta-list__title">{displayTitle(q)}</h3>
            {summary && (
              <p className="quanta-list__summary">
                {truncateSummary(summary, SUMMARY_MAX_LENGTH)}
              </p>
            )}
            {keyPoints.length > 0 && (
              <ul className="quanta-list__key-points" role="list">
                {keyPoints.map((point, i) => (
                  <li key={i}>{point}</li>
                ))}
              </ul>
            )}
            <a
              href={q.verification_url}
              target="_blank"
              rel="noopener noreferrer"
              className="quanta-list__link"
            >
              {q.verification_url}
            </a>
          </li>
        )
      })}
    </ul>
  )
}
