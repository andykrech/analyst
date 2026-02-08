export interface Term {
  id: string
  text: string
  context: string
  translations: Record<string, string>
  needsTranslation: boolean
}
