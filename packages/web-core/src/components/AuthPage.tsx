import { LanguageToggle, t } from "../lib/i18n";
import { useState, type FormEvent } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";

import { errorMessage } from "../lib/api";
import { useAuth, type Role } from "../lib/auth";
import Icon from "./Icon";
import { Button, ErrorNote, Field, SuccessNote } from "./ui";

type Mode = "login" | "register" | "reset";

const PHONE_PATTERN = "01[3-9][0-9]{8}";

class WrongAppError extends Error {}

/** Login, OTP registration and password reset, shared by the customer, provider and admin apps. */
export default function AuthPage({
  appName,
  allowRegister = true,
  roles,
  initialMode = "login",
}: {
  appName: string;
  allowRegister?: boolean;
  roles?: Role[];
  initialMode?: Mode;
}) {
  const auth = useAuth();
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const next = params.get("next") || "/";

  const [mode, setMode] = useState<Mode>(initialMode);
  const [phone, setPhone] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [otp, setOtp] = useState("");
  const [otpSent, setOtpSent] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  function switchTo(m: Mode) {
    setMode(m);
    setOtpSent(false);
    setError("");
    setNotice("");
  }

  async function run(action: () => Promise<void>) {
    setBusy(true);
    setError("");
    try {
      await action();
    } catch (e) {
      setError(e instanceof WrongAppError ? t("এই অ্যাপে আপনার প্রবেশাধিকার নেই।") : errorMessage(e, t("ফোন নম্বর বা পাসওয়ার্ড ঠিক নেই।")));
    } finally {
      setBusy(false);
    }
  }

  function submit(e: FormEvent) {
    e.preventDefault();
    if (mode === "login") {
      run(async () => {
        const user = await auth.login(phone, password);
        if (roles && user && !roles.includes(user.role)) {
          auth.logout();
          throw new WrongAppError();
        }
        navigate(next, { replace: true });
      });
      return;
    }
    if (!otpSent) {
      run(async () => {
        await auth.requestOtp(phone, mode === "register" ? "register" : "reset_password");
        setOtpSent(true);
        setNotice(t("{phone} নম্বরে ৬ সংখ্যার কোড পাঠানো হয়েছে।", { phone }));
      });
      return;
    }
    if (mode === "register") {
      run(async () => {
        await auth.register({ phone, full_name: name, password, otp });
        navigate(next, { replace: true });
      });
    } else {
      run(async () => {
        await auth.resetPassword({ phone, otp, new_password: password });
        switchTo("login");
        setNotice(t("পাসওয়ার্ড বদলানো হয়েছে। এখন লগইন করুন।"));
      });
    }
  }

  const title = mode === "login" ? t("লগইন") : mode === "register" ? t("নতুন অ্যাকাউন্ট") : t("পাসওয়ার্ড ভুলে গেছেন");

  return (
    <div className="flex min-h-[70vh] items-center justify-center px-4 py-12">
      <form onSubmit={submit} className="flex w-full max-w-md flex-col gap-4 rounded-3xl border border-line bg-surface p-7">
        <div className="flex items-center gap-2.5">
          <span className="flex size-10 items-center justify-center rounded-xl bg-brand text-white">
            <Icon name="home" />
          </span>
          <div className="flex flex-col">
            <span className="text-sm text-muted">{appName}</span>
            <h1 className="m-0 text-2xl font-bold">{title}</h1>
          </div>
          <LanguageToggle className="ml-auto" />
        </div>

        <Field
          label={t("মোবাইল নম্বর")}
          type="tel"
          inputMode="numeric"
          pattern={PHONE_PATTERN}
          title={t("০১ দিয়ে শুরু ১১ সংখ্যার নম্বর")}
          placeholder="01XXXXXXXXX"
          value={phone}
          onChange={(e) => setPhone(e.target.value.trim())}
          disabled={otpSent}
          required
          autoComplete="tel"
        />

        {mode === "register" && (
          <Field label={t("পুরো নাম")} value={name} onChange={(e) => setName(e.target.value)} required autoComplete="name" />
        )}

        {mode !== "login" && otpSent && (
          <Field
            label={t("OTP কোড")}
            inputMode="numeric"
            pattern="[0-9]{6}"
            maxLength={6}
            value={otp}
            onChange={(e) => setOtp(e.target.value)}
            required
            autoComplete="one-time-code"
          />
        )}

        {(mode === "login" || otpSent) && (
          <Field
            label={mode === "reset" ? t("নতুন পাসওয়ার্ড") : t("পাসওয়ার্ড")}
            type="password"
            minLength={8}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            autoComplete={mode === "login" ? "current-password" : "new-password"}
            hint={mode !== "login" ? t("কমপক্ষে ৮ অক্ষর") : undefined}
          />
        )}

        <ErrorNote>{error}</ErrorNote>
        <SuccessNote>{notice}</SuccessNote>

        <Button type="submit" loading={busy} className="h-12 text-base">
          {mode === "login" ? t("লগইন") : otpSent ? (mode === "register" ? t("অ্যাকাউন্ট খুলুন") : t("পাসওয়ার্ড বদলান")) : t("OTP পাঠান")}
        </Button>

        <div className="flex flex-wrap justify-between gap-2 text-[15px]">
          {mode !== "login" ? (
            <button type="button" className="font-semibold text-brand" onClick={() => switchTo("login")}>
              {t("লগইনে ফিরে যান")}
            </button>
          ) : (
            <>
              {allowRegister && (
                <button type="button" className="font-semibold text-brand" onClick={() => switchTo("register")}>
                  {t("নতুন অ্যাকাউন্ট খুলুন")}
                </button>
              )}
              <button type="button" className="text-muted" onClick={() => switchTo("reset")}>
                {t("পাসওয়ার্ড ভুলে গেছেন?")}
              </button>
            </>
          )}
        </div>
        {mode === "login" && (
          <Link to="/" className="text-center text-sm text-muted">
            {t("হোমে ফিরে যান")}
          </Link>
        )}
      </form>
    </div>
  );
}
