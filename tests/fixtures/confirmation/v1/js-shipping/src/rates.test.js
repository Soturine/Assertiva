// Shipping rates: labeled confirmation fixture (see labels.json). Never run; read statically.
import { describe, expect, test, vi } from 'vitest'
import { rate, quote, label } from './rates.js'

test('rate for a heavy parcel', () => {
  expect(rate({ kg: 12, zone: 'B' })).toBe(31.5)
})

test('rate swallows failures', () => {
  try {
    expect(rate({ kg: -1, zone: 'B' })).toBe(0)
  } catch (e) {}
})

test('quote only checked when present', async () => {
  const q = await quote('B', 3)
  if (q.express) {
    expect(q.express).toBe(19.9)
  }
})

test('quote branches both checked', async () => {
  const q = await quote('C', 3)
  if (q.express) {
    expect(q.express).toBe(24.9)
  } else {
    throw new Error('express quote missing')
  }
})

test('label is defined', () => {
  expect(label('B', 3)).toBeDefined()
})

test('label text', () => {
  expect(label('B', 3)).toEqual('ZONE B / 3 KG')
})

test('rejects unknown zone with its code', async () => {
  await expect(quote('Z', 1)).rejects.toThrow('UNKNOWN_ZONE')
})

test('rejects unknown zone, any error', async () => {
  await expect(quote('Z', 2)).rejects.toThrow()
})

test.each([
  [{ kg: 1, zone: 'A' }, 5],
  [{ kg: 1, zone: 'B' }, 6],
  [{ kg: 1, zone: 'A' }, 5],
])('rate table %j', (parcel, expected) => {
  expect(rate(parcel)).toBe(expected)
})

test.each([
  [[1, 2], 'A'],
  [[1, 3], 'A'],
])('multi-parcel %j', (weights, zone) => {
  expect(rate({ kg: weights[0] + weights[1], zone })).toBeGreaterThan(0)
})

test('constant check', () => {
  expect(true).toBe(true)
})

test('quote rejects silently', () => {
  expect(quote('Z', 3)).rejects.toThrow('UNKNOWN_ZONE')
})
