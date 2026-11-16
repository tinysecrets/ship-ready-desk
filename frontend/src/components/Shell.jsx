import { Link, NavLink } from "react-router-dom";

const nav = ({ isActive }) =>
  `font-mono text-xs uppercase tracking-widest transition-colors duration-200 ${isActive ? "text-[#c6f24e]" : "text-[#8a8a94] hover:text-[#e9e9ee]"}`;

export const Header = () => (
  <header className="border-b border-[#23232a]">
    <div className="mx-auto flex max-w-6xl items-center justify-between px-5 py-5 sm:px-8">
      <Link to="/" data-testid="nav-home-link" className="group flex items-center gap-2">
        <span className="inline-block h-2.5 w-2.5 bg-[#c6f24e] transition-transform duration-300 group-hover:rotate-45" />
        <span className="text-base font-extrabold tracking-tight">Shipready</span>
      </Link>
      <nav className="flex items-center gap-5 sm:gap-7">
        <NavLink to="/s/shipready-sprint" className={nav} data-testid="nav-store-link">Store</NavLink>
        <NavLink to="/proof" className={nav} data-testid="nav-proof-link">Proof</NavLink>
        <NavLink to="/desk" className={nav} data-testid="nav-desk-link">Desk</NavLink>
      </nav>
    </div>
  </header>
);

export const Footer = () => (
  <footer className="mt-24 border-t border-[#23232a]">
    <div className="mx-auto flex max-w-6xl flex-col gap-3 px-5 py-8 text-xs text-[#8a8a94] sm:flex-row sm:items-center sm:justify-between sm:px-8">
      <span className="font-mono">Money figures are estimated / ledger-derived, not bank settlement.</span>
      <Link to="/access" className="font-mono uppercase tracking-widest hover:text-[#e9e9ee]" data-testid="footer-access-link">Operator access</Link>
    </div>
  </footer>
);

export const Shell = ({ children }) => (
  <div className="grain flex min-h-screen flex-col">
    <Header />
    <main className="mx-auto w-full max-w-6xl flex-1 px-5 sm:px-8">{children}</main>
    <Footer />
  </div>
);

export const Label = ({ children, className = "" }) => (
  <div className={`font-mono text-[11px] uppercase tracking-[0.2em] text-[#8a8a94] ${className}`}>{children}</div>
);

export const Disclaimer = ({ testid }) => (
  <p data-testid={testid} className="font-mono text-[11px] text-[#8a8a94]">estimated / ledger-derived, not bank settlement</p>
);

const BADGE = {
  live: "text-[#c6f24e] border-[#c6f24e]/30 bg-[#c6f24e]/10",
  test: "text-[#ffb86c] border-[#ffb86c]/30 bg-[#ffb86c]/10",
  revoked: "text-[#ff5555] border-[#ff5555]/30 bg-[#ff5555]/10",
  neutral: "text-[#e9e9ee] border-[#23232a] bg-[#121216]",
};

export const Badge = ({ kind = "neutral", children, testid }) => (
  <span data-testid={testid} className={`inline-flex items-center gap-1.5 border px-2 py-0.5 font-mono text-[11px] uppercase tracking-wider ${BADGE[kind]}`}>
    {children}
  </span>
);
