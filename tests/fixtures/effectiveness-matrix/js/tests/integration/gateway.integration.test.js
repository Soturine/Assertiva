import { expect, test, vi } from 'vitest'
import { total } from '../../src/pricing.js'

vi.mock('../../src/apiClient.js')

test('publishes total', () => {
  expect(total([2, 3])).toBe(5)
})
