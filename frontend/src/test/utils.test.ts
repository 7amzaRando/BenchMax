import { describe, it, expect } from 'vitest'
import { cn } from '@/lib/utils'

describe('lib/utils cn()', () => {
  it('joins class names and drops falsy values', () => {
    expect(cn('a', 'b')).toBe('a b')
    expect(cn('a', false, null, undefined, 'c')).toBe('a c')
  })
  it('supports conditional object syntax', () => {
    expect(cn({ active: true, hidden: false })).toBe('active')
  })
  it('merges conflicting tailwind classes (last wins)', () => {
    expect(cn('px-2 px-4')).toBe('px-4')
    expect(cn('text-sm text-lg font-bold')).toBe('text-lg font-bold')
  })
})
