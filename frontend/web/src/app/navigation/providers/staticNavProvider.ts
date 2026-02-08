import type { NavProvider } from '../types'

const items = [
  {
    key: 'new-topic',
    label: 'Новая тема',
    path: '/topic/theme',
  },
]

export const staticNavProvider: NavProvider = {
  getItems: () => items,
}
