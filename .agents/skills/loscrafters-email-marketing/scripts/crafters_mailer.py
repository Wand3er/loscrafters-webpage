#!/usr/bin/env python3
"""
LOS CRAFTERS SRL — Motor Completo de Email Marketing B2B e Inbox CRM (SMTP + IMAP)
Incluye soporte para galería de imágenes reales incrustadas (CID Inline Images)
para que las fotos de proyectos en Punta Cana y Santo Domingo se vean al instante en cualquier correo.

Comandos disponibles:
  1. Enviar correo real de prueba a info@loscrafters.net con las fotos de Punta Cana:
     python3 .agents/skills/loscrafters-email-marketing/scripts/crafters_mailer.py --test --nicho residencial_punta_cana

  2. Enviar a un prospecto específico:
     python3 .agents/skills/loscrafters-email-marketing/scripts/crafters_mailer.py --send-one --to ventas@tralles.do --nombre "Equipo de Proyectos" --empresa "Tralles Developers Group" --zona "Punta Cana y Santo Domingo" --nicho residencial_punta_cana

  3. Enviar campaña a toda la lista CSV:
     python3 .agents/skills/loscrafters-email-marketing/scripts/crafters_mailer.py --send --csv .agents/skills/loscrafters-email-marketing/scripts/prospectos_b2b_rd.csv
"""

import argparse
import csv
import email
from email.header import decode_header
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import imaplib
import os
import smtplib
import ssl
import time
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[4]
ENV_PATH = ROOT_DIR / ".env"
IMAGES_DIR = ROOT_DIR / "assets" / "images"


def load_dotenv():
    if ENV_PATH.exists():
        for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def get_ssl_context():
    cafile = "/etc/ssl/cert.pem" if Path("/etc/ssl/cert.pem").exists() else None
    return ssl.create_default_context(cafile=cafile)


