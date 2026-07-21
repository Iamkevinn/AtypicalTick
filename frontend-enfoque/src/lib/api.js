// src/lib/api.js
export const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const TOKEN_KEY = "atypicaltick_token";

// ANTES: se usaba una API_KEY estática (NEXT_PUBLIC_API_KEY), que
// Next.js incrusta en el JS público del navegador -- cualquiera con
// devtools/Network podía leerla y llamar al backend directamente como
// si fuera el dueño de la cuenta, y nunca expiraba.
//
// AHORA: el usuario hace login con una contraseña (ver login()) y el
// backend devuelve un token de sesión que se guarda aquí, en
// localStorage, y se manda como "Authorization: Bearer <token>" en
// cada llamada. localStorage tampoco es inmune a XSS, pero al menos
// el token es distinto por sesión, expira solo, y se puede revocar
// (logout) sin redeploy. Si más adelante esto se empaqueta como app
// móvil (Expo/React Native), este mismo esquema de Bearer token se
// traslada directo a SecureStore/Keychain -- el backend no cambia.

export function guardarToken(token) {
  if (typeof window !== "undefined") {
    localStorage.setItem(TOKEN_KEY, token);
  }
}

export function obtenerToken() {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(TOKEN_KEY);
}

export function borrarToken() {
  if (typeof window !== "undefined") {
    localStorage.removeItem(TOKEN_KEY);
  }
}

export function haySesion() {
  return Boolean(obtenerToken());
}

/**
 * Hace login contra el backend y guarda el token si es correcto.
 * Lanza un Error con mensaje legible si la contraseña es incorrecta
 * o si el backend no responde.
 */
export async function login(password) {
  let resp;
  try {
    resp = await fetch(`${API_BASE}/api/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ password }),
    });
  } catch (e) {
    throw new Error("No se pudo conectar con el servidor.");
  }

  if (!resp.ok) {
    throw new Error("Contraseña incorrecta.");
  }

  const datos = await resp.json();
  guardarToken(datos.token);
  return datos;
}

/**
 * Cierra la sesión: avisa al backend (para invalidar el token del
 * lado servidor también, no solo borrarlo localmente) y limpia el
 * almacenamiento local pase lo que pase con esa llamada.
 */
export async function logout() {
  const token = obtenerToken();
  borrarToken();

  if (!token) return;

  try {
    await fetch(`${API_BASE}/api/logout`, {
      method: "POST",
      headers: { Authorization: `Bearer ${token}` },
    });
  } catch (e) {
    // Si falla la llamada de red, no pasa nada grave: el token ya
    // expira solo, y localmente ya lo borramos arriba.
  }
}

/**
 * Reemplazo de fetch() para llamadas al backend de AtypicalTick.
 * Antepone API_BASE, agrega "Authorization: Bearer <token>"
 * automáticamente, y si el backend responde 401 (sesión inválida o
 * expirada) limpia el token local y manda al usuario a /login.
 */
export async function apiFetch(path, options = {}) {
  const token = obtenerToken();
  const headers = {
    ...(options.headers || {}),
  };
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const resp = await fetch(`${API_BASE}${path}`, { ...options, headers });

  if (resp.status === 401 && typeof window !== "undefined") {
    borrarToken();
    if (window.location.pathname !== "/login") {
      window.location.href = "/login";
    }
  }

  return resp;
}