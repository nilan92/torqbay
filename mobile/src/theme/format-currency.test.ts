import { formatCurrency } from "@/theme/format-currency";

test("adds comma thousands separators", () => {
  expect(formatCurrency(250000)).toBe("LKR 250,000.00");
});

test("always shows two decimals", () => {
  expect(formatCurrency(1500)).toBe("LKR 1,500.00");
});

test("handles values under a thousand", () => {
  expect(formatCurrency(45.5)).toBe("LKR 45.50");
});

test("honours a different currency", () => {
  expect(formatCurrency(1000, "USD")).toBe("USD 1,000.00");
});
