// app/login/page.js
"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import { login, haySesion } from "@/lib/api";

export default function Login() {
  const router = useRouter();
  const [password, setPassword] = useState("");
  const [cargando, setCargando] = useState(false);
  const [error, setError] = useState(null);

  const manejarSubmit = async (e) => {
    e.preventDefault();
    if (!password || cargando) return;

    setCargando(true);
    setError(null);

    try {
      await login(password);
      router.replace("/");
    } catch (err) {
      setError(err.message || "No se pudo iniciar sesión.");
      setCargando(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#09090b] flex items-center justify-center px-6">
      <motion.form
        onSubmit={manejarSubmit}
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4 }}
        className="w-full max-w-sm flex flex-col gap-4"
      >
        <div className="text-center mb-2">
          <h1 className="text-xl font-medium text-zinc-100">AtypicalTick</h1>
          <p className="text-sm text-zinc-500 mt-1">Un paso a la vez.</p>
        </div>

        <input
          type="password"
          autoFocus
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          placeholder="Contraseña"
          className="w-full rounded-xl bg-zinc-900 border border-zinc-800 px-4 py-3 text-zinc-100 placeholder:text-zinc-600 outline-none focus:border-zinc-600"
        />

        {error && (
          <p className="text-sm text-red-400 text-center">{error}</p>
        )}

        <button
          type="submit"
          disabled={cargando || !password}
          className="w-full rounded-xl bg-blue-50 text-blue-900 hover:bg-blue-100 disabled:opacity-50 disabled:cursor-not-allowed py-3 font-medium transition-colors"
        >
          {cargando ? "Entrando..." : "Entrar"}
        </button>
      </motion.form>
    </div>
  );
}