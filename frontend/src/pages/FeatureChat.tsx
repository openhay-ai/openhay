import SidebarNav from "@/components/layout/SidebarNav";
import { Button } from "@/components/ui/button";
import PromptInput from "@/components/PromptInput";
import { useParams, useSearchParams, useNavigate, useLocation } from "react-router-dom";
import { useEffect, useRef, useState, useMemo } from "react";
import { Markdown } from "@/components/Markdown";
// no slug needed; route is /t/{uuid}
import { getChatSseUrl, getChatHistoryUrl } from "@/lib/api";
import { Loader2 } from "lucide-react";
import {
  Carousel,
  CarouselContent,
  CarouselItem,
  CarouselNext,
  CarouselPrevious,
} from "@/components/ui/carousel";
import { Card, CardContent } from "@/components/ui/card";

type ChatMessage = {
  id: string;
  role: "user" | "assistant" | "system" | "tool";
  content: string;
  toolName?: string;
  results?: any[];
};

// Temporary preset mapping until backend API wiring
const PRESET_DISPLAY: Record<string, { title: string; description?: string } | undefined> = {
  default: { title: "AI Tìm kiếm", description: "Hỏi nhanh, trích nguồn." },
  homework: { title: "Giải bài tập", description: "Giải thích từng bước, có ví dụ." },
  writing: { title: "AI Viết văn", description: "Viết mượt, tự nhiên, mạch lạc." },
  translate: { title: "Dịch", description: "Dịch giữ nguyên thuật ngữ, tên riêng." },
  summary: { title: "Tóm tắt", description: "Tóm tắt trọng tâm ngắn gọn." },
  mindmap: { title: "Mindmap", description: "Lập sơ đồ ý dạng cây." },
};

// Default params
const PRESET_DEFAULT_PARAMS: Record<string, Record<string, unknown>> = {
  default: {},
  homework: { show_steps: true },
  writing: { length: "medium", tone: "trung_lap" },
  translate: { source_lang: "vi", target_lang: "en" },
  summary: { bullet_count: 5 },
  mindmap: { max_depth: 3 },
};

const initialMessagesFor = (typeParam: string | undefined): ChatMessage[] => {
  const effectiveType = typeParam && PRESET_DISPLAY[typeParam] ? typeParam : "default";
  const preset = PRESET_DISPLAY[effectiveType];
  if (!preset) return [];
  return [
    {
      id: "welcome",
      role: "assistant",
      content: `Bạn đang ở chế độ: ${preset.title}. Hãy nhập câu hỏi để bắt đầu.`,
    },
  ];
};

// moved to utils: slugifyVi, shortId

