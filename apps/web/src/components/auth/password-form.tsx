"use client";

import { Eye, EyeOff, KeyRound, Loader2 } from "lucide-react";
import { type FormEvent, useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useCompleteMfaLogin, usePasswordLogin, useRegister } from "@/lib/api";

export const MIN_PASSWORD_LENGTH = 12;

export type Mode = "sign-in" | "register";

function errorText(error: unknown): string | null {
  if (!error) return null;
  return error instanceof Error ? error.message : "Something went wrong. Please try again.";
}

export function PasswordField({
  id,
  label,
  value,
  onChange,
  autoComplete,
  minLength,
}: {
  id: string;
  label: string;
  value: string;
  onChange: (value: string) => void;
  autoComplete: "current-password" | "new-password";
  minLength?: number;
}) {
  const [visible, setVisible] = useState(false);
  return (
    <div>
      <label htmlFor={id} className="mb-1 block text-xs font-medium">
        {label}
      </label>
      <div className="relative">
        <Input
          id={id}
          type={visible ? "text" : "password"}
          required
          minLength={minLength}
          maxLength={128}
          autoComplete={autoComplete}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          className="pr-9"
        />
        <button
          type="button"
          onClick={() => setVisible((v) => !v)}
          className="absolute inset-y-0 right-0 flex w-9 items-center justify-center text-muted-foreground hover:text-foreground"
          aria-label={visible ? "Hide password" : "Show password"}
          aria-pressed={visible}
        >
          {visible ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
        </button>
      </div>
    </div>
  );
}

export function PasswordForm({
  next,
  mode,
  onModeChange,
}: {
  next: string;
  mode: Mode;
  onModeChange: (mode: Mode) => void;
}) {
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [mfaToken, setMfaToken] = useState<string | null>(null);
  const [code, setCode] = useState("");
  const login = usePasswordLogin();
  const register = useRegister();
  const mfa = useCompleteMfaLogin();

  function done() {
    // Full navigation so every cache starts fresh for the signed-in user.
    window.location.assign(next);
  }

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    if (mode === "register") {
      await register.mutateAsync({
        email: email.trim(),
        password,
        ...(name.trim() ? { display_name: name.trim() } : {}),
      });
      done();
      return;
    }
    const result = await login.mutateAsync({ email: email.trim(), password });
    if (result.mfa_required && result.mfa_token) {
      setPassword("");
      setMfaToken(result.mfa_token);
      return;
    }
    done();
  }

  async function onSubmitCode(event: FormEvent) {
    event.preventDefault();
    if (!mfaToken) return;
    try {
      await mfa.mutateAsync({ mfa_token: mfaToken, code: code.trim() });
      done();
    } catch (error) {
      // Expired or exhausted ticket: start over from the password step.
      const status = (error as { status?: number }).status;
      if (status === 401 || status === 429) setMfaToken(null);
      setCode("");
    }
  }

  if (mfaToken) {
    return (
      <form onSubmit={(e) => void onSubmitCode(e)} className="space-y-3" noValidate>
        <p className="flex items-center gap-1.5 text-sm font-medium">
          <KeyRound className="size-4" aria-hidden="true" />
          Two-step verification
        </p>
        <p className="text-[13px] text-muted-foreground">
          Enter the 6-digit code from your authenticator app, or one of your recovery codes.
        </p>
        <div>
          <label htmlFor="mfa-code" className="sr-only">
            Verification code
          </label>
          <Input
            id="mfa-code"
            required
            autoFocus
            inputMode="text"
            autoComplete="one-time-code"
            placeholder="123456"
            maxLength={32}
            value={code}
            onChange={(e) => setCode(e.target.value)}
          />
        </div>
        {mfa.isError ? (
          <p role="alert" className="text-xs text-destructive">
            {errorText(mfa.error)}
          </p>
        ) : null}
        <Button type="submit" className="w-full" disabled={mfa.isPending || code.trim().length < 6}>
          {mfa.isPending ? <Loader2 className="animate-spin" /> : null}
          Verify
        </Button>
        <button
          type="button"
          className="w-full text-center text-xs text-muted-foreground hover:text-foreground"
          onClick={() => {
            setMfaToken(null);
            setCode("");
          }}
        >
          Back
        </button>
      </form>
    );
  }

  const active = mode === "register" ? register : login;
  return (
    <form onSubmit={(e) => void onSubmit(e).catch(() => undefined)} className="space-y-3">
      {mode === "register" ? (
        <div>
          <label htmlFor="pw-name" className="mb-1 block text-xs font-medium">
            Full name
          </label>
          <Input
            id="pw-name"
            autoComplete="name"
            maxLength={200}
            value={name}
            onChange={(e) => setName(e.target.value)}
          />
        </div>
      ) : null}
      <div>
        <label htmlFor="pw-email" className="mb-1 block text-xs font-medium">
          Email
        </label>
        <Input
          id="pw-email"
          type="email"
          required
          autoComplete="email"
          placeholder="you@example.com"
          maxLength={320}
          value={email}
          onChange={(e) => setEmail(e.target.value)}
        />
      </div>
      <PasswordField
        id="pw-password"
        label="Password"
        value={password}
        onChange={setPassword}
        autoComplete={mode === "register" ? "new-password" : "current-password"}
        minLength={mode === "register" ? MIN_PASSWORD_LENGTH : undefined}
      />
      {mode === "register" ? (
        <p className="text-xs text-muted-foreground">
          {MIN_PASSWORD_LENGTH}–128 characters. A few random words is strong and easy to remember.
        </p>
      ) : null}
      {active.isError ? (
        <p role="alert" className="text-xs text-destructive">
          {errorText(active.error)}
        </p>
      ) : null}
      <Button type="submit" size="lg" className="w-full rounded-full" disabled={active.isPending}>
        {active.isPending ? <Loader2 className="animate-spin" /> : null}
        {mode === "register" ? "Create account" : "Sign in"}
      </Button>
      <p className="text-center text-xs text-muted-foreground">
        {mode === "register" ? "Already have an account?" : "New to Saige Vault?"}{" "}
        <button
          type="button"
          className="font-medium text-foreground underline-offset-4 hover:underline"
          onClick={() => {
            login.reset();
            register.reset();
            onModeChange(mode === "register" ? "sign-in" : "register");
          }}
        >
          {mode === "register" ? "Sign in" : "Create an account"}
        </button>
      </p>
    </form>
  );
}
