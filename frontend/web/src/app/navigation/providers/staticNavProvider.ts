import type { NavItem, NavProvider } from '../types'

const SECTION_THEMES = 'themes'

const items: NavItem[] = [
  {
    key: 'new-topic',
    label: 'Новая тема',
    path: '/topic/theme',
    sectionId: SECTION_THEMES,
  },
]

export const staticNavProvider: NavProvider = {
  getItems: () => items,
}
