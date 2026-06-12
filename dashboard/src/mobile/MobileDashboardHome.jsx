import React from 'react'
import { DesktopDashboardHome } from '../desktop/DesktopDashboardHome.jsx'

/** Mobile home — reuses desktop dashboard layout (responsive CSS handles sizing). */
export function MobileDashboardHome(props) {
  return (
    <div className="mob-dash-wrap">
      <DesktopDashboardHome {...props} />
    </div>
  )
}
