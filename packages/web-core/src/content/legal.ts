// Long-form legal text, written in both languages side by side (the i18n checker skips content/).
// DRAFT: describes what the system actually does; have it reviewed by a Bangladeshi lawyer before launch.

export type LegalSection = { title: { bn: string; en: string }; body: { bn: string; en: string } };

export const PRIVACY: LegalSection[] = [
  {
    title: { bn: "আমরা কী তথ্য রাখি", en: "What we keep" },
    body: {
      bn: "নাম, মোবাইল নম্বর, ঐচ্ছিক ইমেইল, সেভ করা ঠিকানা ও ম্যাপ লোকেশন; অর্ডার, বুকিং, সাবস্ক্রিপশন ও পেমেন্টের রেকর্ড; আপনার দেওয়া ছবি, রিভিউ, চ্যাট ও সমস্যা-রিপোর্ট। প্রোভাইডারদের ক্ষেত্রে NID নম্বর ও ছবি, নিজের ছবি, দক্ষতা, কাজের এলাকা, বিকাশ/নগদ নম্বর এবং কাজ চলাকালীন লাইভ লোকেশন (শুধু শেয়ার চালু থাকলে)।",
      en: "Name, mobile number, optional email, saved addresses and map location; records of orders, bookings, subscriptions and payments; photos, reviews, chats and issue reports you submit. For providers: NID number and images, profile photo, skills, work areas, bKash/Nagad number, and live location during a job (only while sharing is on).",
    },
  },
  {
    title: { bn: "কেন রাখি", en: "Why we keep it" },
    body: {
      bn: "সার্ভিস দিতে (প্রোভাইডার পাঠানো, ডেলিভারি, পেমেন্ট), নিরাপত্তা ও যাচাইয়ের জন্য (NID যাচাই, আগমন কোড, প্রতারণা রোধ), সাপোর্ট ও অভিযোগ নিষ্পত্তিতে, এবং হিসাব ও আইনগত দায়িত্ব পালনে। আপনি সম্মতি দিলে তবেই অফার ও প্রচারের বার্তা পাঠাই।",
      en: "To provide the service (sending providers, delivery, payments), for safety and verification (NID checks, arrival codes, fraud prevention), for support and disputes, and for accounting and legal duties. We send offers and promotions only if you opt in.",
    },
  },
  {
    title: { bn: "কার সাথে শেয়ার হয়", en: "Who it is shared with" },
    body: {
      bn: "কাজ নেওয়া প্রোভাইডার আপনার নাম, ফোন ও ঠিকানা দেখতে পান — কাজ নেওয়ার আগে নয়। পেমেন্ট গেটওয়ে (যেমন SSLCommerz, বিকাশ, নগদ) শুধু পেমেন্টের তথ্য পায়; SMS পাঠাতে SMS সেবাদাতা আপনার নম্বর পায়। শহরের সমস্যা-রিপোর্ট সংশ্লিষ্ট কর্তৃপক্ষকে পাঠানো হতে পারে, রিপোর্টকারীর ফোন নম্বর ছাড়া। আমরা আপনার তথ্য বিক্রি করি না।",
      en: "The provider who takes your job sees your name, phone and address — not before they take it. Payment gateways (such as SSLCommerz, bKash, Nagad) receive payment details only; our SMS provider receives your number to send texts. City issue reports may be forwarded to the relevant authority, without the reporter's phone number. We do not sell your data.",
    },
  },
  {
    title: { bn: "কতদিন রাখি", en: "How long we keep it" },
    body: {
      bn: "অ্যাকাউন্ট চালু থাকা পর্যন্ত। প্রত্যাখ্যাত প্রোভাইডার আবেদনের NID ও ছবি ৯০ দিন পর মুছে ফেলা হয়। অ্যাকাউন্ট মুছলে নাম, ফোন, ঠিকানা, ছবি ও পোস্ট মুছে যায়; হিসাবের প্রয়োজনে অর্ডার ও পেমেন্টের অঙ্ক নামহীনভাবে থাকে।",
      en: "For as long as your account is active. Rejected provider applicants' NID and photos are deleted after 90 days. When you delete your account, your name, phone, addresses, photos and posts are removed; order and payment amounts remain without your identity, as accounting requires.",
    },
  },
  {
    title: { bn: "নিরাপত্তা", en: "Security" },
    body: {
      bn: "NID ও আইডি কার্ডের ছবি এনক্রিপ্ট করে রাখা হয় এবং শুধু আপনি ও অনুমোদিত অ্যাডমিন দেখতে পারেন; প্রতিবার খোলার রেকর্ড রাখা হয়। পাসওয়ার্ড কখনো সাধারণ লেখায় রাখা হয় না। তথ্য ফাঁস হলে আইন অনুযায়ী কর্তৃপক্ষ ও আপনাকে জানানো হবে।",
      en: "NID and ID card images are stored encrypted and can be opened only by you and authorised admins; every opening is logged. Passwords are never stored in plain text. If a breach happens we will inform the authority and you as the law requires.",
    },
  },
  {
    title: { bn: "আপনার অধিকার", en: "Your rights" },
    body: {
      bn: "প্রোফাইল পেজ থেকে আপনার সব তথ্য ডাউনলোড করতে, ভুল তথ্য ঠিক করতে, প্রচারের বার্তা বন্ধ করতে এবং অ্যাকাউন্ট মুছে ফেলতে পারবেন। প্রশ্ন বা অভিযোগ থাকলে [সাপোর্ট ইমেইল]-এ লিখুন।",
      en: "From your profile page you can download all your data, correct it, stop promotional messages and delete your account. For questions or complaints, write to [support email].",
    },
  },
];

