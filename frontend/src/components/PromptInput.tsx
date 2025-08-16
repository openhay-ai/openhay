import { FormEvent, useRef, useState } from "react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { FileIcon, Paperclip, Send } from "lucide-react";
import { useToast } from "@/hooks/use-toast";
import AttachmentList from "@/components/AttachmentList";

export type PromptInputProps = {
  onSubmit?: (value: string, files?: File[]) => void | Promise<void>;
  placeholder?: string;
  ctaLabel?: string;
  className?: string;
  fixed?: boolean;
  disabled?: boolean;
};

export const PromptInput = ({
  onSubmit,
  placeholder = "Nhập câu hỏi bất kì...",
  ctaLabel = "Gửi",
  className,
  fixed = false,
  disabled = false,
}: PromptInputProps) => {
  const [value, setValue] = useState("");
  const [files, setFiles] = useState<File[]>([]);
  const { toast } = useToast();
  const fileInputRef = useRef<HTMLInputElement | null>(null);

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
      await onSubmit(trimmed, filesSnapshot);
      setValue("");
      setFiles([]);
      return;
    }
  };

  const formEl = (
    <form onSubmit={handleSubmit} className={className ?? "mt-0"}>
      <div className="rounded-2xl border bg-card p-2 shadow-md">
        {files.length > 0 ? (
          <AttachmentList files={files} onRemoveFile={removeAt} />
        ) : null}

        <div className="flex items-center gap-2">
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
          <Input
            value={value}
            onChange={(e) => setValue(e.target.value)}
            placeholder={placeholder}
            className="h-16 border-0 focus-visible:ring-0 text-base flex-1 w-full"
            aria-label="Ô nhập câu hỏi"
          />
          <Button type="submit" variant="hero" size="xl" aria-label="Gửi câu hỏi" disabled={disabled}>
            <Send className="mr-1" /> {ctaLabel}
          </Button>
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
      <div className="mx-auto max-w-3xl px-3 md:px-6 pb-4 pt-2 bg-gradient-to-t from-background/95 to-background/60 backdrop-blur supports-[backdrop-filter]:bg-background/60">
        {formEl}
      </div>
    </div>
  );
};

export default PromptInput;
