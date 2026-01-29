import type { NavProvider } from '../types'

const items = [
  {
    key: 'new-topic',
    label: 'Новая тема',
    path: '/topics/new',
  },
]

export const staticNavProvider: NavProvider = {
  getItems: () => items,
}
