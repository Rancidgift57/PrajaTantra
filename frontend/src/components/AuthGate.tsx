"use client";

import { Landmark, Lock, Mail, ShieldCheck, UserPlus, Vote } from "lucide-react";
import { useState } from "react";

import { api, AuthResponse, Ideology } from "@/lib/api";

const IDEOLOGIES: { value: Ideology; label: string; hindi: string }[] = [
  { value: "Industrialist", label: "Industrialist", hindi: "औद्योगिक" },
  { value: "Green",         label: "Green",         hindi: "हरित" },
  { value: "Socialist",     label: "Socialist",     hindi: "समाजवादी" },
  { value: "Nationalist",   label: "Nationalist",   hindi: "राष्ट्रवादी" },
  { value: "Technocrat",    label: "Technocrat",    hindi: "तकनीकविद" },
];

export default function AuthGate({ onAuth }: { onAuth: (auth: AuthResponse) => void }) {
  const [mode, setMode] = useState<"login" | "register">("register");
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [cityName, setCityName] = useState("");
  const [ideology, setIdeology] = useState<Ideology>("Technocrat");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const response =
        mode === "register"
          ? await api.register({ username, email, password, city_name: cityName, ideology })
          : await api.login({ username_or_email: username, password });
      onAuth(response);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Pravesh asafal raha. Phir koshish karein.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div
      className="flex min-h-screen items-center justify-center p-4"
      style={{
        background:
          "radial-gradient(ellipse 60% 50% at 20% 10%, rgba(255,107,0,0.08) 0%, transparent 60%)," +
          "radial-gradient(ellipse 60% 50% at 80% 90%, rgba(11,78,162,0.10) 0%, transparent 60%)," +
          "var(--pt-ink)",
      }}
    >
      <div className="w-full max-w-md">
        {/* Tricolour strip */}
        <div className="tricolour-bar mb-6" style={{ maxWidth: "120px", margin: "0 auto 1.5rem" }} />

        <div className="mb-6 text-center">
          <div className="mb-2 flex items-center justify-center gap-2">
            <Landmark className="h-7 w-7" style={{ color: "var(--pt-saffron)" }} />
            <h1 className="text-2xl font-black tracking-tight">PrajaTantra</h1>
          </div>
          <p className="text-xs" style={{ color: "var(--pt-muted)" }}>
            लोकतंत्र सिमुलेटर — अपनी सरकार बनाइए
          </p>
        </div>

        {/* Mode switch */}
        <div
          className="mb-5 grid grid-cols-2 p-1"
          style={{ border: "1px solid var(--pt-line)", background: "var(--pt-panel)" }}
        >
          <button
            type="button"
            onClick={() => { setMode("register"); setError(null); }}
            className="flex h-11 items-center justify-center gap-2 text-xs font-black uppercase transition-all"
            style={
              mode === "register"
                ? { background: "var(--pt-saffron)", color: "#fff" }
                : { color: "var(--pt-muted)" }
            }
          >
            <UserPlus className="h-4 w-4" />
            Naya Khata
          </button>
          <button
            type="button"
            onClick={() => { setMode("login"); setError(null); }}
            className="flex h-11 items-center justify-center gap-2 text-xs font-black uppercase transition-all"
            style={
              mode === "login"
                ? { background: "var(--pt-wheel)", color: "#fff" }
                : { color: "var(--pt-muted)" }
            }
          >
            <Lock className="h-4 w-4" />
            Login
          </button>
        </div>

        <form
          onSubmit={handleSubmit}
          className="grid gap-3 p-5"
          style={{ border: "1px solid var(--pt-line)", background: "var(--pt-panel)" }}
        >
          <Field
            label={mode === "register" ? "Username" : "Username ya Email"}
            hindi="उपयोगकर्ता नाम"
            icon={<UserPlus className="h-4 w-4" />}
            value={username}
            onChange={setUsername}
            placeholder="CM_Nikhil"
          />

          {mode === "register" && (
            <Field
              label="Email"
              hindi="ईमेल"
              icon={<Mail className="h-4 w-4" />}
              type="email"
              value={email}
              onChange={setEmail}
              placeholder="nikhil@example.com"
            />
          )}

          <Field
            label="Password"
            hindi="पासवर्ड"
            icon={<Lock className="h-4 w-4" />}
            type="password"
            value={password}
            onChange={setPassword}
            placeholder="••••••••"
          />

          {mode === "register" && (
            <>
              <Field
                label="Apne Shehar ka Naam"
                hindi="अपने शहर का नाम रखें"
                icon={<Landmark className="h-4 w-4" />}
                value={cityName}
                onChange={setCityName}
                placeholder="e.g. Suryaling Nagar, Veer Bhoomi…"
              />

              <div>
                <div className="mb-1 flex items-center gap-1 text-[10px] uppercase" style={{ color: "var(--pt-muted)" }}>
                  <Vote className="h-3 w-3" />
                  Rajnaitik Vichardhara (Ideology)
                </div>
                <div className="grid grid-cols-3 gap-1">
                  {IDEOLOGIES.map((ideo) => (
                    <button
                      key={ideo.value}
                      type="button"
                      onClick={() => setIdeology(ideo.value)}
                      className="flex flex-col items-center justify-center gap-0.5 px-1 py-2 text-[10px] font-bold uppercase transition-all"
                      style={
                        ideology === ideo.value
                          ? { background: "var(--pt-green)", color: "#fff", border: "1px solid var(--pt-green)" }
                          : { color: "var(--pt-muted)", border: "1px solid var(--pt-line)" }
                      }
                    >
                      <span>{ideo.label}</span>
                      <span style={{ opacity: 0.7 }}>{ideo.hindi}</span>
                    </button>
                  ))}
                </div>
              </div>
            </>
          )}

          {error && (
            <div
              className="px-3 py-2 text-xs font-bold"
              style={{ border: "1px solid var(--pt-red)", color: "var(--pt-red-lt)", background: "var(--pt-ink)" }}
            >
              ⚠️ {error}
            </div>
          )}

          <button
            type="submit"
            disabled={loading}
            className="mt-2 flex h-12 items-center justify-center gap-2 font-black uppercase tracking-wide disabled:opacity-50"
            style={{
              background: mode === "register" ? "var(--pt-saffron)" : "var(--pt-wheel)",
              color: "#fff",
              border: "none",
            }}
          >
            <ShieldCheck className="h-5 w-5" />
            {loading
              ? "Pravesh ho raha hai…"
              : mode === "register"
              ? "Sarkar Sthapit Karein 🇮🇳"
              : "Pravesh Karein"}
          </button>
        </form>

        <p className="mt-4 text-center text-[10px]" style={{ color: "var(--pt-muted)" }}>
          Aapka data sirf is simulation session ke liye save hota hai. · Jai Hind!
        </p>
      </div>
    </div>
  );
}

function Field({
  label, hindi, icon, value, onChange, placeholder, type = "text",
}: {
  label: string;
  hindi: string;
  icon: React.ReactNode;
  value: string;
  onChange: (v: string) => void;
  placeholder: string;
  type?: string;
}) {
  return (
    <label className="grid gap-1">
      <span className="flex items-center gap-1 text-[10px] uppercase" style={{ color: "var(--pt-muted)" }}>
        {icon}
        {label}
        <span style={{ opacity: 0.6 }}>· {hindi}</span>
      </span>
      <input
        type={type}
        required
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="h-11 px-3 text-sm outline-none"
        style={{ background: "var(--pt-ink)", border: "1px solid var(--pt-line)", color: "var(--pt-white)" }}
      />
    </label>
  );
}