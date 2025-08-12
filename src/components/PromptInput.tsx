import { FormEvent, useState } from "react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Paperclip, Send } from "lucide-react";
import { useToast } from "@/hooks/use-toast";

export const PromptInput = () => {
  const [value, setValue] = useState("");
  const { toast } = useToast();

  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    toast({
      title: "Đang phát triển",
      description: "Chức năng hỏi đáp sẽ sớm khả dụng.",
    });
  };

  return (
    <form onSubmit={onSubmit} className="mt-10">
      <div className="flex items-center gap-2 rounded-2xl border bg-card p-2 shadow-md">
        <Button type="button" variant="ghost" size="icon" aria-label="Đính kèm">
          <Paperclip />
        </Button>
        <Input
          value={value}
          onChange={(e) => setValue(e.target.value)}
          placeholder="Nhập câu hỏi bất kì..."
          className="h-14 border-0 focus-visible:ring-0 text-base"
          aria-label="Ô nhập câu hỏi"
        />
        <Button type="submit" variant="hero" size="xl" aria-label="Gửi câu hỏi">
          <Send className="mr-1" /> Gửi
        </Button>
      </div>
      <p className="mt-2 text-xs text-muted-foreground text-center">
        Khi đặt câu hỏi, bạn đồng ý với <a className="underline" href="#">Điều khoản</a> và <a className="underline" href="#">Chính sách quyền riêng tư</a>.
      </p>
    </form>
  );
};

export default PromptInput;
