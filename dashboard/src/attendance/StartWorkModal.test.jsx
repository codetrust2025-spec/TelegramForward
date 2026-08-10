/**
 * The prompt appears once a day, and only when the server says it should.
 *
 * The cases that matter are the ones where a wrong answer is invisible: a
 * prompt that comes back after it was answered, a Start Work button that is
 * live while the employee is off-network, or a prompt that never returns the
 * next morning.
 */

import { beforeEach, describe, expect, it, vi } from 'vitest'
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'

const click = async (element) => {
  await act(async () => {
    fireEvent.click(element)
  })
}

const api = { fetchToday: vi.fn(), startWork: vi.fn() }

vi.mock('./attendanceApi.js', () => ({
  fetchToday: (...args) => api.fetchToday(...args),
  startWork: (...args) => api.startWork(...args),
  deviceInfo: () => ({ platform: 'test' }),
}))

vi.mock('../context/AuthContext.jsx', () => ({
  useAuth: () => ({ authenticated: true, enabled: true, loading: false }),
}))

const { StartWorkModal } = await import('./StartWorkModal.jsx')

const TODAY = {
  status: 'ok',
  configured: true,
  enrolled: true,
  employee_id: 'EMP-0001',
  display_name: 'Thrilok',
  date: '2026-08-10',
  is_working_day: true,
  already_recorded: false,
  record: null,
  shift_start: '09:30',
  network: { verified: true, reason: 'verified', message: null },
  can_start: true,
  prompt: true,
}

beforeEach(() => {
  cleanup()
  localStorage.clear()
  api.fetchToday.mockReset().mockResolvedValue(TODAY)
  api.startWork.mockReset().mockResolvedValue({ status: 'ok', created: true, record: { date: '2026-08-10' } })
})

describe('when the prompt should appear', () => {
  it('greets the employee by name and offers Start Work', async () => {
    render(<StartWorkModal />)
    expect(await screen.findByText(/Good morning, Thrilok/)).toBeTruthy()
    expect(screen.getByText('Ready to start your work day?')).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Start Work' })).toBeTruthy()
  })

  it('records attendance and closes', async () => {
    render(<StartWorkModal />)
    const button = await screen.findByRole('button', { name: 'Start Work' })
    await click(button)
    await waitFor(() => expect(api.startWork).toHaveBeenCalledTimes(1))
    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull())
  })
})

describe('when the prompt must not appear', () => {
  it('stays hidden once attendance is already recorded', async () => {
    api.fetchToday.mockResolvedValue({ ...TODAY, already_recorded: true, prompt: false })
    render(<StartWorkModal />)
    await waitFor(() => expect(api.fetchToday).toHaveBeenCalled())
    expect(screen.queryByRole('dialog')).toBeNull()
  })

  it('stays hidden on a non-working day', async () => {
    api.fetchToday.mockResolvedValue({ ...TODAY, is_working_day: false, prompt: false })
    render(<StartWorkModal />)
    await waitFor(() => expect(api.fetchToday).toHaveBeenCalled())
    expect(screen.queryByRole('dialog')).toBeNull()
  })

  it('stays hidden when the login is not enrolled', async () => {
    api.fetchToday.mockResolvedValue({ ...TODAY, enrolled: false, employee_id: null, prompt: false })
    render(<StartWorkModal />)
    await waitFor(() => expect(api.fetchToday).toHaveBeenCalled())
    expect(screen.queryByRole('dialog')).toBeNull()
  })

  it('never blocks the dashboard when the attendance call fails', async () => {
    api.fetchToday.mockRejectedValue(new Error('offline'))
    render(<StartWorkModal />)
    await waitFor(() => expect(api.fetchToday).toHaveBeenCalled())
    expect(screen.queryByRole('dialog')).toBeNull()
  })
})

describe('off the office network', () => {
  const OFF_NETWORK = {
    ...TODAY,
    can_start: false,
    network: {
      verified: false,
      reason: 'ip_not_allowlisted',
      message: 'You must be connected to the office network to start your workday.',
    },
  }

  it('disables Start Work and explains why', async () => {
    api.fetchToday.mockResolvedValue(OFF_NETWORK)
    render(<StartWorkModal />)
    const button = await screen.findByRole('button', { name: 'Start Work' })
    expect(button.disabled).toBe(true)
    expect(
      screen.getByText('You must be connected to the office network to start your workday.'),
    ).toBeTruthy()
  })

  it('does not record attendance while blocked', async () => {
    api.fetchToday.mockResolvedValue(OFF_NETWORK)
    render(<StartWorkModal />)
    const button = await screen.findByRole('button', { name: 'Start Work' })
    await click(button)
    expect(api.startWork).not.toHaveBeenCalled()
  })
})

describe('once per day', () => {
  it('does not reappear after being dismissed on the same day', async () => {
    const first = render(<StartWorkModal />)
    await click(await screen.findByRole('button', { name: 'Not now' }))
    first.unmount()

    render(<StartWorkModal />)
    await waitFor(() => expect(api.fetchToday).toHaveBeenCalledTimes(2))
    expect(screen.queryByRole('dialog')).toBeNull()
  })

  it('reappears on the next working day', async () => {
    const first = render(<StartWorkModal />)
    await click(await screen.findByRole('button', { name: 'Not now' }))
    first.unmount()

    api.fetchToday.mockResolvedValue({ ...TODAY, date: '2026-08-11' })
    render(<StartWorkModal />)
    expect(await screen.findByRole('dialog')).toBeTruthy()
  })

  it('keeps one employee dismissal from silencing another', async () => {
    const first = render(<StartWorkModal />)
    await click(await screen.findByRole('button', { name: 'Not now' }))
    first.unmount()

    api.fetchToday.mockResolvedValue({ ...TODAY, employee_id: 'EMP-0002', display_name: 'Pavan' })
    render(<StartWorkModal />)
    expect(await screen.findByText(/Good morning, Pavan/)).toBeTruthy()
  })
})

