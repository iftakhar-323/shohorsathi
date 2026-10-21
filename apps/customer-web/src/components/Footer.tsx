export default function Footer() {
  return (
    <footer className="bg-night text-night-text">
      <div className="mx-auto flex max-w-[1200px] flex-wrap items-center justify-between gap-5 px-6 py-10">
        <div className="flex flex-col gap-1.5">
          <span className="text-[22px] font-bold text-white">আপনি কি দক্ষ কারিগর বা হোম শেফ?</span>
          <span>শহরসাথীতে যোগ দিন, নিজের সময়ে কাজ করুন, সাপ্তাহিক পেমেন্ট বিকাশ/নগদে।</span>
        </div>
        <a href="/provider" className="rounded-2xl bg-white px-6 py-3.5 font-bold text-ink no-underline">
          প্রোভাইডার হিসেবে যোগ দিন
        </a>
      </div>
    </footer>
  );
}
