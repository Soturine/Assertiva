import { expect, test } from 'vitest'
import { total } from './pricing.js'

test('applies discount', () => {
  expect(total([10, 20], 10)).toBe(27)
})

test('swallowed', () => {
  try {
    expect(total([10])).toBe(99)
  } catch (e) {}
})

test('conditional', () => {
  const flag = false
  if (flag) {
    expect(total([1])).toBe(1)
  }
})

test('tautology', () => {
  expect(true).toBe(true)
})

test('status only', async () => {
  const response = await fetch('http://localhost/total')
  expect(response.status).toBe(200)
})

test('any error', () => {
  expect(() => total([1], 200)).toThrow()
})

test('sum copy one', () => {
  const result = total([3, 4])
  expect(result).toBe(7)
})

test('sum copy two', () => {
  const result = total([3, 4])
  expect(result).toBe(7)
})

test.each([[[1], 1], [[2, 2], 4], [[1], 1]])('rows %j', (prices, expected) => {
  expect(total(prices)).toBe(expected)
})

test('waits', async () => {
  await new Promise((r) => setTimeout(r, 10))
  expect(total([5])).toBe(5)
})
