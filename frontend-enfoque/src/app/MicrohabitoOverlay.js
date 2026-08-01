// src/app/MicrohabitoOverlay.js
"use client";
import { useEffect, useRef, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { apiFetch } from "@/lib/api";

// Cada cuánto se pregunta al backend si hay un microhábito vencido.
// Deliberadamente independiente del polling de /api/enfoque -- esto
// debe poder aparecer sin importar qué tarea esté activa o qué
// pantalla se esté mirando.
const INTERVALO_CONSULTA_MS = 60 * 1000;

export default function MicrohabitoOverlay() {
  const [pendiente, setPendiente] = useState(null);
  const [enviando, setEnviando] = useState(false);
  const consultando = useRef(false);

  const consultar = async () => {
    if (consultando.current) return;
    consultando.current = true;
    try {
      const res = await apiFetch(`/api/microhabito`);
      if (res.ok) {
        const data = await res.json();
        setPendiente((actual) => actual || data.pendiente);
      }
    } catch (e) {
      // Silencioso a propósito: esto es bienestar de fondo, no algo
      // crítico -- un fallo de red aquí no debe generar un error visible.
    } finally {
      consultando.current = false;
    }
  };

  useEffect(() => {
    consultar();
    const id = setInterval(consultar, INTERVALO_CONSULTA_MS);
    return () => clearInterval(id);
  }, []);

  const responder = async (accion) => {
    if (!pendiente || enviando) return;
    setEnviando(true);

    const categoria = pendiente.categoria;

    try {
      await apiFetch(`/api/microhabito/${categoria}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ accion }),
      });
    } catch (e) {
      // Igual se cierra localmente aunque falle la red -- no vale la
      // pena insistir ni mostrar un error por esto.
    }

    setPendiente(null);
    setEnviando(false);
  };

  return (
    <AnimatePresence>
      {pendiente && (
        <motion.div
          key={pendiente.categoria}
          initial={{ opacity: 0, y: 30, scale: 0.95 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          exit={{ opacity: 0, y: 20, scale: 0.95 }}
          transition={{ duration: 0.3 }}
          className="fixed bottom-6 right-6 z-[70] max-w-xs w-[calc(100%-3rem)] sm:w-80 bg-zinc-900/95 backdrop-blur-md border border-white/10 rounded-2xl p-5 shadow-2xl"
        >
          <div className="flex items-start gap-3 mb-3">
            <span className="text-3xl">{pendiente.emoji}</span>
            <div>
              <p className="text-zinc-100 font-semibold text-sm">{pendiente.titulo}</p>
              <p className="text-zinc-400 text-xs mt-1 leading-relaxed">{pendiente.instrucciones}</p>
            </div>
          </div>

          <div className="flex gap-2">
            <button
              onClick={() => responder("hecho")}
              disabled={enviando}
              className="flex-1 py-2 rounded-xl text-xs font-semibold bg-emerald-600/80 hover:bg-emerald-600 text-white transition-all active:scale-95 disabled:opacity-50"
            >
              Hecho
            </button>
            <button
              onClick={() => responder("pospuesto")}
              disabled={enviando}
              className="flex-1 py-2 rounded-xl text-xs font-medium bg-zinc-800 hover:bg-zinc-700 text-zinc-300 transition-all active:scale-95 disabled:opacity-50"
            >
              5 minutos
            </button>
            <button
              onClick={() => responder("ignorado")}
              disabled={enviando}
              className="px-3 py-2 rounded-xl text-xs text-zinc-500 hover:text-zinc-300 transition-all active:scale-95 disabled:opacity-50"
            >
              ✕
            </button>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}