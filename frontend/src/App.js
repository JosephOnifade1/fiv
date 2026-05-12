import React from "react";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { AuthProvider, useAuth } from "@/AuthContext";
import Login from "@/pages/Login";
import Dashboard from "@/pages/Dashboard";
import { Toaster } from "@/components/ui/sonner";
import "@/App.css";

const Gate = () => {
  const { user, loading } = useAuth();
  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-white">
        <span className="text-[10px] uppercase tracking-[0.3em] font-mono text-zinc-400">Booting terminal…</span>
      </div>
    );
  }
  return user ? <Dashboard /> : <Login />;
};

function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Gate />} />
          <Route path="*" element={<Navigate to="/" />} />
        </Routes>
      </BrowserRouter>
      <Toaster position="bottom-right" />
    </AuthProvider>
  );
}

export default App;
