import { Card, CardContent } from "@/components/ui/card";

export const SourceCard = ({ item, index }: { item: any; index: number }) => {
  const title: string = item?.title ?? item?.url ?? "Nguồn";
  const url: string = item?.url ?? "";
  let host: string = item?.meta_url?.hostname || item?.profile?.long_name || "";
  const favicon: string = item?.meta_url?.favicon || item?.profile?.img || "/favicon.ico";
  if (!host && typeof url === "string" && url) {
    try {
      host = new URL(url).hostname;
    } catch {}
  }
  return (
    <Card className="h-full">
      <CardContent className="p-4 flex items-start gap-3">
        <div className="flex items-center justify-center h-6 w-6 rounded-full bg-secondary text-xs">
          {index + 1}
        </div>
        <div className="flex-1 overflow-hidden">
          <a
            href={url}
            target="_blank"
            rel="noreferrer"
            className="line-clamp-2 text-sm hover:underline"
          >
            {title}
          </a>
          <div className="mt-2 flex items-center gap-2 text-xs text-muted-foreground">
            {favicon ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img src={favicon} alt="icon" className="h-4 w-4 rounded-sm" />
            ) : null}
            <span className="truncate">{host}</span>
          </div>
        </div>
      </CardContent>
    </Card>
  );
};

export default SourceCard;
