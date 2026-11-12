---
name: loscrafters-seo-growth
description: >-
  Especialista en SEO Local en República Dominicana, optimización de imágenes WebP para portafolio/hero,
  Google Business Profile, Google Search Ads y Meta Ads para Los Crafters SRL.
  Úsalo cuando el usuario quiera subir fotos nuevas optimizadas con SEO, mejorar el posicionamiento en Google,
  analizar tráfico o diseñar campañas de anuncios pagados u orgánicos.
---

# Los Crafters — SEO Local, Optimización WebP y Growth Marketing

Este skill guía al agente en la optimización técnica y de crecimiento orgánico/pagado para **Los Crafters SRL** (`https://www.loscrafters.net/`).

## 1. Flujo para Agregar Nuevas Fotos de Proyectos con SEO Perfecto

Cada vez que el usuario entregue nuevas fotos de trabajos realizados:
1. **Conversión y Compresión a `.webp`:**
   - Redimensionar a máximo `1920px` de ancho para slides del Hero o `1200px` para tarjetas del portafolio, con calidad `82-85%` en WebP.
   - Usar nombres de archivo descriptivos con palabras clave separadas por guiones (ej. `letrero-3d-acrilico-santo-domingo.webp` en lugar de `IMG_9999.webp`).
2. **Atributo `alt` con Intención Local:**
   - Nunca usar `alt="Letreros"` genérico.
   - Escribir `alt="[Tipo de trabajo + Material + Cliente/Sector + Santo Domingo RD]"` (ejemplo: `alt="Letrero Corpóreo 3D Iluminado en ACM y Acrílico en Santo Domingo"`).
3. **Actualización de `sitemap.xml`:**
   - Agregar las imágenes destacadas dentro del bloque `<url>` de `sitemap.xml` usando `<image:image>` para posicionar en **Google Imágenes** cuando alguien en RD busque ejemplos de letreros o rotulación.

## 2. Eventos de Conversión Configurados en Google Analytics 4 (`G-5ESKZGEV85`)

En `index.html`, la función `trackCraftersEvent(eventName, params)` envía automáticamente a GA4 los siguientes eventos clave:
- `generate_lead`: Cuando el usuario envía el formulario completo (`lead_type: 'formulario_contacto'`) o el modal rápido (`lead_type: 'modal_cotizacion_rapida'`), incluyendo `service_name` y `company_name`.
- `select_service_quote`: Cuando hace clic en "Cotizar servicio" dentro de cualquiera de las 8 tarjetas de `#servicios`.
- `whatsapp_click`: Cuando hace clic en el botón flotante de WhatsApp (`.wa-float`).
- `view_catalog`: Cuando abre el Catálogo PDF en Google Drive.
- `open_quote_modal`: Cuando abre el modal de cotización desde la barra de navegación.

**En el panel de Google Analytics 4:** Marca `generate_lead` y `whatsapp_click` como **Eventos Clave (Conversiones)** para medir el retorno de inversión (ROI) exacto de Google Search y Google Ads.

## 3. Estructura de Campañas de Alta Conversión en RD

### A. Google Search Ads (Búsqueda de Intención Inmediata)
- **Ubicación:** Santo Domingo, Distrito Nacional, Santiago, Punta Cana / Bávaro.
- **Grupos de Anuncios Recomendados:**
  1. **Letreros Corpóreos y Fachadas:** `[letreros en santo domingo]`, `[fabricacion de letreros luminosos rd]`, `[letras corporeas 3d santo domingo]`, `[fachadas en acm republica dominicana]`.
  2. **Rotulación Vehicular y Flotillas:** `[rotulacion vehicular santo domingo]`, `[rotulacion de camiones rd]`, `[branding vehicular empresas]`.
  3. **Rotulación de Oficinas y Cristales:** `[rotulacion en vinil santo domingo]`, `[vinil esmerilado para oficinas]`, `[murales corporativos en vinil]`.
- **Palabras Clave Negativas (Vital para no gastar presupuesto en vano):** `gratis`, `curso`, `como hacer`, `empleo`, `vacantes`, `descargar`, `plantillas`, `barato`.

### B. Meta Ads (Instagram / Facebook) — El Imán Visual B2B
- **Formato ganador:** Reels de 15 a 25 segundos mostrando **proceso en taller + instalación final** (fresado CNC/láser, soldadura de estructura, instalación con grúa/andamio y encendido nocturno del letrero LED).
- **Objetivo de Campaña:** Clientes potenciales (Mensajes a WhatsApp Business o Tráfico al formulario de `loscrafters.net/#contacto`).
