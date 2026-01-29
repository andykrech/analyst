export interface NavItem {
  key: string
  label: string
  path: string
}

export interface NavProvider {
  getItems: () => NavItem[]
}
