import type { NavItem, NavProvider } from './types'

const providers: NavProvider[] = []

export const NavigationRegistry = {
  register(provider: NavProvider): void {
    providers.push(provider)
  },

  getItems(): NavItem[] {
    return providers.flatMap((p) => p.getItems())
  },
}
