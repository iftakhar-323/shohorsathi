// Date/time/problem chosen on a service page, kept per cart item until checkout sends it.
export type BookingDraft = {
  scheduled_date: string;
  slot: string;
  problem_description: string;
  photo_urls: string[];
  is_emergency?: boolean;
};

const KEY = "shohor.bookingDrafts";

function readAll(): Record<string, BookingDraft> {
  try {
    return JSON.parse(localStorage.getItem(KEY) || "{}");
  } catch {
    return {};
  }
}

function writeAll(drafts: Record<string, BookingDraft>) {
  try {
    localStorage.setItem(KEY, JSON.stringify(drafts));
  } catch {
    // storage blocked: the checkout page asks for the schedule again
  }
}

export function saveDraft(cartItemId: number, draft: BookingDraft) {
  writeAll({ ...readAll(), [cartItemId]: draft });
}

export function getDraft(cartItemId: number): BookingDraft | undefined {
  return readAll()[cartItemId];
}

export function clearDrafts() {
  writeAll({});
}
