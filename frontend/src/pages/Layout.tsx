import { ShieldCheckIcon } from "lucide-react";
import { Link, Outlet } from "react-router-dom";

export function Layout() {
  return (
    <div className="min-h-screen bg-muted/40">
      <header className="border-b bg-background">
        <div className="mx-auto flex h-14 max-w-5xl items-center gap-2 px-6">
          <ShieldCheckIcon className="size-5" />
          <Link to="/" className="font-semibold">
            Underwriting Agent
          </Link>
        </div>
      </header>
      <main className="mx-auto max-w-5xl px-6 py-8">
        <Outlet />
      </main>
    </div>
  );
}
