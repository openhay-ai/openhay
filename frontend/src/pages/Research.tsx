import SidebarNav from "@/components/layout/SidebarNav";
import PromptInput from "@/components/PromptInput";
import { Markdown } from "@/components/Markdown";
import { Card, CardContent } from "@/components/ui/card";
import { ChevronDown, Loader2 } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { getResearchSseUrl } from "@/lib/api";

type ThinkingEntry = { id: string; content: string; open: boolean };

type SearchQueryEntry = {
  id: string; // tool_call_id from backend
  query: string;
  results: Array<{ title?: string; url?: string }>;
  open: boolean;
};

const Research = () => {
  const [isStreaming, setIsStreaming] = useState(false);
  const [thinkingEntries, setThinkingEntries] = useState<ThinkingEntry[]>([]);
  const [leadPlan, setLeadPlan] = useState<string>("");
  const [queries, setQueries] = useState<Record<string, SearchQueryEntry>>({});
  const [queryOrder, setQueryOrder] = useState<string[]>([]);
  const [finalReport, setFinalReport] = useState<string>("");
  const [timelineVisible, setTimelineVisible] = useState(false);
  const [hasSubmitted, setHasSubmitted] = useState(false);
  const [userMessage, setUserMessage] = useState<string>("");

  // Timeline states
  const [step1Done, setStep1Done] = useState(false); // kế hoạch
  const [step2Shown, setStep2Shown] = useState(false); // nghiên cứu
  const [step3Writing, setStep3Writing] = useState(false); // viết báo cáo
  const [step3Done, setStep3Done] = useState(false);

  const endRef = useRef<HTMLDivElement | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [thinkingEntries, queries, leadPlan, finalReport]);

  useEffect(() => {
    return () => {
      if (abortRef.current) abortRef.current.abort();
    };
  }, []);

  const handleSend = async (value: string) => {
    if (isStreaming) return;
    // reset state for new run
    setThinkingEntries([]);
    setLeadPlan("");
    setQueries({});
    setQueryOrder([]);
    setFinalReport("");
    setStep1Done(false);
    setStep2Shown(false);
    setStep3Writing(false);
    setStep3Done(false);
    setTimelineVisible(false);
    setHasSubmitted(true);
    setUserMessage(value);

    const ac = new AbortController();
    abortRef.current = ac;
    setIsStreaming(true);

    try {
      const res = await fetch(getResearchSseUrl(), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: value }),
        signal: ac.signal,
      });
      if (!res.ok || !res.body) throw new Error(`Bad response: ${res.status}`);

      const reader = res.body.getReader();
      const decoder: any = new TextDecoder("utf-8");
      let buffer = "";

      const pushThinking = (text: string) => {
        setThinkingEntries((prev) => [
          ...prev,
          { id: crypto.randomUUID(), content: text, open: true },
        ]);
      };

      while (true) {
        const { done, value: chunk } = await reader.read();
        if (done) break;
        buffer += decoder.decode(chunk as any, { stream: true });

        let idx: number;
        // parse SSE frames
        // eslint-disable-next-line no-cond-assign
        while ((idx = buffer.indexOf("\n\n")) !== -1) {
          const raw = buffer.slice(0, idx);
          buffer = buffer.slice(idx + 2);
          const lines = raw.split(/\r?\n/);
          let eventName = "message";
          const dataLines: string[] = [];
          for (const line of lines) {
            if (line.startsWith("event:")) eventName = line.slice(6).trim();
            else if (line.startsWith("data:")) dataLines.push(line.slice(5).trim());
          }
          const dataStr = dataLines.join("\n");

          if (eventName === "lead_thinking") {
            try {
              const parsed = JSON.parse(dataStr) as { thinking?: string };
              const t = parsed?.thinking?.trim();
              if (t) pushThinking(t);
            } catch {}
          } else if (eventName === "lead_answer") {
            setLeadPlan((prev) => (prev ? prev : JSON.parse(dataStr).answer || ""));
            setStep1Done(true);
            setTimelineVisible(true);
          } else if (eventName === "web_search_query") {
            try {
              const parsed = JSON.parse(dataStr) as { id?: string; query?: string };
              if (!parsed?.id) continue;
              setStep2Shown(true);
              setQueries((prev) => ({
                ...prev,
                [parsed.id as string]: {
                  id: parsed.id as string,
                  query: parsed.query || "",
                  results: [],
                  open: false,
                },
              }));
              setQueryOrder((o) => (o.includes(parsed.id as string) ? o : [...o, parsed.id as string]));
            } catch {}
          } else if (eventName === "web_search_results") {
            try {
              const parsed = JSON.parse(dataStr) as { id?: string; results?: any[] };
              const rid = parsed?.id as string | undefined;
              if (!rid) continue;
              const newResults = Array.isArray(parsed.results) ? parsed.results : [];
              setQueries((prev) => {
                const cur = prev[rid];
                if (!cur) return prev;
                return {
                  ...prev,
                  [rid]: { ...cur, results: [...cur.results, ...newResults] },
                };
              });
            } catch {}
          } else if (eventName === "subagent_completed") {
            setStep3Writing(true);
          } else if (eventName === "final_report") {
            try {
              const parsed = JSON.parse(dataStr) as { report?: string };
              setFinalReport(parsed?.report || "");
              setStep3Done(true);
            } catch {}
          }
        }
      }
    } catch (e) {
      // no-op for now
    } finally {
      setIsStreaming(false);
      abortRef.current = null;
    }
  };

  const QueryItem = ({ entry }: { entry: SearchQueryEntry }) => {
    const count = entry.results.length;
    return (
      <Card className="h-full">
        <CardContent className="p-4">
          <button
            type="button"
            className="flex w-full items-center justify-between hover:opacity-80"
            onClick={() =>
              setQueries((prev) => ({
                ...prev,
                [entry.id]: { ...entry, open: !entry.open },
              }))
            }
            aria-expanded={entry.open}
            aria-controls={`q-${entry.id}`}
          >
            <div className="text-left">
              <div className="text-sm font-medium">{entry.query}</div>
              <div className="text-xs text-muted-foreground">{count} nguồn</div>
            </div>
            <ChevronDown className={`size-4 transition-transform ${entry.open ? "rotate-180" : "rotate-0"}`} />
          </button>
          {entry.open ? (
            <div id={`q-${entry.id}`} className="mt-3 space-y-2">
              {entry.results.map((r, idx) => (
                <div key={idx} className="text-sm">
                  <a
                    href={r?.url || "#"}
                    target="_blank"
                    rel="noreferrer"
                    className="hover:underline"
                  >
                    {r?.title || r?.url || "Nguồn"}
                  </a>
                </div>
              ))}
            </div>
          ) : null}
        </CardContent>
      </Card>
    );
  };

  const ThinkingItem = ({ entry }: { entry: ThinkingEntry }) => {
    return (
      <div className="flex justify-start">
        <div className="max-w-[80%] w-full">
          <div className="rounded-lg border bg-muted/30 p-3">
            <button
              type="button"
              className="flex w-full items-center justify-between hover:opacity-80"
              onClick={() =>
                setThinkingEntries((prev) =>
                  prev.map((t) => (t.id === entry.id ? { ...t, open: !t.open } : t))
                )
              }
              aria-expanded={entry.open}
              aria-controls={`think-${entry.id}`}
            >
              <div className="text-sm font-medium text-muted-foreground">Thought process</div>
              <ChevronDown className={`size-4 transition-transform ${entry.open ? "rotate-180" : "rotate-0"}`} />
            </button>
            {entry.open ? (
              <div id={`think-${entry.id}`} className="mt-2 text-sm">
                <Markdown content={entry.content} />
              </div>
            ) : null}
          </div>
        </div>
      </div>
    );
  };

  const queryEntries = useMemo(
    () => queryOrder.map((id) => queries[id]).filter(Boolean),
    [queries, queryOrder]
  );

  return (
    <div className="min-h-screen flex w-full overflow-hidden">
      <SidebarNav />

      <div className="md:flex-auto overflow-hidden w-full md:ml-64">
        <main className="h-full overflow-auto w-full px-3 md:px-6">
          <header className="flex justify-between items-center gap-3 py-4">
            <div>
              <h1 className="text-2xl font-semibold">Tìm sâu</h1>
              <p className="text-muted-foreground text-sm">Nghiên cứu đa nguồn, có dòng thời gian.</p>
            </div>
          </header>

          <section className="max-w-3xl mx-auto pb-40">
            <div className="flex flex-col gap-4 mt-6">
              {/* Intro helper when idle */}
              {!timelineVisible && !hasSubmitted ? (
                <div className="rounded-lg border bg-muted/30 p-4 text-sm text-muted-foreground">
                  Nhập câu hỏi bất kì để bắt đầu nghiên cứu. Hệ thống sẽ tạo kế hoạch, tra cứu nhiều nguồn và tổng hợp báo cáo cuối cùng.
                </div>
              ) : null}

              {/* User message bubble */}
              {userMessage ? (
                <div className="flex justify-end">
                  <div className="max-w-[80%] rounded-2xl px-4 py-2 text-sm bg-emerald-600 text-white">
                    {userMessage}
                  </div>
                </div>
              ) : null}

              {/* Timeline */}
              {timelineVisible ? (
                <div className="space-y-3">
                  <div className="flex items-start gap-3">
                    <div className={`mt-1 h-2 w-2 rounded-full ${step1Done ? "bg-emerald-600" : "bg-amber-500"}`} />
                    <div className="flex-1">
                      <div className="text-sm font-medium">
                        {step1Done ? "Đã tạo kế hoạch" : "Đang tạo kế hoạch"}
                      </div>
                      {leadPlan ? (
                        <div className="mt-2 text-sm">
                          <Markdown content={leadPlan} />
                        </div>
                      ) : null}
                    </div>
                  </div>

                  {step2Shown ? (
                    <div className="flex items-start gap-3">
                      <div className="mt-1 h-2 w-2 rounded-full bg-amber-500" />
                      <div className="flex-1">
                        <div className="text-sm font-medium">Đang nghiên cứu</div>
                        <div className="mt-2 space-y-2">
                          {queryEntries.map((q) => (
                            <QueryItem key={q.id} entry={q} />
                          ))}
                        </div>
                      </div>
                    </div>
                  ) : null}

                  {step3Writing || step3Done ? (
                    <div className="flex items-start gap-3">
                      <div className={`mt-1 h-2 w-2 rounded-full ${step3Done ? "bg-emerald-600" : "bg-amber-500"}`} />
                      <div className="flex-1 text-sm font-medium">
                        {step3Done ? "Đã hoàn tất báo cáo!" : "Đang viết báo cáo cuối cùng"}
                      </div>
                    </div>
                  ) : null}
                </div>
              ) : null}

              {/* Thinking boxes */}
              {thinkingEntries.map((t) => (
                <ThinkingItem key={t.id} entry={t} />
              ))}

              {/* Final report as AI bubble */}
              {finalReport ? (
                <div className="flex justify-start">
                  <div className="max-w-[80%] rounded-2xl px-4 py-2 text-sm bg-card border">
                    <Markdown content={finalReport} />
                  </div>
                </div>
              ) : null}

              <div ref={endRef} />

              <PromptInput onSubmit={handleSend} fixed disabled={isStreaming} />
            </div>
          </section>
        </main>
      </div>
    </div>
  );
};

export default Research;
