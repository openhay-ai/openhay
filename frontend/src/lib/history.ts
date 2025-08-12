export type HistoryEntry = {
  id: string;
  featureKey?: string;
  content: string;
  createdAt: number; // epoch ms
};

const STORAGE_KEY = "aihay_history_v1";

function readAll(): HistoryEntry[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw) as HistoryEntry[];
    if (!Array.isArray(parsed)) return [];
    return parsed;
  } catch {
    return [];
  }
}

function writeAll(entries: HistoryEntry[]): void {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(entries));
}

export function addHistoryEntry(entry: Omit<HistoryEntry, "id" | "createdAt"> & { id?: string; createdAt?: number }): HistoryEntry {
  const record: HistoryEntry = {
    id: entry.id ?? crypto.randomUUID(),
    featureKey: entry.featureKey,
    content: entry.content,
    createdAt: entry.createdAt ?? Date.now(),
  };
  const all = readAll();
  all.unshift(record);
  writeAll(all);
  return record;
}

export function getHistoryEntries(): HistoryEntry[] {
  return readAll();
}

export function deleteHistoryEntry(id: string): void {
  const all = readAll().filter((e) => e.id !== id);
  writeAll(all);
}

export function clearHistory(): void {
  writeAll([]);
}


