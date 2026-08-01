// @vitest-environment jsdom
import React from 'react'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { SubmitSlotPage, to24h } from './SubmitSlotPage.jsx'

function jsonResponse(payload) {
  return Promise.resolve({
    ok: true,
    status: 200,
    headers: { get: () => 'application/json' },
    json: () => Promise.resolve(payload),
  })
}

describe('Book Interview Slot flow', () => {
  it('converts the displayed 12-hour selection to the existing API format', () => {
    expect(to24h('02:15 PM')).toBe('14:15')
    expect(to24h('12:05 AM')).toBe('00:05')
  })

  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn(url => {
      if (String(url).includes('/public/slots/booked')) {
        return jsonResponse({ status: 'ok', slots: [] })
      }
      return jsonResponse({ status: 'ok', candidates: [] })
    }))
    vi.stubGlobal('URL', {
      ...URL,
      createObjectURL: vi.fn(() => 'blob:test'),
      revokeObjectURL: vi.fn(),
    })
    Element.prototype.scrollIntoView = vi.fn()
  })

  afterEach(() => {
    cleanup()
    vi.unstubAllGlobals()
  })

  async function openRoundWiseForm() {
    render(<SubmitSlotPage />)
    await screen.findByRole('button', { name: 'Profile service' })
    fireEvent.click(screen.getByRole('button', { name: 'Profile service' }))
    fireEvent.click(screen.getByText('Round-wise'))
  }

  it('field changes and closing before confirmation create nothing', async () => {
    await openRoundWiseForm()
    fireEvent.change(screen.getByPlaceholderText('Type client name'), {
      target: { value: 'Gopichand' },
    })
    fireEvent.change(screen.getByRole('combobox', { name: /interview round/i }), {
      target: { value: 'L1' },
    })
    fireEvent.change(screen.getByPlaceholderText('Enter candidate phone number'), {
      target: { value: '9876543210' },
    })
    fireEvent.change(screen.getByRole('combobox', { name: /technology/i }), {
      target: { value: 'Testing' },
    })
    cleanup()

    const mutatingCalls = fetch.mock.calls.filter(([, options]) =>
      String(options?.method || 'GET').toUpperCase() !== 'GET')
    expect(mutatingCalls).toHaveLength(0)
  })

  it('uses custom validation and reports only the first invalid field', async () => {
    await openRoundWiseForm()
    const form = screen.getByRole('button', { name: /Confirm booking/ }).closest('form')
    expect(form.noValidate).toBe(true)
    expect(form.querySelectorAll('[required]')).toHaveLength(0)

    fireEvent.click(screen.getByRole('button', { name: /Confirm booking/ }))

    expect(await screen.findAllByRole('alert')).toHaveLength(1)
    expect(screen.getByRole('alert')).toHaveTextContent('Enter the client name')
    expect(fetch.mock.calls.filter(([, options]) => options?.method === 'POST')).toHaveLength(0)
  })

  it('shows the exact payment validation message after earlier fields are valid', async () => {
    await openRoundWiseForm()
    fireEvent.change(screen.getByPlaceholderText('Type client name'), {
      target: { value: 'Gopichand' },
    })
    const selects = screen.getAllByRole('combobox')
    fireEvent.change(selects[0], { target: { value: 'L1' } })
    fireEvent.change(screen.getByPlaceholderText('Enter candidate phone number'), {
      target: { value: '9876543210' },
    })
    fireEvent.change(selects[1], { target: { value: 'Testing' } })

    fireEvent.click(screen.getByRole('button', { name: /Confirm booking/ }))

    await waitFor(() => {
      expect(screen.getByRole('alert')).toHaveTextContent(
        'Upload and verify the payment screenshot to continue.',
      )
    })
    expect(screen.getAllByRole('alert')).toHaveLength(1)
  })

  it('uses a time-only picker for manually verified invite times', async () => {
    fetch.mockImplementation(url => {
      if (String(url).includes('/public/slots/extract-invite-ai')) {
        return jsonResponse({
          status: 'ok',
          data: {
            looks_like_interview_invite: true,
            auto_booking_safe: true,
            manual_fields_required: true,
            interview_date: '2026-08-01',
            start_time: '1:30 PM',
            failure_reason: 'Enter the date and time shown in the invite.',
          },
        })
      }
      if (String(url).includes('/public/slots/booked')) {
        return jsonResponse({ status: 'ok', slots: [] })
      }
      return jsonResponse({ status: 'ok', candidates: [] })
    })

    const { container } = render(<SubmitSlotPage />)
    await screen.findByRole('button', { name: 'Profile service' })
    const invite = new File(['invite'], 'invite.png', { type: 'image/png' })
    fireEvent.change(container.querySelector('input[type="file"]'), {
      target: { files: [invite] },
    })

    const timePicker = await screen.findByRole('button', { name: 'Start time: 1:30 PM' })
    expect(container.querySelector('input[type="time"]')).not.toBeInTheDocument()

    fireEvent.click(timePicker)
    expect(screen.getByRole('dialog', { name: 'Choose start time' })).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: '2 hour' }))
    fireEvent.click(screen.getByRole('button', { name: '15 minutes' }))
    expect(screen.getByRole('button', { name: 'Start time: 2:15 PM' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'PM' })).toHaveAttribute('aria-pressed', 'true')
  })
})
