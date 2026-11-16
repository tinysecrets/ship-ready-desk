import axios from "axios";

export const api = axios.create({
  baseURL: `${process.env.REACT_APP_BACKEND_URL}/api`,
  withCredentials: true,
});

export const newIdemKey = () =>
  (window.crypto?.randomUUID?.() || `${Date.now()}-${Math.random().toString(36).slice(2)}`).replace(/-/g, "");

export const usd = (cents) => {
  if (cents === null || cents === undefined) return "—";
  const s = (Math.abs(cents) / 100).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  return `${cents < 0 ? "−" : ""}$${s}`;
};

export const when = (iso) => {
  if (!iso) return "never";
  const d = new Date(iso);
  return `${d.toISOString().replace("T", " ").slice(0, 19)} UTC`;
};

export const errMsg = (e, fallback = "Something went wrong.") => e?.response?.data?.detail || fallback;
