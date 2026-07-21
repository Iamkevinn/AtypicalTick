// frontend-enfoque/src/app/cierre/page.js
"use client";
import { useEffect, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import Link from 'next/link';
import { API_BASE } from "@/lib/api";

export default function CierreDiario() {
  const [tareas, setTareas] = useState([]);
  const [cargando, setCargando] = useState(true);
  const [hayLogros, setHayLogros] = useState(false);
  const [errorCierre, setErrorCierre] = useState(null);


  useEffect(() => {
    fetch(`${API_BASE}/api/cierre-diario`)
      .then((res) => res.json())
      .then((data) => {
        setTareas(data.tareas || []);
        setCargando(false);
      })
      .catch((err) => {
        console.error("Error al cargar cierre:", err);
        setCargando(false);
      });
  }, []);

  const marcarComoHecha = async (tarea) => {
    setTareas(prev => prev.filter(t => t.id !== tarea.id));
    setErrorCierre(null);
    try {
      const res = await fetch(`${API_BASE}/api/completar-retroactivo/${tarea.proyecto_id}/${tarea.id}?tarea_nombre=${encodeURIComponent(tarea.titulo)}&carpeta=${encodeURIComponent(tarea.carpeta)}`, { method: "POST" });
      if (!res.ok) throw new Error("fallo_backend");
      setHayLogros(true);
    } catch (error) {
      setTareas(prev => [...prev, tarea]);
      setErrorCierre("No se pudo guardar. Intenta de nuevo.");
    }
  };

  const dejarParaManana = async (tarea) => {
    setTareas(prev => prev.filter(t => t.id !== tarea.id));
    setErrorCierre(null);
    try {
      const res = await fetch(`${API_BASE}/api/posponer-cierre/${tarea.proyecto_id}/${tarea.id}?tarea_nombre=${encodeURIComponent(tarea.titulo)}&carpeta=${encodeURIComponent(tarea.carpeta)}`, { method: "POST" });
      if (!res.ok) throw new Error("fallo_backend");
    } catch (error) {
      setTareas(prev => [...prev, tarea]);
      setErrorCierre("No se pudo guardar. Intenta de nuevo.");
    }
  };

  const noRecuerdo = async (tarea) => {
    setTareas(prev => prev.filter(t => t.id !== tarea.id));
    setErrorCierre(null);
    try {
      const res = await fetch(`${API_BASE}/api/olvido-cierre/${tarea.proyecto_id}/${tarea.id}?tarea_nombre=${encodeURIComponent(tarea.titulo)}&carpeta=${encodeURIComponent(tarea.carpeta)}`, { method: "POST" });
      if (!res.ok) throw new Error("fallo_backend");
    } catch (error) {
      setTareas(prev => [...prev, tarea]);
      setErrorCierre("No se pudo guardar. Intenta de nuevo.");
    }
  };

  return (
    <main className="min-h-screen bg-[#0f172a] flex flex-col items-center p-6 font-sans overflow-y-auto selection:bg-indigo-500/30 text-indigo-100">

      <Link href="/">
        <button className="absolute top-6 left-6 text-indigo-300 hover:text-white text-sm flex items-center gap-2 bg-black/20 px-4 py-2 rounded-full transition-all border border-indigo-500/20">
          ← Volver
        </button>
      </Link>

      <div className="max-w-2xl w-full flex flex-col mt-20 pb-20">

        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} className="mb-10 text-center">
          <span className="text-5xl mb-4 block">🌙</span>
          <h1 className="text-3xl font-medium text-white mb-3">Revisión del Día</h1>
          <p className="text-indigo-200/70 text-sm leading-relaxed max-w-sm mx-auto">
            A veces la mente nos dice que no hicimos nada. Rescatemos lo que sí lograste hacer en la vida real, aunque olvidaras anotarlo.
          </p>
        </motion.div>

        {/* MENSAJE CORREGIDO: Enfoque en recuperación de memoria, no en cantidad de checks */}
        {hayLogros && (
          <motion.div initial={{ scale: 0.9, opacity: 0 }} animate={{ scale: 1, opacity: 1 }} className="mb-8 p-5 rounded-2xl bg-indigo-500/10 border border-indigo-500/30 text-center">
            <p className="text-indigo-200 text-sm font-medium">
              Tu memoria del día ahora es más completa. 🌿<br />
              <span className="text-indigo-300/70 font-normal mt-1 block">Has recuperado acciones que tu mente había descartado como "día perdido".</span>
            </p>
          </motion.div>
        )}

        {errorCierre && (
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="mb-6 p-4 rounded-2xl bg-red-900/20 border border-red-800/30 text-red-300 text-sm text-center">
            ⚠️ {errorCierre}
          </motion.div>
        )}
        
        {cargando ? (
          <div className="flex justify-center py-20">
            <span className="animate-pulse text-indigo-400">Recopilando tu día...</span>
          </div>
        ) : tareas.length > 0 ? (
          <motion.div className="flex flex-col gap-4">
            <AnimatePresence>
              {tareas.map((tarea) => (
                <motion.div
                  key={tarea.id}
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, scale: 0.95, x: -20 }}
                  className="bg-slate-800/50 border border-slate-700/50 p-5 rounded-3xl flex flex-col md:flex-row md:items-center justify-between gap-5 shadow-lg"
                >
                  <div className="flex-1">
                    <p className="text-xs text-indigo-400 uppercase tracking-wider mb-1 font-semibold flex gap-2 items-center">
                      📁 {tarea.carpeta}
                      {tarea.es_rutina && <span className="bg-indigo-900/50 px-2 py-0.5 rounded text-xs">Rutina</span>}
                    </p>
                    <p className="text-lg font-medium text-slate-100">{tarea.titulo}</p>
                  </div>

                  {/* BOTONES ACTUALIZADOS: 3 Opciones claras */}
                  <div className="flex flex-col sm:flex-row md:flex-col lg:flex-row gap-2 shrink-0">
                    <button
                      onClick={() => marcarComoHecha(tarea)}
                      className="flex-1 px-5 py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white font-medium text-sm transition-all active:scale-95 text-center"
                    >
                      ✓ Sí lo hice
                    </button>

                    <button
                      onClick={() => dejarParaManana(tarea)}
                      className="flex-1 px-5 py-2.5 rounded-xl bg-transparent border border-slate-600 text-slate-300 hover:bg-slate-800 hover:text-white text-sm transition-all active:scale-95 text-center"
                    >
                      ○ Aún no
                    </button>

                    <button
                      onClick={() => noRecuerdo(tarea)}
                      className="flex-1 px-5 py-2.5 rounded-xl bg-transparent border border-slate-700/50 text-slate-400 hover:bg-slate-800 hover:text-slate-300 text-sm transition-all active:scale-95 text-center"
                      title="Registraremos esto para ayudarte con recordatorios a futuro."
                    >
                      ❓ No recuerdo
                    </button>
                  </div>
                </motion.div>
              ))}
            </AnimatePresence>
          </motion.div>
        ) : (
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="text-center py-20 flex flex-col items-center">
            <span className="text-4xl mb-4 opacity-50">🏕️</span>
            <p className="text-indigo-200/70 text-lg">Tu día está limpio y cerrado.</p>
            <p className="text-indigo-300 text-sm mt-2">Ya puedes descansar tranquilo.</p>
          </motion.div>
        )}

      </div>
    </main>
  );
}