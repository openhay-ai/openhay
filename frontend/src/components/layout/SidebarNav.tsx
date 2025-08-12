import { Home, HelpCircle, MapPin, GraduationCap, PenLine, Languages, Zap, Brain, History, Smartphone, Flame, School, CircleHelp } from "lucide-react";
import { cn } from "@/lib/utils";
import logo from "@/assets/logo-aihay.png";

interface Item {
  label: string;
  icon: React.ComponentType<{ className?: string }>;
}

const primaryItems: Item[] = [
  { label: "AI Tìm kiếm", icon: Home },
  { label: "Bạn có đồ ĐH?", icon: HelpCircle },
  { label: "Địa điểm", icon: MapPin },
  { label: "Giải bài tập", icon: GraduationCap },
  { label: "AI Viết văn", icon: PenLine },
  { label: "Dịch", icon: Languages },
  { label: "Tóm tắt", icon: Zap },
  { label: "Mindmap", icon: Brain },
  { label: "Lịch sử", icon: History },
];

const secondaryItems: Item[] = [
  { label: "Tải ứng dụng AI Hay", icon: Smartphone },
  { label: "Top câu hỏi Hot", icon: Flame },
  { label: "Đại học", icon: School },
  { label: "Trợ giúp", icon: CircleHelp },
];

export const SidebarNav = () => {
  return (
    <aside className="hidden md:flex h-screen w-64 shrink-0 flex-col border-r bg-sidebar text-sidebar-foreground sticky top-0">
      <div className="flex items-center gap-3 px-4 py-4 border-b">
        <img src={logo} alt="AI Hay logo" className="size-8 rounded" loading="lazy" />
        <span className="font-semibold">AI Hay</span>
      </div>

      <nav className="flex-1 overflow-auto p-2">
        <ul className="space-y-1">
          {primaryItems.map((item, idx) => {
            const Icon = item.icon;
            const active = idx === 0; // highlight the first item
            return (
              <li key={item.label}>
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
