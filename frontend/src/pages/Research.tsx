import SidebarNav from "@/components/layout/SidebarNav";
import PromptInput from "@/components/PromptInput";
import { Markdown } from "@/components/Markdown";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { useNavigate } from "react-router-dom";
import { ChevronDown, Loader2, Clock } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { getResearchSseUrl } from "@/lib/api";
import SourceCard from "@/components/SourceCard";
import { normalizeUrlForMatch } from "@/lib/utils";
import ChatMessage from "@/components/ChatMessage";

type ThinkingEntry = { id: string; content: string; open: boolean; ts: number };

type SearchQueryEntry = {
  id: string; // tool_call_id from backend
  query: string;
  results: Array<{ title?: string; url?: string }>;
  open: boolean;
};

const Research = () => {
  const navigate = useNavigate();
  const [isStreaming, setIsStreaming] = useState(false);
  const [thinkingEntries, setThinkingEntries] = useState<ThinkingEntry[]>([]);
  const [leadPlan, setLeadPlan] = useState<string>("");
  const [queries, setQueries] = useState<Record<string, SearchQueryEntry>>({});
  const [queryOrder, setQueryOrder] = useState<string[]>([]);
  const [finalReport, setFinalReport] = useState<string>("");
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [timelineVisible, setTimelineVisible] = useState(false);
  const [hasSubmitted, setHasSubmitted] = useState(false);
  const [userMessage, setUserMessage] = useState<string>("");
  const [overlayHeight, setOverlayHeight] = useState<number>(120);

  // Timeline states
  const [step1Done, setStep1Done] = useState(false); // kế hoạch
  const [step2Shown, setStep2Shown] = useState(false); // nghiên cứu
  const [step3Writing, setStep3Writing] = useState(false); // viết báo cáo
  const [step3Done, setStep3Done] = useState(false);
  const [step1Open, setStep1Open] = useState(true);
  const [step2Open, setStep2Open] = useState(true);
  const [step3Open, setStep3Open] = useState(true);
  const [showLoader, setShowLoader] = useState(false);
  const [gotFirstThinking, setGotFirstThinking] = useState(false);
  const [startAt, setStartAt] = useState<number | null>(null);
  const [elapsedSec, setElapsedSec] = useState<number>(0);
  const timerRef = useRef<number | null>(null);

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
    setOverlayHeight(0);
    setUserMessage(value);
    setShowLoader(true);
    setStartAt(Date.now());
    setElapsedSec(0);
    if (timerRef.current) {
      window.clearInterval(timerRef.current);
      timerRef.current = null;
    }
    timerRef.current = window.setInterval(() => {
      setElapsedSec((s) => s + 1);
    }, 1000);

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

      const pushThinking = (text: string, ts?: number) => {
        setThinkingEntries((prev) => [
          ...prev,
          { id: crypto.randomUUID(), content: text, open: true, ts: ts ?? Date.now() },
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

          if (eventName === "conversation_created") {
            try {
              const parsed = JSON.parse(dataStr) as { conversation_id?: string };
              if (parsed?.conversation_id) {
                setConversationId(parsed.conversation_id);
              }
            } catch {}
          } else if (eventName === "lead_thinking") {
            try {
              const parsed = JSON.parse(dataStr) as { thinking?: string; ts?: number };
              const t = parsed?.thinking?.trim();
              if (t) pushThinking(t, parsed?.ts);
              if (!gotFirstThinking) setGotFirstThinking(true);
              setShowLoader(false);
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
              if (timerRef.current) {
                window.clearInterval(timerRef.current);
                timerRef.current = null;
              }
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
            <div id={`q-${entry.id}`} className="mt-3 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
              {entry.results.map((r, idx) => (
                <SourceCard key={idx} item={r} index={idx} />
              ))}
            </div>
          ) : null}
        </CardContent>
      </Card>
    );
  };

  // ThinkingItem replaced by shared ChatMessage

  const queryEntries = useMemo(
    () => queryOrder.map((id) => queries[id]).filter(Boolean),
    [queries, queryOrder]
  );

  const totalSources = useMemo(() => {
    let total = 0;
    for (const q of queryEntries) total += q?.results?.length || 0;
    return total;
  }, [queryEntries]);

  useEffect(() => {
    return () => {
      if (timerRef.current) {
        window.clearInterval(timerRef.current);
        timerRef.current = null;
      }
    };
  }, []);

  const formatTime = (sec: number): string => {
    const m = Math.floor(sec / 60)
      .toString()
      .padStart(2, "0");
    const s = (sec % 60).toString().padStart(2, "0");
    return `${m}:${s}`;
  };

  // Build link metadata for Markdown hover previews
  const linkMeta = useMemo(() => {
    const map: Record<string, { url: string; title?: string; description?: string; hostname?: string; favicon?: string }> = {};
    for (const q of Object.values(queries)) {
      for (const it of q.results) {
        const url: string | undefined = (it as any)?.url;
        if (!url) continue;
        const key = normalizeUrlForMatch(url);
        if (map[key]) continue;
        let hostname: string | undefined = (it as any)?.meta_url?.hostname || (it as any)?.profile?.long_name;
        let favicon: string | undefined = (it as any)?.meta_url?.favicon || (it as any)?.profile?.img;
        let title: string | undefined = (it as any)?.title;
        let description: string | undefined = (it as any)?.description;
        if (!hostname) {
          try {
            const u = new URL(url);
            hostname = u.hostname;
          } catch {}
        }
        map[key] = { url, title, description, hostname, favicon };
      }
    }
    return map;
  }, [queries]);

  return (
    <div className="min-h-screen flex w-full overflow-hidden">
      <SidebarNav />

      <div className="md:flex-auto overflow-hidden w-full md:ml-64">
        <main className="h-full overflow-auto w-full px-3 md:px-6">
          <header className="flex justify-between items-center gap-3 py-4">
            <div>
              <h1 className="text-2xl font-semibold">Nghiên cứu chuyên sâu</h1>
              <p className="text-muted-foreground text-sm">Trợ lý AI tự động nghiên cứu, phân tích và tổng hợp thông tin.</p>
            </div>
          </header>

          <section className="max-w-3xl mx-auto" style={{ paddingBottom: Math.max(overlayHeight + 16, 64) }}>
            <div className="flex flex-col gap-4 mt-6">
              {/* Intro helper when idle */}
              {!timelineVisible && !hasSubmitted ? (
                <div className="rounded-lg border bg-muted/30 p-4 text-sm text-muted-foreground space-y-2">
                  <p>
                    Khi bạn đặt câu hỏi, AI sẽ hoạt động như một trợ lý cần mẫn, thực hiện một quy trình nghiên cứu chuyên sâu có thể <b>mất vài phút</b>.
                  </p>
                  <p>AI sẽ tự động:</p>
                  <ul className="list-disc pl-5 space-y-1">
                    <li>
                      <strong>Lên kế hoạch:</strong> Phân tích chủ đề để xác định các hướng đi quan trọng.
                    </li>
                    <li>
                      <strong>Tìm kiếm đa chiều:</strong> Truy vấn nhiều nguồn thông tin đáng tin cậy trên web.
                    </li>
                    <li>
                      <strong>Tổng hợp báo cáo:</strong> Đọc hiểu, chắt lọc và viết thành một câu trả lời hoàn chỉnh kèm trích dẫn.
                    </li>
                  </ul>
                  <p>Kết quả nhận được sẽ giúp bạn tiết kiệm hàng giờ tìm tòi và có được một cái nhìn sâu sắc về vấn đề.</p>
                </div>
              ) : null}

              {/* User message bubble */}
              {userMessage ? (
                <ChatMessage
                  message={{ id: "user-msg", role: "user", content: userMessage }}
                />
              ) : null}

              {/* Typing loader shown until first thinking arrives */}
              {showLoader ? (
                <div className="flex justify-start">
                  <div className="max-w-[80%] rounded-2xl px-4 py-2 text-sm bg-card border">
                    <div className="flex items-center gap-2 text-muted-foreground">
                      <Loader2 className="size-4 animate-spin" />
                      <span>Để xem...</span>
                    </div>
                  </div>
                </div>
              ) : null}

              {/* Thinking boxes (appear before the timeline) */}
              {thinkingEntries.map((t) => (
                <ChatMessage
                  key={t.id}
                  message={{ id: t.id, role: "thinking", content: t.content }}
                  expanded={t.open}
                  onToggleExpanded={(next) =>
                    setThinkingEntries((prev) =>
                      prev.map((x) => (x.id === t.id ? { ...x, open: next } : x))
                    )
                  }
                />
              ))}

              {/* Timeline */}
              {timelineVisible ? (
                <div className="rounded-lg border bg-muted/30 p-4 space-y-4">
                  <div className="flex items-center justify-between">
                    <div className="text-sm font-medium text-muted-foreground">Tiến trình nghiên cứu</div>
                    <div className="text-xs text-muted-foreground flex items-center gap-1">
                      <Clock className="size-3" />
                      <span className="tabular-nums">{formatTime(elapsedSec)}</span>
                    </div>
                  </div>
                  {/* Step 1 */}
                  <div className="flex items-start gap-3">
                    <div className={`mt-1 h-2 w-2 rounded-full ${step1Done ? "bg-emerald-600" : "bg-amber-500"}`} />
                    <div className="flex-1">
                      <button
                        type="button"
                        className="flex w-full items-center justify-between text-left"
                        onClick={() => setStep1Open((o) => !o)}
                        aria-expanded={step1Open}
                      >
                        <div className="text-sm font-medium">
                          {step1Done ? "Đã tạo kế hoạch" : "Đang tạo kế hoạch"}
                        </div>
                        <ChevronDown className={`size-4 transition-transform ${step1Open ? "rotate-180" : "rotate-0"}`} />
                      </button>
                      {step1Open && leadPlan ? (
                        <div className="mt-2 text-sm">
                          <Markdown content={leadPlan} />
                        </div>
                      ) : null}
                    </div>
                  </div>

                  {/* Step 2 */}
                  {step2Shown ? (
                    <div className="flex items-start gap-3">
                      <div className={`mt-1 h-2 w-2 rounded-full ${step3Writing || step3Done ? "bg-emerald-600" : "bg-amber-500"}`} />
                      <div className="flex-1">
                        <button
                          type="button"
                          className="flex w-full items-center justify-between text-left"
                          onClick={() => setStep2Open((o) => !o)}
                          aria-expanded={step2Open}
                        >
                          <div className="text-sm font-medium flex items-center gap-2">
                            {step3Writing || step3Done ? "Nghiên cứu hoàn tất" : "Đang nghiên cứu"}
                            <span className="inline-flex items-center justify-center h-4 min-w-[16px] px-1 rounded-full bg-secondary text-[10px]">
                              {totalSources} nguồn
                            </span>
                          </div>
                          <ChevronDown className={`size-4 transition-transform ${step2Open ? "rotate-180" : "rotate-0"}`} />
                        </button>
                        {step2Open ? (
                          <div className="mt-2 space-y-2">
                            {queryEntries.map((q) => (
                              <QueryItem key={q.id} entry={q} />
                            ))}
                          </div>
                        ) : null}
                      </div>
                    </div>
                  ) : null}

                  {/* Step 3 */}
                  {step3Writing || step3Done ? (
                    <div className="flex items-start gap-3">
                      <div className={`mt-1 h-2 w-2 rounded-full ${step3Done ? "bg-emerald-600" : "bg-amber-500"}`} />
                      <div className="flex-1">
                        <button
                          type="button"
                          className="flex w-full items-center justify-between text-left"
                          onClick={() => setStep3Open((o) => !o)}
                          aria-expanded={step3Open}
                        >
                          <div className="text-sm font-medium">{step3Done ? "Đã hoàn tất báo cáo!" : "Đang viết báo cáo cuối cùng"}</div>
                          <ChevronDown className={`size-4 transition-transform ${step3Open ? "rotate-180" : "rotate-0"}`} />
                        </button>
                      </div>
                    </div>
                  ) : null}
                </div>
              ) : null}

              {/* Final report as AI bubble */}
              {finalReport ? (
                <ChatMessage
                  message={{ id: "final-report", role: "assistant", content: finalReport }}
                  linkMeta={linkMeta}
                />
              ) : null}

              {conversationId ? (
                <div className="flex justify-start">
                  <Button
                    className="mt-3"
                    variant="default"
                    onClick={() => navigate(`/t/${conversationId}`)}
                  >
                    Tiếp tục trò chuyện
                  </Button>
                </div>
              ) : null}

              <div ref={endRef} />

              {!hasSubmitted ? (
                <PromptInput
                  onSubmit={handleSend}
                  fixed
                  disabled={isStreaming}
                  placeholder="Chủ đề bạn muốn nghiên cứu là gì?"
                  ctaLabel="Nghiên cứu"
                  onOverlayHeightChange={(h) => setOverlayHeight(h)}
                />
              ) : null}
            </div>
          </section>
        </main>
      </div>
    </div>
  );
};

export default Research;
