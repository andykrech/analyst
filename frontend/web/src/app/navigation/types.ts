export interface NavItem {
  key: string
  label: string
  /** Маршрут для ссылки (NavLink). */
  path?: string
  /** ID темы — пункт ведёт на загрузку темы по клику. */
  themeId?: string
  /** Секция меню (например "themes", "reports"). Для группировки и заголовков. */
  sectionId?: string
}

export interface NavProvider {
  getItems: () => NavItem[]
}
