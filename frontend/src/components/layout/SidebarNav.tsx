import { Home, HelpCircle, MapPin, GraduationCap, PenLine, Languages, Zap, Brain, History, Smartphone, Flame, School, CircleHelp } from "lucide-react";
import { cn } from "@/lib/utils";
import logo from "@/assets/logo-aihay.png";
import { Link, useLocation } from "react-router-dom";

interface Item {
  label: string;
  icon: React.ComponentType<{ className?: string }>;
}

const primaryItems: Array<Item & { to?: string }> = [
  { label: "AI Tìm kiếm", icon: Home, to: "/" },
  { label: "Giải bài tập", icon: GraduationCap, to: "/?type=homework" },
  { label: "AI Viết văn", icon: PenLine, to: "/?type=writing" },
  { label: "Dịch", icon: Languages, to: "/?type=translate" },
  { label: "Tóm tắt", icon: Zap, to: "/?type=summary" },
  { label: "Mindmap", icon: Brain, to: "/?type=mindmap" },
  { label: "Lịch sử", icon: History, to: "/history" },
];

const secondaryItems: Item[] = [
  { label: "Trợ giúp", icon: CircleHelp },
];

export const SidebarNav = () => {
  const location = useLocation();
  return (
    <aside className="hidden md:flex fixed inset-y-0 left-0 w-64 flex-col border-r bg-sidebar text-sidebar-foreground z-10">
      <div className="flex items-center gap-1 px-4 py-4 border-b">
        <img src={logo} alt="OpenHay Logo" className="size-12 rounded" loading="lazy" />
        <span className="font-semibold">OpenHay</span>
      </div>

      <nav className="flex-1 overflow-auto p-2">
        <ul className="space-y-1">
          {primaryItems.map((item, idx) => {
            const Icon = item.icon;
            const active = (() => {
              if (!item.to) return idx === 0;
              const linkUrl = new URL(item.to, window.location.origin);
              const linkType = new URLSearchParams(linkUrl.search).get("type");
              const currentParams = new URLSearchParams(location.search);
              const currentType = currentParams.get("type");
              const onRootOrThread = location.pathname === "/" || location.pathname.startsWith("/t/");

              // Default mode (no type): active on root or thread when no type set
              if (linkUrl.pathname === "/" && !linkType) {
                return onRootOrThread && !currentType;
              }
              // Typed modes: active when current type matches irrespective of extra params like q
              if (linkUrl.pathname === "/" && linkType) {
                return onRootOrThread && currentType === linkType;
              }
              // Other direct links (e.g., /history)
              return location.pathname === item.to;
            })();
            return (
              <li key={item.label}>
                {item.to ? (
                  <Link
                    to={item.to}
                    className={cn(
                      "flex items-center gap-3 rounded-md px-3 py-2 text-sm transition-colors",
                      active
                        ? "bg-sidebar-accent text-sidebar-foreground"
                        : "hover:bg-sidebar-accent hover:text-sidebar-foreground"
                    )}
                    aria-current={active ? "page" : undefined}
                  >
                    <Icon className="size-4" />
                    <span>{item.label}</span>
                  </Link>
                ) : (
                  <a
                    href="#"
                  className={cn(
                    "flex items-center gap-3 rounded-md px-3 py-2 text-sm transition-colors",
                    active
                      ? "bg-sidebar-accent text-sidebar-foreground"
                      : "hover:bg-sidebar-accent hover:text-sidebar-foreground"
                  )}
                  aria-current={active ? "page" : undefined}
                  >
                    <Icon className="size-4" />
                    <span>{item.label}</span>
                  </a>
                )}
              </li>
            );
          })}
        </ul>

        <div className="my-4 h-px bg-sidebar-border" />

        <ul className="space-y-1">
          {secondaryItems.map((item) => {
            const Icon = item.icon;
            return (
              <li key={item.label}>
                <a
                  href="#"
                  className="flex items-center gap-3 rounded-md px-3 py-2 text-sm hover:bg-sidebar-accent"
                >
                  <Icon className="size-4" />
                  <span>{item.label}</span>
                </a>
              </li>
            );
          })}
        </ul>
      </nav>
    </aside>
  );
};

export default SidebarNav;
