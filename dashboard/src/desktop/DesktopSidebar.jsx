import React, { useEffect, useRef, useState } from 'react'

const NAV = [
  { id: 'dashboard', label: 'Dashboard', icon: '▣' },
  { id: 'accounts', label: 'Accounts', icon: '👤' },
  { id: 'forwarding', label: 'Forwarding', icon: '↻' },
  { id: 'campaigns', label: 'Campaigns', icon: '📣' },
  { id: 'inbox', label: 'Inbox', icon: '✉', badgeKey: 'inbox' },
  { id: 'candidates', label: 'Candidates', icon: '📇' },
  { id: 'data', label: 'Data', icon: '📊' },
  { id: 'logs', label: 'Logs', icon: '📋' },
  { id: 'admin', label: 'Admin', icon: '⚙' },
  { id: 'settings', label: 'Settings', icon: '⚙' },
]

export function DesktopSidebar({
  activeId,
  onNavigate,
  inboxUnreadTotal,
  connected,
  authUsername,
  authEnabled,
  authLogout,
}) {
  const [userMenuOpen, setUserMenuOpen] = useState(false)
  const userMenuRef = useRef(null)
  const userInitials = (authUsername || 'AD').slice(0, 2).toUpperCase()
  const displayName = authUsername || 'Administrator'

  useEffect(() => {
    if (!userMenuOpen) return undefined
    function onDoc(e) {
      if (userMenuRef.current && !userMenuRef.current.contains(e.target)) {
        setUserMenuOpen(false)
      }
    }
    document.addEventListener('mousedown', onDoc)
    return () => document.removeEventListener('mousedown', onDoc)
  }, [userMenuOpen])

  return (
    <aside className="desktop-sidebar desktop-sidebar--sigma">
      <button
        type="button"
        className="desktop-sidebar__brand"
        onClick={() => onNavigate('dashboard')}
        aria-label="Go to dashboard"
      >
        <span className="desktop-sidebar__logo" aria-hidden>⚡</span>
        <span className="desktop-sidebar__title">TeleAutomation</span>
      </button>
      <nav className="desktop-sidebar__nav" aria-label="Main">
        {NAV.map(item => (
          <button
            key={item.id}
            type="button"
            className={`desktop-sidebar__link${activeId === item.id ? ' desktop-sidebar__link--active' : ''}`}
            onClick={() => onNavigate(item.id)}
          >
            <span className="desktop-sidebar__link-icon" aria-hidden>{item.icon}</span>
            {item.label}
            {item.badgeKey === 'inbox' && inboxUnreadTotal > 0 && (
              <span className="desktop-sidebar__badge">
                {inboxUnreadTotal > 99 ? '99+' : inboxUnreadTotal}
              </span>
            )}
          </button>
        ))}
      </nav>
      <div className="desktop-sidebar__footer">
        <div className="desktop-sidebar__status">
          <span className="desktop-sidebar__status-check" aria-hidden>✓</span>
          {connected ? 'All systems operational' : 'Reconnecting…'}
        </div>
        <div className="desktop-sidebar__uptime">
          <span>Uptime 99.98%</span>
          <div className="desktop-sidebar__uptime-bar" aria-hidden>
            <div className="desktop-sidebar__uptime-fill" style={{ width: '99.98%' }} />
          </div>
        </div>
        <div className="desktop-sidebar__version">Version v2.4.1</div>
        <div className="desktop-sidebar__user-wrap" ref={userMenuRef}>
          <button
            type="button"
            className="desktop-sidebar__user"
            aria-expanded={userMenuOpen}
            onClick={() => setUserMenuOpen(v => !v)}
            title={displayName}
          >
            <span className="desktop-sidebar__user-avatar" aria-hidden>{userInitials}</span>
            <span className="desktop-sidebar__user-text">
              <span className="desktop-sidebar__user-name">{displayName}</span>
              <span className="desktop-sidebar__user-role">Administrator</span>
            </span>
            <span className="desktop-sidebar__user-chev" aria-hidden>▾</span>
          </button>
          {userMenuOpen && (
            <div className="desk-user-menu desk-user-menu--sidebar" role="menu">
              {authEnabled ? (
                <button
                  type="button"
                  className="desk-user-menu__item desk-user-menu__item--danger"
                  role="menuitem"
                  onClick={() => {
                    setUserMenuOpen(false)
                    authLogout?.()
                  }}
                >
                  Sign out
                </button>
              ) : (
                <p className="desk-user-menu__hint">Login not required on this server.</p>
              )}
              <button
                type="button"
                className="desk-user-menu__item"
                role="menuitem"
                onClick={() => {
                  setUserMenuOpen(false)
                  onNavigate('admin')
                }}
              >
                Admin
              </button>
            </div>
          )}
        </div>
      </div>
    </aside>
  )
}
