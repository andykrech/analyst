import { useTopicStore } from '@/app/store/topicStore'
import type { NavItem, NavProvider } from '../types'

const SECTION_THEMES = 'themes'

export const topicsNavProvider: NavProvider = {
  getItems(): NavItem[] {
    const themes = useTopicStore.getState().themesForNav
    return themes.map((t) => ({
      key: `theme-${t.id}`,
      label: t.title || 'Без названия',
      themeId: t.id,
      sectionId: SECTION_THEMES,
    }))
  },
}
