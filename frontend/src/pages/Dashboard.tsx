import SidebarNav from "@/components/layout/SidebarNav";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Calendar } from "@/components/ui/calendar";
import { addDays, endOfDay, startOfDay } from "date-fns";
import { useEffect, useMemo, useState } from "react";
import {
  getMetricsMessagesByPreset,
  getMetricsMessagesByUser,
  getMetricsTotalMessages,
  getMetricsTotalUsers,
} from "@/lib/api";
import { authFetch } from "@/lib/auth";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { RefreshCw, MessageSquare, Users } from "lucide-react";

type GroupItem = { key: string; count: number };

const DASHBOARD_PASSWORD = import.meta.env.VITE_DASHBOARD_PASSWORD as
  | string
  | undefined;

const Dashboard = () => {
  const [password, setPassword] = useState("");
  const [authed, setAuthed] = useState(false);

  useEffect(() => {
    const saved = sessionStorage.getItem("dashboard_authed");
    if (saved === "true") setAuthed(true);
  }, []);

  const [range, setRange] = useState<{ from: Date; to: Date }>(() => {
    const to = endOfDay(new Date());
    const from = startOfDay(addDays(to, -7));
    return { from, to };
  });

  const startIso = useMemo(() => range.from.toISOString(), [range.from]);
  const endIso = useMemo(() => range.to.toISOString(), [range.to]);

  const [loading, setLoading] = useState(false);
  const [totalMsgs, setTotalMsgs] = useState<number | null>(null);
  const [msgsByUser, setMsgsByUser] = useState<GroupItem[]>([]);
  const [msgsByPreset, setMsgsByPreset] = useState<GroupItem[]>([]);
  const [showAllUsers, setShowAllUsers] = useState(false);
  const [showAllPresets, setShowAllPresets] = useState(false);
  const [totalUsers, setTotalUsers] = useState<number | null>(null);

  const handleUnlock = () => {
    if (!DASHBOARD_PASSWORD) {
      // If not set, allow dev access
      setAuthed(true);
      sessionStorage.setItem("dashboard_authed", "true");
      return;
    }
    if (password === DASHBOARD_PASSWORD) {
      setAuthed(true);
      sessionStorage.setItem("dashboard_authed", "true");
    } else {
      alert("Sai mật khẩu");
    }
  };

  const fetchAll = async () => {
    setLoading(true);
    try {
      const [a, b, c, d] = await Promise.all([
        authFetch(getMetricsTotalMessages(startIso, endIso)),
        authFetch(getMetricsMessagesByUser(startIso, endIso)),
        authFetch(getMetricsMessagesByPreset(startIso, endIso)),
        authFetch(getMetricsTotalUsers(startIso, endIso)),
      ]);
      const aj = await a.json();
      const bj = await b.json();
      const cj = await c.json();
      const dj = await d.json();
      setTotalMsgs(aj.count ?? 0);
      setMsgsByUser(bj.items ?? []);
      setMsgsByPreset(cj.items ?? []);
      setTotalUsers(dj.count ?? 0);
    } catch (e) {
      // keep previous values
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (authed) fetchAll();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [authed, startIso, endIso]);

  if (!authed) {
    return (
      <div className="min-h-screen flex flex-col md:flex-row w-full overflow-hidden">
        <SidebarNav />
        <div className="md:flex-auto overflow-hidden w-full md:ml-64">
          <main className="h-full overflow-auto w-full px-3 md:px-6">
            <section className="max-w-xl mx-auto py-20">
              <Card>
                <CardHeader>
                  <CardTitle>Dashboard Access</CardTitle>
                </CardHeader>
                <CardContent className="space-y-3">
                  <div className="space-y-2">
                    <Label htmlFor="pwd">Password</Label>
                    <Input
                      id="pwd"
                      type="password"
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                    />
                  </div>
                  <Button onClick={handleUnlock}>Unlock</Button>
                </CardContent>
              </Card>
            </section>
          </main>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex flex-col md:flex-row w-full overflow-hidden">
      <SidebarNav />
      <div className="md:flex-auto overflow-hidden w-full md:ml-64">
        <main className="h-full overflow-auto w-full px-3 md:px-6">
          <section className="max-w-5xl mx-auto py-6 space-y-6">
            <div className="flex items-start md:items-center justify-between gap-4">
              <h1 className="text-2xl font-semibold">Metrics Dashboard</h1>
              <div className="flex items-center gap-3">
                <Calendar
                  mode="range"
                  selected={{ from: range.from, to: range.to }}
                  onSelect={(val: any) => {
                    const from: Date = val?.from
                      ? startOfDay(val.from)
                      : range.from;
                    const to: Date = val?.to ? endOfDay(val.to) : range.to;
                    setRange({ from, to });
                  }}
                  numberOfMonths={2}
                />
                <Button
                  variant="secondary"
                  onClick={fetchAll}
                  disabled={loading}
                  size="icon"
                >
                  <RefreshCw
                    className={"h-4 w-4 " + (loading ? "animate-spin" : "")}
                  />
                </Button>
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
              <Card className="rounded-xl shadow-md">
                <CardHeader className="pb-2">
                  <CardTitle className="flex items-center gap-2 text-sm text-muted-foreground">
                    <MessageSquare className="h-4 w-4" /> Total messages (user)
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="text-3xl font-semibold">
                    {totalMsgs ?? "-"}
                  </div>
                </CardContent>
              </Card>
              <Card className="rounded-xl shadow-md">
                <CardHeader className="pb-2">
                  <CardTitle className="flex items-center gap-2 text-sm text-muted-foreground">
                    <Users className="h-4 w-4" /> Total users (active)
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="text-3xl font-semibold">
                    {totalUsers ?? "-"}
                  </div>
                </CardContent>
              </Card>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <Card className="rounded-xl shadow-sm">
                <CardHeader>
                  <CardTitle>Messages by user</CardTitle>
                </CardHeader>
                <CardContent>
                  <BarList
                    items={msgsByUser}
                    showAll={showAllUsers}
                    onToggle={() => setShowAllUsers((v) => !v)}
                    truncateLabel
                  />
                </CardContent>
              </Card>

              <Card className="rounded-xl shadow-sm">
                <CardHeader>
                  <CardTitle>Messages by preset</CardTitle>
                </CardHeader>
                <CardContent>
                  <BarList
                    items={msgsByPreset}
                    showAll={showAllPresets}
                    onToggle={() => setShowAllPresets((v) => !v)}
                  />
                </CardContent>
              </Card>
            </div>
          </section>
        </main>
      </div>
    </div>
  );
};

export default Dashboard;

// Helpers
function truncateId(id: string): string {
  if (id.length <= 12) return id;
  return `${id.slice(0, 6)}...${id.slice(-4)}`;
}

function BarList({
  items,
  showAll = false,
  onToggle,
  truncateLabel = false,
}: {
  items: GroupItem[];
  showAll?: boolean;
  onToggle?: () => void;
  truncateLabel?: boolean;
}) {
  const max = Math.max(1, ...items.map((i) => i.count));
  const limit = 7;
  const visible = showAll ? items : items.slice(0, limit);
  return (
    <div className="space-y-3">
      <ul className="space-y-2">
        {visible.map((it) => {
          const widthPct = Math.max(4, Math.round((it.count / max) * 100));
          const label = truncateLabel ? truncateId(it.key) : it.key;
          return (
            <li key={it.key} className="text-sm">
              <div className="flex items-center gap-3">
                <Tooltip>
                  <TooltipTrigger asChild>
                    <span className="w-44 truncate" title={label}>
                      {label}
                    </span>
                  </TooltipTrigger>
                  <TooltipContent>{it.key}</TooltipContent>
                </Tooltip>
                <div className="flex-1">
                  <div className="h-2 rounded bg-muted relative overflow-hidden">
                    <div
                      className="absolute left-0 top-0 h-2 bg-primary"
                      style={{ width: `${widthPct}%` }}
                    />
                  </div>
                </div>
                <div className="w-10 text-right font-medium">{it.count}</div>
              </div>
            </li>
          );
        })}
      </ul>
      {items.length > limit && onToggle ? (
        <button
          type="button"
          className="text-xs text-primary hover:underline"
          onClick={onToggle}
        >
          {showAll ? "Show less" : "Show more"}
        </button>
      ) : null}
    </div>
  );
}
