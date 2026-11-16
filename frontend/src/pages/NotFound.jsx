import { Link } from "react-router-dom";
import { Shell, Label } from "../components/Shell";

export default function NotFound() {
  return (
    <Shell>
      <section className="py-24 sm:py-32">
        <Label>404</Label>
        <h1 data-testid="not-found-heading" className="mt-6 text-4xl font-black tracking-tight sm:text-5xl lg:text-6xl">Nothing at this address.</h1>
        <pre className="mt-8 overflow-x-auto border border-[#23232a] bg-[#121216] p-4 font-mono text-xs text-[#8a8a94]">
{`GET ${typeof window !== "undefined" ? window.location.pathname : ""}\n→ no ship, certificate or page here`}
        </pre>
        <Link to="/" data-testid="not-found-home-link" className="mt-8 inline-block font-mono text-xs uppercase tracking-widest text-[#c6f24e] hover:underline">← Back to Shipready</Link>
      </section>
    </Shell>
  );
}
