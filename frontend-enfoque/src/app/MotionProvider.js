// MotionProvider.js
// ---------------------------------------------------------
// Framer Motion NO respeta `prefers-reduced-motion` por defecto.
// Si el sistema operativo de la persona tiene activado "reducir
// movimiento" (algo común en gente con migrañas, vértigo, o que
// simplemente la sobre-estimulación visual empeora su ansiedad),
// este wrapper hace que TODAS las animaciones del proyecto bajen
// su movimiento automáticamente, sin tener que tocar cada
// motion.div uno por uno.
//
// "user" = respeta la preferencia del sistema operativo.
// Framer Motion mantiene los fade de opacidad (las pantallas
// igual aparecen/desaparecen) pero elimina el desplazamiento y
// escalado — la parte que más sobre-estimula.
// ---------------------------------------------------------
"use client";
import { MotionConfig } from "framer-motion";

export default function MotionProvider({ children }) {
  return <MotionConfig reducedMotion="user">{children}</MotionConfig>;
}