const FeatureChat = () => {
  const { threadId } = useParams<{ threadId?: string }>();
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const location = useLocation();
  const typeParam = searchParams.get("type") ?? undefined;
  const [messages, setMessages] = useState<ChatMessage[]>(() => initialMessagesFor(typeParam));
  const messagesRef = useRef<ChatMessage[]>(messages);
  const featureParams = useMemo(() => PRESET_DEFAULT_PARAMS[typeParam ?? "default"] ?? {}, [typeParam]);

  // reset initial message when feature type changes
  useEffect(() => {
    setMessages(initialMessagesFor(typeParam));
  }, [typeParam]);

  // keep a ref to latest messages so async handlers can access up-to-date list
  useEffect(() => {
    messagesRef.current = messages;
  }, [messages]);

  // If navigating from root after first stream, preload messages passed via navigation state
  useEffect(() => {
    const st = (location.state as any) || {};
    const preload = st.preloadMessages as ChatMessage[] | undefined;
    if (threadId && preload && preload.length > 0) {
      setMessages(preload);
    }
    // no separate preload for search results; they are embedded as tool messages now

    // On hard refresh or direct visit to /t/{uuid}, fetch history
    const uuidMatch = threadId?.match(
      /[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}/
    );
    const canonicalId = uuidMatch ? uuidMatch[0] : undefined;
    if (!canonicalId) return;

    (async () => {
      try {
        const res = await fetch(getChatHistoryUrl(canonicalId));
        if (!res.ok) return;
        const data = (await res.json()) as {
          conversation_id: string;
          messages: any[];
        };
        // Map to UI messages from new ConversationHistoryResponse parts
        const mapped: ChatMessage[] = [];
        for (let idx = 0; idx < data.messages.length; idx++) {
          const part: any = data.messages[idx];
          const id = `${data.conversation_id}-${idx}`;
          const partKind: string | undefined = part?.part_kind;
          if (partKind === "user-prompt") {
            const content = typeof part?.content === "string" ? part.content : "";
            mapped.push({ id, role: "user", content });
          } else if (partKind === "text") {
            const content = typeof part?.content === "string" ? part.content : "";
            mapped.push({ id, role: "assistant", content });
          } else if (partKind === "tool-return" && part?.tool_name === "search_web") {
            const results = Array.isArray(part?.content) ? part.content : [];
            mapped.push({ id, role: "tool", content: "", toolName: "search_web", results });
          } else {
            // ignore other parts (e.g., tool-call, other tools) for UI
          }
        }
        // If nothing in history, keep preset welcome
        setMessages((prev) => (mapped.length > 0 ? mapped : prev));
      } catch {
        // ignore fetch errors; keep current state
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [threadId]);

  // auto-send when ?q= is present (works for both root and thread routes).
  // After consuming q once, remove it from the URL so revisits won't trigger another send.
  useEffect(() => {
    const q = searchParams.get("q");
    if (!q) return;
    (async () => {
      await handleSend(q);
      // Only remove q if we are already in a thread; otherwise, let the thread page remove it
      if (threadId) {
        const params = new URLSearchParams(searchParams);
        params.delete("q");
        navigate({ pathname: location.pathname, search: params.toString() ? `?${params.toString()}` : "" }, { replace: true });
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [threadId]);

  const title = PRESET_DISPLAY[typeParam ?? "default"]?.title ?? "Trò chuyện";
  const description = PRESET_DISPLAY[typeParam ?? "default"]?.description;
  const endRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    return () => {
      if (abortRef.current) abortRef.current.abort();
    };
  }, []);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const abortRef = useRef<AbortController | null>(null);

  const handleSend = async (value: string) => {
    const userMsg: ChatMessage = { id: crypto.randomUUID(), role: "user", content: value };
    const assistantMsg: ChatMessage = { id: crypto.randomUUID(), role: "assistant", content: "" };
    setMessages((prev) => [...prev, userMsg, assistantMsg]);

    // cancel previous stream if any
    if (abortRef.current) {
      abortRef.current.abort();
    }
    const ac = new AbortController();
    abortRef.current = ac;

    try {
      const extractUuidFromThreadId = (raw?: string): string | undefined => {
        if (!raw) return undefined;
        // Try to find a UUID anywhere in the string
        const uuidMatch = raw.match(/[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}/);
        return uuidMatch ? uuidMatch[0] : undefined;
      };

      const payload: Record<string, unknown> = { message: value };
      const canonicalId = extractUuidFromThreadId(threadId);
      if (canonicalId) payload.conversation_id = canonicalId;

      const res = await fetch(getChatSseUrl(), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
        signal: ac.signal,
      });
      if (!res.ok || !res.body) {
        throw new Error(`Bad response: ${res.status}`);
      }

      const reader = res.body.getReader();
      const decoder: any = new TextDecoder("utf-8");
      let buffer = "";

      const commitChunk = (chunkContent: string) => {
        setMessages((prev) =>
          prev.map((m) =>
            m.id === assistantMsg.id
              ? { ...m, content: m.content + chunkContent }
              : m
          )
        );
      };

      // Read SSE stream manually and parse events
      let createdConversationId: string | null = null;
      while (true) {
        const { done, value: chunk } = await reader.read();
        if (done) break;
        const bytes: any = chunk as any;
        buffer += decoder.decode(bytes, { stream: true });

        // Process complete SSE messages separated by double newlines
        let idx: number;
        // eslint-disable-next-line no-cond-assign
        while ((idx = buffer.indexOf("\n\n")) !== -1) {
          const rawEvent = buffer.slice(0, idx);
          buffer = buffer.slice(idx + 2);

          // Parse event name and data lines
          const lines = rawEvent.split(/\r?\n/);
          let eventName = "message";
          let dataLines: string[] = [];
          for (const line of lines) {
            if (line.startsWith("event:")) {
              eventName = line.slice(6).trim();
            } else if (line.startsWith("data:")) {
              dataLines.push(line.slice(5).trim());
            }
          }
          const dataStr = dataLines.join("\n");

          console.log(eventName, dataStr);

          if (eventName === "conversation_created") {
            try {
              const parsed = JSON.parse(dataStr) as { conversation_id?: string };
              const cid = parsed?.conversation_id;
              if (cid) {
                createdConversationId = cid;
              }
            } catch {
              // ignore navigation errors
            }
          } else if (eventName === "ai_message") {
            try {
              const parsed = JSON.parse(dataStr) as { chunk?: { content?: string } };
              const chunk = parsed?.chunk?.content ?? "";
              if (chunk) commitChunk(chunk);
            } catch {
              // ignore parse errors per chunk
            }
          } else if (eventName === "search_results") {
            // Append search_web tool results as their own message
            try {
              const parsed = JSON.parse(dataStr) as { results?: any[] };
              const results = Array.isArray(parsed?.results) ? parsed.results : [];
              const toolMsg: ChatMessage = {
                id: crypto.randomUUID(),
                role: "tool",
                content: "",
                toolName: "search_web",
                results,
              };
              setMessages((prev) => {
                const idx = prev.findIndex((m) => m.id === assistantMsg.id);
                if (idx === -1) {
                  return [...prev, toolMsg];
                }
                const next = prev.slice();
                next.splice(idx, 0, toolMsg);
                return next;
              });
            } catch {
              // ignore
            }
          } else if (eventName === "error") {
            // surface error to assistant bubble
            try {
              const err = JSON.parse(dataStr);
              commitChunk(`\n\n> Lỗi: ${err?.error || "Không xác định"}`);
            } catch {
              commitChunk("\n\n> Lỗi không xác định khi xử lý phản hồi.");
            }
          }
        }
      }

      // flush remainder if any (not expected for SSE, but defensive)
      if (buffer.trim().length > 0) {
        try {
          const lines = buffer.split(/\r?\n/);
          let dataLines: string[] = [];
          for (const line of lines) if (line.startsWith("data:")) dataLines.push(line.slice(5).trim());
          const parsed = JSON.parse(dataLines.join("\n"));
          const chunk = parsed?.chunk?.content ?? "";
          if (chunk) commitChunk(chunk);
        } catch {
          // ignore
        }
      }

      // Only now navigate to /t/{uuid} (after stream completes) to avoid aborting the stream
      if (!canonicalId && createdConversationId) {
        const params = new URLSearchParams();
        if (typeParam) params.set("type", typeParam);
        navigate(`/t/${createdConversationId}?${params.toString()}` , {
          replace: true,
          state: { preloadMessages: messagesRef.current },
        });
      }
    } catch (e) {
      setMessages((prev) =>
        prev.map((m) =>
          m.id === assistantMsg.id
            ? { ...m, content: m.content + "\n\n> Không thể kết nối đến máy chủ." }
            : m
        )
      );
    }
  };

  const SourceCard = ({ item, index }: { item: any; index: number }) => {
    const title: string = item?.title ?? item?.url ?? "Nguồn";
    const url: string = item?.url ?? "";
    const host: string = item?.meta_url?.hostname || item?.profile?.long_name || "";
    const favicon: string =
      item?.meta_url?.favicon || item?.profile?.img || "/favicon.ico";
    return (
      <Card className="h-full">
        <CardContent className="p-4 flex items-start gap-3">
          <div className="flex items-center justify-center h-6 w-6 rounded-full bg-secondary text-xs">
            {index + 1}
          </div>
          <div className="flex-1 overflow-hidden">
            <a
              href={url}
              target="_blank"
              rel="noreferrer"
              className="line-clamp-2 text-sm hover:underline"
            >
              {title}
            </a>
            <div className="mt-2 flex items-center gap-2 text-xs text-muted-foreground">
              {favicon ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img src={favicon} alt="icon" className="h-4 w-4 rounded-sm" />
              ) : null}
              <span className="truncate">{host}</span>
            </div>
          </div>
        </CardContent>
      </Card>
    );
  };

  return (
    <div className="min-h-screen flex w-full overflow-hidden">
      <SidebarNav />

      <div className="md:flex-auto overflow-hidden w-full">
        <main className="h-full overflow-auto w-full px-3 md:px-6">
          <header className="flex justify-between items-center gap-3 py-4">
            <div>
              <h1 className="text-2xl font-semibold">{title}</h1>
              {description && (
                <p className="text-muted-foreground text-sm">{description}</p>
              )}
            </div>
          </header>

          <section className="max-w-3xl mx-auto pb-40">
            <div className="flex flex-col gap-4 mt-6">
              {/* Messages */}
              <div className="space-y-3">
                {messages.map((m) => {
                  if (m.role === "tool" && m.toolName === "search_web") {
                    const results = Array.isArray(m.results) ? m.results : [];
                    return (
                      <div key={m.id} className="flex justify-start">
                        <div className="max-w-[80%] w-full">
                          <div className="rounded-lg border bg-muted/30 p-3">
                            <div className="flex items-center justify-between">
                              <div className="text-sm font-medium text-muted-foreground">
                                {results.length} nguồn
                              </div>
                            </div>
                            <div className="relative mt-3">
                              <Carousel opts={{ align: "start" }} className="w-full">
                                <CarouselContent>
                                  {results.map((it, idx) => (
                                    <CarouselItem
                                      key={idx}
                                      className="basis-full sm:basis-1/2 lg:basis-1/3"
                                    >
                                      <SourceCard item={it} index={idx} />
                                    </CarouselItem>
                                  ))}
                                </CarouselContent>
                                <CarouselPrevious className="-left-5" />
                                <CarouselNext className="-right-5" />
                              </Carousel>
                            </div>
                          </div>
                        </div>
                      </div>
                    );
                  }

                  return (
                    <div
                      key={m.id}
                      className={
                        m.role === "user" ? "flex justify-end" : "flex justify-start"
                      }
                    >
                      <div
                        className={
                          "max-w-[80%] rounded-2xl px-4 py-2 text-sm " +
                          (m.role === "user" ? "bg-emerald-600 text-white" : "bg-card border")
                        }
                      >
                        {m.role === "assistant" ? (
                          m.content.trim().length === 0 ? (
                            <div className="flex items-center gap-2 text-muted-foreground">
                              <Loader2 className="size-4 animate-spin" />
                              <span>Để xem...</span>
                            </div>
                          ) : (
                            <Markdown content={m.content} />
                          )
                        ) : (
                          m.content
                        )}
                      </div>
                    </div>
                  );
                })}
                <div ref={endRef} />
              </div>

              <PromptInput onSubmit={handleSend} fixed />
            </div>
          </section>
        </main>
      </div>
    </div>
  );
};

export default FeatureChat;


