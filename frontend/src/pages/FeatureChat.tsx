import SidebarNav from "@/components/layout/SidebarNav";
import { Button } from "@/components/ui/button";
import PromptInput from "@/components/PromptInput";
import {
  useParams,
  useSearchParams,
  useNavigate,
  useLocation,
} from "react-router-dom";
import { useEffect, useRef, useState, useMemo } from "react";
import { Markdown } from "@/components/Markdown";
import { normalizeUrlForMatch } from "@/lib/utils";
// no slug needed; route is /t/{uuid}
import { getChatSseUrl, getChatHistoryUrl } from "@/lib/api";
import { Loader2, ChevronDown } from "lucide-react";
import { Alert, AlertTitle, AlertDescription } from "@/components/ui/alert";
import {
  Carousel,
  CarouselContent,
  CarouselItem,
  CarouselNext,
  CarouselPrevious,
} from "@/components/ui/carousel";
import { Card, CardContent } from "@/components/ui/card";
import SourceCard from "@/components/SourceCard";
import AttachmentList from "@/components/AttachmentList";

type ChatMedia = {
  src: string;
  mediaType: string;
  identifier?: string;
};

type ChatMessage = {
  id: string;
  role: "user" | "assistant" | "system" | "tool" | "thinking";
  content: string;
  media?: ChatMedia[];
  toolName?: string;
  results?: any[];
};

// Temporary preset mapping until backend API wiring
const PRESET_DISPLAY: Record<
  string,
  { title: string; description?: string } | undefined
