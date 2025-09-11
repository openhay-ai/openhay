import { useEffect, useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Button } from "@/components/ui/button";
import { useToast } from "@/hooks/use-toast";
import { getSupportEndpoint } from "@/lib/api";
import { withAuthHeaders } from "@/lib/auth";

type Props = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  ownerEmail?: string;
  onSubmit?: (data: {
    email: string;
    question: string;
  }) => void | Promise<void>;
};

const SupportModal = ({
  open,
  onOpenChange,
  ownerEmail,
  onSubmit,
}: Props) => {
  const [email, setEmail] = useState("");
  const [question, setQuestion] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [emailError, setEmailError] = useState<string>("");
  const { toast } = useToast();

  useEffect(() => {
    if (!open) {
      setSubmitting(false);
      setEmailError("");
    }
  }, [open]);

  const isValidEmail = (value: string) => {
    const re = /^(?:[a-zA-Z0-9_'^&\-+])+(?:\.(?:[a-zA-Z0-9_'^&\-+])+)*@(?:(?:[a-zA-Z0-9-]+\.)+[a-zA-Z]{2,})$/;
    return re.test(value.trim());
  };

  const handleSubmit = async () => {
    if (submitting) return;
    if (!email.trim() || !question.trim()) return;
    if (!isValidEmail(email)) {
      setEmailError("Email không hợp lệ");
      return;
    }
    setSubmitting(true);
    try {
      if (onSubmit) {
        await onSubmit({ email, question });
      } else {
        const init = await withAuthHeaders({
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ email, question }),
        });
        const res = await fetch(getSupportEndpoint(), init);
        if (!res.ok) {
          const data = await res.json().catch(() => ({}));
          const message = (data && data.detail) || "Gửi thất bại";
          throw new Error(message);
        }
      }
      onOpenChange(false);
      toast({
        title: "Thành công",
        description:
          "Bạn đã gửi email thành công. Vui lòng đợi admin liên hệ lại.",
      });
      setEmail("");
      setQuestion("");
      setEmailError("");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader className="p-1 sm:p-2">
          <DialogTitle>Hỗ trợ</DialogTitle>
          <DialogDescription>
            Vui lòng để lại email và câu hỏi của bạn. Chúng tôi sẽ phản hồi sớm.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 p-1 sm:p-2">
          <div className="text-sm text-muted-foreground">
            Email của chúng tôi:{" "}
            <a className="underline" href={`mailto:${ownerEmail}`}>
              {ownerEmail}
            </a>
          </div>
          <div className="space-y-2">
            <label className="text-sm font-medium" htmlFor="support-email">
              Email của bạn
            </label>
            <Input
              id="support-email"
              type="email"
              placeholder="you@example.com"
              value={email}
              onChange={(e) => {
                const value = e.target.value;
                setEmail(value);
                if (!value.trim()) {
                  setEmailError("");
                } else if (!isValidEmail(value)) {
                  setEmailError("Email không hợp lệ");
                } else {
                  setEmailError("");
                }
              }}
              aria-invalid={!!emailError}
              className={emailError ? "border-destructive" : undefined}
            />
            {emailError ? (
              <p className="text-sm text-destructive">{emailError}</p>
            ) : null}
          </div>
          <div className="space-y-2">
            <label className="text-sm font-medium" htmlFor="support-question">
              Câu hỏi
            </label>
            <Textarea
              id="support-question"
              placeholder="Mô tả vấn đề hoặc câu hỏi của bạn"
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              rows={5}
              className="resize-none"
            />
          </div>
          <div className="flex items-center justify-between">
            <a
              className="text-sm underline"
              href={`mailto:${ownerEmail}?subject=Hỗ%20trợ%20OpenHay&body=${encodeURIComponent(
                question || ""
              )}`}
            >
              Gửi email trực tiếp
            </a>
            <Button
              onClick={handleSubmit}
              disabled={
                submitting ||
                !email.trim() ||
                !question.trim() ||
                (email.trim() && !isValidEmail(email))
              }
            >
              Gửi
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
};

export default SupportModal;
