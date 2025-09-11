import SidebarNav from "@/components/layout/SidebarNav";
import PromptInput from "@/components/PromptInput";
import { Button } from "@/components/ui/button";
import {
  Carousel,
  CarouselContent,
  CarouselItem,
  CarouselNext,
  CarouselPrevious,
} from "@/components/ui/carousel";
import { useEffect, useMemo, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import city from "@/assets/thumb-city.jpg";
import nature from "@/assets/thumb-nature.jpg";
import { cn } from "@/lib/utils";

import { getFeaturedUrl } from "@/lib/api";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { authFetch } from "@/lib/auth";
import { ExternalLink } from "lucide-react";

type FeaturedItem = { title: string; img?: string; url?: string; category?: string | null };
const fallbackFeatured: FeaturedItem[] = [
  { title: "Tàu Trung Quốc tự đâm vào nhau", img: city },
  { title: "Tổng Bí thư Tô Lâm thăm Hàn Quốc", img: city },
  { title: "Tài khoản giao thông là gì", img: nature },
  { title: "Rừng Amazon đang bị cháy", img: nature },
];

const defaultChips = [
  "Vượt đèn vàng có bị phạt không",
  "Thử nhanh hơn tốc độ ánh sáng là gì",
  "Cách mạng là gì",
  "Cách chửi tiểu tam",
  "Loại rượu phổ biến nhất thế giới",
  "Nhà thờ Đức Bà Sài Gòn mở cửa ở đâu",
  "Ma có thật không",
];

const Index = () => {
  const [featured, setFeatured] = useState<FeaturedItem[]>(fallbackFeatured);
  const [categories, setCategories] = useState<string[]>([]);
  const [activeCat, setActiveCat] = useState<string>("");
  const [chips, setChips] = useState<string[]>(defaultChips);
  const filled: FeaturedItem[] = useMemo(() => {
    if (featured.length === 0) return [];
    if (featured.length >= 3) return featured;
    const result = [...featured];
    while (result.length < 3) {
      result.push(result[result.length - 1]);
    }
    return result;
  }, [featured]);
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();

  useEffect(() => {
    const run = async () => {
      try {
        const res = await authFetch(getFeaturedUrl());
        if (!res.ok) throw new Error("Failed to fetch featured");
        const data = await res.json();
        const items: { title: string; url?: string; image_url?: string; category?: string | null }[] = data.items || [];
        const serverCats: string[] = data.categories || [];
        const serverKeywords: { keyword: string; count: number }[] = data.keywords || [];
        if (items.length > 0) {
          const mapped = items.map((i) => ({ title: i.title, url: i.url, img: i.image_url, category: i.category ?? null }));
          setFeatured(mapped);
        }
        setCategories(serverCats);
        setActiveCat(serverCats[0] ?? "");
        if (serverKeywords.length > 0) {
          setChips(serverKeywords.map((k) => k.keyword));
        } else {
          setChips(defaultChips);
        }
      } catch (e) {
        // ignore and keep fallback
        setFeatured(fallbackFeatured);
        setChips(defaultChips);
      }
    };
    run();
  }, []);

  const handleSubmit = (value: string, files?: File[]) => {
    const currentType = searchParams.get("type") ?? undefined;
    const params = new URLSearchParams();
    if (currentType) params.set("type", currentType);
    params.set("q", value);
    const to = { pathname: "/", search: `?${params.toString()}` } as const;
    const state = files && files.length > 0 ? { files } : undefined;
    navigate(to, { state });
  };

  return (
    <div className="min-h-screen flex w-full overflow-hidden">
      <SidebarNav />

      <div className="md:flex-auto overflow-hidden w-full md:ml-64">
        <main className="h-full overflow-auto w-full px-3 md:px-6">


          <section className="max-w-3xl mx-auto pb-40 min-h-[calc(100vh-10rem)] flex items-center">
            <div className="flex flex-col items-center w-full">
              <h1 className="text-4xl md:text-5xl font-semibold tracking-tight mb-2">🎓 Xin chào</h1>
              <p className="text-center text-muted-foreground max-w-xl mb-10">
                OpenHay giúp bạn giải đáp mọi thắc mắc trong học tập và cập nhật kiến thức nhanh chóng.
              </p>

              <div className="w-full">
                {categories.length > 0 && (
                    <div className="mb-6">
                      <Tabs value={activeCat} onValueChange={setActiveCat}>
                        <TabsList className="flex flex-wrap gap-1">
                          <TabsTrigger value="">Tất cả</TabsTrigger>
                          {categories.map((c) => (
                            <TabsTrigger key={c} value={c}>
                              {c}
                            </TabsTrigger>
                          ))}
                        </TabsList>
                        <TabsContent value={activeCat} />
                      </Tabs>
                    </div>
                  )}
                <Carousel opts={{ align: "start", slidesToScroll: 1 }} className="mb-10">
                  <CarouselContent>
                    {(activeCat ? filled.filter((f) => f.category === activeCat) : filled).map((f) => (
                      <CarouselItem key={f.title} className="basis-full md:basis-1/3">
                        <article
                          onClick={() => handleSubmit(`Tin tức mới nhất về ${f.title}`)}
                          className={cn(
                            "relative group flex items-center rounded-lg border overflow-hidden bg-card hover:shadow-md transition-shadow cursor-pointer"
                          )}
                        >
                          <img
                            src={f.img ?? city}
                            width={60}
                            height={60}
                            alt={f.title}
                            className="object-cover size-[60px]"
                            loading="lazy"
                          />
                          <div className="px-3 py-2 text-sm">{f.title}</div>
                          {f.url ? (
                            <Button
                              size="icon"
                              variant="secondary"
                              className="absolute top-1 right-1 rounded-full h-8 w-8 opacity-0 group-hover:opacity-100 transition-opacity"
                              onClick={(e) => {
                                e.stopPropagation();
                                window.open(f.url as string, "_blank", "noopener,noreferrer");
                              }}
                              aria-label="Mở liên kết nguồn"
                              title={f.url}
                            >
                              <ExternalLink className="h-4 w-4" />
                            </Button>
                          ) : null}
                        </article>
                      </CarouselItem>
                    ))}
                  </CarouselContent>
                  <CarouselPrevious />
                  <CarouselNext />
                </Carousel>


                {/* Dot pagination removed */}

                <div className="flex items-center gap-2 text-sm text-muted-foreground mb-2">
                  <span>🌟 Từ khóa của ngày</span>
                </div>
                <div className="flex flex-wrap gap-2">
                  {chips.map((c) => (
                    <Button key={c} variant="chip" size="sm" onClick={() => handleSubmit(`Tin tức mới nhất về ${c}`)}>
                      {c}
                    </Button>
                  ))}
                </div>
              </div>

              <PromptInput fixed onSubmit={handleSubmit} />
            </div>
          </section>
        </main>
      </div>
    </div>
  );
};

export default Index;