> = {
  default: { title: "AI Tìm kiếm", description: "Hỏi nhanh, trích nguồn." },
  homework: {
    title: "Giải bài tập",
    description: "Giải thích từng bước, có ví dụ.",
  },
  writing: {
    title: "AI Viết văn",
    description: "Viết mượt, tự nhiên, mạch lạc.",
  },
  translate: {
    title: "Dịch",
    description: "Dịch giữ nguyên thuật ngữ, tên riêng.",
  },
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
  const effectiveType =
    typeParam && PRESET_DISPLAY[typeParam] ? typeParam : "default";
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
  const [messages, setMessages] = useState<ChatMessage[]>(() =>
    initialMessagesFor(typeParam)
  );
  const [isStreaming, setIsStreaming] = useState<boolean>(false);
  const messagesRef = useRef<ChatMessage[]>(messages);
  const featureParams = useMemo(
    () => PRESET_DEFAULT_PARAMS[typeParam ?? "default"] ?? {},
    [typeParam]
  );
  const [sourceExpanded, setSourceExpanded] = useState<Record<string, boolean>>(
    {}
  );
  const [thinkingExpanded, setThinkingExpanded] = useState<Record<string, boolean>>(
    {}
  );
  const [overlayHeight, setOverlayHeight] = useState<number>(120);
  const [errorNotice, setErrorNotice] = useState<
    { title?: string; message: string; retryAfterSec?: number } | null
  >(null);
  const lastAttemptRef = useRef<{ value: string; files?: File[] } | null>(null);

  const normalizeBase64 = (input: string): string => {
    let out = input.replace(/-/g, "+").replace(/_/g, "/");
    const mod = out.length % 4;
    if (mod === 2) out += "==";
    else if (mod === 3) out += "=";
    else if (mod === 1) out += "==="; // extremely rare, but keep safe
    return out;
  };

  // Build URL -> metadata map from any
  // search_web and fetch_url_content tool results present in the message list
  const linkMeta = useMemo(() => {
    const map: Record<
      string,
      {
        url: string;
        title?: string;
        description?: string;
        hostname?: string;
        favicon?: string;
      }
    > = {};
    for (const m of messages) {
      if (
        m.role === "tool" &&
        (m.toolName === "search_web" || m.toolName === "fetch_url_content") &&
        Array.isArray(m.results)
      ) {
        for (const it of m.results) {
          const url: string | undefined = it?.url;
          if (!url) continue;
          const key = normalizeUrlForMatch(url);
          if (map[key]) continue;

          // For fetch_url_content results, extract hostname from URL since meta_url might not exist
          let hostname: string | undefined =
            it?.meta_url?.hostname || it?.profile?.long_name;
          let favicon: string | undefined =
            it?.meta_url?.favicon || it?.profile?.img;
          let title: string | undefined = it?.title;
          let description: string | undefined = it?.description;

          // If fetched content doesn't have title/description, use URL parts
          if (m.toolName === "fetch_url_content" && !hostname) {
            try {
              const urlObj = new URL(url);
              hostname = urlObj.hostname;
            } catch {
              // ignore invalid URL
            }
          }

          map[key] = { url, title, description, hostname, favicon };
        }
      }
    }
    return map;
  }, [messages]);

  // reset initial message when feature type changes
  useEffect(() => {
    setMessages(initialMessagesFor(typeParam));
    setSourceExpanded({});
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
      setSourceExpanded({});
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
        let idx = 0;
        while (idx < data.messages.length) {
          const part: any = data.messages[idx];
          const partKind: string | undefined = part?.part_kind;
          // Combine contiguous tool-return parts (search_web, fetch_url_content) into one message
          if (
            partKind === "tool-return" &&
            (part?.tool_name === "search_web" ||
              part?.tool_name === "fetch_url_content")
          ) {
            const currentToolName: "search_web" | "fetch_url_content" =
              part?.tool_name === "search_web"
                ? "search_web"
                : "fetch_url_content";
            const startIdx = idx;
            const combinedResults: any[] = [];
            while (idx < data.messages.length) {
              const p: any = data.messages[idx];
              const pk: string | undefined = p?.part_kind;
              if (pk === "tool-return" && p?.tool_name === currentToolName) {
                const res = Array.isArray(p?.content) ? p.content : [];
                combinedResults.push(...res);
                idx += 1;
                continue;
              }
              break;
            }
            const id = `${data.conversation_id}-${startIdx}`;
            mapped.push({
              id,
              role: "tool",
              content: "",
              toolName: currentToolName,
              results: combinedResults,
            });
            continue;
          }

          // Regular mapping for non-tool or other tool parts
          const id = `${data.conversation_id}-${idx}`;
          if (partKind === "user-prompt") {
            let content = "";
            const media: ChatMedia[] = [];
            const raw = part?.content as unknown;
            if (typeof raw === "string") {
              content = raw;
            } else if (Array.isArray(raw)) {
              for (const item of raw) {
                if (typeof item === "string") {
                  content = content ? `${content} ${item}` : item;
                  continue;
                }
                if (item && typeof item === "object") {
                  const kind: string | undefined =
                    (item as any)?.kind ?? (item as any)?.part_kind;
                  const data: unknown = (item as any)?.data;
                  const mediaType: unknown =
                    (item as any)?.media_type ?? (item as any)?.mime_type;
                  const identifier: string | undefined =
                    (item as any)?.identifier ?? (item as any)?.name;
                  if (
                    (kind === "binary" ||
                      typeof (item as any)?.data === "string") &&
                    typeof data === "string" &&
                    typeof mediaType === "string"
                  ) {
                    const src = `data:${mediaType};base64,${normalizeBase64(
                      data
                    )}`;
                    media.push({ src, mediaType, identifier });
                  }
                }
              }
            }
            if (content.trim().length === 0) {
              // Skip purely empty text prompts, but still render attachments-only prompts
              if (media.length === 0) {
                idx += 1;
                continue;
              }
            }
            mapped.push({
              id,
              role: "user",
              content,
              media: media.length ? media : undefined,
            });
          } else if (partKind === "text") {
            const content =
              typeof part?.content === "string" ? part.content : "";
            mapped.push({ id, role: "assistant", content });
          } else if (partKind === "thinking") {
            const content =
              typeof part?.content === "string" ? part.content : "";
            mapped.push({ id, role: "thinking", content });
          } else {
            // ignore other parts (e.g., tool-call, other tools) for UI
          }
          idx += 1;
        }
        // If nothing in history, keep preset welcome
        setMessages((prev) => (mapped.length > 0 ? mapped : prev));
        setSourceExpanded({});
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
    const st = (location.state as any) || {};
    const stateFiles = Array.isArray(st.files)
      ? (st.files as File[])
      : undefined;
    const hasMessage = typeof q === "string" && q.length > 0;
    const hasFiles = Array.isArray(stateFiles) && stateFiles.length > 0;
    if (!hasMessage && !hasFiles) return;
    (async () => {
      await handleSend(q ?? "", stateFiles);
      // Only remove q if we are already in a thread; otherwise, let the thread page remove it
      if (threadId) {
        const params = new URLSearchParams(searchParams);
        params.delete("q");
        navigate(
          {
            pathname: location.pathname,
            search: params.toString() ? `?${params.toString()}` : "",
          },
          { replace: true }
        );
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

  const retryLast = async () => {
    if (isStreaming) return;
    const last = lastAttemptRef.current;
    if (!last) return;
    setErrorNotice(null);
    await handleSend(last.value, last.files);
  };

  const handleSend = async (value: string, files?: File[]) => {
    if (isStreaming) return;
    // Remember last attempt for Retry
    lastAttemptRef.current = { value, files };
    // Clear any previous error banner when starting a new attempt
    setErrorNotice(null);
    // Auto-collapse all source cards except the latest one when user sends a new message
    const toolIds = messagesRef.current
      .filter(
        (m) =>
          m.role === "tool" &&
          (m.toolName === "search_web" || m.toolName === "fetch_url_content")
      )
      .map((m) => m.id);
    const lastToolId =
      toolIds.length > 0 ? toolIds[toolIds.length - 1] : undefined;
    setSourceExpanded((prev) => {
      const next = { ...prev } as Record<string, boolean>;
      for (const id of Object.keys(next)) {
        if (id !== lastToolId) next[id] = false;
      }
      return next;
    });
    let userMsg: ChatMessage;
    let assistantMsg: ChatMessage;

    // cancel previous stream if any
    if (abortRef.current) {
      abortRef.current.abort();
    }
    const ac = new AbortController();
    abortRef.current = ac;
    setIsStreaming(true);

    let sseErrorInfo: { message: string; retryAfterSec?: number } | null = null;
    try {
      const extractUuidFromThreadId = (raw?: string): string | undefined => {
        if (!raw) return undefined;
        // Try to find a UUID anywhere in the string
        const uuidMatch = raw.match(
          /[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}/
        );
        return uuidMatch ? uuidMatch[0] : undefined;
      };

      const payload: Record<string, unknown> = { message: value };
      const canonicalId = extractUuidFromThreadId(threadId);
      if (canonicalId) payload.conversation_id = canonicalId;

      // If files were provided, read and attach as base64 for backend to convert into BinaryContent
      if (files && files.length > 0) {
        const readAsDataUrl = (file: File) =>
          new Promise<string>((resolve, reject) => {
            const reader = new FileReader();
            reader.onerror = () => reject(reader.error);
            reader.onload = () => resolve(String(reader.result || ""));
            reader.readAsDataURL(file);
          });

        const dataUrls = await Promise.all(files.map(readAsDataUrl));
        const media = files.map((f, idx) => {
          const dataUrl = dataUrls[idx] || "";
          const commaIdx = dataUrl.indexOf(",");
          const base64Data =
            commaIdx >= 0 ? dataUrl.slice(commaIdx + 1) : dataUrl;
          return {
            data: base64Data,
            media_type: f.type || "application/octet-stream",
            identifier: f.name,
          };
        });
        (payload as any).media = media;

        // Prepare local preview media as data URLs for the user bubble
        const previewMedia = dataUrls
          .map((url, idx) => ({
            src: url,
            mediaType: files[idx]?.type || "application/octet-stream",
            identifier: files[idx]?.name,
          }))
          .filter((m) => m.mediaType.startsWith("image/"));

        userMsg = {
          id: crypto.randomUUID(),
          role: "user",
          content: value,
          media: previewMedia,
        };
      } else {
        userMsg = { id: crypto.randomUUID(), role: "user", content: value };
      }

      assistantMsg = {
        id: crypto.randomUUID(),
        role: "assistant",
        content: "",
      };
      setMessages((prev) => [...prev, userMsg!, assistantMsg!]);

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

      const handleToolResults = (
        toolName: "search_web" | "fetch_url_content",
        dataStr: string
      ) => {
        try {
          const parsed = JSON.parse(dataStr) as { results?: any[] };
          const results = Array.isArray(parsed?.results) ? parsed.results : [];
          const toolMsg: ChatMessage = {
            id: crypto.randomUUID(),
            role: "tool",
            content: "",
            toolName,
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
          // Expand the latest source card by default
          setSourceExpanded((prev) => ({ ...prev, [toolMsg.id]: true }));
        } catch {
          // ignore
        }
      };

      // Read SSE stream manually and parse events
      let createdConversationId: string | null = null;
      let sseError: Error | null = null;
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
              const parsed = JSON.parse(dataStr) as {
                conversation_id?: string;
              };
              const cid = parsed?.conversation_id;
              if (cid) {
                createdConversationId = cid;
              }
            } catch {
              // ignore navigation errors
            }
          } else if (eventName === "ai_message") {
            try {
              const parsed = JSON.parse(dataStr) as {
                chunk?: { content?: string };
              };
              const chunk = parsed?.chunk?.content ?? "";
              if (chunk) commitChunk(chunk);
            } catch {
              // ignore parse errors per chunk
            }
          } else if (
            eventName === "search_results" ||
            eventName === "fetch_url_results"
          ) {
            const map = {
              search_results: "search_web",
              fetch_url_results: "fetch_url_content",
            } as const;
            handleToolResults(map[eventName as keyof typeof map], dataStr);
          } else if (eventName === "error") {
            try {
              const err = JSON.parse(dataStr) as any;
              const detailsStr =
                typeof err?.details === "string" ? (err.details as string) : "";
              // Try to extract retry delay from provider details, e.g. "retryDelay': '55s'"
              const m = detailsStr.match(/retryDelay['\"]?\s*:\s*['\"](?<sec>\d+)s['\"]/);
              const sec = m && m.groups && m.groups.sec ? Number(m.groups.sec) : undefined;
              const friendly =
                typeof sec === "number"
                  ? `Hệ thống đang quá tải tạm thời. Vui lòng thử lại sau khoảng ${sec} giây.`
                  : "Hệ thống đang quá tải tạm thời. Vui lòng thử lại sau ít phút.";
              sseErrorInfo = { message: friendly, retryAfterSec: sec };
              // Show banner immediately for better UX
              setErrorNotice({ message: friendly, retryAfterSec: sec });
              // Ensure assistant bubble shows a friendly message instead of AbortError
              setMessages((prev) =>
                prev.map((m) =>
                  m.id === assistantMsg.id
                    ? {
                        ...m,
                        content:
                          m.content && m.content.trim().length > 0
                            ? m.content
                            : `> ${friendly}`,
                      }
                    : m
                )
              );
              sseError = new Error(friendly);
              // abort the stream; we'll throw after the loop ends
              try {
                ac.abort();
              } catch {}
            } catch {
              const friendly = "Đã xảy ra lỗi khi xử lý phản hồi. Vui lòng thử lại.";
              sseErrorInfo = { message: friendly };
              setErrorNotice({ message: friendly });
              sseError = new Error(friendly);
              try {
                ac.abort();
              } catch {}
            }
          }
        }
      }

      // flush remainder if any (not expected for SSE, but defensive)
      if (buffer.trim().length > 0) {
        try {
          const lines = buffer.split(/\r?\n/);
          let dataLines: string[] = [];
          for (const line of lines)
            if (line.startsWith("data:")) dataLines.push(line.slice(5).trim());
          const parsed = JSON.parse(dataLines.join("\n"));
          const chunk = parsed?.chunk?.content ?? "";
          if (chunk) commitChunk(chunk);
        } catch {
          // ignore
        }
      }

      if (sseError) {
        throw sseError;
      }

      // Only now navigate to /t/{uuid} (after stream completes) to avoid aborting the stream
      if (!canonicalId && createdConversationId) {
        const params = new URLSearchParams();
        if (typeParam) params.set("type", typeParam);
        navigate(`/t/${createdConversationId}?${params.toString()}`, {
          replace: true,
          state: { preloadMessages: messagesRef.current },
        });
      }
    } catch (e) {
      const msg =
        e instanceof Error ? e.message : "Không thể kết nối đến máy chủ.";
      setMessages((prev) =>
        prev.map((m) =>
          m.id === assistantMsg.id
            ? {
                ...m,
                content:
                  m.content && m.content.trim().length > 0
                    ? m.content
                    : `> ${msg}`,
              }
            : m
        )
      );
      // Show friendly banner with Retry option, prefer parsed SSE error info
      setErrorNotice((prev) => prev ?? (sseErrorInfo || { message: msg }));
    } finally {
      setIsStreaming(false);
      abortRef.current = null;
    }
  };

  // SourceCard moved to a shared component

  return (
    <div className="min-h-screen flex w-full overflow-hidden">
      <SidebarNav />

      <div className="md:flex-auto overflow-hidden w-full md:ml-64">
        <main className="h-full overflow-auto w-full px-3 md:px-6">
          <header className="flex justify-between items-center gap-3 py-4">
            <div>
              <h1 className="text-2xl font-semibold">{title}</h1>
              {description && (
                <p className="text-muted-foreground text-sm">{description}</p>
              )}
            </div>
          </header>

          <section
            className="max-w-3xl mx-auto"
            style={{ paddingBottom: Math.max(overlayHeight + 16, 64) }}
          >
            <div className="flex flex-col gap-4 mt-6">
              {/* Messages */}
              <div className="space-y-3">
                {messages.map((m) => {
                  if (m.role === "thinking") {
                    const isOpen = thinkingExpanded[m.id] ?? true;
                    return (
                      <div key={m.id} className="flex justify-start">
                        <div className="max-w-[80%] w-full">
                          <div className="rounded-lg border bg-muted/30 p-3">
                            <button
                              type="button"
                              className="flex w-full items-center justify-between hover:opacity-80"
                              onClick={() =>
                                setThinkingExpanded((prev) => ({
                                  ...prev,
                                  [m.id]: !isOpen,
                                }))
                              }
                              aria-expanded={isOpen}
                              aria-controls={`think-${m.id}`}
                            >
                              <div className="text-sm font-medium text-muted-foreground">
                                Tư duy
                              </div>
                              <ChevronDown
                                className={`size-4 transition-transform ${
                                  isOpen ? "rotate-180" : "rotate-0"
                                }`}
                              />
                            </button>
                            {isOpen ? (
                              <div id={`think-${m.id}`} className="mt-2 text-sm">
                                <Markdown content={m.content} />
                              </div>
                            ) : null}
                          </div>
                        </div>
                      </div>
                    );
                  }
                  if (
                    m.role === "tool" &&
                    (m.toolName === "search_web" ||
                      m.toolName === "fetch_url_content")
                  ) {
                    const results = Array.isArray(m.results) ? m.results : [];
                    const isOpen = !!sourceExpanded[m.id];
                    return (
                      <div key={m.id} className="flex justify-start">
                        <div className="max-w-[80%] w-full">
                          <div className="rounded-lg border bg-muted/30 p-3">
                            <button
                              type="button"
                              className="flex w-full items-center justify-between hover:opacity-80"
                              onClick={() =>
                                setSourceExpanded((prev) => ({
                                  ...prev,
                                  [m.id]: !isOpen,
                                }))
                              }
                              aria-expanded={isOpen}
                              aria-controls={`sources-${m.id}`}
                            >
                              <div className="text-sm font-medium text-muted-foreground">
                                {results.length} nguồn
                              </div>
                              <ChevronDown
                                className={`size-4 transition-transform ${
                                  isOpen ? "rotate-180" : "rotate-0"
                                }`}
                              />
                            </button>
                            {isOpen ? (
                              <div
                                id={`sources-${m.id}`}
                                className="relative mt-3"
                              >
                                <Carousel
                                  opts={{ align: "start" }}
                                  className="w-full"
                                >
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
                            ) : null}
                          </div>
                        </div>
                      </div>
                    );
                  }

                  return (
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
                            <Markdown content={m.content} linkMeta={linkMeta} />
                          )
                        ) : (
                          <>
                            {Array.isArray(m.media) && m.media.length > 0 ? (
                              <AttachmentList
                                media={m.media}
                                variant={
                                  m.role === "user" ? "onAccent" : "default"
                                }
                              />
                            ) : null}
                            <div>{m.content}</div>
                          </>
                        )}
                      </div>
                    </div>
                  );
                })}
                <div ref={endRef} />
              </div>

              {/* Error banner near input */}
              {errorNotice ? (
                <Alert variant="destructive">
                  <AlertTitle>{errorNotice.title ?? "Xin lỗi, hệ thống đang bận"}</AlertTitle>
                  <AlertDescription>
                    {errorNotice.message}
                  </AlertDescription>
                  <div className="mt-3 flex items-center gap-2">
                    <Button onClick={retryLast} disabled={isStreaming}>
                      Thử lại
                    </Button>
                    <Button variant="ghost" onClick={() => setErrorNotice(null)}>
                      Đóng
                    </Button>
                  </div>
                </Alert>
              ) : null}

              <PromptInput
                onSubmit={handleSend}
                fixed
                disabled={isStreaming}
                onOverlayHeightChange={(h) => setOverlayHeight(h)}
              />
            </div>
          </section>
        </main>
      </div>
    </div>
  );
};

export default FeatureChat;