TEMPLATES = {
    "residencial_punta_cana": {
        "subject": "Señalización arquitectónica y numeración 3D para proyectos residenciales de {empresa}",
        "eyebrow": "ESPECIALISTAS EN PROYECTOS RESIDENCIALES · PUNTA CANA · SANTO DOMINGO · STO. DGO. ESTE",
        "headline": "Señalización que Eleva el Valor de Entrega de tus Viviendas y Edificios",
        "intro": (
            "Sabemos que en los desarrollos habitacionales de <strong>{empresa}</strong> en <strong>{zona}</strong>, "
            "los detalles de terminación marcan la diferencia en la entrega final a cada propietario e inversionista.<br><br>"
            "En <strong>Los Crafters SRL</strong> fabricamos e instalamos <strong>sistemas completos de señalización arquitectónica "
            "y numeración en relieve 3D</strong> para complejos de villas, torres de apartamentos y residenciales cerrados en "
            "<strong>Punta Cana, Bávaro, Vista Cana, Santo Domingo (DN) y Santo Domingo Este</strong>."
        ),
        "show_punta_cana_gallery": True,
        "bullets": [
            "<strong>Numeración de Villas y Apartamentos en Relieve 3D:</strong> Placas arquitectónicas en aluminio cepillado, ACM y acrílico de alto brillo cortado a láser, diseñadas para resistir el salitre, la humedad y el sol intenso de Punta Cana sin oxidarse ni decolorarse.",
            "<strong>Señalética Integral de Edificios y Áreas Comunes:</strong> Identificación de bloques/torres, niveles, numeración de parqueos, áreas de piscina/gazebo, directorios de lobby y señalización vial interna.",
            "<strong>Letreros Corpóreos de Entrada Principal y Casetas:</strong> Logotipos volumétricos 3D con o sin iluminación LED IP67 para la fachada del proyecto y oficinas de venta.",
            "<strong>Producción en Serie + Instalación en Obra:</strong> Capacidad de taller propio para entregar lotes de 20, 50, 100 o +300 unidades a tiempo para tus fechas de entrega, con facturación NCF / E-CF."
        ],
        "cta_note": (
            "¿Tienen actualmente en <strong>{empresa}</strong> algún proyecto de villas o edificios en etapa de terminación en "
            "<strong>Punta Cana, Santo Domingo o Santo Domingo Este</strong>? Respóndenos con la cantidad aproximada de unidades "
            "o el plano de señalética y te preparamos una cotización formal comparativa más una muestra física del acabado."
        )
    },
    "constructora": {
        "subject": "Señalética arquitectónica y letreros 3D para proyectos de {empresa}",
        "eyebrow": "LOS CRAFTERS SRL · DIVISIÓN CONSTRUCCIÓN E INMOBILIARIA",
        "headline": "Señalización de Obra y Letreros Corpóreos 3D",
        "intro": (
            "Vi los desarrollos recientes de <strong>{empresa}</strong> y quise contactarte directamente "
            "porque en <strong>Los Crafters SRL</strong> apoyamos a constructoras e ingenierías en República Dominicana "
            "(como <em>Elenma Construcciones</em>) desde el cierre perimetral hasta la entrega de la torre o plaza."
        ),
        "show_punta_cana_gallery": True,
        "bullets": [
            "<strong>Etapa de Obra:</strong> Vallas perimetrales en gran formato, señalización de seguridad industrial y rotulación de maquinaria/flotillas.",
            "<strong>Etapa de Entrega y Lobby:</strong> Letras corpóreas 3D en acero inoxidable, acrílico y aluminio con iluminación LED cálida/fría.",
            "<strong>Señalética Arquitectónica:</strong> Numeración de niveles/apartamentos, directorios de lobby y señalización vial de parqueos."
        ],
        "cta_note": "¿Tienen algún proyecto próximo en etapa de terminación donde podamos cotizarles una partida comparativa con Comprobante Fiscal?"
    },
    "colegio": {
        "subject": "Renovación visual, murales y letras corpóreas 3D para {empresa}",
        "eyebrow": "LOS CRAFTERS SRL · INSTITUCIONES EDUCATIVAS",
        "headline": "Espacios Educativos que Inspiran y Comunican",
        "intro": (
            "Recientemente fabricamos e instalamos los emblemas corpóreos 3D y murales interiores para "
            "instituciones educativas en Santo Domingo (como <em>AF School</em>, que puedes ver en la portada de nuestra web)."
        ),
        "show_punta_cana_gallery": False,
        "bullets": [
            "<strong>Escudos y Letras Corpóreas 3D:</strong> Máxima durabilidad para fachadas, recepciones y salones de actos.",
            "<strong>Rotulación Mural en Vinil Mate:</strong> Ambientación educativa e institucional de gran formato para aulas, pasillos y bibliotecas.",
            "<strong>Señalización de Plantel:</strong> Identificación de aulas, laboratorios, áreas deportivas y rutas de evacuación."
        ],
        "cta_note": "Si planean renovar áreas del centro educativo, podemos coordinar una visita técnica de levantamiento en Santo Domingo sin costo."
    },
    "flotilla": {
        "subject": "Rotulación vehicular de alta durabilidad para la flota de {empresa}",
        "eyebrow": "LOS CRAFTERS SRL · BRANDING VEHICULAR",
        "headline": "Convierte tu Flotilla en Publicidad en Movimiento",
        "intro": (
            "Cada vehículo comercial de <strong>{empresa}</strong> recorre miles de kilómetros al mes en la ciudad. "
            "Bien rotulado, es una valla publicitaria móvil trabajando las 24 horas sin pagar renta mensual."
        ),
        "show_punta_cana_gallery": False,
        "bullets": [
            "<strong>Vinil Grado Automotriz + Laminado UV:</strong> Máxima resistencia al sol del Caribe y al lavado frecuente sin decolorarse ni levantarse.",
            "<strong>Camiones, Furgonetas y Flotas Ligeras:</strong> Rotulación integral (wrapping), parcial o microperforado homologado.",
            "<strong>Instalación Programada:</strong> Trabajamos por turnos o fines de semana para no detener la operación de tus rutas."
        ],
        "cta_note": "¿Cuántas unidades manejan actualmente en {empresa}? Respóndenos con el modelo o una foto y te preparamos una propuesta formal hoy mismo."
    },
    "seguimiento": {
        "subject": "Seguimiento a tu solicitud de cotización — {empresa} | Los Crafters SRL",
        "eyebrow": "LOS CRAFTERS SRL · SEGUIMIENTO DE PROYECTOS",
        "headline": "Propuesta Técnica y Disponibilidad de Taller",
        "intro": (
            "Te escribo brevemente para confirmar que hayas recibido nuestra información sobre el proyecto de "
            "<strong>{servicio}</strong> para <strong>{empresa}</strong>."
        ),
        "show_punta_cana_gallery": True,
        "bullets": [
            "<strong>Taller Propio en Santo Domingo con Cobertura en Punta Cana:</strong> Control total de calidad en corte láser/CNC, estructura metálica, pintura e impresión.",
            "<strong>Materiales Certificados:</strong> ACM de 4mm, acrílico importado, vinil cast automotriz y módulos LED IP67 a prueba de agua.",
            "<strong>Facturación Corporativa:</strong> Emisión de Comprobante Fiscal (B01 / E-CF) y garantía escrita de instalación."
        ],
        "cta_note": "Actualmente contamos con espacio en nuestra agenda de producción de esta semana. ¿Deseas que ajustemos alguna medida o coordinemos el levantamiento técnico?"
    }
}


