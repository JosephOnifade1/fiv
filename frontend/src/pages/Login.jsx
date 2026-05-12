import React, { useState } from "react";
import { useAuth } from "../AuthContext";
import { Input } from "../components/ui/input";
import { Button } from "../components/ui/button";
import { Label } from "../components/ui/label";
import { toast } from "sonner";
import { TrendUp, ArrowRight } from "@phosphor-icons/react";

export default function Login() {
  const { login, register } = useAuth();
  const [mode, setMode] = useState("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    try {
      if (mode === "login") {
        await login(email, password);
      } else {
        await register(email, password, name);
      }
      toast.success(mode === "login" ? "Welcome back." : "Account created.");
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Authentication failed");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="min-h-screen w-full grid lg:grid-cols-2 bg-white">
      <div className="hidden lg:flex flex-col justify-between p-12 border-r border-zinc-200 bg-zinc-50 relative overflow-hidden">
        <div className="flex items-center gap-3 z-10">
          <div className="w-8 h-8 bg-black flex items-center justify-center">
            <TrendUp size={18} weight="bold" color="#F59E0B" />
          </div>
          <span className="font-black tracking-tight text-lg" style={{ fontFamily: "'Cabinet Grotesk', system-ui" }}>
            FIVERR&nbsp;SCOUT
          </span>
        </div>
        <div className="z-10">
          <p className="text-[10px] uppercase tracking-[0.3em] text-zinc-500 mb-4">A niche arbitrage terminal</p>
          <h1 className="text-5xl font-black tracking-tighter leading-[0.95] mb-6" style={{ fontFamily: "'Cabinet Grotesk', system-ui" }}>
            Find the gigs<br />Fiverr's algorithm<br />is <span className="text-amber-500">hungry for.</span>
          </h1>
          <p className="text-sm text-zinc-600 max-w-md leading-relaxed font-mono">
            Deep-scrape competition density, order queue depth and review velocity.
            Score every niche 0-100 and surface 5:1 demand-to-supply gaps in seconds.
          </p>
        </div>
        <div className="z-10 grid grid-cols-3 gap-px bg-zinc-200">
          {[
            { l: "OPP. SCORE", v: "0-100" },
            { l: "RATIO GOLD", v: ">5x" },
            { l: "AI", v: "Gemini 3" },
          ].map((s) => (
            <div key={s.l} className="bg-zinc-50 p-4">
              <div className="text-[10px] uppercase tracking-[0.2em] text-zinc-500 font-mono">{s.l}</div>
              <div className="text-xl font-bold mt-1" style={{ fontFamily: "'Cabinet Grotesk', system-ui" }}>{s.v}</div>
            </div>
          ))}
        </div>
        <div className="absolute inset-0 opacity-[0.04] pointer-events-none"
             style={{ backgroundImage: "radial-gradient(#000 1px, transparent 1px)", backgroundSize: "16px 16px" }} />
      </div>

      <div className="flex items-center justify-center p-8">
        <form onSubmit={submit} className="w-full max-w-md space-y-6" data-testid="auth-form">
          <div>
            <p className="text-[10px] uppercase tracking-[0.3em] text-zinc-500 mb-2 font-mono">
              {mode === "login" ? "Operator Sign-in" : "Provision Access"}
            </p>
            <h2 className="text-3xl font-black tracking-tight" style={{ fontFamily: "'Cabinet Grotesk', system-ui" }}>
              {mode === "login" ? "Enter the terminal" : "Create your account"}
            </h2>
          </div>

          {mode === "register" && (
            <div>
              <Label className="text-[10px] uppercase tracking-[0.2em] font-mono text-zinc-600">Name</Label>
              <Input
                data-testid="auth-name"
                className="mt-2 rounded-none border-zinc-300 focus-visible:ring-0 focus-visible:border-black h-11"
                value={name}
                onChange={(e) => setName(e.target.value)}
                required
              />
            </div>
          )}

          <div>
            <Label className="text-[10px] uppercase tracking-[0.2em] font-mono text-zinc-600">Email</Label>
            <Input
              data-testid="auth-email"
              type="email"
              className="mt-2 rounded-none border-zinc-300 focus-visible:ring-0 focus-visible:border-black h-11"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
          </div>

          <div>
            <Label className="text-[10px] uppercase tracking-[0.2em] font-mono text-zinc-600">Password</Label>
            <Input
              data-testid="auth-password"
              type="password"
              className="mt-2 rounded-none border-zinc-300 focus-visible:ring-0 focus-visible:border-black h-11"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              minLength={6}
            />
          </div>

          <Button
            data-testid="auth-submit"
            type="submit"
            disabled={busy}
            className="w-full rounded-none bg-black hover:bg-zinc-800 text-white h-11 font-mono uppercase tracking-[0.2em] text-xs"
          >
            {busy ? "..." : mode === "login" ? "Sign in" : "Create account"}
            <ArrowRight size={14} weight="bold" className="ml-2" />
          </Button>

          <button
            type="button"
            data-testid="auth-toggle"
            onClick={() => setMode(mode === "login" ? "register" : "login")}
            className="block w-full text-xs text-zinc-500 hover:text-black font-mono"
          >
            {mode === "login" ? "No account? Register →" : "Have an account? Sign in →"}
          </button>
        </form>
      </div>
    </div>
  );
}
