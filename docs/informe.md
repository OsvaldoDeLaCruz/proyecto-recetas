# Informe técnico — Recetas IA (borrador para el PDF de máx. 3 páginas)

**Curso:** Tecnologías Web (5916) · Grupo T02 · 2026-2
**Autor(es):** _completar_
**Repositorio:** _URL de GitHub_ · **Aplicación:** _https://tu-dominio_

## 1. Descripción y arquitectura

Recetas IA es una aplicación web que permite a cada usuario registrar su inventario de
ingredientes y generar recetas con un modelo de lenguaje. Las recetas se almacenan en MySQL y
pueden consultarse, calificarse (1–5) y eliminarse.

La arquitectura tiene tres capas desplegadas como contenedores en un VPS:

1. **Caddy** (proxy inverso): termina HTTPS con certificado de Let's Encrypt y reenvía el
   tráfico a la aplicación.
2. **FastAPI** (aplicación): expone la API REST documentada con Swagger y sirve la interfaz
   web (Jinja2 + JavaScript). Está organizada en `routers` (HTTP), `schemas` (validación),
   `models` (ORM) y `services` (lógica del LLM).
3. **MySQL 8.4** (datos): servicio separado con volumen persistente.

El servicio `llm_service.py` encapsula la IA: construye el prompt con el inventario,
llama a OpenRouter, extrae y valida el JSON con Pydantic y reintenta si la respuesta no es
válida. El usuario nunca escribe texto libre al modelo; solo elige tipo de comida y porciones.

_[Insertar diagrama de arquitectura del README]_

## 2. Modelo de base de datos

_[Insertar diagrama ER (el diagrama Mermaid del README se puede exportar en mermaid.live)]_

- `usuarios` 1—N `ingredientes` (nombre único por usuario)
- `usuarios` 1—N `recetas` (ingredientes y pasos en columnas JSON)
- `recetas` 1—0..1 `calificaciones` (score 1..5 con CHECK, `ON DELETE CASCADE`)

## 3. Decisiones técnicas

| Decisión | Justificación |
|---|---|
| FastAPI + SQLAlchemy 2 | Tipado, validación automática y Swagger sin código adicional. |
| JWT + bcrypt | Autenticación sin estado, adecuada para API REST; contraseñas nunca en texto plano. |
| JSON columns para ingredientes/pasos de la receta | La receta es un documento que se lee completo; evita tablas extra sin perder estructura. |
| Contrato `LLMRecipe` en Pydantic | El LLM puede devolver formatos inconsistentes; se normaliza (dificultad, minutos) y se rechaza lo inválido (HTTP 502) en vez de guardar basura. |
| Reintentos en el servicio LLM | Los modelos gratuitos a veces devuelven texto no JSON; un reintento mejora la tasa de éxito. |
| Inyección de dependencias (`get_llm_service`) | Permite probar los endpoints con un LLM falso, sin red ni costo. |
| Caddy en vez de Nginx + Certbot | Emite y renueva el certificado SSL automáticamente con una configuración de 4 líneas. |
| Secretos en `.env` | Evita la penalización por credenciales expuestas; `.env.example` documenta las variables. |
| Pruebas con SQLite en memoria | Rápidas y reproducibles; 41 pruebas que cubren validación, prompt, parseo y endpoints. |

## 4. Capturas del sistema

_[Inicio de sesión]_ · _[Inventario con ingredientes]_ · _[Receta generada]_ ·
_[Historial con calificación]_ · _[Swagger /docs]_ · _[Candado HTTPS + favicon en el navegador]_ ·
_[`docker compose ps` en el VPS]_ · _[Resultado de `pytest`]_
