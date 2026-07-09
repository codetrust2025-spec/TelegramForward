import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App.jsx'
import { AuthGate } from './components/AuthGate.jsx'
import { SubmitSlotPage } from './pages/SubmitSlotPage.jsx'
import { ConfirmProvider } from './context/ConfirmContext.jsx'
import { AuthProvider } from './context/AuthContext.jsx'
import './index.css'
import './teleautomation.css'
import './inbox/inboxLayout.css'
import './components/ui/CommonModal.css'
import './inbox/outgoingCall.css'
import './admin.css'
import './responsive.css'
import './desktop/desktopDashboard.css'
import './mobile/mobileDashboard.css'
import './dailyOps.css'

const isSubmitSlot =
  typeof window !== 'undefined' &&
  window.location.pathname.replace(/\/+$/, '') === '/submit-slot'

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    {isSubmitSlot ? (
      <SubmitSlotPage />
    ) : (
      <AuthProvider>
        <ConfirmProvider>
          <AuthGate>
            <App />
          </AuthGate>
        </ConfirmProvider>
      </AuthProvider>
    )}
  </React.StrictMode>,
)
