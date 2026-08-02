// @vitest-environment jsdom
import React from 'react'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { SubmitSlotPage } from './SubmitSlotPage.jsx'

function jsonResponse(payload) {
  return Promise.resolve({
    ok: true,
    status: 200,
    headers: { get: () => 'application/json' },
    json: () => Promise.resolve(payload),
  })
}

function routeExtraction(data, processingMode) {
  fetch.mockImplementation(url => {
    if (String(url).includes('/public/slots/extract-invite-ai')) {
      return jsonResponse({ status: 'ok', processing_mode: processingMode, data })
    }
    if (String(url).includes('/public/slots/booked')) {
      return jsonResponse({ status: 'ok', slots: [] })
    }
    return jsonResponse({ status: 'ok', candidates: [] })
  })
}

async function upload() {
  const { container } = render(<SubmitSlotPage />)
  await screen.findByRole('button', { name: 'Profile service' })
  fireEvent.change(container.querySelector('input[type="file"]'), {
    target: { files: [new File(['invite'], 'invite.png', { type: 'image/png' })] },
  })
  return container
}

// The Capgemini invite the operator uploaded: 10 Aug 2026, 02:30 PM IST.
const AI_ONLY_SUCCESS = {
  processing_mode: 'ai',
  ocr_used: false,
  looks_like_interview_invite: true,
  auto_booking_safe: true,
  manual_fields_required: false,
  extraction_method: 'ai_only',
  interview_date: '2026-08-10',
  start_time: '02:30 PM',
  end_time: '03:30 PM',
  confidence_score: 90,
}

describe('booking with the global OCR switch off', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn(() => jsonResponse({ status: 'ok', candidates: [] })))
    vi.stubGlobal('URL', { ...URL, createObjectURL: vi.fn(() => 'blob:test'), revokeObjectURL: vi.fn() })
    Element.prototype.scrollIntoView = vi.fn()
  })

  afterEach(() => {
    cleanup()
    vi.unstubAllGlobals()
  })

  it('accepts the booking from AI evidence alone, with no OCR blocker', async () => {
    routeExtraction(AI_ONLY_SUCCESS, 'ai')
    await upload()

    // The detected panel is what appears when the booking is accepted; the
    // manual-entry fallback and its OCR blocker must not be shown at all.
    await waitFor(() => expect(document.querySelector('.sbs-detected')).toBeInTheDocument())
    expect(document.querySelector('.sbs-detected__time').textContent).toContain('02:30 PM')
    expect(document.querySelector('.sbs-manual')).toBeNull()
    expect(document.body.textContent).not.toMatch(/OCR/)
  })

  it('never tells the operator that OCR failed', async () => {
    routeExtraction(
      {
        ...AI_ONLY_SUCCESS,
        auto_booking_safe: false,
        manual_fields_required: true,
        start_time: '',
        failure_stage: 'ai_incomplete',
        failure_reason: 'The AI did not return a complete start time.',
      },
      'ai',
    )
    await upload()

    await waitFor(() => expect(document.body.textContent).toMatch(/AI did not return a complete/i))
    expect(document.body.textContent).not.toMatch(/OCR/)
  })

  it('suppresses an OCR-worded reason that reaches it anyway', async () => {
    // Defence in depth: a stale worker could still return the old string.
    routeExtraction(
      {
        ...AI_ONLY_SUCCESS,
        auto_booking_safe: false,
        manual_fields_required: true,
        start_time: '',
        failure_reason: 'OCR did not independently extract a supported date and start time.',
      },
      'ai',
    )
    await upload()

    await waitFor(() =>
      expect(document.body.textContent).toMatch(/AI could not read the interview date/i))
    expect(document.body.textContent).not.toMatch(/OCR/)
  })

  it('hides the OCR-vs-AI conflict panel entirely', async () => {
    routeExtraction(
      {
        ...AI_ONLY_SUCCESS,
        auto_booking_safe: false,
        manual_fields_required: true,
        verification_conflict: {
          ocr: { interview_date: '2026-08-11', start_time: '04:00 PM' },
          vision: { interview_date: '2026-08-10', start_time: '02:30 PM' },
        },
      },
      'ai',
    )
    await upload()

    await waitFor(() => expect(document.querySelector('.sbs-manual__hint')).toBeInTheDocument())
    expect(document.querySelector('.sbs-verification-conflict')).toBeNull()
    expect(document.body.textContent).not.toMatch(/OCR/)
  })
})

describe('booking with OCR + AI still cross-checks', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn(() => jsonResponse({ status: 'ok', candidates: [] })))
    vi.stubGlobal('URL', { ...URL, createObjectURL: vi.fn(() => 'blob:test'), revokeObjectURL: vi.fn() })
    Element.prototype.scrollIntoView = vi.fn()
  })

  afterEach(() => {
    cleanup()
    vi.unstubAllGlobals()
  })

  it('still shows the conflict panel and the OCR wording', async () => {
    routeExtraction(
      {
        processing_mode: 'ocr+ai',
        ocr_used: true,
        looks_like_interview_invite: true,
        auto_booking_safe: false,
        manual_fields_required: true,
        interview_date: '2026-08-10',
        start_time: '02:30 PM',
        verification_conflict: {
          ocr: { interview_date: '2026-08-11', start_time: '04:00 PM' },
          vision: { interview_date: '2026-08-10', start_time: '02:30 PM' },
        },
      },
      'ocr+ai',
    )
    await upload()

    await waitFor(() =>
      expect(document.querySelector('.sbs-verification-conflict')).toBeInTheDocument())
    expect(document.body.textContent).toMatch(/OCR and AI read different values/i)
  })
})
