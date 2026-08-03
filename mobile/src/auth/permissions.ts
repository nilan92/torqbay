import type { UserRole } from "@/auth/auth-context";

export type TabName = "jobs" | "customers" | "inventory" | "settings";

/**
 * Which tabs each role sees, per the matrix in docs/05-mobile-app.md.
 *
 * Presentation only — the backend enforces permissions on every request, so
 * hiding a tab is a convenience, never a security boundary.
 */
const VISIBLE: Record<UserRole, TabName[]> = {
  owner: ["jobs", "customers", "inventory", "settings"],
  manager: ["jobs", "customers", "inventory", "settings"],
  technician: ["jobs", "inventory", "settings"],
  frontdesk: ["jobs", "customers", "inventory", "settings"],
};

export function canSeeTab(role: UserRole, tab: TabName): boolean {
  return VISIBLE[role]?.includes(tab) ?? false;
}