def build_html_email(
    nombre: str,
    empresa: str,
    nicho: str,
    servicio: str = "Señalización Residencial y Corporativa",
    zona: str = "Punta Cana y Santo Domingo",
    use_cid: bool = True
) -> tuple[str, str]:
    tpl = TEMPLATES.get(nicho, TEMPLATES["residencial_punta_cana"])
    subject = tpl["subject"].format(nombre=nombre, empresa=empresa, servicio=servicio, zona=zona)
    intro_html = tpl["intro"].format(nombre=nombre, empresa=empresa, servicio=servicio, zona=zona)
    cta_note = tpl["cta_note"].format(nombre=nombre, empresa=empresa, servicio=servicio, zona=zona)
    bullets_html = "".join(f'<li style="margin-bottom: 12px;">{b}</li>' for b in tpl["bullets"])

    if use_cid:
        img_pc2 = "cid:pc_detalle"
        img_pc1 = "cid:pc_instalacion"
        img_elenma = "cid:elenma_obra"
    else:
        img_pc2 = "https://www.loscrafters.net/assets/images/senalizacion-residencial-punta-cana-2.jpg"
        img_pc1 = "https://www.loscrafters.net/assets/images/senalizacion-residencial-punta-cana-1.jpg"
        img_elenma = "https://www.loscrafters.net/assets/images/letrero-elenma-construcciones.jpg"

    gallery_html = ""
    if tpl.get("show_punta_cana_gallery", True):
        gallery_html = f"""
              <!-- Galería de Trabajos Reales en Punta Cana y Santo Domingo -->
              <div style="margin:26px 0;background-color:#101929;border:1px solid #1C2E47;border-radius:8px;padding:18px;">
                <div style="font-size:11px;font-weight:800;letter-spacing:1.5px;color:#5BA3F5;text-transform:uppercase;margin-bottom:6px;">
                  📍 CASO REAL RECIENTE · PROYECTO RESIDENCIAL EN PUNTA CANA
                </div>
                <div style="font-size:13px;color:#8BA4C2;margin-bottom:14px;">
                  Numeración volumétrica en relieve 3D (acrílico negro de alto brillo sobre placa arquitectónica en aluminio cepillado resistente a intemperie y salitre):
                </div>
                <table role="presentation" width="100%" cellspacing="0" cellpadding="0">
                  <tr>
                    <td width="49%" valign="top" style="padding-right:6px;">
                      <a href="https://www.loscrafters.net/#portafolio" target="_blank" style="text-decoration:none;">
                        <img src="{img_pc2}" alt="Detalle Señalización Residencial 3D en Punta Cana" width="245" style="width:100%;max-width:245px;height:auto;border-radius:6px;border:1px solid #3265A6;display:block;">
                      </a>
                      <div style="font-size:11px;color:#8BA4C2;margin-top:6px;text-align:center;">Acabado en relieve 3D de alta precisión</div>
                    </td>
                    <td width="49%" valign="top" style="padding-left:6px;">
                      <a href="https://www.loscrafters.net/#portafolio" target="_blank" style="text-decoration:none;">
                        <img src="{img_pc1}" alt="Instalación en Villa Residencial Punta Cana" width="245" style="width:100%;max-width:245px;height:auto;border-radius:6px;border:1px solid #3265A6;display:block;">
                      </a>
                      <div style="font-size:11px;color:#8BA4C2;margin-top:6px;text-align:center;">Instalación limpia en fachada residencial</div>
                    </td>
                  </tr>
                </table>
                <div style="margin-top:14px;padding-top:14px;border-top:1px solid #1C2E47;">
                  <div style="font-size:11px;font-weight:800;letter-spacing:1.5px;color:#5BA3F5;text-transform:uppercase;margin-bottom:8px;">
                    🏢 IDENTIDAD DE FACHADA Y CORPORATIVA PARA CONSTRUCTORAS
                  </div>
                  <a href="https://www.loscrafters.net/#portafolio" target="_blank" style="text-decoration:none;">
                    <img src="{img_elenma}" alt="Letrero Corpóreo 3D y Rotulación para Constructora" width="500" style="width:100%;max-width:500px;height:auto;border-radius:6px;border:1px solid #1C2E47;display:block;">
                  </a>
                </div>
              </div>
        """

    html = f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<title>{subject}</title>
