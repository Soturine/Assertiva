import { discount, type Tier } from "../src/price";

export async function quote(total: number, tier: Tier): Promise<{ total: number }> {
  await Promise.resolve();
  return { total: discount(total, tier) };
}
