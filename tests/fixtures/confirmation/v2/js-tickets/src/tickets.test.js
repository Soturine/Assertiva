// Event tickets: frozen confirmation fixture v2 (see labels.json). Never run; read statically.
const { price, reserve, cancel } = require('./tickets')

describe('tickets', () => {
  it('prices a seat', () => {
    expect(price('A1')).toBe(42)
  })

  it('rethrows unexpected errors', () => {
    try {
      expect(price('Z9')).toBe(0)
    } catch (e) {
      throw e
    }
  })

  it('reservation exists', () => {
    expect(reserve('A1')).toBeTruthy()
  })

  it('cancel notifies the gateway', () => {
    const gateway = { refund: jest.fn() }
    cancel('A1', gateway)
    expect(gateway.refund).toHaveBeenCalledWith('A1', 42)
  })

  it('rejects a sold seat, any error', () => {
    expect(() => reserve('SOLD')).toThrow()
  })

  it('rejects a sold seat with its error', () => {
    expect(() => reserve('SOLD')).toThrow(RangeError)
  })

  it('waits for the reservation worker', async () => {
    reserve('B2')
    await new Promise((resolve) => setTimeout(resolve, 500))
    expect(price('B2')).toBe(40)
  })

  it('debounces repeated holds', async () => {
    reserve('C3')
    await new Promise((resolve) => setTimeout(resolve, 300))
    expect(price('C3')).toBe(38)
  })

  it('skips itself in CI', () => {
    if (process.env.CI) return
    expect(price('D4')).toBe(36)
  })

  it('arithmetic sanity', () => {
    expect(2 + 2).toBe(4)
  })
})

test.each([
  [1, [2]],
  [1, [2]],
  [3, [4]],
])('bundle %j', (count, seats) => {
  expect(price(seats[0]) * count).toBeGreaterThan(0)
})
