/** Bumped on each production deploy so Vite emits a new app-[hash].js (cache bust). */
export const BUILD_STAMP = '2026-06-22T133144Z'

/** API base — Vite dev uses the dev-server proxy configured in vite.config.js. */
export const isDevFrontend = import.meta.env.DEV || window.location.port === '3000'
export const API = isDevFrontend
  ? ''
  : `${window.location.protocol}//${window.location.host}`
export const WS = isDevFrontend
  ? `${window.location.protocol === 'https:' ? 'wss' : 'ws'}://${window.location.host}/ws`
  : `${window.location.protocol === 'https:' ? 'wss' : 'ws'}://${window.location.host}/ws`

export const COUNTRY_CODES = ['+91', '+1', '+44', '+971', '+61', '+65', '+60']
export const SAVED_PHONES = [
  '+916304215610',
  '+918639074573',
  '+919032598858',
  '+918919515419',
  '+918886422592',
  '+917075074573',
]
