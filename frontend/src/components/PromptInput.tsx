import { FormEvent, useEffect, useRef, useState } from "react";
import { Textarea } from "@/components/ui/textarea";
import { Button } from "@/components/ui/button";
import { Paperclip, Send } from "lucide-react";
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
    ".doc",
    ".docx",
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
        console.log(err)
        const description = typeof err?.message === "string" && err.message.trim().length > 0
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
                const list = Array.from(e.target.files ?? []);
                setFiles((prev) => {
                  const byName = new Set(prev.map((f) => f.name + ":" + f.size + ":" + f.type));
                  const dedup = list.filter((f) => !byName.has(f.name + ":" + f.size + ":" + f.type));
                  return [...prev, ...dedup];
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
            <Button type="submit" variant="hero" size="xl" aria-label="Gửi câu hỏi" disabled={disabled}>
              <Send className="mr-1" /> {ctaLabel}
            </Button>
          </div>
        </div>
      </div>
      <p className="mt-2 text-xs text-muted-foreground text-center">
        Khi đặt câu hỏi, bạn đồng ý với <a className="underline" href="#">Điều khoản</a> và <a className="underline" href="#">Chính sách quyền riêng tư</a>.
      </p>
    </form>
  );

  if (!fixed) {
    return formEl;
  }

  return (
    <div className="fixed bottom-0 left-0 right-0 z-40 md:pl-64">
      <div ref={overlayRef} className="mx-auto max-w-3xl px-3 md:px-6 pb-4 pt-2 bg-gradient-to-t from-background/95 to-background/60 backdrop-blur supports-[backdrop-filter]:bg-background/60">
        {formEl}
      </div>
    </div>
  );
};

export default PromptInput;