</head>
<body style="margin:0;padding:0;background-color:#080E18;font-family:'Segoe UI',Arial,sans-serif;">
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background-color:#080E18;padding:28px 12px;">
    <tr>
      <td align="center">
        <table role="presentation" width="600" cellspacing="0" cellpadding="0" style="max-width:600px;width:100%;background-color:#0A0F1A;border:1px solid #1C2E47;border-radius:10px;overflow:hidden;">
          <!-- Header -->
          <tr>
            <td style="padding:28px 32px;background:linear-gradient(135deg,#0A0F1A 0%,#1A3F6F 100%);border-bottom:3px solid #3265A6;">
              <div style="font-size:11px;font-weight:800;letter-spacing:1.6px;color:#5BA3F5;text-transform:uppercase;">{tpl["eyebrow"]}</div>
              <h1 style="margin:8px 0 0;font-size:21px;line-height:1.3;color:#F0F6FF;font-weight:800;">{tpl["headline"]}</h1>
            </td>
          </tr>
          <!-- Body -->
          <tr>
            <td style="padding:30px 32px;color:#F0F6FF;font-size:15px;line-height:1.7;">
              <p style="margin-top:0;">Hola <strong>{nombre}</strong>, un gusto saludarte.</p>
              <p>{intro_html}</p>
              {gallery_html}
              <div style="background-color:#101929;border-left:3px solid #5BA3F5;padding:18px 20px;margin:22px 0;border-radius:4px;">
                <div style="font-size:12px;font-weight:800;color:#5BA3F5;text-transform:uppercase;letter-spacing:1px;margin-bottom:10px;">
                  ¿Qué fabricamos e instalamos para tus proyectos?
                </div>
                <ul style="margin:0;padding-left:18px;color:#dbeafe;font-size:14px;">
                  {bullets_html}
                </ul>
              </div>
              <p>{cta_note}</p>
              <!-- CTA Buttons -->
              <table role="presentation" cellspacing="0" cellpadding="0" style="margin:26px 0 10px;">
                <tr>
                  <td style="border-radius:4px;background-color:#25D366;">
                    <a href="https://wa.me/18294109362?text=Hola%20Los%20Crafters,%20vi%20su%20correo%20sobre%20se%C3%B1alizaci%C3%B3n%20de%20proyectos%20residenciales%20y%20me%20gustar%C3%ADa%20cotizar." target="_blank" style="display:inline-block;padding:13px 20px;color:#050505;text-decoration:none;font-weight:bold;font-size:13px;text-transform:uppercase;letter-spacing:0.8px;">Cotizar Proyecto por WhatsApp →</a>
                  </td>
                  <td width="12"></td>
                  <td style="border-radius:4px;background-color:#3265A6;">
                    <a href="https://drive.google.com/file/d/1S1DoP-ZQEbCIRiCjIFdfrzE1bGpqKmhf/view?usp=sharing" target="_blank" style="display:inline-block;padding:13px 20px;color:#F0F6FF;text-decoration:none;font-weight:bold;font-size:13px;text-transform:uppercase;letter-spacing:0.8px;">Ver Catálogo PDF</a>
                  </td>
                </tr>
              </table>
            </td>
          </tr>
          <!-- Footer -->
          <tr>
            <td style="padding:20px 32px;background-color:#080E18;border-top:1px solid #1C2E47;color:#8BA4C2;font-size:12px;line-height:1.6;">
              <strong>Los Crafters SRL</strong> · Señalización Arquitectónica, Letreros 3D y Rotulación en RD<br>
              📍 Cobertura activa: <strong>Punta Cana / Bávaro · Santo Domingo (DN) · Santo Domingo Este</strong><br>
              📞 Oficina: +1 (809) 568-6663 · 💬 WhatsApp Comercial: +1 (829) 410-9362<br>
              🌐 <a href="https://www.loscrafters.net" style="color:#5BA3F5;text-decoration:none;">www.loscrafters.net</a> · ✉️ <a href="mailto:info@loscrafters.net" style="color:#5BA3F5;text-decoration:none;">info@loscrafters.net</a>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""
    return subject, html


