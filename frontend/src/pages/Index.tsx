import SidebarNav from "@/components/layout/SidebarNav";
import PromoBanner from "@/components/layout/PromoBanner";
import PromptInput from "@/components/PromptInput";
import { Button } from "@/components/ui/button";
import city from "@/assets/thumb-city.jpg";
import laptop from "@/assets/thumb-laptop.jpg";
import nature from "@/assets/thumb-nature.jpg";

const featured = [
  { title: "Tàu Trung Quốc tự đâm vào nhau", img: city },
  { title: "Tổng Bí thư Tô Lâm thăm Hàn Quốc", img: laptop },
  { title: "Tài khoản giao thông là gì", img: nature },
];

const chips = [
  "Vượt đèn vàng có bị phạt không",
  "Thử nhanh hơn tốc độ ánh sáng là gì",
  "Cách mạng là gì",
  "Cách chửi tiểu tam",
  "Loại rượu phổ biến nhất thế giới",
  "Nhà thờ Đức Bà Sài Gòn mở cửa ở đâu",
  "Ma có thật không",
];

const Index = () => {
  return (
    <div className="min-h-screen flex w-full overflow-hidden">
      <SidebarNav />

      <div className="md:flex-auto overflow-hidden w-full">
        <PromoBanner />

        <main className="h-full overflow-auto w-full px-3 md:px-6">
          <header className="flex justify-end items-center gap-3 py-4">
            <Button variant="ghost" size="sm">Đăng nhập</Button>
            <Button variant="hero" size="sm">Tạo tài khoản miễn phí</Button>
          </header>

          <section className="max-w-3xl mx-auto pb-12">
            <div className="flex flex-col items-center mt-10">
              <h1 className="text-4xl md:text-5xl font-semibold tracking-tight mb-2">🎓 Xin chào</h1>
              <p className="text-center text-muted-foreground max-w-xl mb-10">
                AI Hay giúp bạn giải đáp mọi thắc mắc trong học tập và cập nhật kiến thức nhanh chóng.
              </p>

              <div className="w-full">
                <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mb-6">
                  {featured.map((f) => (
                    <article key={f.title} className="flex items-center rounded-lg border overflow-hidden bg-card hover:shadow-md transition-shadow">
                      <img src={f.img} width={60} height={60} alt={f.title} className="object-cover size-[60px]" loading="lazy" />
                      <div className="px-3 py-2 text-sm">{f.title}</div>
                    </article>
                  ))}
                </div>

                <div className="flex items-center gap-2 text-sm text-muted-foreground mb-2">
                  <span>🌎 Khám phá thêm:</span>
                </div>
                <div className="flex flex-wrap gap-2">
                  {chips.map((c) => (
                    <Button key={c} variant="chip" size="sm" asChild>
                      <a href="#" aria-label={c}>{c}</a>
                    </Button>
                  ))}
                </div>
              </div>

              <PromptInput />
            </div>
          </section>
        </main>
      </div>
    </div>
  );
};

export default Index;
