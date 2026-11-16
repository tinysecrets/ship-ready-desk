import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Loader2 } from "lucide-react";
import { Shell, Label } from "../components/Shell";
import { api, errMsg } from "../lib/api";

export default function Access() {
  const [secret, setSecret] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const navigate = useNavigate();

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      await api.post("/auth/login", { secret });
      setSecret("");
      navigate("/desk");
    } catch (err) {
      setError(err?.response?.status === 401 ? "Wrong secret." : errMsg(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Shell>
      <section className="mx-auto max-w-md py-20 sm:py-28">
        <Label>Operator access</Label>
        <h1 className="mt-5 text-4xl font-black tracking-tight sm:text-5xl">The desk.</h1>
        <p className="mt-3 text-sm text-[#8a8a94]">One shared operator secret. Session lasts 8 hours.</p>
        <form onSubmit={submit} className="mt-10 space-y-4" data-testid="access-form">
          <input data-testid="access-secret-input" type="password" autoComplete="off" required value={secret}
            onChange={(e) => setSecret(e.target.value)} placeholder="operator secret"
            className="w-full border border-[#23232a] bg-[#121216] px-4 py-3 font-mono text-sm text-[#e9e9ee] placeholder:text-[#55555e] transition-colors duration-200 focus:border-[#c6f24e] focus:outline-none" />
          <button data-testid="access-submit-button" disabled={busy}
            className="inline-flex w-full items-center justify-center gap-2 bg-[#c6f24e] px-6 py-3 text-sm font-bold text-[#0b0b0d] transition-colors duration-200 hover:bg-[#b2df3b] disabled:opacity-50">
            {busy && <Loader2 className="h-4 w-4 animate-spin" />} Open the desk
          </button>
          {error && <p data-testid="access-error-message" className="font-mono text-sm text-[#ff5555]">{error}</p>}
        </form>
      </section>
    </Shell>
  );
}
