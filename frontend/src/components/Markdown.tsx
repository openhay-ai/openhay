import React from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { normalizeLinksToSiteAnchors, normalizeUrlForMatch, stripHtml } from "@/lib/utils";
import { HoverCard, HoverCardContent, HoverCardTrigger } from "@/components/ui/hover-card";

export type CitationMeta = {
  url: string;
  title?: string;
  description?: string;
  hostname?: string;
  favicon?: string;
};

export type MarkdownProps = {
  content: string;
  className?: string;
  linkMeta?: Record<string, CitationMeta>;
};

// Lightweight markdown renderer with sensible defaults for chat bubbles
export const Markdown: React.FC<MarkdownProps> = ({ content, className, linkMeta }) => {
  const normalized = normalizeLinksToSiteAnchors(content);
  return (
    <div className={className}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          a({ node, href, children, ...props }) {
            const hrefStr = typeof href === "string" ? href : undefined;
            const key = hrefStr ? normalizeUrlForMatch(hrefStr) : undefined;
            const meta = key && linkMeta ? linkMeta[key] : undefined;
            const Anchor = (
              <a
                href={hrefStr}
                {...props}
                target="_blank"
                rel="noreferrer noopener"
                className="inline-flex items-center gap-1 rounded-full bg-muted px-2 py-0.5 text-xs font-medium text-foreground no-underline hover:opacity-80"
              >
                {children}
              </a>
            );
            if (!meta) return Anchor;
            const site = meta.hostname?.replace(/^www\./, "") || meta.hostname || undefined;
            return (
              <HoverCard openDelay={100} closeDelay={100}>
                <HoverCardTrigger asChild>
                  {Anchor}
                </HoverCardTrigger>
                <HoverCardContent className="w-80">
                  <div className="space-y-1">
                    <div className="flex items-center gap-2 min-w-0">
                      {meta.favicon ? (
                        // eslint-disable-next-line @next/next/no-img-element
                        <img src={meta.favicon} alt="icon" className="h-5 w-5 rounded-sm" />
                      ) : null}
                      <div className="text-xs text-muted-foreground truncate">{site || meta.url}</div>
                    </div>
                    {meta.title ? (
                      <div className="font-medium truncate" title={meta.title}>{meta.title}</div>
                    ) : null}
                    {meta.description ? (
                      <div className="line-clamp-3 text-xs text-muted-foreground">{stripHtml(meta.description)}</div>
                    ) : null}
                  </div>
                </HoverCardContent>
              </HoverCard>
            );
          },
          code({ className, children, ...props }) {
            const isBlock = typeof className === "string" && /(^|\s)language-/.test(className);
            if (!isBlock) {
              return (
                <code
                  className="rounded bg-muted px-1.5 py-0.5 text-[0.9em]"
                  {...props}
                >
                  {children}
                </code>
              );
            }
            return (
              <pre className="overflow-x-auto rounded-lg border bg-muted p-3 text-sm">
                <code className={className} {...props}>
                  {children}
                </code>
              </pre>
            );
          },
          ul({ children, ...props }) {
            return (
              <ul className="ml-5 list-disc space-y-1" {...props}>
                {children}
              </ul>
            );
          },
          ol({ children, ...props }) {
            return (
              <ol className="ml-5 list-decimal space-y-1" {...props}>
                {children}
              </ol>
            );
          },
          blockquote({ children, ...props }) {
            return (
              <blockquote
                className="border-l-4 pl-3 italic text-muted-foreground"
                {...props}
              >
                {children}
              </blockquote>
            );
          },
          p({ children, ...props }) {
            return (
              <p className="leading-7 [&:not(:first-child)]:mt-3" {...props}>
                {children}
              </p>
            );
          },
          h1({ children, ...props }) {
            return (
              <h1 className="mt-4 scroll-m-20 text-2xl font-semibold tracking-tight" {...props}>
                {children}
              </h1>
            );
          },
          h2({ children, ...props }) {
            return (
              <h2 className="mt-4 scroll-m-20 text-xl font-semibold tracking-tight" {...props}>
                {children}
              </h2>
            );
          },
          h3({ children, ...props }) {
            return (
              <h3 className="mt-3 scroll-m-20 text-lg font-semibold tracking-tight" {...props}>
                {children}
              </h3>
            );
          },
          table({ children, ...props }) {
            return (
              <div className="my-3 overflow-x-auto">
                <table className="w-full text-sm" {...props}>{children}</table>
              </div>
            );
          },
          th({ children, ...props }) {
            return (
              <th className="border-b px-3 py-2 text-left font-semibold" {...props}>
                {children}
              </th>
            );
          },
          td({ children, ...props }) {
            return (
              <td className="border-b px-3 py-2 align-top" {...props}>{children}</td>
            );
          },
        }}
      >
        {normalized}
      </ReactMarkdown>
    </div>
  );
};

export default Markdown;


