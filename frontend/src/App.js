import "@/App.css";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { Toaster } from "./components/ui/sonner";
import Landing from "./pages/Landing";
import Store from "./pages/Store";
import Access from "./pages/Access";
import Desk from "./pages/Desk";
import Drafts from "./pages/Drafts";
import Proof from "./pages/Proof";
import Certificate from "./pages/Certificate";
import NotFound from "./pages/NotFound";

function App() {
  return (
    <div className="App">
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Landing />} />
          <Route path="/s/:slug" element={<Store />} />
          <Route path="/access" element={<Access />} />
          <Route path="/desk" element={<Desk />} />
          <Route path="/desk/drafts" element={<Drafts />} />
          <Route path="/proof" element={<Proof />} />
          <Route path="/p/:code" element={<Certificate />} />
          <Route path="*" element={<NotFound />} />
        </Routes>
      </BrowserRouter>
      <Toaster theme="dark" position="bottom-right" toastOptions={{ style: { borderRadius: 0, background: "#121216", border: "1px solid #23232a", color: "#e9e9ee" } }} />
    </div>
  );
}

export default App;
