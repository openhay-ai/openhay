import SidebarNav from "@/components/layout/SidebarNav";
import { useEffect, useState } from "react";
import { getConversationsUrl } from "@/lib/api";
import { useNavigate, useSearchParams } from "react-router-dom";
import { authFetch } from "@/lib/auth";

type ConversationListItem = {
  id: string;
  feature_key?: string;
  title?: string | null;
  created_at: string; // ISO timestamp
  updated_at: string; // ISO timestamp
  content_preview?: string | null;
};

const History = () => {
  const [items, setItems] = useState<ConversationListItem[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();

  useEffect(() => {
    (async () => {
      try {
        const res = await authFetch(getConversationsUrl());
        if (!res.ok) throw new Error(String(res.status));
        const data = (await res.json()) as { items: ConversationListItem[] };
        setItems(Array.isArray(data.items) ? data.items : []);
      } catch {
        setItems([]);
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  return (
    <div className="min-h-screen flex w-full overflow-hidden">
      <SidebarNav />
      <div className="md:flex-auto overflow-hidden w-full md:ml-64">
        <main className="h-full overflow-auto w-full px-3 md:px-6">
          <header className="flex justify-between items-center gap-3 py-4">
            <h1 className="text-2xl font-semibold">Lịch sử</h1>
          </header>

          <section className="max-w-3xl mx-auto pb-12">
            {loading ? (
              <p className="text-sm text-muted-foreground">Đang tải...</p>
            ) : items.length === 0 ? (
              <p className="text-sm text-muted-foreground">Chưa có lịch sử trò chuyện.</p>
            ) : (
              <ul className="divide-y rounded-lg border bg-card">
                {items.map((it) => (
                  <li
                    key={it.id}
                    className="p-4 flex items-start gap-3 cursor-pointer hover:bg-muted/50"
                    onClick={() => {
                      const params = new URLSearchParams(searchParams);
                      navigate(`/t/${it.id}?${params.toString()}`);
                    }}
                  >
                    <div className="flex-1 min-w-0">
                      <div className="text-sm font-medium truncate">
                        {it.title || it.content_preview || "Không có tiêu đề"}
                      </div>
                      <div className="text-xs text-muted-foreground mt-1">
                        {new Date(it.created_at).toLocaleString("vi-VN")} {it.feature_key ? `• ${it.feature_key}` : ""}
                      </div>
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </section>
        </main>
      </div>
    </div>
  );
};

export default History;
