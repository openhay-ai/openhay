import SidebarNav from "@/components/layout/SidebarNav";
import { Button } from "@/components/ui/button";
import { Trash2 } from "lucide-react";
import { deleteHistoryEntry, getHistoryEntries, HistoryEntry, clearHistory } from "@/lib/history";
import { useEffect, useState } from "react";

const History = () => {
  const [items, setItems] = useState<HistoryEntry[]>([]);

  useEffect(() => {
    setItems(getHistoryEntries());
  }, []);

  const handleDelete = (id: string) => {
    deleteHistoryEntry(id);
    setItems(getHistoryEntries());
  };

  const handleClear = () => {
    clearHistory();
    setItems([]);
  };

  return (
    <div className="min-h-screen flex w-full overflow-hidden">
      <SidebarNav />
      <div className="md:flex-auto overflow-hidden w-full">
        <main className="h-full overflow-auto w-full px-3 md:px-6">
          <header className="flex justify-between items-center gap-3 py-4">
            <h1 className="text-2xl font-semibold">Lịch sử</h1>
            {items.length > 0 && (
              <Button variant="outline" size="sm" onClick={handleClear}>Xóa tất cả</Button>
            )}
          </header>

          <section className="max-w-3xl mx-auto pb-12">
            {items.length === 0 ? (
              <p className="text-sm text-muted-foreground">Chưa có lịch sử trò chuyện.</p>
            ) : (
              <ul className="divide-y rounded-lg border bg-card">
                {items.map((it) => (
                  <li key={it.id} className="p-4 flex items-start gap-3">
                    <div className="flex-1">
                      <div className="text-sm font-medium truncate">
                        {it.content}
                      </div>
                      <div className="text-xs text-muted-foreground mt-1">
                        {new Date(it.createdAt).toLocaleString("vi-VN")} {it.featureKey ? `• ${it.featureKey}` : ""}
                      </div>
                    </div>
                    <Button variant="ghost" size="icon" onClick={() => handleDelete(it.id)} aria-label="Xóa">
                      <Trash2 className="size-4" />
                    </Button>
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


