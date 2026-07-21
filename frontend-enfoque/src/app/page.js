// app/page.js
"use client";
import { useEffect, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import Link from 'next/link';
import { API_BASE, apiFetch, logout } from "@/lib/api";
import { useRouter } from "next/navigation";

export default function Home() {
  const router = useRouter();
  const manejarLogout = async () => {
    await logout();
    router.replace("/login");
  };
  const [metricasClinicas, setMetricasClinicas] = useState(null);
  const [datos, setDatos] = useState(null);
  const [procesando, setProcesando] = useState(false);
  const [pantallaIntermedia, setPantallaIntermedia] = useState(null);
  const [textoCaptura, setTextoCaptura] = useState("");
  const [guardando, setGuardando] = useState(false);
  const [errorAccion, setErrorAccion] = useState(null);
  const [estadoBloqueo, setEstadoBloqueo] = useState(null);
  const [pasosIA, setPasosIA] = useState([]);
  const [energia, setEnergia] = useState(null);
  const [mostrandoMotivosPosponer, setMostrandoMotivosPosponer] = useState(false);
  const [mostrandoIntenciones, setMostrandoIntenciones] = useState(false);
  const [mostrarGuia, setMostrarGuia] = useState(false);
  const [pantallaCrisis, setPantallaCrisis] = useState(null);
  const [pantallaPostCrisis, setPantallaPostCrisis] = useState(false);
  const [estadoPaso1, setEstadoPaso1] = useState(null);
  const [motivoBloqueoActual, setMotivoBloqueoActual] = useState(null);
  const [intervencionUsadaActual, setIntervencionUsadaActual] = useState(null);
  const [intentosValientes, setIntentosValientes] = useState(0);
  const [insightDiscrepancia, setInsightDiscrepancia] = useState(null);
  const [discrepanciaRespondida, setDiscrepanciaRespondida] = useState(false);
  const [chequeoFidelidad, setChequeoFidelidad] = useState(null);
  const [confirmacionesRespondidas, setConfirmacionesRespondidas] = useState({});

  const [indiceTarea, setIndiceTarea] = useState(0);
  const [cambiosRestantes, setCambiosRestantes] = useState(0);

  const tareaActual = datos?.tareas && datos.tareas.length > 0 ? datos.tareas[indiceTarea] : null;

  const isSurvival = energia === 'baja';
  const animDuration = isSurvival ? 1.2 : 0.6;
  const bgMain = isSurvival ? "bg-[#1c1917]" : "bg-[#09090b]";
  const btnPrimary = isSurvival ? "bg-stone-200 text-stone-900 hover:bg-stone-300" : "bg-blue-50 text-blue-900 hover:bg-blue-100";

  const [mostrandoPrediccion, setMostrandoPrediccion] = useState(false);

  const PREDICCIONES_RAPIDAS = [
    "😩 Me va a costar muchísimo",
    "⏳ Me va a tomar más de lo que parece",
    "🌀 Me voy a bloquear a medio camino",
    "😬 Va a salir mal o incompleto",
  ];

  useEffect(() => {
    apiFetch(`/api/metricas-clinicas`)
      .then(res => res.json())
      .then(data => {
        if (data && data.recuperaciones_exitosas > 0) {
          setMetricasClinicas(data);
        }
      })
      .catch(e => console.error(e));
  }, []);

  const cargarTarea = (nivel) => {
    setEstadoPaso1(null);
    setIndiceTarea(0);

    setDatos({ mensaje: "Sincronizando con tu mente (TickTick)... 🧘‍♂️" });

    apiFetch(`/api/enfoque?energia=${nivel}&t=${Date.now()}`, { cache: 'no-store' })
      .then((res) => {
        if (!res.ok) throw new Error("El servidor de TickTick está saturado o tardó demasiado");
        return res.json();
      })
      .then((data) => {
        setDatos(data);
        if (data.estadisticas) setIntentosValientes(data.estadisticas.intentos_hoy);
      })
      .catch((error) => {
        console.error("Error clínico de conexión:", error);
        setDatos({
          estado: "error",
          mensaje: "TickTick tardó mucho en responder. Respira un momento e intenta de nuevo. ⏳"
        });
      });
  };

  const seleccionarEnergia = (nivel) => {
    setEnergia(nivel);
    setCambiosRestantes(nivel === 'baja' ? 5 : 3);
    cargarTarea(nivel);
  };

  const manejarRespuesta = (data) => {
    if (data?.estado === "riesgo_detectado") {
      setPantallaCrisis(data.recursos);
      return true;
    }
    return false;
  };

  const obtenerDatosBloqueoParaSesion = () => {
    if (estadoBloqueo === 'resuelto' && motivoBloqueoActual) {
      return {
        bloqueoPrevio: motivoBloqueoActual,
        intervencionUsada: intervencionUsadaActual || "Desglose IA"
      };
    }
    return { bloqueoPrevio: "Ninguno", intervencionUsada: "Ninguna" };
  };

  const procesarRechazo = (intencion) => {
    if (cambiosRestantes <= 0 || !tareaActual) return;

    const tareaRechazada = tareaActual;

    setMostrandoIntenciones(false);
    setEstadoBloqueo(null);
    setEstadoPaso1(null);
    setMotivoBloqueoActual(null);
    setIntervencionUsadaActual(null);
    setMostrandoPrediccion(false);
    setCambiosRestantes(prev => prev - 1);

    const buscarSiguienteMatch = (condicion) => {
      for (let i = 1; i < datos.tareas.length; i++) {
        const nextIndex = (indiceTarea + i) % datos.tareas.length;
        if (condicion(datos.tareas[nextIndex])) {
          return nextIndex;
        }
      }
      return -1;
    };

    let nuevoIndice = (indiceTarea + 1) % datos.tareas.length;

    if (intencion === "Algo rápido y fácil") {
      const index = buscarSiguienteMatch(t => t.prioridad === 0 || t.etiquetas.includes("facil") || t.etiquetas.includes("baja-energia"));
      if (index !== -1) nuevoIndice = index;
    } else if (intencion === "Algo urgente o importante") {
      const index = buscarSiguienteMatch(t => t.prioridad > 0);
      if (index !== -1) nuevoIndice = index;
    } else if (intencion === "Algo diferente o creativo") {
      const index = buscarSiguienteMatch(t => t.carpeta !== tareaRechazada.carpeta);
      if (index !== -1) nuevoIndice = index;
    }

    setIndiceTarea(nuevoIndice);

    apiFetch(`/api/rechazar/${tareaRechazada.id}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        tarea_nombre: tareaRechazada.titulo,
        energia: energia,
        carpeta: tareaRechazada.carpeta || "Inbox",
        intencion: intencion
       })
    })
      .then(res => res.json())
      .then(data => { manejarRespuesta(data); })   // <-- NUEVO
      .catch(err => console.error("Error al registrar el rechazo:", err));
  };

  const comprometerseAlPaso1 = () => {
    setMostrandoPrediccion(true);
  };

  const confirmarPaso1ConPrediccion = (prediccionTexto) => {
    setMostrandoPrediccion(false);

    if (prediccionTexto && tareaActual) {
      apiFetch(`/api/prediccion`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          tarea_id: tareaActual.id,
          tarea_nombre: tareaActual.titulo,
          prediccion: prediccionTexto,
          energia: energia,
          carpeta: tareaActual.carpeta || "Inbox"
        })
      }).catch(err => console.error("Error al registrar predicción:", err));
    }

    registrarAccionPaso1('paso1_comprometido');
  };

  const registrarAccionPaso1 = async (tipo) => {
    if (tipo === 'paso1_comprometido' || tipo === 'exposicion_mirar') {
      setIntentosValientes(prev => prev + 1);
      if (tareaActual) {
        setDatos(prev => ({ ...prev, estadisticas: { ...prev.estadisticas, intentos_tarea: (prev.estadisticas.intentos_tarea || 0) + 1 } }));
      }
    }

    if (tareaActual) {
      const { id, titulo, carpeta } = tareaActual;
      await apiFetch(`/api/intento/${id}?accion=${tipo}&tarea_nombre=${encodeURIComponent(titulo)}&energia=${energia}&carpeta=${encodeURIComponent(carpeta)}`, { method: "POST" });
    }

    if (tipo === 'exposicion_mirar') setEstadoPaso1('exposicion_lograda');
    else if (tipo === 'paso1_comprometido') setEstadoPaso1('comprometido');
    else setEstadoPaso1('realizado');
  };

  // ─── CAMBIO: liberarTarea ahora lee es_recurrente del backend ───
  const liberarTarea = async () => {
    if (!tareaActual) return;
    setProcesando(true);
    setErrorAccion(null);
    const { proyecto_id, id, titulo, carpeta } = tareaActual;
    const { bloqueoPrevio, intervencionUsada } = obtenerDatosBloqueoParaSesion();

    try {
      const res = await apiFetch(
        `/api/liberar/${proyecto_id}/${id}` +
        `?tarea_nombre=${encodeURIComponent(titulo)}` +
        `&energia=${energia}` +
        `&carpeta=${encodeURIComponent(carpeta || "Inbox")}` +
        `&bloqueo_previo=${encodeURIComponent(bloqueoPrevio)}` +
        `&intervencion_usada=${encodeURIComponent(intervencionUsada)}`,
        { method: "POST" }
      );

      if (!res.ok) {
        setProcesando(false);
        setErrorAccion("No se pudo confirmar con TickTick. Puede que esté lento — intenta de nuevo.");
        return;
      }

      const data = await res.json();

      // Si la tarea era recurrente, mostramos una pantalla que explica
      // por qué reaparece mañana — interceptando la distorsión cognitiva
      // antes de que se instale ("¿ya vuelve? entonces no sirvió de nada").
      const tipo = data.es_recurrente ? 'descanso_rutina' : 'descanso';
      const delay = data.es_recurrente
        ? (isSurvival ? 4500 : 3500)
        : (isSurvival ? 3500 : 2500);

      // Si el backend detecta que vale la pena confirmar que se hizo en
      // el momento correcto, preguntamos ANTES de la pantalla de cierre
      // (para no contaminar efectividad_historica_v2 con datos dudosos).
      if (data.chequeo_fidelidad) {
        setChequeoFidelidad({
          tareaId: id,
          tareaNombre: titulo,
          energia,
          carpeta: carpeta || "Inbox",
          pregunta: data.chequeo_fidelidad.pregunta,
          siguientePantalla: tipo,
          siguienteDelay: delay,
        });
        setPantallaIntermedia('chequeo_fidelidad');
        setProcesando(false);
        return;
      }

      setPantallaIntermedia(tipo);
      setTimeout(() => { resetearYRecargar(delay); }, 0);

    } catch (error) {
      setProcesando(false);
      setErrorAccion("No hay conexión con el servidor. Revisa tu conexión e intenta de nuevo.");
    }
  };

  const responderChequeoFidelidad = async (respuesta) => {
    if (!chequeoFidelidad) return;
    const { tareaId, tareaNombre, energia: energiaTarea, carpeta, siguientePantalla, siguienteDelay } = chequeoFidelidad;

    try {
      await apiFetch(`/api/chequeo-fidelidad/${tareaId}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          respuesta,
          tarea_nombre: tareaNombre,
          energia: energiaTarea,
          carpeta,
        }),
      });
    } catch (error) {
      // No bloqueamos el flujo de cierre por esto — es un dato
      // adicional, no algo crítico para el usuario en este momento.
    }

    setChequeoFidelidad(null);
    setPantallaIntermedia(siguientePantalla);
    setTimeout(() => { resetearYRecargar(siguienteDelay); }, 0);
  };
  // ────────────────────────────────────────────────────────────────

  const responderConfirmacionClasificacion = async (respuesta) => {
    if (!tareaActual?.confirmar_clasificacion) return;
    const { valor_detectado } = tareaActual.confirmar_clasificacion;
    const tareaId = tareaActual.id;

    // Ocultamos ya mismo en la UI (optimista) — no vale la pena bloquear
    // esto por la red, es un dato secundario, no algo crítico del flujo.
    setConfirmacionesRespondidas((prev) => ({ ...prev, [tareaId]: true }));

    try {
      await apiFetch(`/api/corregir-decision`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          tarea_id: tareaId,
          tipo_decision: "clasificacion_tarea",
          valor_original: valor_detectado,
          correccion: respuesta === "si" ? "aceptada" : "rechazada",
          carpeta: tareaActual.carpeta || "Inbox",
        }),
      });
    } catch (error) {
      // Si falla la red, no revertimos el estado optimista: preguntar nunca
      // es tan importante como para arriesgar interrumpir el flujo principal.
    }
  };

  const avanceParcial = async () => {
    if (!tareaActual) return;
    setProcesando(true);
    setErrorAccion(null);
    const { proyecto_id, id, titulo, carpeta } = tareaActual;
    const { bloqueoPrevio, intervencionUsada } = obtenerDatosBloqueoParaSesion();

    try {
      const resIntento = await apiFetch(`/api/intento/${id}?accion=avance_parcial&tarea_nombre=${encodeURIComponent(titulo)}&energia=${energia}&carpeta=${encodeURIComponent(carpeta)}`, { method: "POST" });
      const resPosponer = await apiFetch(`/api/posponer/${proyecto_id}/${id}`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ tarea_nombre: titulo, energia: energia, carpeta: carpeta || "Inbox", motivo_posponer: "Avance Parcial (Victoria)", bloqueo_previo: bloqueoPrevio, intervencion_usada: intervencionUsada })
      });

      if (!resIntento.ok || !resPosponer.ok) {
        setProcesando(false);
        setErrorAccion("No se pudo guardar el avance. Intenta de nuevo.");
        return;
      }

      setPantallaIntermedia('parcial');
      setTimeout(() => { resetearYRecargar(3000); }, 0);
    } catch (error) {
      setProcesando(false);
      setErrorAccion("No hay conexión con el servidor. Revisa tu conexión e intenta de nuevo.");
    }
  };

  const posponerTareaConsciente = async (motivoReal) => {
    if (!tareaActual) return;
    setProcesando(true);
    setErrorAccion(null);
    const { proyecto_id, id, titulo, carpeta } = tareaActual;
    const { bloqueoPrevio, intervencionUsada } = obtenerDatosBloqueoParaSesion();

    try {
      const res = await apiFetch(`/api/posponer/${proyecto_id}/${id}`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ tarea_nombre: titulo, energia: energia, carpeta: carpeta || "Inbox", motivo_posponer: motivoReal, bloqueo_previo: bloqueoPrevio, intervencion_usada: intervencionUsada })
      });

      if (!res.ok) {
        setProcesando(false);
        setErrorAccion("No se pudo posponer la tarea. Intenta de nuevo.");
        return;
      }

      const data = await res.json();
      if (manejarRespuesta(data)) {   // <-- NUEVO: corta el flujo si es crisis
        setProcesando(false);
        return;
      }

      setPantallaIntermedia('pospuesto');
      setMostrandoMotivosPosponer(false);
      setTimeout(() => { resetearYRecargar(3000); }, 0);
    } catch (error) {
      setProcesando(false);
      setErrorAccion("No hay conexión con el servidor. Revisa tu conexión e intenta de nuevo.");
    }
  };

  const resetearYRecargar = (delay) => {
    setTimeout(() => {
      setPantallaIntermedia(null);
      setProcesando(false);
      setEstadoBloqueo(null);
      setEstadoPaso1(null);
      setMotivoBloqueoActual(null);
      setIntervencionUsadaActual(null);
      setMostrandoPrediccion(false);
      setErrorAccion(null);
      cargarTarea(energia);
    }, delay);
  };

  const manejarCaptura = async (e) => {
    e.preventDefault();
    if (!textoCaptura.trim()) return;
    setGuardando(true);
    try {
      const res = await apiFetch(`/api/captura`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ texto: textoCaptura })
      });
      const data = await res.json();
      if (manejarRespuesta(data)) return;
      setTextoCaptura("");
    } catch (error) { } finally { setGuardando(false); }
  };

  const solicitarAyudaIA = async (motivo) => {
    setEstadoBloqueo('cargando');
    setEstadoPaso1(null);
    setMotivoBloqueoActual(motivo);
    setIntervencionUsadaActual(null);
    setIntentosValientes(prev => prev + 1);
    if (tareaActual) setDatos(prev => ({ ...prev, estadisticas: { ...prev.estadisticas, intentos_tarea: (prev.estadisticas.intentos_tarea || 0) + 1 } }));

    try {
      const res = await apiFetch(`/api/desglose`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          tarea_id: tareaActual.id, titulo_tarea: tareaActual.titulo, descripcion_tarea: tareaActual.descripcion || "", motivo: motivo, energia: energia, carpeta: tareaActual.carpeta, etiquetas: tareaActual.etiquetas,
          patron_historico: tareaActual.patron_emocional
        }),
      });
      const data = await res.json();
      if (manejarRespuesta(data)) {   // <-- NUEVO
        setEstadoBloqueo(null);
        return;
      }
      setPasosIA((data && data.pasos) ? data.pasos : ["Respira.", "Haz lo mínimo.", "Cierra la app si lo necesitas."]);

      setInsightDiscrepancia(data?.insight_discrepancia || null);
      setDiscrepanciaRespondida(false);
      setIntervencionUsadaActual(data?.nombre_intervencion || null);

      setEstadoBloqueo('resuelto');
    } catch (error) { setEstadoBloqueo(null); }
  };

  const esLunes = new Date().getDay() === 1;

  const obtenerMensajePerfil = () => {
    if (!tareaActual || !tareaActual.perfil_clinico) return null;
    const perfil = tareaActual.perfil_clinico.perfil;
    if (perfil === "evitacion") return "En ocasiones esta área genera resistencia. Hoy no necesitas resolverla completa, solo ábrela.";
    if (perfil === "agotamiento") return "El historial sugiere que esto drena tu energía. Haz solo una versión mínima y para.";
    if (perfil === "falta_claridad") return "Antes de empezar, dedica 1 minuto solo a escribir qué te falta entender de esto.";
    if (perfil === "sobrecarga") return "Si sientes que es demasiado, usa el botón de bloqueo para desglosarla.";
    return null;
  };

  const friccionContinua = tareaActual?.friccion_consecutiva || 0;
  const colapsoEmocional = friccionContinua >= 4 && estadoBloqueo !== 'solo_mirar';

  return (
    <main className={`min-h-screen ${bgMain} flex flex-col items-center p-6 font-sans overflow-y-auto transition-colors duration-1000`}>

      <div className="fixed top-6 left-6 z-50 flex gap-3 flex-wrap">
        <button onClick={() => setMostrarGuia(true)} className="text-zinc-400 hover:text-zinc-300 text-sm flex items-center gap-2 bg-black/40 backdrop-blur-md px-4 py-2 rounded-full transition-all border border-white/5">
          ℹ️ Guía
        </button>
        <Link href="/mente">
          <button className="text-zinc-400 hover:text-zinc-300 text-sm flex items-center gap-2 bg-black/40 backdrop-blur-md px-4 py-2 rounded-full transition-all border border-white/5">
            🧠 Mi Mente
          </button>
        </Link>
        <Link href="/cierre">
          <button className="text-indigo-400 hover:text-indigo-300 text-sm flex items-center gap-2 bg-indigo-900/20 backdrop-blur-md px-4 py-2 rounded-full transition-all border border-indigo-500/20">
            🌙 Cierre Diario
          </button>
        </Link>
        <button onClick={manejarLogout} className="text-zinc-500 hover:text-zinc-300 text-sm flex items-center gap-2 bg-black/40 backdrop-blur-md px-4 py-2 rounded-full transition-all border border-white/5">
          🚪 Salir
        </button>
      </div>

      {energia && !pantallaPostCrisis && (
        <div className="fixed top-6 right-6 z-50">
          <button onClick={() => setEnergia(null)} className="text-zinc-400 hover:text-zinc-300 text-sm flex items-center gap-2 bg-black/40 backdrop-blur-md px-4 py-2 rounded-full transition-all border border-white/5">
            ⚙️ Cambiar estado
          </button>
        </div>
      )}

      <div className="max-w-2xl w-full text-center flex flex-col items-center mt-16 pb-32">

        {datos && datos.estadisticas && datos.estadisticas.dias_ausente > 1 && !estadoBloqueo && !colapsoEmocional && !pantallaPostCrisis && (
          <motion.div initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }} className="mb-10 p-5 rounded-3xl bg-blue-900/20 border border-blue-500/20 max-w-sm w-full">
            <p className="text-xl mb-1">👋 ¡Bienvenido de vuelta!</p>
            <p className="text-blue-300 text-sm">Estuviste fuera {datos.estadisticas.dias_ausente} días. Cero culpa. Ignoraremos ese tiempo y nos enfocaremos solo en lo que sigue.</p>
          </motion.div>
        )}

        {pantallaPostCrisis ? (
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="flex flex-col items-center gap-6 mt-20 text-center max-w-sm">
            <span className="text-4xl opacity-60">🌿</span>
            <p className="text-zinc-200 text-lg font-medium leading-relaxed">
              No hay nada que tengas que hacer ahora mismo.
            </p>
            <p className="text-zinc-400 text-sm leading-relaxed">
              Tu mente necesita una pausa y está bien. Cuando sientas que tienes la capacidad, puedes volver a tus tareas. No hay prisa, el sistema te esperará.
            </p>
            <button
              onClick={() => {
                setPantallaPostCrisis(false);
                setEnergia(null);
              }}
              className="mt-6 px-6 py-2 rounded-full text-sm font-medium border border-zinc-700/50 text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800/50 transition-all"
            >
              Volver a mis tareas cuando esté listo
            </button>
          </motion.div>
        ) : (
          <>
            {!energia ? (
              <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} className="flex flex-col items-center w-full mt-10">
                <h1 className="text-3xl font-medium text-zinc-200 mb-2">Check-in</h1>

                {esLunes ? (
                  <div className="mb-10 text-center">
                    <p className="text-blue-400 font-medium mb-1">Hoy no estamos resolviendo la semana.</p>
                    <p className="text-zinc-400 text-sm">Solo estamos resolviendo el siguiente paso. Respira.</p>
                  </div>
                ) : (
                  <p className="text-zinc-400 mb-10">¿Qué necesitas de ti hoy?</p>
                )}

                {metricasClinicas && !energia && (
                  <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className={`mb-8 p-4 rounded-2xl text-center text-xs max-w-sm border ${isSurvival ? 'bg-stone-900/40 border-stone-800 text-stone-400' : 'bg-blue-900/10 border-blue-900/30 text-blue-300'}`}>
                    📊 <b>{metricasClinicas.mensaje}</b>
                  </motion.div>
                )}

                <div className="flex flex-col gap-4 w-full max-w-sm">
                  <button onClick={() => seleccionarEnergia("alta")} className="w-full py-5 bg-[#121214] text-zinc-200 rounded-3xl hover:bg-[#18181b] transition-all flex items-center justify-start px-6 gap-5 border border-white/5 hover:border-blue-500/30">
                    <span className="text-2xl opacity-80">⚡</span>
                    <div className="text-left"><p className="font-semibold text-lg text-blue-100">Avanzar</p><p className="text-xs text-zinc-400">Tengo capacidad para mis pendientes</p></div>
                  </button>

                  <button onClick={() => seleccionarEnergia("baja")} className="w-full py-5 bg-[#1a1715] text-zinc-200 rounded-3xl hover:bg-[#211d1a] transition-all flex items-center justify-start px-6 gap-5 border border-white/5 hover:border-stone-500/30">
                    <span className="text-2xl opacity-80">🛋️</span>
                    <div className="text-left"><p className="font-semibold text-lg text-stone-200">Sobrevivir</p><p className="text-xs text-zinc-400">Solo lo innegociable. Cero culpa.</p></div>
                  </button>

                  <div className="mt-6 text-center">
                    <Link href="/cierre">
                      <button className="text-xs text-zinc-400 hover:text-indigo-400 transition-colors border-b border-transparent hover:border-indigo-400/50 pb-1">
                        🌙 Ya terminé por hoy. Quiero registrar mis logros.
                      </button>
                    </Link>
                  </div>
                </div>
              </motion.div>

            ) : (
              <>
                {intentosValientes > 0 && !colapsoEmocional && (
                  <motion.p initial={{ opacity: 0 }} animate={{ opacity: 1 }} className={`text-xs mb-6 px-4 py-1.5 rounded-full ${isSurvival ? 'bg-stone-800/50 text-stone-400' : 'bg-blue-900/20 text-blue-300'}`}>
                    Hoy has actuado a pesar de la fricción {intentosValientes} {intentosValientes === 1 ? 'vez' : 'veces'}. ¡Eso cuenta muchísimo!
                  </motion.p>
                )}

                <p className={`uppercase tracking-widest text-xs font-semibold mb-12 flex items-center gap-2 ${isSurvival ? 'text-stone-400' : 'text-blue-400'}`}>
                  {isSurvival ? '🌿 Modo Supervivencia' : '🌊 Modo Avance'}
                </p>

                <AnimatePresence mode="wait">
                  {pantallaIntermedia === 'chequeo_fidelidad' ? (
                    <motion.div
                      key="chequeo_fidelidad"
                      initial={{ opacity: 0, y: 10 }}
                      animate={{ opacity: 1, y: 0 }}
                      exit={{ opacity: 0 }}
                      transition={{ duration: animDuration }}
                      className="flex flex-col items-center gap-5 text-center max-w-xs"
                    >
                      <span className="text-4xl opacity-70">🕐</span>
                      <p className={`text-lg font-light tracking-wide leading-relaxed ${isSurvival ? 'text-stone-300' : 'text-zinc-300'}`}>
                        {chequeoFidelidad?.pregunta}
                      </p>
                      <div className="flex gap-2 w-full">
                        <button
                          onClick={() => responderChequeoFidelidad('si')}
                          className={`flex-1 py-2 rounded-lg text-xs font-medium transition-all active:scale-95 ${isSurvival ? 'bg-stone-700/60 text-stone-200 hover:bg-stone-700' : 'bg-zinc-800/60 text-zinc-200 hover:bg-zinc-700/60'}`}
                        >
                          Sí
                        </button>
                        <button
                          onClick={() => responderChequeoFidelidad('no')}
                          className={`flex-1 py-2 rounded-lg text-xs font-medium transition-all active:scale-95 ${isSurvival ? 'bg-stone-800/60 text-stone-400 hover:bg-stone-700/60' : 'bg-zinc-900/60 text-zinc-400 hover:bg-zinc-800/60'}`}
                        >
                          No
                        </button>
                      </div>
                    </motion.div>

                  ) : pantallaIntermedia === 'descanso' ? (
                    <motion.div key="descanso" initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }} exit={{ opacity: 0 }} transition={{ duration: animDuration }} className={`text-2xl font-light tracking-wide ${isSurvival ? 'text-stone-400' : 'text-zinc-400'}`}>
                      Respira... bien hecho. 🍃
                    </motion.div>

                    // ─── NUEVO: pantalla para tareas recurrentes completadas ───
                  ) : pantallaIntermedia === 'descanso_rutina' ? (
                    <motion.div
                      key="descanso_rutina"
                      initial={{ opacity: 0, scale: 0.95 }}
                      animate={{ opacity: 1, scale: 1 }}
                      exit={{ opacity: 0 }}
                      transition={{ duration: animDuration }}
                      className="flex flex-col items-center gap-4 text-center"
                    >
                      <span className={`text-4xl ${isSurvival ? 'opacity-60' : 'opacity-80'}`}>✓</span>
                      <p className={`text-xl font-light tracking-wide ${isSurvival ? 'text-stone-300' : 'text-zinc-300'}`}>
                        Hecho para hoy. 🍃
                      </p>
                      <p className={`text-sm max-w-xs leading-relaxed ${isSurvival ? 'text-stone-500' : 'text-zinc-500'}`}>
                        Como es una rutina, reaparece mañana — no porque fallaste, sino porque eso es lo que hacen los hábitos.
                      </p>
                    </motion.div>
                    // ────────────────────────────────────────────────────────────

                  ) : pantallaIntermedia === 'pospuesto' ? (
                    <motion.div key="pospuesto" initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} transition={{ duration: animDuration }} className="flex flex-col items-center gap-4">
                      <span className="text-4xl opacity-50">☕</span>
                      <p className={`text-xl font-light tracking-wide ${isSurvival ? 'text-stone-400' : 'text-zinc-400'}`}>Cero estrés. <br /> Mañana será otro día.</p>
                    </motion.div>
                  ) : pantallaIntermedia === 'parcial' ? (
                    <motion.div key="parcial" initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} transition={{ duration: animDuration }} className="flex flex-col items-center gap-4">
                      <span className="text-4xl opacity-80">🌗</span>
                      <p className={`text-xl font-light tracking-wide ${isSurvival ? 'text-stone-400' : 'text-zinc-400'}`}>Media victoria sigue siendo victoria.<br />Excelente trabajo hoy.</p>
                    </motion.div>
                  ) : !tareaActual ? (
                    <motion.div key="vacio" initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="flex flex-col items-center gap-6">
                      <h1 className="text-zinc-300 text-2xl font-medium">
                        {datos?.mensaje || "Sincronizando tareas..."}
                      </h1>
                      {datos?.estado === "error" && (
                        <button onClick={() => cargarTarea(energia)} className={`px-4 py-2 mt-4 rounded-xl text-sm transition-all border ${isSurvival ? 'border-stone-700 text-stone-400 hover:bg-stone-800' : 'border-zinc-700 text-zinc-400 hover:bg-zinc-800'}`}>
                          Reintentar conexión
                        </button>
                      )}
                    </motion.div>
                  ) : (
                    <motion.div key={tareaActual.id} initial={{ opacity: 0, y: 15 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: pantallaIntermedia ? -60 : 30, scale: 0.95 }} transition={{ duration: animDuration }} className="flex flex-col items-center w-full">

                      {colapsoEmocional ? (
                        <motion.div initial={{ opacity: 0, scale: 0.9 }} animate={{ opacity: 1, scale: 1 }} className="flex flex-col items-center text-center max-w-sm mt-10">
                          <span className="text-5xl mb-6 opacity-80">⚖️</span>
                          <h2 className="text-2xl font-bold text-zinc-200 mb-4">Suficiente fricción por hoy</h2>
                          <p className="text-zinc-400 text-sm mb-8 leading-relaxed">
                            Has intentado acercarte a <b>"{tareaActual.titulo}"</b> varias veces hoy.<br /><br />
                            Seguir empujando cuando hay tanta resistencia no siempre es la mejor inversión de tus recursos ahora mismo.
                          </p>

                          <button onClick={() => posponerTareaConsciente("Mucha fricción / Inversión de energía")} className="w-full py-4 bg-zinc-800 text-zinc-200 rounded-2xl font-bold text-lg hover:bg-zinc-700 transition-all shadow-lg active:scale-95 mb-4">
                            Dejarla para mañana
                          </button>

                          <button onClick={() => { setEstadoBloqueo('solo_mirar');}} className={`text-xs underline decoration-transparent transition-colors ${isSurvival ? 'text-stone-400 hover:text-stone-300' : 'text-zinc-400 hover:text-zinc-300'}`}>
                            Intentaré acercarme solo 30 segundos
                          </button>
                        </motion.div>
                      ) : (
                        <>
                          <div className={`mb-6 flex flex-col items-center gap-2 text-center`}>
                            <div className="flex gap-2">
                              <div className={`px-4 py-1.5 border rounded-full ${isSurvival ? 'border-stone-800 bg-stone-900/50' : 'border-zinc-800 bg-zinc-900/50'}`}>
                                <p className={`text-xs tracking-widest uppercase ${isSurvival ? 'text-stone-400' : 'text-zinc-400'}`}>
                                  {datos.fase === 'calentamiento' ? '🔥 Calentamiento' : '🎯 Tu siguiente paso'}
                                </p>
                              </div>
                              {tareaActual.carpeta && (
                                <div className={`px-3 py-1.5 rounded-full ${isSurvival ? 'bg-stone-800 text-stone-400' : 'bg-zinc-800 text-zinc-400'}`}>
                                  <p className="text-xs tracking-wider uppercase">📁 {tareaActual.carpeta}</p>
                                </div>
                              )}
                            </div>

                            {obtenerMensajePerfil() && !estadoBloqueo && (
                              <motion.span initial={{ opacity: 0 }} animate={{ opacity: 1 }} className={`text-xs px-4 py-2 mt-2 rounded-2xl max-w-xs leading-relaxed ${isSurvival ? 'text-stone-400 bg-stone-800/30' : 'text-purple-300 bg-purple-900/20'}`}>
                                {obtenerMensajePerfil()}
                              </motion.span>
                            )}
                          </div>

                          <h1 className={`text-4xl md:text-5xl font-semibold leading-tight px-4 break-words ${isSurvival ? 'text-stone-200' : 'text-zinc-100'}`}>
                            {tareaActual.titulo}
                          </h1>

                          {datos.tareas && datos.tareas.length > 1 && !estadoBloqueo && !mostrandoMotivosPosponer && (
                            <div className="mt-8 flex flex-col items-center w-full max-w-sm">
                              {!mostrandoIntenciones ? (
                                cambiosRestantes > 0 ? (
                                  <button onClick={() => setMostrandoIntenciones(true)} className={`px-5 py-2.5 rounded-full text-xs font-medium transition-all active:scale-95 border ${isSurvival ? 'border-stone-800 text-stone-400 hover:bg-stone-800 hover:text-stone-300' : 'border-zinc-800 text-zinc-400 hover:bg-zinc-800 hover:text-zinc-300'}`}>
                                    Esta tarea no encaja ahora (Quedan {cambiosRestantes})
                                  </button>
                                ) : (
                                  <div className="bg-orange-900/10 border border-orange-900/30 p-4 rounded-xl mt-2 w-full text-left">
                                    <p className="text-xs text-orange-400/80 leading-relaxed font-medium">
                                      Has cambiado de tarea varias veces. Parece que ninguna se siente cómoda. <br /><br />
                                      Quizá el problema no sea encontrar "la tarea correcta", sino tu nivel de energía o ansiedad actual.
                                    </p>
                                  </div>
                                )
                              ) : (
                                <motion.div initial={{ opacity: 0, y: 5 }} animate={{ opacity: 1, y: 0 }} className="flex flex-col gap-2 w-full bg-black/20 p-4 rounded-2xl border border-white/5">
                                  <p className={`text-sm mb-2 font-medium ${isSurvival ? 'text-stone-400' : 'text-zinc-400'}`}>¿Qué busca tu mente ahora mismo?</p>

                                  <button onClick={() => procesarRechazo("Algo rápido y fácil")} className={`w-full py-3 rounded-xl text-xs transition-colors text-left px-4 ${isSurvival ? 'bg-stone-800/50 hover:bg-stone-700/50 text-stone-300' : 'bg-zinc-800/50 hover:bg-zinc-700/50 text-zinc-300'}`}>
                                    ⚡ Algo rápido y fácil
                                  </button>
                                  <button onClick={() => procesarRechazo("Algo urgente o importante")} className={`w-full py-3 rounded-xl text-xs transition-colors text-left px-4 ${isSurvival ? 'bg-stone-800/50 hover:bg-stone-700/50 text-stone-300' : 'bg-zinc-800/50 hover:bg-zinc-700/50 text-zinc-300'}`}>
                                    🎯 Algo urgente o importante
                                  </button>
                                  <button onClick={() => procesarRechazo("Algo diferente o creativo")} className={`w-full py-3 rounded-xl text-xs transition-colors text-left px-4 ${isSurvival ? 'bg-stone-800/50 hover:bg-stone-700/50 text-stone-300' : 'bg-zinc-800/50 hover:bg-zinc-700/50 text-zinc-300'}`}>
                                    🎨 Algo diferente (cambiar de tema)
                                  </button>
                                  <button onClick={() => procesarRechazo("Cualquier otra")} className={`w-full py-3 rounded-xl text-xs transition-colors text-left px-4 ${isSurvival ? 'bg-stone-800/50 hover:bg-stone-700/50 text-stone-300' : 'bg-zinc-800/50 hover:bg-zinc-700/50 text-zinc-300'}`}>
                                    🎲 Sorpréndeme
                                  </button>

                                  <button onClick={() => setMostrandoIntenciones(false)} className={`mt-3 text-xs uppercase tracking-widest ${isSurvival ? 'text-stone-400 hover:text-stone-200' : 'text-zinc-400 hover:text-zinc-200'}`}>
                                    ← Cancelar, me quedo con esta
                                  </button>
                                </motion.div>
                              )}
                            </div>
                          )}

                          {(() => {
                            const perfil = tareaActual.perfil_clinico?.perfil;
                            if (!perfil || estadoBloqueo) return null;

                            let objetivo = "";
                            if (perfil === "evitacion") objetivo = "Objetivo mínimo hoy: Solo acercarse o abrirlo.";
                            else if (perfil === "sobrecarga") objetivo = "Objetivo mínimo hoy: Dar un solo paso minúsculo.";
                            else if (perfil === "agotamiento") objetivo = "Objetivo mínimo hoy: Hacer la versión más reducida posible y parar.";
                            else if (perfil === "falta_claridad") objetivo = "Objetivo mínimo hoy: Identificar exactamente qué no entiendes.";

                            if (!objetivo) return null;

                            return (
                              <motion.div initial={{ opacity: 0, y: 5 }} animate={{ opacity: 1, y: 0 }} className={`mt-5 px-5 py-2.5 rounded-xl inline-block border ${isSurvival ? 'bg-stone-800/40 border-stone-700/50 text-stone-300' : 'bg-zinc-800/50 border-zinc-700/50 text-zinc-300'}`}>
                                <p className="text-sm font-medium">🎯 {objetivo}</p>
                              </motion.div>
                            );
                          })()}

                          {tareaActual.confirmar_clasificacion && !estadoBloqueo && !confirmacionesRespondidas[tareaActual.id] && (
                            <motion.div initial={{ opacity: 0, y: 5 }} animate={{ opacity: 1, y: 0 }} className={`mt-5 px-5 py-4 rounded-2xl max-w-sm w-full border ${isSurvival ? 'bg-stone-800/40 border-stone-700/50' : 'bg-zinc-800/50 border-zinc-700/50'}`}>
                              <p className={`text-sm mb-3 leading-relaxed ${isSurvival ? 'text-stone-300' : 'text-zinc-300'}`}>
                                🔎 {tareaActual.confirmar_clasificacion.pregunta}
                              </p>
                              <div className="flex gap-2">
                                <button
                                  onClick={() => responderConfirmacionClasificacion('si')}
                                  className={`flex-1 py-2 rounded-lg text-xs font-medium transition-all active:scale-95 ${isSurvival ? 'bg-stone-700/60 text-stone-200 hover:bg-stone-700' : 'bg-zinc-700/60 text-zinc-200 hover:bg-zinc-700'}`}
                                >
                                  Sí, es correcto
                                </button>
                                <button
                                  onClick={() => responderConfirmacionClasificacion('no')}
                                  className={`flex-1 py-2 rounded-lg text-xs font-medium transition-all active:scale-95 ${isSurvival ? 'bg-stone-800/60 text-stone-400 hover:bg-stone-700/60' : 'bg-zinc-900/60 text-zinc-400 hover:bg-zinc-800/60'}`}
                                >
                                  No
                                </button>
                              </div>
                            </motion.div>
                          )}

                          {errorAccion && (
                            <motion.div initial={{ opacity: 0, y: -5 }} animate={{ opacity: 1, y: 0 }} className="mt-6 px-4 py-3 rounded-xl bg-red-900/20 border border-red-800/30 text-red-300 text-xs text-center max-w-sm">
                              ⚠️ {errorAccion}
                            </motion.div>
                          )}

                          <div className="mt-16 flex flex-col w-full max-w-sm gap-4">
                            <AnimatePresence mode="wait">

                              {!estadoBloqueo && !mostrandoIntenciones && (
                                <motion.div key="normal" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="flex flex-col gap-3">

                                  {!mostrandoMotivosPosponer ? (
                                    <>
                                      <button onClick={liberarTarea} disabled={procesando} className={`w-full py-4 rounded-2xl font-semibold text-lg transition-all active:scale-95 disabled:opacity-70 ${btnPrimary}`}>
                                        {procesando ? "Soltando..." : "✓ Lo logré completo"}
                                      </button>

                                      <button onClick={avanceParcial} disabled={procesando} className={`w-full py-4 rounded-2xl font-medium text-sm transition-all active:scale-95 disabled:opacity-50 ${isSurvival ? 'bg-stone-800/40 text-stone-300 hover:bg-stone-800' : 'bg-zinc-800/60 text-zinc-300 hover:bg-zinc-700/80 border border-zinc-700/50'}`}>
                                        {procesando ? "Registrando..." : "🌗 Avancé algo (Dejar resto para mañana)"}
                                      </button>

                                      <button onClick={() => setMostrandoMotivosPosponer(true)} disabled={procesando} className={`w-full py-3 rounded-2xl font-medium text-sm transition-all active:scale-95 disabled:opacity-50 ${isSurvival ? 'text-stone-400 hover:text-stone-300' : 'text-zinc-400 hover:text-zinc-300'}`}>
                                        ↻ Posponer o reprogramar
                                      </button>

                                      <button onClick={() => setEstadoBloqueo('menu')} className={`mt-4 text-sm transition-colors border-b border-transparent pb-1 mx-auto ${isSurvival ? 'text-stone-400 hover:text-stone-300 hover:border-stone-500' : 'text-zinc-400 hover:text-zinc-300 hover:border-zinc-500'}`}>
                                        Se me está haciendo difícil
                                      </button>
                                    </>
                                  ) : (
                                    <motion.div initial={{ opacity: 0, y: 5 }} animate={{ opacity: 1, y: 0 }} className="flex flex-col gap-2 w-full bg-black/20 p-4 rounded-2xl border border-white/5">
                                      <p className={`text-sm mb-2 font-medium ${isSurvival ? 'text-stone-400' : 'text-zinc-400'}`}>Sé honesto contigo. ¿Por qué lo posponemos?</p>

                                      <button onClick={() => posponerTareaConsciente("Sin energía")} className={`w-full py-3 rounded-xl text-xs transition-colors text-left px-4 ${isSurvival ? 'bg-stone-800/50 hover:bg-stone-700/50 text-stone-300' : 'bg-zinc-800/50 hover:bg-zinc-700/50 text-zinc-300'}`}>
                                        🔋Hoy no tengo energía física/mental
                                      </button>
                                      <button onClick={() => posponerTareaConsciente("Ansiedad / Miedo")} className={`w-full py-3 rounded-xl text-xs transition-colors text-left px-4 ${isSurvival ? 'bg-stone-800/50 hover:bg-stone-700/50 text-stone-300' : 'bg-zinc-800/50 hover:bg-zinc-700/50 text-zinc-300'}`}>
                                        😰 Me genera mucha ansiedad enfrentarlo
                                      </button>
                                      <button onClick={() => posponerTareaConsciente("Falta información")} className={`w-full py-3 rounded-xl text-xs transition-colors text-left px-4 ${isSurvival ? 'bg-stone-800/50 hover:bg-stone-700/50 text-stone-300' : 'bg-zinc-800/50 hover:bg-zinc-700/50 text-zinc-300'}`}>
                                        ❓ Me falta información para poder hacerlo
                                      </button>
                                      <button onClick={() => posponerTareaConsciente("Dependencia Externa")} className={`w-full py-3 rounded-xl text-xs transition-colors text-left px-4 ${isSurvival ? 'bg-stone-800/50 hover:bg-stone-700/50 text-stone-300' : 'bg-zinc-800/50 hover:bg-zinc-700/50 text-zinc-300'}`}>
                                        ⏳ Dependo de alguien o algo más (En espera)
                                      </button>
                                      <button onClick={() => posponerTareaConsciente("No es prioridad")} className={`w-full py-3 rounded-xl text-xs transition-colors text-left px-4 ${isSurvival ? 'bg-stone-800/50 hover:bg-stone-700/50 text-stone-300' : 'bg-zinc-800/50 hover:bg-zinc-700/50 text-zinc-300'}`}>
                                        🌫️ Sinceramente no es prioridad hoy
                                      </button>

                                      <button onClick={() => setMostrandoMotivosPosponer(false)} className={`mt-3 text-xs uppercase tracking-widest ${isSurvival ? 'text-stone-400 hover:text-stone-200' : 'text-zinc-400 hover:text-zinc-200'}`}>
                                        ← Cancelar, intentaré hacerlo
                                      </button>
                                    </motion.div>
                                  )}
                                </motion.div>
                              )}

                              {estadoBloqueo === 'menu' && (
                                <motion.div key="menu" initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} className="flex flex-col gap-2 w-full">

                                  <p className={`text-sm mb-3 font-medium ${isSurvival ? 'text-stone-400' : 'text-zinc-400'}`}>¿Qué necesitas para arrancar?</p>

                                  <button onClick={() => setEstadoBloqueo('intento_propio')} className={`w-full py-3.5 rounded-xl text-sm transition-colors text-left px-5 border ${isSurvival ? 'bg-stone-800/50 text-stone-200 border-stone-600/50' : 'bg-zinc-800/50 text-zinc-200 border-zinc-600/50'}`}>
                                    🧠 Quiero intentar dividirla yo mismo
                                  </button>

                                  <div className={`mb-3 p-3 rounded-xl border ${isSurvival ? 'border-stone-800/50 bg-stone-900/30' : 'border-blue-900/30 bg-blue-900/10'}`}>
                                    <button onClick={() => setEstadoBloqueo('solo_mirar')} className={`w-full py-2 text-sm font-medium transition-colors text-center ${isSurvival ? 'text-stone-300 hover:text-white' : 'text-blue-300 hover:text-blue-100'}`}>
                                      👀 Solo quiero "abrirlo/mirarlo" sin compromiso
                                    </button>
                                  </div>

                                  <div className="h-px w-full my-2 bg-white/5 relative">
                                    <span className={`absolute -top-2 left-1/2 -translate-x-1/2 px-2 text-xs ${isSurvival ? 'bg-[#1c1917] text-stone-400' : 'bg-[#09090b] text-zinc-400'}`}>O pedir ayuda a la IA</span>
                                  </div>

                                  <button onClick={() => solicitarAyudaIA("No sé cómo empezar")} className={`w-full py-3 rounded-xl text-xs transition-colors text-left px-5 border ${isSurvival ? 'bg-transparent text-stone-400 border-stone-800 hover:bg-stone-800/50' : 'bg-transparent text-zinc-400 border-zinc-800 hover:bg-zinc-800/50'}`}>
                                    🌫️ No sé por dónde empezar
                                  </button>
                                  <button onClick={() => solicitarAyudaIA("Es demasiado grande y me abruma")} className={`w-full py-3 rounded-xl text-xs transition-colors text-left px-5 border ${isSurvival ? 'bg-transparent text-stone-400 border-stone-800 hover:bg-stone-800/50' : 'bg-transparent text-zinc-400 border-zinc-800 hover:bg-zinc-800/50'}`}>
                                    🏔️ Parece enorme y me abruma
                                  </button>
                                  <button onClick={() => solicitarAyudaIA("Me da miedo / ansiedad hacerlo")} className={`w-full py-3 rounded-xl text-xs transition-colors text-left px-5 border ${isSurvival ? 'bg-transparent text-stone-400 border-stone-800 hover:bg-stone-800/50' : 'bg-transparent text-zinc-400 border-zinc-800 hover:bg-zinc-800/50'}`}>
                                    😰 Me preocupa / me da ansiedad
                                  </button>
                                  <button onClick={() => solicitarAyudaIA("Siento que debería hacerlo perfecto / No estoy listo")} className={`w-full py-3 rounded-xl text-xs transition-colors text-left px-5 border ${isSurvival ? 'bg-transparent text-stone-400 border-stone-800 hover:bg-stone-800/50' : 'bg-transparent text-zinc-400 border-zinc-800 hover:bg-zinc-800/50'}`}>
                                    🎯 Siento que debe quedar perfecto
                                  </button>

                                  <button onClick={() => { setEstadoBloqueo(null); setEstadoPaso1(null); setMostrandoPrediccion(false); }} className={`mt-4 text-xs uppercase tracking-widest ${isSurvival ? 'text-stone-400 hover:text-stone-200' : 'text-zinc-400 hover:text-zinc-200'}`}>
                                    ← Regresar
                                  </button>
                                </motion.div>
                              )}

                              {estadoBloqueo === 'solo_mirar' && estadoPaso1 !== 'exposicion_lograda' && (
                                <motion.div key="solo_mirar" initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }} className={`flex flex-col items-center gap-5 text-center p-6 rounded-3xl border ${isSurvival ? 'bg-stone-800/30 border-stone-700/30' : 'bg-blue-900/10 border-blue-800/30'}`}>
                                  <span className="text-4xl mb-2">👀</span>
                                  <p className={`text-sm font-medium ${isSurvival ? 'text-stone-300' : 'text-blue-200'}`}>El primer paso no es hacer. Es acercarse.</p>

                                  <p className={`text-xs leading-relaxed ${isSurvival ? 'text-stone-400' : 'text-blue-300/70'}`}>
                                    No tienes que hacerlo ahora. Solo ubícate frente a lo que necesitas para: <br />
                                    <span className={`block my-2 text-sm font-bold ${isSurvival ? 'text-stone-200' : 'text-blue-100'}`}>"{tareaActual.titulo}"</span>
                                    (Ve al lugar, abre el documento o párate frente al objeto). Solo obsérvalo por 10 segundos y respira.<br /><br />
                                    Si tu cuerpo te pide huir después de eso, puedes hacerlo con orgullo. Si te da curiosidad, puedes seguir.
                                  </p>

                                  <button onClick={() => registrarAccionPaso1('exposicion_mirar')} className={`w-full py-4 mt-2 rounded-xl text-sm font-bold transition-all active:scale-95 shadow-lg ${isSurvival ? 'bg-stone-200 text-stone-900' : 'bg-blue-600 text-white hover:bg-blue-500'}`}>
                                    ✅ Ya me acerqué (Exposición superada)
                                  </button>
                                  <button onClick={() => setEstadoBloqueo('menu')} className={`text-xs underline decoration-transparent transition-colors ${isSurvival ? 'text-stone-400 hover:text-stone-300' : 'text-zinc-400 hover:text-zinc-300'}`}>
                                    Volver al menú
                                  </button>
                                </motion.div>
                              )}

                              {estadoBloqueo === 'intento_propio' && (
                                <motion.div key="intento_propio" initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }} className={`flex flex-col gap-4 text-center p-6 rounded-3xl border ${isSurvival ? 'bg-stone-800/30 border-stone-700/30' : 'bg-zinc-900/50 border-zinc-800/50'}`}>
                                  <span className="text-3xl">🧠</span>
                                  <p className={`text-sm font-medium ${isSurvival ? 'text-stone-300' : 'text-zinc-200'}`}>Tú conoces esta tarea mejor que la IA.</p>
                                  <p className={`text-xs ${isSurvival ? 'text-stone-400' : 'text-zinc-400'}`}>¿Cuál es el paso físico más absurdo y pequeño que puedes dar ahora mismo?</p>

                                  <div className="flex flex-col gap-2 mt-4">
                                    <button onClick={() => registrarAccionPaso1('paso1_comprometido')} className={`w-full py-3.5 rounded-xl text-sm font-bold transition-all active:scale-95 ${isSurvival ? 'bg-stone-200 text-stone-900' : 'bg-zinc-200 text-zinc-900'}`}>
                                      Ya sé cuál es, lo voy a hacer
                                    </button>
                                    <button onClick={() => setEstadoBloqueo('menu')} className={`w-full py-2 text-xs transition-colors ${isSurvival ? 'text-stone-400 hover:text-stone-300' : 'text-zinc-400 hover:text-zinc-300'}`}>
                                      Mmm, mejor sí le pido ayuda a la IA
                                    </button>
                                  </div>
                                </motion.div>
                              )}

                              {estadoBloqueo === 'cargando' && (
                                <motion.div key="cargando" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="flex flex-col items-center py-8">
                                  <span className="text-3xl animate-pulse opacity-50 mb-4">{isSurvival ? '🕯️' : '💡'}</span>
                                  <p className={`text-sm animate-pulse ${isSurvival ? 'text-stone-400' : 'text-zinc-400'}`}>Pensando en un camino fácil para ti...</p>
                                </motion.div>
                              )}

                              {estadoBloqueo === 'resuelto' && (
                                <motion.div key="resuelto" initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className={`flex flex-col gap-5 text-left p-6 rounded-3xl border ${isSurvival ? 'bg-stone-800/30 border-stone-700/30' : 'bg-zinc-900/50 border-zinc-800/50'}`}>

                                  {estadoPaso1 !== 'realizado' && (
                                    <>
                                      <p className={`text-sm font-medium ${isSurvival ? 'text-stone-300' : 'text-zinc-300'}`}>Intenta solo esto:</p>
                                      <ul className="flex flex-col gap-3">
                                        {pasosIA?.map((paso, idx) => (
                                          <li key={idx} className={`p-4 rounded-2xl text-sm leading-relaxed transition-all duration-500
                                                    ${idx === 0 && estadoPaso1 === 'comprometido'
                                              ? (isSurvival ? 'bg-stone-700 border border-stone-500 text-stone-100 scale-[1.02] shadow-lg' : 'bg-zinc-700 border border-blue-500/50 text-zinc-100 scale-[1.02] shadow-lg')
                                              : (isSurvival ? 'bg-stone-800/60 text-stone-200' : 'bg-zinc-800/50 text-zinc-200')}
                                                    ${idx !== 0 && estadoPaso1 === 'comprometido' ? 'opacity-30 blur-[1px]' : ''}
                                                `}>
                                            {paso}
                                          </li>
                                        ))}
                                      </ul>
                                      <div className={`h-px w-full my-3 ${isSurvival ? 'bg-stone-700/30' : 'bg-zinc-800'}`}></div>
                                    </>
                                  )}

                                  {insightDiscrepancia && !discrepanciaRespondida && (
                                    <motion.div initial={{ opacity: 0, y: 5 }} animate={{ opacity: 1, y: 0 }} className="p-4 rounded-2xl bg-purple-900/10 border border-purple-800/30 mb-3">
                                      <p className="text-sm text-purple-200/90 leading-relaxed mb-3">
                                        💭 {insightDiscrepancia.sugerencia}
                                      </p>
                                      <div className="flex gap-2">
                                        <button
                                          onClick={async () => {
                                            await apiFetch(`/api/feedback-discrepancia`, {
                                              method: "POST", headers: { "Content-Type": "application/json" },
                                              body: JSON.stringify({
                                                motivo_declarado: insightDiscrepancia.motivo_declarado,
                                                energia: energia,
                                                intervencion_sugerida: insightDiscrepancia.intervencion_que_funciona,
                                                respuesta: "tiene_sentido"
                                              })
                                            });
                                            setDiscrepanciaRespondida(true);
                                          }}
                                          className="flex-1 py-2 rounded-lg text-xs font-medium bg-purple-800/40 text-purple-200 hover:bg-purple-800/60 transition-all active:scale-95"
                                        >
                                          Tiene sentido
                                        </button>
                                        <button
                                          onClick={async () => {
                                            await apiFetch(`/api/feedback-discrepancia`, {
                                              method: "POST", headers: { "Content-Type": "application/json" },
                                              body: JSON.stringify({
                                                motivo_declarado: insightDiscrepancia.motivo_declarado,
                                                energia: energia,
                                                intervencion_sugerida: insightDiscrepancia.intervencion_que_funciona,
                                                respuesta: "no_es_eso"
                                              })
                                            });
                                            setDiscrepanciaRespondida(true);
                                          }}
                                          className="flex-1 py-2 rounded-lg text-xs font-medium bg-zinc-800/60 text-zinc-400 hover:bg-zinc-700/60 transition-all active:scale-95"
                                        >
                                          No es eso
                                        </button>
                                      </div>
                                    </motion.div>
                                  )}

                                  {(() => {
                                    const esSalud = tareaActual.carpeta?.toLowerCase().includes("health") ||
                                      tareaActual.etiquetas?.some(t => t.toLowerCase().includes("medicina"));

                                    if (esSalud) {
                                      return (
                                        <div className="flex flex-col gap-3">
                                          <button onClick={liberarTarea} className={`w-full py-4 rounded-xl text-sm font-bold transition-all active:scale-95 bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 hover:bg-emerald-500/30`}>
                                            💊 Listo. Cuidé de mí mismo.
                                          </button>
                                          <button onClick={() => { setEstadoBloqueo(null); setEstadoPaso1(null); setMostrandoPrediccion(false); }} className={`w-full py-2 mt-1 text-xs underline decoration-transparent transition-colors ${isSurvival ? 'text-stone-400 hover:text-stone-300' : 'text-zinc-400 hover:text-zinc-300'}`}>
                                            No lo haré, asumo la responsabilidad.
                                          </button>
                                        </div>
                                      );
                                    }

                                    return (
                                      <div className="flex flex-col gap-3">
                                        {!estadoPaso1 && !mostrandoPrediccion && (
                                          <>
                                            <button onClick={comprometerseAlPaso1} className={`w-full py-3.5 rounded-xl text-sm font-bold transition-all active:scale-95 shadow-lg ${isSurvival ? 'bg-stone-200 text-stone-900 hover:bg-white' : 'bg-blue-600 text-white border border-blue-500 hover:bg-blue-500'}`}>
                                              Me comprometo a hacer el Paso 1
                                            </button>
                                            <button onClick={() => posponerTareaConsciente("No pude comprometerme al Paso 1")} className={`w-full py-3.5 rounded-xl text-sm transition-all active:scale-95 ${isSurvival ? 'bg-transparent text-stone-400 border border-stone-700/50 hover:bg-stone-800/50' : 'bg-transparent text-zinc-400 border border-zinc-700/50 hover:bg-zinc-800/50'}`}>
                                              Sinceramente, hoy no puedo empezar
                                            </button>
                                          </>
                                        )}

                                        {mostrandoPrediccion && (
                                          <motion.div initial={{ opacity: 0, y: 5 }} animate={{ opacity: 1, y: 0 }} className="flex flex-col gap-2 w-full bg-black/20 p-4 rounded-2xl border border-white/5">
                                            <p className={`text-sm mb-1 font-medium ${isSurvival ? 'text-stone-400' : 'text-zinc-400'}`}>
                                              Antes de empezar, algo rápido y opcional: ¿qué crees que va a pasar?
                                            </p>
                                            {PREDICCIONES_RAPIDAS.map((p) => (
                                              <button key={p} onClick={() => confirmarPaso1ConPrediccion(p)} className={`w-full py-3 rounded-xl text-xs transition-colors text-left px-4 ${isSurvival ? 'bg-stone-800/50 hover:bg-stone-700/50 text-stone-300' : 'bg-zinc-800/50 hover:bg-zinc-700/50 text-zinc-300'}`}>
                                                {p}
                                              </button>
                                            ))}
                                            <button onClick={() => confirmarPaso1ConPrediccion(null)} className={`mt-2 text-xs font-medium ${isSurvival ? 'text-stone-300 hover:text-white' : 'text-blue-300 hover:text-blue-100'}`}>
                                              Omitir, solo quiero empezar →
                                            </button>
                                            <button onClick={() => setMostrandoPrediccion(false)} className={`text-xs uppercase tracking-widest ${isSurvival ? 'text-stone-400 hover:text-stone-200' : 'text-zinc-400 hover:text-zinc-200'}`}>
                                              ← Espera, lo pienso un poco más
                                            </button>
                                          </motion.div>
                                        )}

                                        {estadoPaso1 === 'comprometido' && (
                                          <motion.div initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }} className="flex flex-col gap-3 w-full mt-2">
                                            <div className="text-center mb-3">
                                              <span className="text-3xl animate-pulse block mb-2 opacity-80">⏳</span>
                                              <p className={`text-sm font-bold ${isSurvival ? 'text-stone-300' : 'text-zinc-200'}`}>Haz el paso 1 ahora. Te espero aquí.</p>
                                            </div>
                                            <button onClick={() => registrarAccionPaso1('paso1_realizado')} className={`w-full py-4 rounded-xl text-sm font-bold transition-all active:scale-95 shadow-lg ${isSurvival ? 'bg-emerald-200 text-emerald-900 hover:bg-emerald-300' : 'bg-emerald-600 text-white border border-emerald-500 hover:bg-emerald-500'}`}>
                                              ✅ ¡REALMENTE hice el paso 1!
                                            </button>
                                            <button onClick={() => posponerTareaConsciente("Me bloqueé  intentando el Paso 1")} className={`w-full py-3 rounded-xl text-sm transition-all active:scale-95 border ${isSurvival ? 'border-stone-700/50 text-stone-400 hover:bg-stone-800/50' : 'border-zinc-700/50 text-zinc-400 hover:bg-zinc-800/50'}`}>
                                              Lo intenté pero me bloqueé (Posponer)
                                            </button>
                                          </motion.div>
                                        )}

                                        {estadoBloqueo === 'solo_mirar' && estadoPaso1 === 'exposicion_lograda' && (
                                          <motion.div
                                            key="exposicion_lograda_directa"
                                            initial={{ opacity: 0, y: 10 }}
                                            animate={{ opacity: 1, y: 0 }}
                                            className="flex flex-col items-center gap-4 text-center p-6 rounded-3xl border bg-blue-900/10 border-blue-800/30"
                                          >
                                            <span className="text-4xl block mb-2 opacity-80">🛡️</span>
                                            <p className={`text-lg font-bold ${isSurvival ? 'text-stone-200' : 'text-zinc-100'}`}>
                                              Exposición lograda
                                            </p>
                                            <p className={`text-xs leading-relaxed ${isSurvival ? 'text-stone-400' : 'text-zinc-400'}`}>
                                              Te acercaste a algo que estabas evitando. Eso importa, aunque no hayas hecho nada más.
                                            </p>

                                            <button
                                              onClick={() => { setEstadoBloqueo('menu'); }}
                                              className={`w-full py-3.5 rounded-xl text-sm font-bold transition-all active:scale-95 shadow-lg ${isSurvival ? 'bg-stone-200 text-stone-900' : 'bg-blue-600 text-white border border-blue-500 hover:bg-blue-500'}`}
                                            >
                                              La ansiedad bajó. Quiero intentar un micro-paso.
                                            </button>

                                            <button
                                              onClick={avanceParcial}
                                              className={`w-full py-3.5 rounded-xl text-sm transition-all active:scale-95 border ${isSurvival ? 'bg-transparent text-stone-300 border-stone-600' : 'bg-transparent text-zinc-300 border-zinc-600'}`}
                                            >
                                              Fue suficiente exposición por hoy (Posponer)
                                            </button>
                                          </motion.div>
                                        )}

                                        {estadoPaso1 === 'realizado' && (
                                          <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="flex flex-col gap-3 w-full">
                                            <div className="text-center mb-4">
                                              <span className="text-4xl block mb-2">🎉</span>
                                              <p className={`text-lg font-bold ${isSurvival ? 'text-stone-200' : 'text-zinc-100'}`}>¡Rompiste la inercia!</p>
                                              <p className={`text-xs mt-1 ${isSurvival ? 'text-stone-400' : 'text-zinc-400'}`}>Esa era la batalla real. ¿Qué deseas hacer ahora?</p>
                                            </div>
                                            <button onClick={() => { setEstadoBloqueo(null); setEstadoPaso1(null); setMostrandoPrediccion(false); }} className={`w-full py-3.5 rounded-xl text-sm font-bold transition-all active:scale-95 shadow-lg ${isSurvival ? 'bg-stone-200 text-stone-900 hover:bg-white' : 'bg-blue-600 text-white border border-blue-500 hover:bg-blue-500'}`}>
                                              Me siento capaz de seguir trabajando
                                            </button>
                                            <button onClick={avanceParcial} className={`w-full py-3.5 rounded-xl text-sm transition-all active:scale-95 border ${isSurvival ? 'bg-transparent text-stone-300 border-stone-600 hover:bg-stone-800/50' : 'bg-transparent text-zinc-300 border-zinc-600 hover:bg-zinc-800/50'}`}>
                                              Avancé algo, dejo el resto para mañana
                                            </button>
                                            <button onClick={liberarTarea} className={`w-full py-2 mt-2 text-xs underline decoration-transparent transition-colors ${isSurvival ? 'text-stone-400 hover:text-stone-300' : 'text-zinc-400 hover:text-zinc-300'}`}>
                                              Sorprendentemente, terminé toda la tarea
                                            </button>
                                          </motion.div>
                                        )}
                                      </div>
                                    );
                                  })()}
                                </motion.div>
                              )}
                            </AnimatePresence>
                          </div>
                        </>
                      )}
                    </motion.div>
                  )}
                </AnimatePresence>
              </>
            )}
          </>
        )}

        {!pantallaPostCrisis && (
          <div className="fixed bottom-6 left-0 w-full px-6 flex justify-center z-50 pointer-events-none">
            <form onSubmit={manejarCaptura} className="w-full max-w-lg relative flex items-center pointer-events-auto">
              <input type="text" value={textoCaptura} onChange={(e) => setTextoCaptura(e.target.value)} disabled={guardando} placeholder="Escribe una idea, tarea o lo que sea que tengas en la cabeza..." className={`w-full backdrop-blur-xl rounded-2xl py-4 pl-6 pr-12 focus:outline-none focus:ring-1 shadow-2xl disabled:opacity-50 transition-colors ${isSurvival ? 'bg-stone-800/80 text-stone-200 focus:ring-stone-400 placeholder:text-stone-400 border border-stone-700/50' : 'bg-zinc-800/80 text-zinc-200 focus:ring-zinc-400 placeholder:text-zinc-400 border border-zinc-700/50'}`} />
              {guardando ? <span className="absolute right-5 animate-pulse opacity-50">...</span> : <button type="submit" className={`absolute right-4 text-xl opacity-40 hover:opacity-100 transition-opacity ${isSurvival ? 'text-stone-300' : 'text-zinc-300'}`}>↵</button>}
            </form>
          </div>
        )}

      </div>

      <AnimatePresence>
        {pantallaCrisis && (
          <motion.div
            initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
            className="fixed inset-0 z-[200] flex items-center justify-center p-6 bg-black/90 backdrop-blur-sm"
          >
            <motion.div
              initial={{ scale: 0.95, y: 20 }} animate={{ scale: 1, y: 0 }}
              className="bg-[#161618] border border-blue-900/40 p-8 rounded-3xl max-w-md w-full text-left"
            >
              <p className="text-zinc-100 text-base leading-relaxed mb-6">
                {pantallaCrisis.mensaje_principal}
              </p>

              <div className="flex flex-col gap-3 mb-6">
                {pantallaCrisis.lineas.map((linea, idx) => (
                  <div key={idx} className="bg-blue-900/10 border border-blue-900/30 p-4 rounded-2xl">
                    <p className="text-xs text-blue-300 uppercase tracking-wide mb-1">{linea.pais}</p>
                    <p className="text-zinc-200 font-medium text-sm">{linea.nombre}</p>
                    {linea.telefono && (
                      <a href={`tel:${linea.telefono}`} className="text-blue-400 text-lg font-bold block mt-1">
                        📞 {linea.telefono}
                      </a>
                    )}
                    {linea.url && (
                      <a href={linea.url} target="_blank" rel="noopener noreferrer" className="text-blue-400 text-sm block mt-1 underline">
                        {linea.url}
                      </a>
                    )}
                    <p className="text-xs text-zinc-400 mt-1">{linea.detalle}</p>
                  </div>
                ))}
              </div>

              <p className="text-xs text-zinc-400 leading-relaxed mb-6">
                {pantallaCrisis.mensaje_secundario}
              </p>

              <button
                onClick={() => {
                  setPantallaCrisis(null);
                  setPantallaPostCrisis(true);
                }}
                className="w-full py-3 bg-zinc-800 text-zinc-300 rounded-xl text-sm hover:bg-zinc-700 transition-all shadow-lg"
              >
                Entendido
              </button>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      <AnimatePresence>
        {mostrarGuia && (
          <motion.div
            initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
            className="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm overflow-y-auto"
          >
            <motion.div
              initial={{ scale: 0.95, y: 20 }} animate={{ scale: 1, y: 0 }} exit={{ scale: 0.95, y: 20 }}
              className="bg-[#121214] border border-zinc-800 p-8 rounded-3xl max-w-2xl w-full text-left relative my-8 overflow-y-auto max-h-[90vh] scrollbar-hide"
            >
              <button onClick={() => setMostrarGuia(false)} aria-label="Cerrar guía" className="absolute top-6 right-6 text-zinc-400 hover:text-zinc-300 text-xl">
                ✕
              </button>

              <h2 className="text-2xl font-bold text-zinc-100 mb-2">🧠 Cómo entiende AtypicalTick tu mente</h2>
              <p className="text-zinc-400 text-sm mb-6 leading-relaxed">
                <b>Regla de oro: Menos etiquetas, más inteligencia.</b><br />
                No queremos que pierdas tiempo organizando. Si usas buenas carpetas o títulos descriptivos (ej. "pagar tarjeta" o "llamar a mamá"), la IA lo detectará sola. Las etiquetas son solo ayudas extra.
              </p>

              <div className="flex flex-col gap-4">

                <div className="bg-red-900/10 p-5 rounded-2xl border border-red-900/30">
                  <h3 className="text-red-400 font-semibold mb-2 flex items-center gap-2"><span>⚠️</span> 1. Consecuencias (El Impuesto TDAH)</h3>
                  <p className="text-sm text-zinc-400 leading-relaxed mb-3">
                    Son cosas que si no haces, hay problemas reales (Burocracia, Finanzas, Salud). El sistema <b>NUNCA te las perdonará automáticamente</b> y tiene una IA entrenada para reducir tu ansiedad al enfrentarlas.
                  </p>
                  <p className="text-xs text-zinc-400 mb-2">💡 La IA las detecta sola si:</p>
                  <ul className="text-xs text-zinc-400 list-disc pl-5">
                    <li>Están en carpetas como: <b>Finanzas, Banco, Salud</b>.</li>
                    <li>Tienen <b>Prioridad Alta (Bandera Roja)</b> en TickTick.</li>
                    <li>El título dice "pagar", "impuesto", "cita", etc.</li>
                  </ul>
                </div>

                <div className="bg-blue-900/10 p-5 rounded-2xl border border-blue-900/30">
                  <h3 className="text-blue-400 font-semibold mb-2 flex items-center gap-2"><span>💬</span> 2. Ansiedad Social y Comunicación</h3>
                  <p className="text-sm text-zinc-400 leading-relaxed mb-3">
                    Tareas que no quitan energía física, pero bloquean por miedo a la interacción o el rechazo. La IA tiene un protocolo de "Borradoles Seguros" para esto.
                  </p>
                  <p className="text-xs text-zinc-400">💡 La IA las detecta sola si el título incluye: <b>llamar, enviar correo, mensaje, responder</b> (O si le pones la etiqueta #ansiedad).</p>
                </div>

                <div className="bg-stone-900/50 p-5 rounded-2xl border border-stone-800">
                  <h3 className="text-stone-300 font-semibold mb-2 flex items-center gap-2"><span>🔋</span> 3. Fricción y Energía</h3>
                  <p className="text-sm text-zinc-400 leading-relaxed mb-2">
                    En "Modo Sobrevivir", AtypicalTick esconde lo abrumador. Si hay tareas muy sencillas que quieres que siempre aparezcan en días malos, ponles etiquetas como:
                  </p>
                  <div className="flex flex-wrap gap-2">
                    <span className="bg-stone-800 text-stone-300 px-2 py-1 rounded text-xs border border-stone-700">#facil</span>
                    <span className="bg-stone-800 text-stone-300 px-2 py-1 rounded text-xs border border-stone-700">#baja-energia</span>
                  </div>
                </div>

                <div className="bg-purple-900/10 p-5 rounded-2xl border border-purple-900/30">
                  <h3 className="text-purple-400 font-semibold mb-2 flex items-center gap-2"><span>🎨</span> 4. Curiosidad e Intereses</h3>
                  <p className="text-sm text-zinc-400 leading-relaxed mb-3">
                    Si te bloqueas, a veces no necesitas descansar, necesitas <b>cambiar de contexto</b>. Si en la app rechazas una tarea y pides "Algo creativo", priorizaremos tus hiperfijaciones o hobbies.
                  </p>
                  <div className="flex flex-wrap gap-2">
                    <span className="bg-purple-900/40 text-purple-300 px-2 py-1 rounded text-xs border border-purple-800/50">#creativo</span>
                    <span className="bg-purple-900/40 text-purple-300 px-2 py-1 rounded text-xs border border-purple-800/50">#aprender</span>
                    <span className="bg-purple-900/40 text-purple-300 px-2 py-1 rounded text-xs border border-purple-800/50">#hobbie</span>
                  </div>
                </div>

                <div className="bg-black/30 p-5 rounded-2xl border border-white/5 mt-2">
                  <h3 className="text-emerald-400 font-semibold mb-2 flex items-center gap-2"><span>🔄</span> El Perdón de las Rutinas</h3>
                  <p className="text-sm text-zinc-400 leading-relaxed">
                    Cualquier tarea que tenga "Repetición" en TickTick (ej. Leer a diario) es considerada un Hábito. Si la pospones, el sistema <b>la perdonará por hoy</b> y no te acumulará deudas para mañana.
                  </p>
                </div>

              </div>

              <button onClick={() => setMostrarGuia(false)} className="w-full mt-8 py-4 bg-zinc-200 text-zinc-900 rounded-xl font-bold hover:bg-white active:scale-95 transition-all sticky bottom-0">
                Entendido, el sistema trabaja para mí
              </button>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </main>
  );
}