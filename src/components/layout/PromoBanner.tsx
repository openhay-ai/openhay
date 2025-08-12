export const PromoBanner = () => {
  return (
    <div className="w-full bg-secondary text-center px-3 sticky top-0 z-30 border-b">
      <a
        className="inline-block py-2 text-sm text-accent-foreground hover:underline"
        href="https://edu.ai-hay.vn/"
        target="_blank"
        rel="noreferrer"
      >
        Tặng ngay gói AI Hay Pro cho sinh viên 👉 <b>Tìm hiểu ngay</b>
      </a>
    </div>
  );
};

export default PromoBanner;
