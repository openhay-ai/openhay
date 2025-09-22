import { FormEvent, useEffect, useRef, useState } from "react";
import { Textarea } from "@/components/ui/textarea";
import { Button } from "@/components/ui/button";
import { Paperclip, Send, Linkedin } from "lucide-react";
import { useToast } from "@/hooks/use-toast";
import AttachmentList from "@/components/AttachmentList";

export type PromptInputProps = {
  onSubmit?: (value: string, files?: File[]) => void | Promise<void>;
  placeholder?: string;
  ctaLabel?: string;
  className?: string;
  fixed?: boolean;
  disabled?: boolean;
  onOverlayHeightChange?: (height: number) => void;
};

export const PromptInput = ({
  onSubmit,
  placeholder = "Nhập câu hỏi bất kì...",
  ctaLabel = "Gửi",
  className,
  fixed = false,
  disabled = false,
  onOverlayHeightChange,
}: PromptInputProps) => {
  const [value, setValue] = useState("");
  const [files, setFiles] = useState<File[]>([]);
  const { toast } = useToast();
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);
  const formRef = useRef<HTMLFormElement | null>(null);
  const overlayRef = useRef<HTMLDivElement | null>(null);

  const MIN_HEIGHT = 40; // px (~1-2 lines, tailwind h-10)
  const MAX_HEIGHT = 192; // px (tailwind max-h-48)

  // Local per-file attachment size limit: 5 MB
  const MAX_FILE_BYTES = 5 * 1024 * 1024;
  const isOversizeFile = (file: File): boolean => file.size > MAX_FILE_BYTES;
  const formatMb = (bytes: number): string =>
    (bytes / (1024 * 1024)).toFixed(1);

  const adjustTextareaSize = () => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    const next = Math.min(el.scrollHeight, MAX_HEIGHT);
    el.style.height = `${Math.max(next, MIN_HEIGHT)}px`;
    el.style.overflowY = el.scrollHeight > MAX_HEIGHT ? "auto" : "hidden";
  };

  const ACCEPT = [
    "image/*",
    "audio/*",
    "video/*",
    ".pdf",
    ".txt",
    ".csv",
    ".xls",
    ".xlsx",
    ".html",
    ".md",
    ".markdown",
  ].join(",");

  const removeAt = (idx: number) => {
    setFiles((prev) => prev.filter((_, i) => i !== idx));
  };

  // type label logic moved to AttachmentList

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (disabled) return;
    const trimmed = value.trim();
    if (!trimmed && files.length === 0) return;

    // Guard: prevent sending if any attachment exceeds 5 MB
    if (files.length > 0) {
      const overs = files.filter((f) => isOversizeFile(f));
      if (overs.length > 0) {
        const names = overs
          .slice(0, 2)
          .map((f) => `${f.name} (${formatMb(f.size)} MB)`)
          .join(", ");
        const more = overs.length > 2 ? ` và ${overs.length - 2} tệp khác` : "";
        toast({
          variant: "destructive",
          title: "Tệp quá lớn",
          description: `${names}${more}. Giới hạn mỗi tệp là 5 MB.`,
        });
        return;
      }
    }

    if (onSubmit) {
      const filesSnapshot = files.slice();
      const valueSnapshot = trimmed;
      // Optimistically clear UI immediately
      setValue("");
      setFiles([]);
      if (fileInputRef.current) fileInputRef.current.value = "";
      try {
        await onSubmit(valueSnapshot, filesSnapshot);
        // Keep cleared on success
      } catch (err: any) {
        // Restore previous state on error and show toast
        setValue(valueSnapshot);
        setFiles(filesSnapshot);
        console.log(err);
        const description =
          typeof err?.message === "string" && err.message.trim().length > 0
            ? err.message
            : "Đã xảy ra lỗi khi gửi. Vui lòng thử lại.";
        toast({ variant: "destructive", title: "Gửi thất bại", description });
      }
      // After submit, ensure textarea size is recalculated
      requestAnimationFrame(adjustTextareaSize);
      return;
    }
  };

  useEffect(() => {
    adjustTextareaSize();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [value]);

  // Measure fixed overlay height to reserve scroll space
  const measureOverlay = () => {
    const el = overlayRef.current;
    if (!el) return;
    const h = el.offsetHeight;
    if (h) {
      if (typeof onOverlayHeightChange === "function") onOverlayHeightChange(h);
    }
  };
  useEffect(() => {
    measureOverlay();
    window.addEventListener("resize", measureOverlay);
    return () => window.removeEventListener("resize", measureOverlay);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  useEffect(() => {
    requestAnimationFrame(measureOverlay);
  }, [value, files.length]);

  const formEl = (
    <form ref={formRef} onSubmit={handleSubmit} className={className ?? "mt-0"}>
      <div className="rounded-2xl border bg-card p-2 shadow-md">
        {files.length > 0 ? (
          <AttachmentList files={files} onRemoveFile={removeAt} />
        ) : null}

        <div className="flex flex-col gap-2">
          {/* Row 1: Auto-growing textarea */}
          <Textarea
            ref={textareaRef}
            value={value}
            onChange={(e) => setValue(e.target.value)}
            placeholder={placeholder}
            className="min-h-[40px] max-h-48 border-0 focus-visible:ring-0 focus-visible:ring-offset-0 outline-none resize-none text-base w-full bg-transparent"
            aria-label="Ô nhập câu hỏi"
            onKeyDown={(e) => {
              const composing = (e as any)?.nativeEvent?.isComposing === true;
              if (e.key === "Enter" && !e.shiftKey && !composing) {
                e.preventDefault();
                if (!disabled) formRef.current?.requestSubmit();
              }
            }}
          />

          {/* Row 2: Actions */}
          <div className="flex items-center">
            <input
              ref={fileInputRef}
              type="file"
              multiple
              accept={ACCEPT}
              className="hidden"
              onChange={(e) => {
                const picked = Array.from(e.target.files ?? []);
                setFiles((prev) => {
                  const byKey = new Set(
                    prev.map((f) => f.name + ":" + f.size + ":" + f.type)
                  );
                  const dedup = picked.filter(
                    (f) => !byKey.has(f.name + ":" + f.size + ":" + f.type)
                  );
                  const invalid = dedup.filter((f) => isOversizeFile(f));
                  const valid = dedup.filter((f) => !isOversizeFile(f));
                  if (invalid.length > 0) {
                    const names = invalid
                      .slice(0, 2)
                      .map((f) => `${f.name} (${formatMb(f.size)} MB)`)
                      .join(", ");
                    const more =
                      invalid.length > 2
                        ? ` và ${invalid.length - 2} tệp khác`
                        : "";
                    toast({
                      variant: "destructive",
                      title: "Tệp quá lớn",
                      description: `${names}${more}. Giới hạn mỗi tệp là 5 MB.`,
                    });
                  }
                  const next = valid.length > 0 ? [...prev, ...valid] : prev;
                  return next;
                });
                if (fileInputRef.current) fileInputRef.current.value = "";
              }}
            />
            <Button
              type="button"
              variant="ghost"
              size="icon"
              aria-label="Đính kèm"
              onClick={() => fileInputRef.current?.click()}
              disabled={disabled}
            >
              <Paperclip />
            </Button>
            <div className="flex-1" />
            <Button
              type="submit"
              variant="hero"
              size="xl"
              aria-label="Gửi câu hỏi"
              disabled={disabled}
            >
              <Send className="mr-1" /> {ctaLabel}
            </Button>
          </div>
          {/* Removed inline limit note per UX feedback; oversize handled via toast */}
        </div>
      </div>
      <div className="mt-2 text-xs text-muted-foreground text-center flex items-center justify-center gap-2">
        <a
          href="https://github.com/openhay-ai/openhay"
          target="_blank"
          rel="noopener noreferrer"
          className="flex items-center gap-1"
        >
          <svg
            role="img"
            viewBox="0 0 24 24"
            xmlns="http://www.w3.org/2000/svg"
            className="w-4 h-4"
          >
            <title>GitHub</title>
            <path d="M12 .297c-6.63 0-12 5.373-12 12 0 5.303 3.438 9.8 8.205 11.385.6.113.82-.258.82-.577 0-.285-.01-1.04-.015-2.04-3.338.724-4.042-1.61-4.042-1.61C4.422 18.07 3.633 17.7 3.633 17.7c-1.087-.744.084-.729.084-.729 1.205.084 1.838 1.236 1.838 1.236 1.07 1.835 2.809 1.305 3.495.998.108-.776.417-1.305.76-1.605-2.665-.3-5.466-1.332-5.466-5.93 0-1.31.465-2.38 1.235-3.22-.135-.303-.54-1.523.105-3.176 0 0 1.005-.322 3.3 1.23.96-.267 1.98-.399 3-.405 1.02.006 2.04.138 3 .405 2.28-1.552 3.285-1.23 3.285-1.23.645 1.653.24 2.873.12 3.176.765.84 1.23 1.91 1.23 3.22 0 4.61-2.805 5.625-5.475 5.92.42.36.81 1.096.81 2.22 0 1.606-.015 2.896-.015 3.286 0 .315.21.69.825.57C20.565 22.092 24 17.592 24 12.297c0-6.627-5.373-12-12-12" />
          </svg>
          openhay-ai
        </a>
        <span className="text-gray-400">•</span>
        <a
          href="https://www.linkedin.com/in/tisu/"
          target="_blank"
          rel="noopener noreferrer"
          className="flex items-center gap-1"
        >
          <Linkedin className="w-4 h-4" /> quang
        </a>
        <span className="text-gray-400">•</span>
        <a
          href="https://www.linkedin.com/in/tran-nhat-quy-16b25720b/"
          target="_blank"
          rel="noopener noreferrer"
          className="flex items-center gap-1"
        >
          <Linkedin className="w-4 h-4" /> quy
        </a>
      </div>
    </form>
  );

  if (!fixed) {
    return formEl;
  }

  return (
    <div className="fixed bottom-0 left-0 right-0 z-40 md:pl-64">
      <div
        ref={overlayRef}
        className="mx-auto max-w-3xl px-3 md:px-6 pb-4 pt-2 bg-gradient-to-t from-background/95 to-background/60 backdrop-blur supports-[backdrop-filter]:bg-background/60"
      >
        {formEl}
      </div>
    </div>
  );
};

export default PromptInput;
