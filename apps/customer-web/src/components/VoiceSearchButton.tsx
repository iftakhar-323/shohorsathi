import { Icon, t } from "@shohor/web-core";
import { useRef, useState } from "react";

type Recognition = {
  lang: string;
  interimResults: boolean;
  maxAlternatives: number;
  onresult: (e: { results: ArrayLike<ArrayLike<{ transcript: string }>> }) => void;
  onend: () => void;
  onerror: () => void;
  start: () => void;
  stop: () => void;
};

function recognitionClass(): (new () => Recognition) | undefined {
  const w = window as unknown as { SpeechRecognition?: new () => Recognition; webkitSpeechRecognition?: new () => Recognition };
  return w.SpeechRecognition ?? w.webkitSpeechRecognition;
}

/** Bangla (bn-BD) speech to text with the browser's speech API; hidden where the browser has none. */
export function VoiceSearchButton({ onTranscript, className = "" }: { onTranscript: (text: string) => void; className?: string }) {
  const [listening, setListening] = useState(false);
  const current = useRef<Recognition | null>(null);
  const Recognition = recognitionClass();
  if (!Recognition) return null;

  function toggle() {
    if (current.current) {
      current.current.stop();
      return;
    }
    const r = new Recognition!();
    r.lang = "bn-BD";
    r.interimResults = false;
    r.maxAlternatives = 1;
    r.onresult = (e) => {
      const text = e.results[0]?.[0]?.transcript?.trim();
      if (text) onTranscript(text);
    };
    r.onend = r.onerror = () => {
      current.current = null;
      setListening(false);
    };
    current.current = r;
    setListening(true);
    r.start();
  }

  return (
    <button
      type="button"
      onClick={toggle}
      aria-label={listening ? t("শুনছি... বাংলায় বলুন") : t("ভয়েস সার্চ")}
      aria-pressed={listening}
      className={`flex size-11 shrink-0 items-center justify-center rounded-xl ${listening ? "animate-pulse bg-bad text-white" : "bg-brand-soft text-brand-strong"} ${className}`}
    >
      <Icon name="mic" />
    </button>
  );
}