export const TERMS: LegalSection[] = [
  {
    title: { bn: "সেবা", en: "The service" },
    body: {
      bn: "শহরসাথী গ্রাহক ও যাচাইকৃত স্বাধীন প্রোভাইডারদের মধ্যে যোগাযোগ, বুকিং ও পেমেন্টের প্ল্যাটফর্ম। নির্দিষ্ট দাম, ওয়ারেন্টি ও রি-ক্লিনের শর্ত প্রতিটি সার্ভিসের পেজে দেখানো থাকে।",
      en: "ShohorSathi is a platform that connects customers with verified independent providers for booking and payment. Fixed prices, warranty and re-clean terms are shown on each service page.",
    },
  },
  {
    title: { bn: "পেমেন্ট ও রিফান্ড", en: "Payments and refunds" },
    body: {
      bn: "অনলাইনে দেওয়া টাকা কাজ শেষ বা পণ্য পৌঁছানো পর্যন্ত পেমেন্ট গেটওয়েতে জমা থাকে; অর্ডার বাতিল হলে স্বয়ংক্রিয়ভাবে ফেরত যায়। কাস্টম কাজে সর্বোচ্চ ১০% অগ্রিম নেওয়া হয়। শহরসাথী ক্রেডিট শুধু শহরসাথীতে খরচ করা যায়; নগদে তোলা বা অন্যকে পাঠানো যায় না।",
      en: "Online payments stay with the payment gateway until the job is done or the product is delivered, and are refunded automatically if the order is cancelled. Custom jobs take at most a 10% advance. ShohorSathi Credit can be spent only on ShohorSathi; it cannot be cashed out or transferred.",
    },
  },
  {
    title: { bn: "দায়িত্ব", en: "Responsibilities" },
    body: {
      bn: "সঠিক ঠিকানা ও তথ্য দিন, প্রোভাইডারের সাথে সম্মানজনক আচরণ করুন এবং প্ল্যাটফর্মের বাইরে লেনদেন এড়িয়ে চলুন — তাতে ওয়ারেন্টি ও সুরক্ষা থাকে না। প্রোভাইডাররা যাচাইকৃত তথ্য, সময়মতো উপস্থিতি ও কাজের মান বজায় রাখতে বাধ্য।",
      en: "Give accurate addresses and details, treat providers with respect, and avoid paying outside the platform — warranty and protection do not cover off-platform deals. Providers must keep their verified details current, arrive on time and maintain the quality of work.",
    },
  },
];
