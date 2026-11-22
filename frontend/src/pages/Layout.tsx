import { ShieldCheckIcon } from "lucide-react";
import { Link, NavLink, Outlet } from "react-router-dom";
import { cn } from "@/lib/utils";

const NAV = [
  { to: "/", label: "Applicant" },
  { to: "/requirements", label: "Requirements" },
];

export function Layout() {
  return (
    <div className="min-h-screen bg-muted/40">
      <header className="border-b bg-background">
        <div className="mx-auto flex h-14 max-w-5xl items-center gap-6 px-6">
          <Link to="/" className="flex items-center gap-2 font-semibold">
            <ShieldCheckIcon className="size-5" />
            Underwriting Agent
          </Link>
          <nav className="flex gap-4 text-sm">
            {NAV.map(({ to, label }) => (
              <NavLink
                key={to}
                to={to}
                end // "/" is only active on "/", not on every page
                className={({ isActive }) =>
                  cn(
                    "text-muted-foreground hover:text-foreground",
                    isActive && "font-medium text-foreground",
                  )
                }
              >
                {label}
              </NavLink>
            ))}
          </nav>
        </div>
      </header>
      <main className="mx-auto max-w-5xl px-6 py-8">
        <Outlet />
      </main>
    </div>
  );
}
