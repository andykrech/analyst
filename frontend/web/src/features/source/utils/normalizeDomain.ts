/**
 * Нормализует домен из URL или строки.
 * - trim + lower
 * - если содержит "://" => hostname через URL
 * - иначе взять до первого "/" и до ":" (порт убрать)
 * - убрать префикс "www."
 * - если пусто/невалидно => null
 */
export function normalizeDomain(input: string): string | null {
  const s = (input ?? '').trim().toLowerCase()
  if (!s) return null

  let host: string
  if (s.includes('://')) {
    try {
      host = new URL(s).hostname
    } catch {
      return null
    }
  } else {
    const beforePath = s.split('/')[0]
    host = beforePath.split(':')[0]
  }

  if (!host) return null
  if (host.toLowerCase().startsWith('www.')) {
    host = host.slice(4)
  }
  if (!host || host.indexOf('.') < 0) return null
  return host
}