def attach_inline_images(msg_root: MIMEMultipart):
    inline_map = {
        "pc_detalle": IMAGES_DIR / "email-punta-cana-2.jpg",
        "pc_instalacion": IMAGES_DIR / "email-punta-cana-1.jpg",
        "elenma_obra": IMAGES_DIR / "email-elenma-construcciones.jpg",
    }
    for cid, img_path in inline_map.items():
        if img_path.exists():
            img_part = MIMEImage(img_path.read_bytes(), _subtype="jpeg")
            img_part.add_header("Content-ID", f"<{cid}>")
            img_part.add_header("Content-Disposition", "inline", filename=img_path.name)
            msg_root.attach(img_part)


def create_mime_message(smtp_user: str, to_email: str, subject: str, html: str, include_images: bool = True) -> MIMEMultipart:
    msg_root = MIMEMultipart("related")
    msg_root["Subject"] = subject
    msg_root["From"] = f"Los Crafters SRL <{smtp_user}>"
    msg_root["To"] = to_email
    msg_root["Reply-To"] = smtp_user

    msg_alt = MIMEMultipart("alternative")
    msg_root.attach(msg_alt)
    msg_alt.attach(MIMEText(html, "html", "utf-8"))

    if include_images:
        attach_inline_images(msg_root)

    return msg_root


def send_single_email(smtp_host, smtp_port, smtp_user, smtp_pass, to_email, subject, html, include_images=True):
    context = get_ssl_context()
    msg_root = create_mime_message(smtp_user, to_email, subject, html, include_images=include_images)

    with smtplib.SMTP_SSL(smtp_host, smtp_port, context=context) as server:
        server.login(smtp_user, smtp_pass)
        server.sendmail(smtp_user, to_email, msg_root.as_string())


def decode_mime_words(s):
    if not s:
        return ""
    decoded = decode_header(s)
    parts = []
    for content, charset in decoded:
        if isinstance(content, bytes):
            parts.append(content.decode(charset or "utf-8", errors="replace"))
        else:
            parts.append(str(content))
    return "".join(parts)


def check_inbox(imap_host, smtp_user, smtp_pass, limit=10):
    mail = imaplib.IMAP4_SSL(imap_host, ssl_context=get_ssl_context())
    mail.login(smtp_user, smtp_pass)
    mail.select("INBOX")
    status, messages = mail.search(None, "ALL")
    if status != "OK" or not messages[0]:
        print("Bandeja de entrada vacía.")
        return
    ids = messages[0].split()
    recent_ids = ids[-limit:][::-1]
    print(f"📬 Últimos {len(recent_ids)} correos en {smtp_user}:\n" + "-" * 70)
    for num in recent_ids:
        res, msg_data = mail.fetch(num, "(RFC822.HEADER)")
        for response_part in msg_data:
            if isinstance(response_part, tuple):
                msg = email.message_from_bytes(response_part[1])
                subj = decode_mime_words(msg.get("Subject", "(Sin asunto)"))
                sender = decode_mime_words(msg.get("From", ""))
                date = msg.get("Date", "")
                print(f"• De: {sender}\n  Asunto: {subj}\n  Fecha: {date}\n")
    mail.logout()


