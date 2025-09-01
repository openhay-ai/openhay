import { Languages, History, CircleHelp, Search, Sparkles } from "lucide-react";
import { cn } from "@/lib/utils";
import logo from "@/assets/logo-aihay.png";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { useState } from "react";
import SupportModal from "@/components/SupportModal";

interface Item {
  label: string;
  icon: React.ComponentType<{ className?: string }>;
  to?: string;
  onClick?: () => void;
}

const primaryItems: Array<Item> = [];

const secondaryItems: Item[] = [{ label: "Hỗ trợ", icon: CircleHelp }];

export const SidebarNav = () => {
  const location = useLocation();
  const navigate = useNavigate();
  const [supportOpen, setSupportOpen] = useState(false);

  // Build items here to access navigate for translate item
  const items: Array<Item> = [
    { label: "AI Hỏi đáp", icon: Search, to: "/" },
    { label: "Nghiên cứu chuyên sâu", icon: Sparkles, to: "/research" },
    // { label: "Gỡ rối bài tập", icon: GraduationCap, to: "/?type=homework" },
    // { label: "Chắp bút cùng AI", icon: PenLine, to: "/?type=writing" },
    { label: "AI Dịch thuật", icon: Languages, to: "/translate" },
    // { label: "Tóm tắt thần tốc", icon: Zap, to: "/?type=summary" },
    // { label: "Tạo Mindmap AI", icon: Brain, to: "/?type=mindmap" },
    { label: "Lịch sử", icon: History, to: "/history" },
  ];
  return (
    <aside className="hidden md:flex fixed inset-y-0 left-0 w-64 flex-col border-r bg-sidebar text-sidebar-foreground z-10">
      <div className="flex items-center gap-1 px-4 py-4 border-b">
        <img
          src={logo}
          alt="OpenHay Logo"
          className="size-12 rounded"
          loading="lazy"
        />
        <span className="font-semibold">OpenHay</span>
      </div>

      <nav className="flex-1 overflow-auto p-2">
        <ul className="space-y-1">
          {items.map((item, idx) => {
            const Icon = item.icon;
            const active = (() => {
              if (!item.to) return idx === 0;
              const linkUrl = new URL(item.to, window.location.origin);
              const linkType = new URLSearchParams(linkUrl.search).get("type");
              const currentParams = new URLSearchParams(location.search);
              const currentType = currentParams.get("type");
              const onRootOrThread =
                location.pathname === "/" ||
                location.pathname.startsWith("/t/");

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
                ) : item.onClick ? (
                  <button
                    type="button"
                    onClick={item.onClick}
                    className={cn(
                      "flex w-full items-center gap-3 rounded-md px-3 py-2 text-left text-sm transition-colors",
                      active
                        ? "bg-sidebar-accent text-sidebar-foreground"
                        : "hover:bg-sidebar-accent hover:text-sidebar-foreground"
                    )}
                    aria-current={active ? "page" : undefined}
                  >
                    <Icon className="size-4" />
                    <span>{item.label}</span>
                  </button>
                ) : (
                  <span
                    className={cn(
                      "flex items-center gap-3 rounded-md px-3 py-2 text-sm",
                      active
                        ? "bg-sidebar-accent text-sidebar-foreground"
                        : undefined
                    )}
                  >
                    <Icon className="size-4" />
                    <span>{item.label}</span>
                  </span>
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
                <button
                  type="button"
                  onClick={() => setSupportOpen(true)}
                  className="flex w-full items-center gap-3 rounded-md px-3 py-2 text-left text-sm hover:bg-sidebar-accent"
                >
                  <Icon className="size-4" />
                  <span>{item.label}</span>
                </button>
              </li>
            );
          })}
        </ul>
      </nav>
      <SupportModal
        open={supportOpen}
        onOpenChange={setSupportOpen}
        ownerEmail="quymyhungill@gmail.com"
      />
    </aside>
  );
};

export default SidebarNav;
