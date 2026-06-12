import React from 'react'
import { SegmentedControl } from './SegmentedControl.jsx'

/**
 * Responsive tab/option strip — wraps SegmentedControl with layout classes.
 */
export function ResponsiveOptions({
  options,
  value,
  onChange,
  label,
  className = '',
  segmentedClassName = '',
  role = 'group',
  compactColumns,
}) {
  const wrapClass = [
    'responsive-options',
    className,
    compactColumns ? `responsive-options--cols-${compactColumns}` : '',
  ]
    .filter(Boolean)
    .join(' ')

  return (
    <div className={wrapClass}>
      <SegmentedControl
        options={options}
        value={value}
        onChange={onChange}
        label={label}
        className={segmentedClassName}
        role={role}
      />
    </div>
  )
}
