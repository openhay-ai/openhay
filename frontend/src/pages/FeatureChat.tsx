import SidebarNav from "@/components/layout/SidebarNav";
import { Button } from "@/components/ui/button";
import PromptInput from "@/components/PromptInput";
import { useParams, useSearchParams } from "react-router-dom";
import { useEffect, useRef, useState } from "react";
import { addHistoryEntry } from "@/lib/history";
import { Markdown } from "@/components/Markdown";
import { getChatSseUrl } from "@/lib/api";
import { Loader2 } from "lucide-react";

type ChatMessage = {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
};

// Temporary preset mapping until backend API wiring
const PRESET_DISPLAY: Record<string, { title: string; description?: string } | undefined> = {
  ai_tim_kiem: { title: "AI Tìm kiếm", description: "Hỏi nhanh, có trích nguồn khi có." },
  giai_bai_tap: { title: "Giải bài tập", description: "Giải thích từng bước, có ví dụ." },
  ai_viet_van: { title: "AI Viết văn", description: "Viết mượt, tự nhiên, mạch lạc." },
  dich: { title: "Dịch", description: "Dịch giữ nguyên thuật ngữ, tên riêng." },
  tom_tat: { title: "Tóm tắt", description: "Tóm tắt trọng tâm ngắn gọn." },
  mindmap: { title: "Mindmap", description: "Lập sơ đồ ý dạng cây." },
};

// Default params mirroring backend seeds in `backend/db_init.py`
const PRESET_DEFAULT_PARAMS: Record<string, Record<string, unknown>> = {
  ai_tim_kiem: {},
  giai_bai_tap: { show_steps: true },
  ai_viet_van: { length: "medium", tone: "trung_lap" },
  dich: { source_lang: "vi", target_lang: "en" },
  tom_tat: { bullet_count: 5 },
  mindmap: { max_depth: 3 },
};

const initialMessagesFor = (key: string | undefined): ChatMessage[] => {
  if (!key) return [];
  const preset = PRESET_DISPLAY[key];
  if (!preset) return [];
  return [
    {
      id: "welcome",
      role: "assistant",
      content: `Bạn đang ở chế độ: ${preset.title}. Hãy nhập câu hỏi để bắt đầu.`,
    },
  ];
};

const FeatureChat = () => {
  const { featureKey } = useParams<{ featureKey: string }>();
  const [searchParams] = useSearchParams();
  const [messages, setMessages] = useState<ChatMessage[]>(() => initialMessagesFor(featureKey));
  const featureParams = PRESET_DEFAULT_PARAMS[featureKey ?? ""] ?? {};

  // reset initial message when feature changes
  useEffect(() => {
    setMessages(initialMessagesFor(featureKey));
  }, [featureKey]);

  // auto-send when ?q= is present
  useEffect(() => {
    const q = searchParams.get("q");
    if (!q) return;
    // Clear param from URL UX-wise is optional; we keep it for now
    handleSend(q);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const title = PRESET_DISPLAY[featureKey ?? ""]?.title ?? "Trò chuyện";
  const description = PRESET_DISPLAY[featureKey ?? ""]?.description;
  const endRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    return () => {
      if (abortRef.current) abortRef.current.abort();
    };
  }, [featureKey]);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const abortRef = useRef<AbortController | null>(null);

  const handleSend = async (value: string) => {
    addHistoryEntry({ featureKey: featureKey, content: value });

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
      const res = await fetch(getChatSseUrl(), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: value }),
        signal: ac.signal,
      });
      if (!res.ok || !res.body) {
        throw new Error(`Bad response: ${res.status}`);
      }

      const reader = res.body.getReader();
      const decoder = new TextDecoder("utf-8");
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
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });

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

          if (eventName === "ai_message") {
            try {
              const parsed = JSON.parse(dataStr) as { chunk?: { content?: string } };
              const chunk = parsed?.chunk?.content ?? "";
              if (chunk) commitChunk(chunk);
            } catch {
              // ignore parse errors per chunk
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
            <div className="flex items-center gap-2">
              <Button variant="ghost" size="sm">Đăng nhập</Button>
              <Button variant="hero" size="sm">Tạo tài khoản miễn phí</Button>
            </div>
          </header>

          <section className="max-w-3xl mx-auto pb-40">
            <div className="flex flex-col gap-4 mt-6">
              {/* Messages */}
              <div className="space-y-3">
                {messages.map((m) => (
                  <div
                    key={m.id}
                    className={
                      m.role === "user"
                        ? "flex justify-end"
                        : "flex justify-start"
                    }
                  >
                    <div
                      className={
                        "max-w-[80%] rounded-2xl px-4 py-2 text-sm " +
                        (m.role === "user"
                          ? "bg-emerald-600 text-white"
                          : "bg-card border")
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
                ))}
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


