import { expect, test } from "vitest";
import { quote } from "./quote";

test("quotes a VIP total asynchronously", async () => {
  await expect(quote(200, "VIP")).resolves.toEqual({ total: 180 });
});
