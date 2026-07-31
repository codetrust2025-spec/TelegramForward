// @vitest-environment jsdom
import React from 'react'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { SubmitSlotPage } from './SubmitSlotPage.jsx'

function jsonResponse(payload) {
  return Promise.resolve({
    ok: true,
    json: () => Promise.resolve(payload),
  })
}

describe('Book Interview Slot flow', () => {
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
})
