# Arquitectura de AtypicalTick

## Objetivo

Este documento describe la arquitectura del backend de AtypicalTick, la responsabilidad de cada módulo y las decisiones técnicas tomadas durante su evolución.

Su propósito es facilitar el mantenimiento, futuras migraciones (Render, Supabase) y el desarrollo de nuevas funcionalidades sin aumentar el acoplamiento del proyecto.

---

# Estructura del proyecto

backend/

├── core/
├── services/
├── frontend-enfoque/
├── main.py
├── db.py
├── config.py
└── scheduler.py

---

# Preguntas

¿Cuál es su responsabilidad?
¿Quién lo utiliza?
¿De qué depende?
¿Debería seguir existiendo como módulo independiente?
¿Pertenece al dominio (lógica del negocio) o a la infraestructura?

# Inventario de archivos

