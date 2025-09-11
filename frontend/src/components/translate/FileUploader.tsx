import { useCallback, useMemo, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { Trash2, UploadCloud } from "lucide-react";

export type UploadStatus = "idle" | "reading" | "complete" | "failed";

export type UploadItem = {
  id: string;
  file: File;
  name: string;
  size: number;
  type: string;
  progress: number;
  status: UploadStatus;
  dataUrl?: string; // filled when reading completes
  error?: string;
};

export type FileUploaderProps = {
  accept: string;
  multiple?: boolean;
  onChange?: (items: UploadItem[]) => void;
};

function formatBytes(bytes: number): string {
  if (bytes === 0) return "0 B";
  const k = 1024;
  const sizes = ["B", "KB", "MB", "GB", "TB"];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(2))} ${sizes[i]}`;
}

const FileUploader = ({ accept, multiple = true, onChange }: FileUploaderProps) => {
  const [items, setItems] = useState<UploadItem[]>([]);
  const inputRef = useRef<HTMLInputElement | null>(null);
  const [dragOver, setDragOver] = useState(false);

  const startRead = (item: UploadItem) => {
    const reader = new FileReader();
    reader.onprogress = (e) => {
      if (!e.lengthComputable) return;
      const pct = Math.min(100, Math.round((e.loaded / e.total) * 100));
      setItems((prev) => {
        const next: UploadItem[] = prev.map((x) =>
          x.id === item.id ? { ...x, progress: pct, status: "reading" as UploadStatus } : x
        );
        if (onChange) onChange(next);
        return next;
      });
    };
    reader.onerror = () => {
      setItems((prev) => {
        const next: UploadItem[] = prev.map((x) =>
          x.id === item.id
            ? { ...x, status: "failed" as UploadStatus, error: String(reader.error || "Read error") }
            : x
        );
        if (onChange) onChange(next);
        return next;
      });
    };
    reader.onload = () => {
      const dataUrl = String(reader.result || "");
      setItems((prev) => {
        const next: UploadItem[] = prev.map((x) =>
          x.id === item.id
            ? { ...x, status: "complete" as UploadStatus, progress: 100, dataUrl }
            : x
        );
        if (onChange) onChange(next);
        return next;
      });
    };
    reader.readAsDataURL(item.file);
  };

  const addFiles = (files: File[]) => {
    const newItems: UploadItem[] = files.map((f) => ({
      id: crypto.randomUUID(),
      file: f,
      name: f.name,
      size: f.size,
      type: f.type,
      progress: 0,
      status: "idle",
    }));
    setItems((prev) => {
      const next = multiple ? [...prev, ...newItems] : [...newItems];
      // start reading each
      next.forEach((it) => startRead(it));
      if (onChange) onChange(next);
      return next;
    });
  };

  const onDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragOver(false);
    const files = Array.from(e.dataTransfer.files || []);
    if (files.length) addFiles(files);
  }, []);

  const removeAt = (id: string) => {
    setItems((prev) => {
      const next = prev.filter((x) => x.id !== id);
      if (onChange) onChange(next);
      return next;
    });
  };

  const retry = (id: string) => {
    const it = items.find((x) => x.id === id);
    if (!it) return;
    setItems((prev) => prev.map((x) => (x.id === id ? { ...x, progress: 0, status: "idle", error: undefined } : x)));
    startRead({ ...it, progress: 0, status: "idle", error: undefined });
  };

  return (
    <div className="space-y-3">
      <div
        className={`flex flex-col items-center justify-center gap-2 rounded-lg border-2 border-dashed p-6 text-center ${dragOver ? "border-primary bg-muted/30" : "border-muted-foreground/25"}`}
        onDragEnter={(e) => {
          e.preventDefault();
          e.stopPropagation();
          setDragOver(true);
        }}
        onDragOver={(e) => {
          e.preventDefault();
          e.stopPropagation();
        }}
        onDragLeave={(e) => {
          e.preventDefault();
          e.stopPropagation();
          setDragOver(false);
        }}
        onDrop={onDrop}
      >
        <UploadCloud className="text-muted-foreground" />
        <div>
          <button type="button" className="underline" onClick={() => inputRef.current?.click()}>
            Bấm để tải lên
          </button>
          <span className="text-muted-foreground"> hoặc kéo thả</span>
        </div>
        <div className="text-xs text-muted-foreground">PDF, DOC, XLS, TXT, MD, HTML, Hình ảnh</div>
        <input
          ref={inputRef}
          type="file"
          accept={accept}
          multiple={multiple}
          className="hidden"
          onChange={(e) => {
            const files = Array.from(e.target.files || []);
            if (files.length) addFiles(files);
            if (inputRef.current) inputRef.current.value = "";
          }}
        />
      </div>

      {items.length > 0 && (
        <div className="space-y-2">
          {items.map((it) => (
            <div key={it.id} className={`rounded-md border p-3 ${it.status === "failed" ? "border-destructive" : ""}`}>
              <div className="flex items-center gap-2">
                <div className="w-10 text-center text-xs font-medium rounded bg-muted px-2 py-1">
                  {it.type?.includes("pdf") ? "PDF" : it.type?.includes("jpeg") || it.type?.includes("png") ? "IMG" : (it.name.split(".").pop() || "FILE").toUpperCase()}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center justify-between">
                    <span className="truncate">{it.name}</span>
                    <span className="text-xs text-muted-foreground ml-2 shrink-0">{formatBytes(it.size)}</span>
                  </div>
                  <div className="mt-1">
                    <Progress value={it.status === "complete" ? 100 : it.progress} className="max-w-full" />
                  </div>
                  <div className="mt-1 text-xs">
                    {it.status === "reading" && <span className="text-muted-foreground">Đang tải...</span>}
                    {it.status === "complete" && <span className="text-emerald-600">Hoàn tất</span>}
                    {it.status === "failed" && (
                      <span className="text-destructive">Thất bại</span>
                    )}
                  </div>
                  {it.status === "failed" && (
                    <button className="text-xs underline mt-1" type="button" onClick={() => retry(it.id)}>
                      Thử lại
                    </button>
                  )}
                </div>
                <Button variant="ghost" size="icon" onClick={() => removeAt(it.id)} aria-label="Xoá tệp">
                  <Trash2 className="size-4" />
                </Button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default FileUploader;
