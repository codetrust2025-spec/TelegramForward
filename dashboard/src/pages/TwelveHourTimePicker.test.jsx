// @vitest-environment jsdom
import React from 'react'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { TwelveHourTimePicker } from './TwelveHourTimePicker.jsx'

describe('TwelveHourTimePicker', () => {
  afterEach(cleanup)

  it('always presents detected 24-hour values in 12-hour format', () => {
    render(<TwelveHourTimePicker value="13:30" onChange={() => {}} />)
    expect(screen.getByRole('button', { name: 'Start time: 1:30 PM' })).toBeInTheDocument()
  })

  it('selects hour, minutes, and AM or PM without free-text entry', () => {
    const onChange = vi.fn()
    const { container } = render(<TwelveHourTimePicker value="01:00 PM" onChange={onChange} />)

    fireEvent.click(screen.getByRole('button', { name: 'Start time: 1:00 PM' }))
    fireEvent.click(screen.getByRole('button', { name: '2 hour' }))
    fireEvent.click(screen.getByRole('button', { name: '15 minutes' }))
    fireEvent.click(screen.getByRole('button', { name: 'AM' }))

    expect(onChange).toHaveBeenLastCalledWith('02:15 AM')
    expect(container.querySelector('input')).not.toBeInTheDocument()
  })
})
