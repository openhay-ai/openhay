import { useMemo, useState } from "react";
import { Markdown } from "@/components/Markdown";
import AttachmentList from "@/components/AttachmentList";
import {
  Carousel,
  CarouselContent,
  CarouselItem,
  CarouselNext,
  CarouselPrevious,
} from "@/components/ui/carousel";
import SourceCard from "@/components/SourceCard";
import { ChevronDown, Loader2, Copy, Check } from "lucide-react";

export type ChatMedia = {
  src: string;
  mediaType: string;
  identifier?: string;
};

export type ChatMessageData = {
  id: string;
  role: "user" | "assistant" | "system" | "tool" | "thinking";
  content: string;
  media?: ChatMedia[];
  toolName?: string;
  results?: any[];
};

export type LinkMetaMap = Record<
  string,
  {
    url: string;
    title?: string;
    description?: string;
    hostname?: string;
    favicon?: string;
  }
>;

type ChatMessageProps = {
  message: ChatMessageData;
  linkMeta?: LinkMetaMap;
  expanded?: boolean;
  onToggleExpanded?: (next: boolean) => void;
  defaultExpanded?: boolean;
};

const ChatMessage = ({
  message,
  linkMeta,
  expanded,
  onToggleExpanded,
  defaultExpanded,
}: ChatMessageProps) => {
  const { role, content } = message;
  const [copied, setCopied] = useState(false);

  const isCollapsible = role === "thinking" || role === "tool";
  const [internalOpen, setInternalOpen] = useState<boolean>(
    defaultExpanded ?? (role === "thinking")
  );
  const isOpen = isCollapsible ? (expanded ?? internalOpen) : true;

  const toggleOpen = () => {
    const next = !isOpen;
    if (onToggleExpanded) onToggleExpanded(next);
    else setInternalOpen(next);
  };

  if (role === "thinking") {
    return (
      <div className="flex justify-start">
        <div className="max-w-[80%] w-full">
          <div className="rounded-lg border bg-muted/30 p-3">
            <button
              type="button"
              className="flex w-full items-center justify-between hover:opacity-80"
              onClick={toggleOpen}
              aria-expanded={isOpen}
              aria-controls={`think-${message.id}`}
            >
              <div className="text-sm font-medium text-muted-foreground">Tư duy</div>
              <ChevronDown className={`size-4 transition-transform ${isOpen ? "rotate-180" : "rotate-0"}`} />
            </button>
            {isOpen ? (
              <div id={`think-${message.id}`} className="mt-2 text-sm">
                <Markdown content={content} />
              </div>
            ) : null}
          </div>
        </div>
      </div>
    );
  }

  if (role === "tool") {
    const results = Array.isArray(message.results) ? message.results : [];
    const count = results.length;
    return (
      <div className="flex justify-start">
        <div className="max-w-[80%] w-full">
          <div className="rounded-lg border bg-muted/30 p-3">
            <button
              type="button"
              className="flex w-full items-center justify-between hover:opacity-80"
              onClick={toggleOpen}
              aria-expanded={isOpen}
              aria-controls={`sources-${message.id}`}
            >
              <div className="text-sm font-medium text-muted-foreground">{count} nguồn</div>
              <ChevronDown className={`size-4 transition-transform ${isOpen ? "rotate-180" : "rotate-0"}`} />
            </button>
            {isOpen ? (
              <div id={`sources-${message.id}`} className="relative mt-3">
                <Carousel opts={{ align: "start" }} className="w-full">
                  <CarouselContent>
                    {results.map((it, idx) => (
                      <CarouselItem key={idx} className="basis-full sm:basis-1/2 lg:basis-1/3">
                        <SourceCard item={it} index={idx} />
                      </CarouselItem>
                    ))}
                  </CarouselContent>
                  <CarouselPrevious className="-left-5" />
                  <CarouselNext className="-right-5" />
                </Carousel>
              </div>
            ) : null}
          </div>
        </div>
      </div>
    );
  }

  const showLoader = role === "assistant" && content.trim().length === 0;

  return (
    <div className={role === "user" ? "flex justify-end" : "flex justify-start"}>
      <div
        className={
          "max-w-[80%] rounded-2xl px-4 py-2 text-sm " +
          (role === "user" ? "bg-emerald-600 text-white" : "bg-card border") +
          (role === "assistant" ? " group" : "")
        }
      >
        {role === "assistant" ? (
          showLoader ? (
            <div className="flex items-center gap-2 text-muted-foreground">
              <Loader2 className="size-4 animate-spin" />
              <span>Để xem...</span>
            </div>
          ) : (
            <div className="relative pr-8">
              <div className="absolute right-0 top-0 flex flex-col gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                <button
                  type="button"
                  className="inline-flex h-6 w-6 items-center justify-center rounded-md text-muted-foreground hover:text-foreground"
                  onClick={async () => {
                    try {
                      await navigator.clipboard.writeText(content);
                      setCopied(true);
                      window.setTimeout(() => setCopied(false), 1500);
                    } catch {
                      // no-op on failure
                    }
                  }}
                  aria-label="Sao chép nội dung trả lời"
                  title="Sao chép"
                >
                  {copied ? (
                    <Check className="size-4 text-emerald-600 transition-transform duration-200 scale-110" />
                  ) : (
                    <Copy className="size-4 transition-transform duration-200" />
                  )}
                  <span className="sr-only">Sao chép</span>
                </button>
              </div>
              <Markdown content={content} linkMeta={linkMeta} />
            </div>
          )
        ) : (
          <>
            {Array.isArray(message.media) && message.media.length > 0 ? (
              <AttachmentList
                media={message.media}
                variant={role === "user" ? "onAccent" : "default"}
              />
            ) : null}
            <div>{content}</div>
          </>
        )}
      </div>
    </div>
  );
};

export default ChatMessage;
