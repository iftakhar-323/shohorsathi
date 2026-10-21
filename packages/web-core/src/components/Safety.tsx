import { useState } from "react";

import { api, errorMessage } from "../lib/api";
import { t } from "../lib/i18n";
import { Button, ErrorNote, Modal, SuccessNote, TextArea } from "./ui";

/** SOS during a job: alerts ShohorSathi's safety team with the job and the device location. */
export function SosButton({ source, sourceId, className = "" }: { source: string; sourceId: number; className?: string }) {
  const [open, setOpen] = useState(false);
  const [note, setNote] = useState("");
  const [sent, setSent] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function send(position?: GeolocationPosition) {
    setBusy(true);
    setError("");
    try {
      await api.post("/providers/safety/sos/", {
        source,
        source_id: sourceId,
        note,
        latitude: position?.coords.latitude.toFixed(6),
        longitude: position?.coords.longitude.toFixed(6),
      });
      setSent(true);
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  }

  function press() {
    // Location helps the team reach you; send without it rather than wait if it is unavailable.
    if (!("geolocation" in navigator)) return send();
    navigator.geolocation.getCurrentPosition(send, () => send(), { timeout: 5000 });
  }

  return (
    <>
      <Button variant="danger" icon="alert" onClick={() => setOpen(true)} className={className}>{t("SOS / বিপদ")}</Button>
      <Modal title={t("জরুরি সাহায্য")} open={open} onClose={() => setOpen(false)}>
        {sent ? (
          <SuccessNote>{t("আমাদের সেফটি টিম জানতে পেরেছে এবং এখনই যোগাযোগ করবে। বিপদ গুরুতর হলে ৯৯৯-এ কল করুন।")}</SuccessNote>
        ) : (
          <>
            <p className="m-0 text-muted">{t("এটি চাপলে শহরসাথী সেফটি টিম আপনার লোকেশনসহ সাথে সাথে খবর পাবে।")}</p>
            <TextArea label={t("কী হয়েছে? (ঐচ্ছিক)")} value={note} onChange={(e) => setNote(e.target.value)} />
            <ErrorNote>{error}</ErrorNote>
            <Button variant="danger" loading={busy} onClick={press} className="h-12 text-base">{t("এখনই সাহায্য পাঠান")}</Button>
            <a href="tel:999" className="text-center font-semibold text-bad">{t("৯৯৯-এ কল করুন")}</a>
          </>
        )}
      </Modal>
    </>
  );
}
