import SidebarNav from "@/components/layout/SidebarNav";
import { Button } from "@/components/ui/button";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import FileUploader, { UploadItem } from "@/components/translate/FileUploader";
import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";

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

const Translate = () => {
  const navigate = useNavigate();
  const [tab, setTab] = useState("link");
  const [url, setUrl] = useState("");
  const [urlError, setUrlError] = useState<string | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [sourceLang, setSourceLang] = useState("Tự động");
  const [targetLang, setTargetLang] = useState("Tiếng Việt");
  const [submitting, setSubmitting] = useState(false);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    return () => {
      if (abortRef.current) abortRef.current.abort();
    };
  }, []);

  // streaming handled in FeatureChat; navigation happens immediately with preload state
  const isValidHttpUrl = (value: string): boolean => {
    try {
      const u = new URL(value);
      return u.protocol === "http:" || u.protocol === "https:";
    } catch {
      return false;
    }
  };

  const handleSubmitLink = async () => {
    if (submitting) return;
    const pureUrl = url.trim();
    if (!pureUrl || !isValidHttpUrl(pureUrl)) {
      setUrlError("URL không hợp lệ");
      return;
    }
    setSubmitting(true);
    try {
      const message = `Dịch từ '${sourceLang}' sang '${targetLang}'\n\n${pureUrl}`;
      const userMsg = {
        id: crypto.randomUUID(),
        role: "user" as const,
        content: message,
      };
      const assistantMsg = { id: crypto.randomUUID(), role: "assistant" as const, content: "" };
      navigate(`/t/pending`, {
        replace: true,
        state: {
          preloadMessages: [userMsg, assistantMsg],
          translateRun: { kind: "link", url: pureUrl, source_lang: sourceLang, target_lang: targetLang, assistantId: assistantMsg.id, message },
        },
      });
    } finally {
      setSubmitting(false);
    }
  };

  const handleSubmitFile = async () => {
    if (submitting || !file) return;
    setSubmitting(true);
    try {
      const toDataUrl = (f: File) => new Promise<string>((resolve, reject) => { const r = new FileReader(); r.onerror = () => reject(r.error); r.onload = () => resolve(String(r.result || "")); r.readAsDataURL(f); });
      const dataUrl = await toDataUrl(file);
      const commaIdx = dataUrl.indexOf(",");
      const base64Data = commaIdx >= 0 ? dataUrl.slice(commaIdx + 1) : dataUrl;
      const media = [{ data: base64Data, media_type: file.type || "application/octet-stream", identifier: file.name }];
      const message = `Dịch từ '${sourceLang}' sang '${targetLang}' cho file '${file.name}'`;
      const userMsg = {
        id: crypto.randomUUID(),
        role: "user" as const,
        content: message,
      };
      const assistantMsg = { id: crypto.randomUUID(), role: "assistant" as const, content: "" };
      navigate(`/t/pending`, {
        replace: true,
        state: {
          preloadMessages: [userMsg, assistantMsg],
          translateRun: { kind: "file", media, source_lang: sourceLang, target_lang: targetLang, assistantId: assistantMsg.id, message },
        },
      });
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen flex w-full overflow-hidden">
      <SidebarNav />
      <div className="md:flex-auto overflow-hidden w-full md:ml-64">
        <main className="h-full overflow-auto w-full px-3 md:px-6">
          <header className="flex justify-between items-center gap-3 py-4">
            <div>
              <h1 className="text-2xl font-semibold">AI Dịch thuật</h1>
              <p className="text-muted-foreground text-sm">Chọn phương thức dịch. OpenHay dịch mượt, giữ đúng thuật ngữ.</p>
            </div>
          </header>

          <section className="max-w-3xl mx-auto pb-16">
            <div className="rounded-xl border bg-card shadow-sm p-4 md:p-6">
              <Tabs value={tab} onValueChange={setTab}>
                <div className="flex justify-center">
                  <TabsList className="mx-auto w-full sm:w-auto grid grid-cols-2 rounded-full">
                    <TabsTrigger value="link">Dịch Link</TabsTrigger>
                    <TabsTrigger value="file">Dịch File</TabsTrigger>
                  </TabsList>
                </div>

                <div className="mt-5 space-y-5">
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                    <div className="space-y-1">
                      <Label htmlFor="source-lang">Dịch từ</Label>
                      <Input id="source-lang" className="h-10" value={sourceLang} onChange={(e) => setSourceLang(e.target.value)} placeholder="Tự động" aria-label="Dịch từ" />
                    </div>
                    <div className="space-y-1">
                      <Label htmlFor="target-lang">Dịch sang</Label>
                      <Input id="target-lang" className="h-10" value={targetLang} onChange={(e) => setTargetLang(e.target.value)} placeholder="Tiếng Việt" aria-label="Sang" />
                    </div>
                  </div>

                  <TabsContent value="link" className="space-y-3">
                    <div>
                      <h3 className="font-medium">Dịch bài viết từ một liên kết</h3>
                      <p className="text-sm text-muted-foreground">Dán URL, chọn ngôn ngữ. OpenHay sẽ dịch mượt, giữ đúng thuật ngữ.</p>
                    </div>
                    <div className="flex items-center gap-3">
                      <Input
                        className="flex-1 h-10"
                        value={url}
                        onChange={(e) => {
                          const v = e.target.value;
                          setUrl(v);
                          const t = v.trim();
                          setUrlError(t.length === 0 ? null : isValidHttpUrl(t) ? null : "URL không hợp lệ");
                        }}
                        aria-invalid={!!urlError}
                        placeholder="https://..."
                        aria-label="URL cần dịch"
                      />
                      <Button className="shrink-0" onClick={handleSubmitLink} disabled={submitting || !url.trim() || !!urlError}>
                        Dịch
                      </Button>
                    </div>
                    {urlError ? (
                      <p className="text-sm text-destructive">{urlError}</p>
                    ) : null}
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
            </div>
          </section>
        </main>
      </div>
    </div>
  );
};

export default Translate;
