import { formatDuration } from "@/jobs/format-duration";

test("shows minutes only under an hour", () => {
  expect(formatDuration("2026-08-13T09:00:00Z", "2026-08-13T09:45:00Z")).toBe("45m");
});

test("shows hours and minutes over an hour", () => {
  expect(formatDuration("2026-08-13T09:00:00Z", "2026-08-13T11:30:00Z")).toBe("2h 30m");
});

test("treats a null end time as running until now", () => {
  const start = new Date(Date.now() - 10 * 60_000).toISOString();
  expect(formatDuration(start, null)).toBe("10m");
});
