# Los Crafters SRL — Reglas del Proyecto y Contexto de Negocio

## 1. Identidad de la Empresa
- **Nombre Comercial:** Los Crafters SRL
- **Ubicación:** Santo Domingo, República Dominicana (cobertura en Distrito Nacional, Gran Santo Domingo, Santiago, Punta Cana y todo el país).
- **Sitio Web Oficial:** https://www.loscrafters.net/ (alojado en GitHub Pages desde la rama `main`).
- **Teléfono Oficina:** +1 (809) 568-6663
- **WhatsApp Comercial (Cotizaciones):** +1 (829) 410-9362
- **Correo Corporativo:** info@loscrafters.net
- **Catálogo Digital:** https://drive.google.com/file/d/1S1DoP-ZQEbCIRiCjIFdfrzE1bGpqKmhf/view?usp=sharing

## 2. Portafolio de 8 Especialidades (B2B y Comercial)
1. **Señalización Corporativa (`Señalización`):** Señalética arquitectónica, directorios de torres empresariales, clínicas, colegios, señalización vial e industrial (acrílico, PVC, ACM, vinil reflectivo).
2. **Branding Vehicular (`Branding Vehicular`):** Rotulación integral o parcial de flotillas comerciales, camiones, furgonetas y vehículos corporativos en vinil cast grado automotriz con laminado protector UV y microperforado.
3. **Letreros Corpóreos 3D (`Letreros`):** Letras volumétricas y emblemas en relieve 3D (acrílico, acero inoxidable, PVC expandido, aluminio, latón) con iluminación directa o retroiluminación LED cálida/fría.
4. **Rotulación & Murales (`Letreros`):** Murales decorativos e institucionales en vinil mate/brillante de gran formato, vinil esmerilado (sandblasting) en corte electrónico o impreso para oficinas y cristales comerciales.
5. **Exhibidores & Displays (`Exhibidores`):** Estructuras modulares, displays de piso y mostrador, góndolas brandeadas y material POP para supermercados, farmacias y tiendas retail.
6. **Fachadas & Cajas de Luz (`Fachadas`):** Revestimiento arquitectónico en panel de aluminio compuesto (ACM), cajas lumínicas tensadas en lona panaflex o acrílico con módulos LED de alto brillo e impermeabilidad IP67.
7. **Artículos Promocionales (`Artículos Promocionales`):** Merchandising corporativo, termos grabados a láser, bolígrafos metálicos, libretas, tazas, lanyards y kits de onboarding/eventos.
8. **Bordados & Uniformes (`Bordados`):** Bordado industrial computarizado de alta densidad y serigrafía/DTF textil en polos ejecutivos, camisas Columbia/Oxford, gorras y uniformes operativos.

## 3. Sistema de Diseño y Estética Web
- **Paleta Oficial:**
  - Navy / Fondo Principal: `#0A0F1A` y `#080E18`
  - Azul Marca (`--blue`): `#3265A6`
  - Azul Claro / Acento (`--blue-light`): `#5BA3F5`
  - Azul Pálido (`--blue-pale`): `#7EC8F7`
  - Azul Profundo (`--blue-deep`): `#1A3F6F`
  - Blanco Texto (`--white`): `#F0F6FF`
  - Gris Secundario (`--grey`): `#8BA4C2`
- **Tipografías:** `Montserrat` (700, 800, 900 uppercase para titulares y etiquetas) y `Open Sans` (400, 600 para cuerpos de texto).
- **Hero Slideshow (`#inicio`):**
  - El slideshow inicia directamente sin pantallas previas de texto.
  - Mantiene superposición de textura de ruido (`.hero-noise` al 28% con `mix-blend-mode: overlay`).
  - Los botones de cada slide siguen siempre el mismo orden: 1º `Ver catálogo` (`.btn-primary`) y 2º `Cotizar →` (`.btn-secondary`).
- **Sección Servicios (`#servicios`):**
  - Fondo vivo en `<canvas id="svcFluidCanvas">` a 60 FPS donde el nodo blanco sigue el cursor y deforma orgánicamente la malla de azules, cubierto por `.svc-noise-overlay` (30% ruido).

## 4. Directivas de Ejecución del Agente
- **Acción Directa (Cero Fricción):** Cuando el usuario solicite un cambio en la página web, ejecútalo, verifica la sintaxis HTML/JS y realiza `git commit` + `git push origin main` de inmediato sin pedir permiso previo.
- **Programación Puntual de Campañas (`launchd`):** Nunca uses temporizadores/crons de sesión (`schedule`) para programar envíos de correo o monitoreos CRM con hora fija. Usa siempre `.agents/skills/loscrafters-email-marketing/scripts/crafters_scheduler.py` (`--schedule-campaign` / `--install-crm-monitor`), que registra `LaunchAgents` nativos en macOS (`~/Library/LaunchAgents/`) con lock anti-duplicado, tolerancia a reconexión y notificación push (`--notify`).
- **Higiene de Git:** Al hacer `git add`, agrega únicamente los archivos correspondientes a la web (`index.html`, `sitemap.xml`, `robots.txt`, `GEMINI.md`, `.agents/`, `assets/`) y nunca subas archivos locales privados no relacionados (como bases de datos o reportes personales).
- **Skills Especializados Disponibles en `.agents/skills/`:**
  - `loscrafters-email-marketing`: Automatización de campañas de correo, prospección B2B en RD, seguimiento de cotizaciones y conexión de formularios con Google Sheets/Gmail.
  - `loscrafters-seo-growth`: Optimización de nuevas fotos a `.webp`, SEO local en Santo Domingo, Google Search Console, Google Ads y Meta Ads.
  - `loscrafters-cotizador-b2b`: Estructuración de cotizaciones formales con ITBIS (18%), especificaciones de materiales y mensajes de cierre por WhatsApp/Email.
