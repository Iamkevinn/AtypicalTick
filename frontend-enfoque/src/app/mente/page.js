//frontend-enfoque/src/app/mente/page.js
"use client";
import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import Link from 'next/link';
import { API_BASE } from "@/lib/api";

export default function MiMente() {
  const [espejo, setEspejo] = useState(null);
  const [cargando, setCargando] = useState(true);

  useEffect(() => {
    fetch(`${API_BASE}/api/espejo-conductual`)
      .then((res) => res.json())
      .then((data) => {
        setEspejo(data);
        setCargando(false);
      })
      .catch((error) => {
        console.error("Error cargando espejo:", error);
        setCargando(false);
      });
  }, []);

  return (
    <main className="min-h-screen bg-[#09090b] flex flex-col items-center p-6 font-sans overflow-y-auto selection:bg-blue-500/30">

      <Link href="/">
        <button className="absolute top-6 left-6 text-zinc-400 hover:text-zinc-300 text-sm flex items-center gap-2 bg-black/20 px-4 py-2 rounded-full transition-all z-10 border border-white/5">
          ← Volver a mis tareas
        </button>
      </Link>

      <div className="max-w-2xl w-full flex flex-col mt-20 pb-20">

        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} className="mb-12 text-center">
          <span className="text-4xl mb-4 block">🗺️</span>
          {/* [CLÍNICO]: Cambio de "Identidad" a "Patrones de Acción" */}
          <h1 className="text-3xl font-medium text-zinc-100 mb-3">Patrones de Acción</h1>
          {/* [CLÍNICO]: Eliminación de la palabra "Define" */}
          <p className="text-zinc-400 text-sm leading-relaxed max-w-md mx-auto">
            Tu progreso no se mide solo por lo que terminas. También se refleja en cómo respondes cuando aparece la fricción.
          </p>
        </motion.div>

        {cargando ? (
          <div className="flex justify-center py-20"><span className="animate-pulse text-zinc-400 font-mono">Revisando tus interacciones recientes...</span></div>
        ) : espejo ? (
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ staggerChildren: 0.15 }} className="flex flex-col gap-6">

            {/* 1. LATENCIA DE ACTIVACIÓN (Ahora basada en TENDENCIAS) */}
            {espejo.latencia !== null && (
              <motion.div initial={{ opacity: 0, scale: 0.98 }} animate={{ opacity: 1, scale: 1 }} className="p-8 rounded-3xl bg-gradient-to-br from-[#121214] to-[#18181b] border border-zinc-800 flex flex-col md:flex-row items-center gap-8 shadow-2xl relative overflow-hidden">
                <div className="text-center md:text-left z-10">
                  <p className="text-xs uppercase tracking-widest text-zinc-400 mb-1 font-bold">Tiempo de Fricción</p>
                  <h2 className="text-2xl font-semibold text-zinc-200">Tiempo hasta el primer paso</h2>
                  <p className="text-sm text-zinc-400 mt-3 leading-relaxed max-w-sm">
                    El tiempo promedio entre <i className="text-zinc-300">reconocer la fricción</i> y <i className="text-zinc-300">dar el primer paso físico</i>.
                  </p>
                </div>
                <div className="flex-1 flex justify-center z-10">
                  <div className="flex flex-col items-center">
                    <span className="text-5xl font-bold text-blue-400">{espejo.latencia}</span>
                    <span className="text-zinc-400 font-mono text-sm mt-1 mb-2">minutos</span>

                    {/* [CLÍNICO]: Mostramos la tendencia para no castigar el número absoluto */}
                    {espejo.tendencia_latencia && (
                      <span className={`text-xs px-3 py-1 rounded-full border ${espejo.tendencia_latencia.includes('↓') ? 'bg-emerald-900/20 text-emerald-400 border-emerald-800/30' : 'bg-stone-900/50 text-stone-400 border-stone-800'}`}>
                        {espejo.tendencia_latencia}
                      </span>
                    )}
                  </div>
                </div>
              </motion.div>
            )}

            {/* 2. DESGLOSE ESPECÍFICO DE APROXIMACIONES */}
            {espejo.desglose && (
              <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="p-6 rounded-3xl bg-zinc-900/30 border border-zinc-800/50">
                <p className="text-xs uppercase tracking-widest text-zinc-400 mb-5 font-bold">Evidencia de Movimiento (Últimos 7 días)</p>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  <div className="bg-black/20 border border-white/5 p-4 rounded-2xl flex flex-col items-center text-center">
                    <span className="text-2xl mb-2">👀</span>
                    <span className="text-xl font-bold text-zinc-200">{espejo.desglose.miradas || 0} veces</span>
                    <span className="text-xs text-zinc-400 mt-1">Miraste una tarea que evitabas</span>
                  </div>
                  <div className="bg-black/20 border border-white/5 p-4 rounded-2xl flex flex-col items-center text-center">
                    <span className="text-2xl mb-2">🏃</span>
                    <span className="text-xl font-bold text-zinc-200">{espejo.desglose.primeros_pasos || 0} veces</span>
                    <span className="text-xs text-zinc-400 mt-1">Diste el primer paso físico</span>
                  </div>
                  <div className="bg-black/20 border border-white/5 p-4 rounded-2xl flex flex-col items-center text-center">
                    <span className="text-2xl mb-2">🔄</span>
                    <span className="text-xl font-bold text-zinc-200">{espejo.desglose.retornos || 0} veces</span>
                    <span className="text-xs text-zinc-400 mt-1">Retomaste algo abandonado</span>
                  </div>
                </div>
              </motion.div>
            )}

            {/* NUEVO: EVIDENCIA ACUMULADA (30 días) — el backend ya la calculaba, nunca se mostraba */}
            {espejo.evidencia_acumulada && (
              <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="p-6 rounded-3xl bg-zinc-900/30 border border-zinc-800/50">
                <p className="text-xs uppercase tracking-widest text-zinc-400 mb-5 font-bold">Evidencia acumulada (Últimos {espejo.evidencia_acumulada.periodo_dias} días)</p>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  <div className="bg-black/20 border border-white/5 p-4 rounded-2xl flex flex-col items-center text-center">
                    <span className="text-xl font-bold text-zinc-200">{espejo.evidencia_acumulada.veces_inicio} veces</span>
                    <span className="text-xs text-zinc-400 mt-1">Empezaste algo a pesar del bloqueo</span>
                  </div>
                  <div className="bg-black/20 border border-white/5 p-4 rounded-2xl flex flex-col items-center text-center">
                    <span className="text-xl font-bold text-zinc-200">{espejo.evidencia_acumulada.veces_siguio_tras_bloqueo} veces</span>
                    <span className="text-xs text-zinc-400 mt-1">Seguiste después de un bloqueo</span>
                  </div>
                  <div className="bg-black/20 border border-white/5 p-4 rounded-2xl flex flex-col items-center text-center">
                    <span className="text-xl font-bold text-zinc-200">{espejo.evidencia_acumulada.veces_energia_baja} veces</span>
                    <span className="text-xs text-zinc-400 mt-1">Avanzaste con energía baja</span>
                  </div>
                </div>
              </motion.div>
            )}

            {/* 3. ADAPTACIÓN DEL SISTEMA (Anti-Patrones Contextuales) */}
            {espejo.anti_patron ? (
              <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="p-6 rounded-3xl bg-purple-900/10 border border-purple-800/30">
                <p className="text-xs uppercase tracking-widest text-purple-400 mb-3 font-bold flex items-center gap-2">
                  🧠 Ajuste Contextual del Sistema
                </p>
                <p className="text-sm text-purple-200/80 leading-relaxed">
                  {espejo.anti_patron}
                </p>
              </motion.div>
            ) : (
              <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="p-6 rounded-3xl bg-zinc-900/30 border border-zinc-800/50 flex flex-col justify-center text-left">
                <p className="text-xs uppercase tracking-widest text-zinc-400 mb-2 font-bold flex items-center gap-2">
                  🧠 Aprendizaje del Sistema
                </p>
                <p className="text-sm text-zinc-400 leading-relaxed">El sistema está cruzando datos de tu energía y contexto. Cuando identifique qué estrategias te ayudan y cuáles te congelan, ajustará la IA automáticamente.</p>
              </motion.div>
            )}

            {/* NUEVO: BLOQUEOS ATRAVESADOS — la métrica más importante, va primero */}
            {espejo.bloqueos_atravesados > 0 && (
              <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="p-6 rounded-3xl bg-blue-900/10 border border-blue-800/30 text-center">
                <p className="text-xs uppercase tracking-widest text-blue-400 mb-2 font-bold">Lo que de verdad cuenta</p>
                <span className="text-4xl font-bold text-blue-200">{espejo.bloqueos_atravesados}</span>
                <p className="text-sm text-zinc-400 mt-2">bloqueos atravesados esta semana</p>
                <p className="text-xs text-zinc-400 mt-1">No es cuántas tareas hiciste. Es cuántas veces la fricción no ganó.</p>
              </motion.div>
            )}

            {/* NUEVO: TRANSICIONES — agregar como cuarta tarjeta en el grid de "Evidencia de Movimiento" */}
            {/* (si quieres, cámbiala a grid-cols-4, o déjala como tarjeta aparte como aquí) */}
            {espejo.transiciones_logradas > 0 && (
              <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="p-6 rounded-3xl bg-zinc-900/30 border border-zinc-800/50">
                <div className="bg-black/20 border border-white/5 p-4 rounded-2xl flex flex-col items-center text-center">
                  <span className="text-2xl mb-2">🚪</span>
                  <span className="text-xl font-bold text-zinc-200">{espejo.transiciones_logradas} veces</span>
                  <span className="text-xs text-zinc-400 mt-1">Cruzaste de "evitar" a "estar frente a ello"</span>
                </div>
              </motion.div>
            )}

            {/* NUEVO: DÍAS DE AUTOCUIDADO — solo aparece si el usuario registró autocuidado */}
            {espejo.dias_autocuidado > 0 && (
              <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="p-4 rounded-2xl bg-stone-900/30 border border-stone-800/50 text-center">
                <p className="text-xs text-stone-400">
                  💧 Días esta semana que priorizaste lo básico: <b className="text-stone-200">{espejo.dias_autocuidado}</b>
                </p>
              </motion.div>
            )}

            {/* 4. EVIDENCIA BASADA EN DATOS (Reemplaza a "Identidad") */}
            {espejo.evidencia_retorno && (
              <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="mt-6 text-center">
                <p className="text-sm text-zinc-400 max-w-md mx-auto leading-relaxed border-l-2 border-blue-500/50 pl-4 text-left">
                  {espejo.evidencia_retorno}
                </p>
              </motion.div>
            )}

            {/* NUEVO: CONTRASTES PREDICCIÓN VS RESULTADO — el dato más fuerte para reestructuración cognitiva, antes calculado y nunca mostrado */}
            {espejo.contrastes_recientes && espejo.contrastes_recientes.length > 0 && (
              <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="p-6 rounded-3xl bg-amber-900/10 border border-amber-800/30">
                <p className="text-xs uppercase tracking-widest text-amber-400 mb-4 font-bold">
                  🔍 Lo que predijiste vs. lo que pasó
                </p>
                <div className="flex flex-col gap-4">
                  {espejo.contrastes_recientes.map((contraste, idx) => (
                    <div key={idx} className="bg-black/20 border border-white/5 p-4 rounded-2xl">
                      <p className="text-sm font-medium text-zinc-200 mb-2">{contraste.tarea_nombre}</p>
                      <p className="text-xs text-amber-300/80 leading-relaxed mb-1">Predijiste: &ldquo;{contraste.prediccion}&rdquo;</p>
                      <p className="text-xs text-zinc-400 leading-relaxed">Pasó: {contraste.resultado_frase}</p>
                    </div>
                  ))}
                </div>
              </motion.div>
            )}

            {espejo.siguiente_experimento && (
              <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="mt-6 p-6 rounded-3xl bg-emerald-900/10 border border-emerald-800/30">
                <p className="text-xs uppercase tracking-widest text-emerald-400 mb-3 font-bold">
                  🧪 Tu siguiente experimento
                </p>
                <p className="text-zinc-100 text-base leading-relaxed mb-3">
                  {espejo.siguiente_experimento.experimento}
                </p>
                <p className="text-xs text-zinc-400">
                  {espejo.siguiente_experimento.evidencia}
                </p>
              </motion.div>
            )}

          </motion.div>
        ) : (
          <p className="text-center text-zinc-400 text-sm">Interactúa con tus tareas para generar tus primeras métricas clínicas.</p>
        )}

      </div>
    </main>
  );
}