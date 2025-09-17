import { useEffect, useMemo, useRef, useState } from "react";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "@/components/ui/dialog";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import FileUploader, { UploadItem } from "./FileUploader";

type Props = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSubmitLink: (args: { url: string; source_lang: string; target_lang: string;}) => void | Promise<void>;
  onSubmitFile: (args: { file: File; source_lang: string; target_lang: string;}) => void | Promise<void>;
};

const ACCEPT = [
  ".pdf",
  ".txt",
  ".csv",
  ".docx",
  ".xlsx",
  ".html",
  ".md",
  ".markdown",
].join(",");

const TranslateModal = ({ open, onOpenChange, onSubmitLink, onSubmitFile }: Props) => {
  const [tab, setTab] = useState("link");
  const [url, setUrl] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [sourceLang, setSourceLang] = useState("Tự động");
  const [targetLang, setTargetLang] = useState("Tiếng Việt");
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (!open) {
      setSubmitting(false);
    }
  }, [open]);

  const handleSubmitLink = async () => {
    if (submitting) return;
    setSubmitting(true);
    onOpenChange(false);
    try {
      await onSubmitLink({ url, source_lang: sourceLang, target_lang: targetLang});
    } finally {
      setSubmitting(false);
    }
  };

  const handleSubmitFile = async () => {
    if (submitting) return;
    if (!file) return;
    setSubmitting(true);
    onOpenChange(false);
    try {
      await onSubmitFile({ file, source_lang: sourceLang, target_lang: targetLang});
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>AI Dịch thuật</DialogTitle>
          <DialogDescription>
            Chọn phương thức dịch. OpenHay dịch mượt, giữ đúng thuật ngữ.
          </DialogDescription>
        </DialogHeader>
        <Tabs value={tab} onValueChange={setTab}>
          <TabsList className="grid grid-cols-2 w-full">
            <TabsTrigger value="link">Dịch Link</TabsTrigger>
            <TabsTrigger value="file">Dịch File</TabsTrigger>
          </TabsList>

          <div className="mt-4 space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-2">
              <Input value={sourceLang} onChange={(e) => setSourceLang(e.target.value)} placeholder="Tự động" aria-label="Dịch từ" />
              <Input value={targetLang} onChange={(e) => setTargetLang(e.target.value)} placeholder="Tiếng Việt" aria-label="Sang" />
            </div>

            <TabsContent value="link" className="space-y-3">
              <div>
                <h3 className="font-medium">Dịch bài viết từ một liên kết</h3>
                <p className="text-sm text-muted-foreground">Dán URL, chọn ngôn ngữ. OpenHay sẽ dịch mượt, giữ đúng thuật ngữ.</p>
              </div>
              <Input value={url} onChange={(e) => setUrl(e.target.value)} placeholder="https://..." aria-label="URL cần dịch" />
              <div className="flex justify-end">
                <Button onClick={handleSubmitLink} disabled={submitting || !url.trim()}>
                  Dịch
                </Button>
              </div>
            </TabsContent>

            <TabsContent value="file" className="space-y-3">
              <div>
                <h3 className="font-medium">Dịch tài liệu từ file</h3>
                <p className="text-sm text-muted-foreground">Tải file của bạn lên. OpenHay dịch nhanh, rõ ý, dễ đọc.</p>
              </div>
              <FileUploader
                accept={ACCEPT}
                multiple={false}
                onChange={(items: UploadItem[]) => {
                  const first = items.find((i) => i.status === "complete");
                  setFile(first ? first.file : null);
                }}
              />
              <div className="flex justify-end">
                <Button onClick={handleSubmitFile} disabled={submitting || !file}>
                  Dịch
                </Button>
              </div>
            </TabsContent>
          </div>
        </Tabs>
      </DialogContent>
    </Dialog>
  );
};

export default TranslateModal;