def main():
    load_dotenv()
    parser = argparse.ArgumentParser(description="Motor de Email Marketing B2B e Inbox — Los Crafters SRL")
    parser.add_argument("--preview", action="store_true", help="Genera archivo HTML de vista previa sin enviar correo")
    parser.add_argument("--test", action="store_true", help="Envía un correo real de prueba a info@loscrafters.net")
    parser.add_argument("--send-one", action="store_true", help="Envía un correo individual personalizado")
    parser.add_argument("--send", action="store_true", help="Envía los correos de la lista CSV por SMTP")
    parser.add_argument("--inbox", action="store_true", help="Lista los últimos correos recibidos en info@loscrafters.net")
    parser.add_argument("--limit", type=int, default=8, help="Cantidad de correos a mostrar con --inbox")
    parser.add_argument("--to", default="", help="Correo destino para --send-one o --test")
    parser.add_argument("--nombre", default="Equipo de Ingeniería y Proyectos", help="Nombre del contacto")
    parser.add_argument("--empresa", default="Constructora & Desarrolladora", help="Nombre de la empresa")
    parser.add_argument("--zona", default="Punta Cana, Santo Domingo y Sto. Dgo. Este", help="Zona de operación")
    parser.add_argument("--servicio", default="Señalización Arquitectónica y Numeración 3D", help="Servicio")
    parser.add_argument("--nicho", default="residencial_punta_cana", choices=list(TEMPLATES.keys()), help="Plantilla de nicho a usar")
    parser.add_argument("--csv", default=str(ROOT_DIR / ".agents/skills/loscrafters-email-marketing/scripts/prospectos_b2b_rd.csv"), help="Ruta al archivo CSV de prospectos")
    args = parser.parse_args()

    smtp_host = os.environ.get("CRAFTERS_SMTP_HOST", "smtp.gmail.com")
    smtp_port = int(os.environ.get("CRAFTERS_SMTP_PORT", "465"))
    imap_host = os.environ.get("CRAFTERS_IMAP_HOST", "imap.gmail.com")
    smtp_user = os.environ.get("CRAFTERS_SMTP_USER", "info@loscrafters.net")
    smtp_pass = os.environ.get("CRAFTERS_SMTP_PASS", "").replace(" ", "")

    if args.inbox:
        check_inbox(imap_host, smtp_user, smtp_pass, args.limit)
        return

    tpl_info = TEMPLATES.get(args.nicho, TEMPLATES["residencial_punta_cana"])
    inc_imgs = bool(tpl_info.get("show_punta_cana_gallery", True))

    if args.test:
        target = args.to or smtp_user
        subject, html = build_html_email(args.nombre, args.empresa, args.nicho, args.servicio, args.zona, use_cid=True)
        send_single_email(smtp_host, smtp_port, smtp_user, smtp_pass, target, f"[VISTA PREVIA CAMPAÑA PUNTA CANA] {subject}", html, include_images=inc_imgs)
        print(f"✅ Correo de prueba con fotos incrustadas enviado exitosamente a {target}!")
        print(f"   Asunto: [VISTA PREVIA CAMPAÑA PUNTA CANA] {subject}")
        return

    if args.send_one:
        if not args.to:
            print("❌ Debes indicar --to correo@destino.com")
            return
        subject, html = build_html_email(args.nombre, args.empresa, args.nicho, args.servicio, args.zona, use_cid=True)
        send_single_email(smtp_host, smtp_port, smtp_user, smtp_pass, args.to, subject, html, include_images=inc_imgs)
        print(f"✅ Correo enviado exitosamente a {args.nombre} ({args.empresa}) <{args.to}>!")
        return

    if args.preview or not args.send:
        subject, html = build_html_email(args.nombre, args.empresa, args.nicho, args.servicio, args.zona, use_cid=False)
        out_path = Path(f"/tmp/preview_email_{args.nicho}.html")
        out_path.write_text(html, encoding="utf-8")
        print(f"✅ Vista previa generada con éxito:")
        print(f"   Asunto: {subject}")
        print(f"   Archivo: {out_path}")
        return

    csv_path = Path(args.csv)
    if not csv_path.exists():
        print(f"❌ No se encontró el archivo CSV: {csv_path}")
        return

    context = get_ssl_context()
    with smtplib.SMTP_SSL(smtp_host, smtp_port, context=context) as server:
        server.login(smtp_user, smtp_pass)
        with open(csv_path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                email_to = row.get("correo", "").strip()
                if not email_to or "@" not in email_to or "ejemplo-" in email_to:
                    continue
                nombre = row.get("nombre", "Equipo de Ingeniería y Proyectos").strip()
                empresa = row.get("empresa", "su empresa").strip()
                nicho = row.get("nicho", args.nicho).strip()
                servicio = row.get("servicio", "Señalización Residencial y Letreros 3D").strip()
                zona = row.get("zona", "Punta Cana y Santo Domingo").strip()

                tpl_row = TEMPLATES.get(nicho, TEMPLATES["residencial_punta_cana"])
                row_imgs = bool(tpl_row.get("show_punta_cana_gallery", True))
                subject, html = build_html_email(nombre, empresa, nicho, servicio, zona, use_cid=True)
                msg_root = create_mime_message(smtp_user, email_to, subject, html, include_images=row_imgs)

                server.sendmail(smtp_user, email_to, msg_root.as_string())
                print(f"📨 Enviado a {nombre} ({empresa} - {zona}) <{email_to}> [{nicho}]")
                time.sleep(4)


if __name__ == "__main__":
    main()
