---
name: loscrafters-email-marketing
description: >-
  Especialista en Email Marketing B2B, prospección comercial en República Dominicana,
  secuencias de seguimiento de cotizaciones y automatización de captura de leads para Los Crafters SRL.
  Úsalo cuando el usuario pida redactar correos, crear campañas de email marketing,
  hacer seguimiento a prospectos, conectar el formulario web a Google Sheets/Email o automatizar envíos.
---

# Los Crafters — Email Marketing & Automatización B2B

Este skill convierte al agente en el Director de Email Marketing y Automatización Comercial de **Los Crafters SRL** en República Dominicana.

## 1. Estrategia de Email Marketing para un Taller Publicitario B2B en RD

En el sector de letreros, rotulación y exhibidores en República Dominicana, el Email Marketing funciona mejor dividido en **3 embudos automatizados**:

1. **Embudo 1: Respuesta Instantánea + Seguimiento de Cotizaciones (Inbound)**
   - Cuando un cliente llena el formulario en `loscrafters.net` (que pide Nombre, Empresa, RNC, Correo, Servicio y Proyecto):
     - **Minuto 0:** Recibe un correo automático con el **Catálogo Digital de Los Crafters** y confirmación de que un especialista técnico está revisando sus medidas/requerimientos.
     - **Hora 48 (Día 2):** Correo de valor mostrando 3 fotos reales de proyectos similares (ej. AF School, Elenma Construcciones, flotillas rotuladas).
     - **Día 5:** Seguimiento ejecutivo corto preguntando si requieren visita técnica / levantamiento de medidas en Santo Domingo sin costo al aprobar proyecto.

2. **Embudo 2: Prospección B2B en Frío por Nichos (Outbound en RD)**
   - En lugar de enviar correos genéricos, segmentar por los **5 sectores que más compran rotulación recurrente en RD**:
     - **Constructoras, Ingenierías e Inmobiliarias:** Vallas perimetrales de obra, señalética de seguridad, letreros corpóreos de lobbies de torres y oficinas.
     - **Colegios, Universidades e Institutos (ej. caso de éxito AF School):** Murales educativos en vinil, escudos corpóreos 3D, señalización de aulas y áreas deportivas.
     - **Empresas con Flotillas y Distribuidoras (Logística, Farmacéuticas, Consumo Masivo):** Rotulación vehicular en vinil cast con laminado UV.
     - **Franquicias, Restaurantes y Plazas Comerciales:** Fachadas en ACM, cajas de luz LED, menús iluminados y viniles de vitrina.
     - **Gerentes de RRHH y Mercadeo Corporativo:** Kits de bienvenida (artículos promocionales, termos láser) y uniformes bordados.
   - Ver plantillas listas para usar en: [secuencias_b2b_rd.md](./references/secuencias_b2b_rd.md)

3. **Embudo 3: Reactivación Estacional de Clientes Actuales**
   - **Enero – Febrero:** Renovación de uniformes bordados, agendas/termos corporativos y señalética interna.
   - **Mayo – Julio (Temporada Escolar / Verano):** Campaña para colegios, campamentos y remodelaciones de oficinas.
   - ** Septiembre – Noviembre (Pre-Black Friday y Fin de Año):** Fachadas luminosas, vitrinas navideñas, exhibidores POP y regalos corporativos de fin de año.

## 2. Conexión Gratuita del Sitio Web a Google Sheets + Auto-Respuesta por Email

El archivo `index.html` ya cuenta con la variable `window.LOSCRAFTERS_WEBHOOK_URL` y la función `sendCraftersLeadWebhook(payload)`.
Para activarlo 100% gratis usando tu cuenta de Google:
1. Abre un Google Sheet nuevo llamado **`CRM Leads — Los Crafters`**.
2. En el menú superior ve a **Extensiones > Apps Script**.
3. Pega el código completo de [google_apps_script_webhook.gs](./scripts/google_apps_script_webhook.gs).
4. Haz clic en **Implementar > Nueva implementación > Aplicación web** (Ejecutar como: *Yo*, Quién tiene acceso: *Cualquier persona*).
5. Copia la URL generada (`https://script.google.com/macros/s/.../exec`) y pégala en `window.LOSCRAFTERS_WEBHOOK_URL` dentro de `index.html`.

## 3. Reglas de Redacción de Correos de Los Crafters
- **Tono:** Ejecutivo, cercano, técnico y confiable. Hablar en el lenguaje corporativo dominicano (mencionar disponibilidad de facturación con **Comprobante Fiscal B01 / E-CF con RNC**, levantamiento técnico en Santo Domingo y garantía en materiales).
- **Llamado a la Acción (CTA):** Siempre ofrecer dos vías claras sin fricción:
  1. Responder al correo con el logo en curvas (`.ai` / `.pdf`) y medidas aproximadas (o foto de la pared/vehículo).
  2. Escribir directo al WhatsApp comercial: `https://wa.me/18294109362`

## 4. Programación Puntual Obligatoria (macOS `launchd`)
- **Prohibido usar temporizadores de chat (`schedule`) para envíos o monitoreos con hora pautada.** Los temporizadores internos del chat pueden retenerse si la cola de sesión queda en pausa.
- Toda campaña programada para una hora exacta debe registrarse obligatoriamente en el sistema operativo con [`crafters_scheduler.py`](/Users/wandermarte/Documents/REPOSITORIOS/loscrafters-webpage/.agents/skills/loscrafters-email-marketing/scripts/crafters_scheduler.py):
  ```bash
  /Library/Frameworks/Python.framework/Versions/3.14/bin/python3 \
    /Users/wandermarte/Documents/REPOSITORIOS/loscrafters-webpage/.agents/skills/loscrafters-email-marketing/scripts/crafters_scheduler.py \
    --schedule-campaign --datetime "YYYY-MM-DD HH:MM" --nicho <nicho> --csv <ruta.csv>
  ```
- Cada campaña crea un `LaunchAgent` one-shot en `~/Library/LaunchAgents/com.loscrafters.campaign.<id>.plist` con `StartCalendarInterval`, lock anti-doble-envío, espera de red al despertar el Mac, envío con `--notify` (resumen push por `ntfy`) y autolimpieza del `.plist` al terminar.
- El monitoreo CRM diurno (`08:00–23:30` cada 30 min, silencio total `00:00–07:59`) corre de forma nativa y persistente en `com.loscrafters.crm-monitor` (`--install-crm-monitor`).
- Usa `--list` para auditar campañas programadas y `--cancel <job_id>` para cancelar un envío pendiente.
- **Advertencia física de laptop:** Con el Mac encendido o despierto, `launchd` dispara al segundo `:00` exacto. Si la tapa de la MacBook estuvo cerrada en suspensión al momento pautado, macOS ejecutará automáticamente la campaña al instante de abrir/despertar el equipo tras reconectar el Wi-Fi.
