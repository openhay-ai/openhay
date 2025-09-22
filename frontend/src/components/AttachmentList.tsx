import { FileIcon } from "lucide-react";
import { cn } from "@/lib/utils";

type AttachmentMedia = {
  src?: string;
  mediaType?: string;
  identifier?: string;
};

type AttachmentListProps = {
  files?: File[];
  media?: AttachmentMedia[];
  onRemoveFile?: (index: number) => void;
  className?: string;
  variant?: "default" | "onAccent";
};

const getTypeLabelFromMimeOrName = (mime?: string, name?: string): string => {
  const t = mime || "";
  if (t.includes("pdf")) return "PDF";
  if (t.startsWith("image/")) return "Image";
  if (t.startsWith("audio/")) return "Audio";
  if (t.startsWith("video/")) return "Video";
  if (t.includes("word")) return "DOCX";
  if (t.includes("spreadsheet")) return "XLSX";
  if (t.includes("csv")) return "CSV";
  if (t.includes("plain")) return "TXT";
  const ext = (name || "").split(".").pop();
  return (ext || "File").toUpperCase();
};

const formatMb = (bytes?: number): string => {
  if (typeof bytes !== "number" || isNaN(bytes)) return "";
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
};

export const AttachmentList = ({
  files,
  media,
  onRemoveFile,
  className,
  variant = "default",
}: AttachmentListProps) => {
  const hasFiles = Array.isArray(files) && files.length > 0;
  const hasMedia = Array.isArray(media) && media.length > 0;
  if (!hasFiles && !hasMedia) return null;

  return (
    <div
      className={cn(
        "mb-2 flex items-center gap-2 overflow-x-auto p-1",
        className
      )}
    >
      {files?.map((f, idx) => {
        const isImage = (f.type || "").startsWith("image/");
        if (isImage) {
          return (
            <div
              key={f.name + f.size + idx}
              className="relative h-12 w-12 flex-shrink-0"
            >
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={URL.createObjectURL(f)}
                alt={f.name}
                className={cn(
                  "h-12 w-12 rounded-md object-cover border",
                  variant === "onAccent" ? "border-white/30" : "border-gray-200"
                )}
              />
              <div
                className={cn(
                  "absolute bottom-0 left-0 right-0 text-[9px] leading-none px-1 py-0.5 truncate",
                  variant === "onAccent"
                    ? "bg-black/40 text-white"
                    : "bg-black/50 text-white"
                )}
                title={formatMb(f.size)}
              >
                {formatMb(f.size)}
              </div>
              {onRemoveFile ? (
                <button
                  type="button"
                  aria-label="Xóa tệp"
                  className="absolute -top-1 -right-1 h-5 w-5 rounded-full bg-gray-900 text-white grid place-items-center text-[10px]"
                  onClick={() => onRemoveFile(idx)}
                >
                  ×
                </button>
              ) : null}
            </div>
          );
        }
        return (
          <div
            key={f.name + f.size + idx}
            className={cn(
              "relative flex items-center gap-2 rounded-xl px-3 py-2 min-w-[220px] max-w-[260px]",
              variant === "onAccent"
                ? "border border-white/25 bg-white/10 text-white"
                : "border border-gray-200 bg-gray-50 text-gray-900"
            )}
          >
            <div
              className={cn(
                "h-8 w-8 rounded-full grid place-items-center",
                variant === "onAccent"
                  ? "bg-white/90 text-black ring-1 ring-white/50"
                  : "bg-gray-200 text-gray-800 ring-1 ring-gray-300"
              )}
            >
              <FileIcon className="h-4 w-4" strokeWidth={2} />
            </div>
            <div className="min-w-0">
              <div className="text-xs font-medium truncate" title={f.name}>
                {f.name}
              </div>
              <div
                className={cn(
                  "text-[10px] uppercase flex items-center gap-2",
                  variant === "onAccent" ? "text-white/70" : "text-gray-600"
                )}
              >
                <span>{getTypeLabelFromMimeOrName(f.type, f.name)}</span>
                <span
                  className={cn(
                    "normal-case",
                    variant === "onAccent" ? "text-white/70" : "text-gray-500"
                  )}
                >
                  {formatMb(f.size)}
                </span>
              </div>
            </div>
            {onRemoveFile ? (
              <button
                type="button"
                aria-label="Xóa tệp"
                className="absolute -top-1 -right-1 h-5 w-5 rounded-full bg-gray-900 text-white grid place-items-center text-[10px]"
                onClick={() => onRemoveFile(idx)}
              >
                ×
              </button>
            ) : null}
          </div>
        );
      })}

      {media?.map((m, idx) => {
        const isImage = (m.mediaType || "").startsWith("image/");
        if (isImage && m.src) {
          return (
            <div
              key={(m.identifier || m.src) + idx}
              className="relative h-12 w-12 flex-shrink-0"
            >
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={m.src}
                alt={m.identifier || "image"}
                className={cn(
                  "h-12 w-12 rounded-md object-cover border",
                  variant === "onAccent" ? "border-white/30" : "border-gray-200"
                )}
              />
            </div>
          );
        }
        const displayName = m.identifier || m.mediaType || "Tệp";
        return (
          <div
            key={(m.identifier || m.mediaType || "file") + idx}
            className={cn(
              "relative flex items-center gap-2 rounded-xl px-3 py-2 min-w-[220px] max-w-[260px]",
              variant === "onAccent"
                ? "border border-white/25 bg-white/10 text-white"
                : "border border-gray-200 bg-gray-50 text-gray-900"
            )}
          >
            <div
              className={cn(
                "h-8 w-8 rounded-full grid place-items-center",
                variant === "onAccent"
                  ? "bg-white/90 text-black ring-1 ring-white/50"
                  : "bg-gray-200 text-gray-800 ring-1 ring-gray-300"
              )}
            >
              <FileIcon className="h-4 w-4" strokeWidth={2} />
            </div>
            <div className="min-w-0">
              <div className="text-xs font-medium truncate" title={displayName}>
                {displayName}
              </div>
              <div
                className={cn(
                  "text-[10px] uppercase",
                  variant === "onAccent" ? "text-white/70" : "text-gray-600"
                )}
              >
                {getTypeLabelFromMimeOrName(m.mediaType, m.identifier)}
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
};

export default AttachmentList;
