import SidebarNav from "@/components/layout/SidebarNav";
import { Button } from "@/components/ui/button";
import PromptInput from "@/components/PromptInput";
import { useParams } from "react-router-dom";
import { useEffect, useState } from "react";
import { addHistoryEntry } from "@/lib/history";

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
  const [messages, setMessages] = useState<ChatMessage[]>(() => initialMessagesFor(featureKey));
  const featureParams = PRESET_DEFAULT_PARAMS[featureKey ?? ""] ?? {};

  // reset initial message when feature changes
  useEffect(() => {
    setMessages(initialMessagesFor(featureKey));
  }, [featureKey]);

  const title = PRESET_DISPLAY[featureKey ?? ""]?.title ?? "Trò chuyện";
  const description = PRESET_DISPLAY[featureKey ?? ""]?.description;

  const handleSend = (value: string) => {
    // save to local history
    addHistoryEntry({ featureKey: featureKey, content: value });

    const newUser: ChatMessage = { id: crypto.randomUUID(), role: "user", content: value };
    const newAssistant: ChatMessage = {
      id: crypto.randomUUID(),
      role: "assistant",
      content: "(Đang phát triển) Mô phỏng trả lời cho: " + value +
        "\n\n" + "[feature params] " + JSON.stringify(featureParams),
    };
    setMessages((prev) => [...prev, newUser, newAssistant]);
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
                      {m.content}
                    </div>
                  </div>
                ))}
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


