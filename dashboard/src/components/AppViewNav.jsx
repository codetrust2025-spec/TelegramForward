import React from 'react'

const VIEWS = [
  { value: 'dashboard', label: 'Dashboard' },
  { value: 'inbox', label: 'Inbox' },
  { value: 'candidates', label: 'Candidates' },
  { value: 'data-room', label: 'Data' },
  { value: 'logs', label: 'Logs' },
  { value: 'admin', label: 'Admin' },
]

export function AppViewNav({ mainView, inboxUnreadTotal = 0, inboxUnreadBadge, onNavigate }) {
  return (
    <nav className="app-view-nav" aria-label="Main views">
      {VIEWS.map(view => {
        const active = mainView === view.value
        const showBadge = view.value === 'inbox' && inboxUnreadTotal > 0
        return (
          <button
            key={view.value}
            type="button"
            className={[
              'app-view-nav__btn',
              active ? 'app-view-nav__btn--active' : '',
              showBadge ? 'app-view-nav__btn--has-unread' : '',
            ]
              .filter(Boolean)
              .join(' ')}
            onClick={() => onNavigate?.(view.value)}
            aria-current={active ? 'page' : undefined}
            aria-label={
              showBadge
                ? `Inbox, ${inboxUnreadTotal} unread message${inboxUnreadTotal === 1 ? '' : 's'}`
                : view.label
            }
          >
            {view.label}
            {showBadge && (
              <span className="app-view-nav-badge" aria-hidden>
                {inboxUnreadBadge ?? inboxUnreadTotal}
              </span>
            )}
          </button>
        )
      })}
    </nav>
  )
}
