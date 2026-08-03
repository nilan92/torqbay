import { canSeeTab } from "@/auth/permissions";

test("owner sees every tab", () => {
  for (const tab of ["jobs", "customers", "inventory", "settings"] as const) {
    expect(canSeeTab("owner", tab)).toBe(true);
  }
});

test("manager sees every tab", () => {
  for (const tab of ["jobs", "customers", "inventory", "settings"] as const) {
    expect(canSeeTab("manager", tab)).toBe(true);
  }
});

test("technician sees jobs, inventory and settings but not customers", () => {
  expect(canSeeTab("technician", "jobs")).toBe(true);
  expect(canSeeTab("technician", "inventory")).toBe(true);
  expect(canSeeTab("technician", "settings")).toBe(true);
  expect(canSeeTab("technician", "customers")).toBe(false);
});

test("frontdesk sees every tab", () => {
  for (const tab of ["jobs", "customers", "inventory", "settings"] as const) {
    expect(canSeeTab("frontdesk", tab)).toBe(true);
  }
});
