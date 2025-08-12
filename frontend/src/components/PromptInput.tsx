import { FormEvent, useState } from "react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Paperclip, Send } from "lucide-react";
import { useToast } from "@/hooks/use-toast";

export type PromptInputProps = {
  onSubmit?: (value: string) => void;
  placeholder?: string;
  ctaLabel?: string;
  className?: string;
  fixed?: boolean;
};

export const PromptInput = ({
  onSubmit,
  placeholder = "Nhập câu hỏi bất kì...",
  ctaLabel = "Gửi",
  className,
  fixed = false,
}: PromptInputProps) => {
  const [value, setValue] = useState("");
  const { toast } = useToast();

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    const trimmed = value.trim();
    if (!trimmed) return;

    if (onSubmit) {
      onSubmit(trimmed);
      setValue("");
      return;
    }

    toast({
      title: "Đang phát triển",
      description: "Chức năng hỏi đáp sẽ sớm khả dụng.",
    });
  };

  const formEl = (
    <form onSubmit={handleSubmit} className={className ?? "mt-0"}>
      <div className="flex items-center gap-2 rounded-2xl border bg-card p-2 shadow-md">
        <Button type="button" variant="ghost" size="icon" aria-label="Đính kèm">
          <Paperclip />
        </Button>
        <Input
          value={value}
          onChange={(e) => setValue(e.target.value)}
          placeholder={placeholder}
          className="h-16 border-0 focus-visible:ring-0 text-base"
          aria-label="Ô nhập câu hỏi"
        />
        <Button type="submit" variant="hero" size="xl" aria-label="Gửi câu hỏi">
          <Send className="mr-1" /> {ctaLabel}
        </Button>
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
