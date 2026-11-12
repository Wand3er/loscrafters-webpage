#!/usr/bin/env python3
"""
LOS CRAFTERS SRL — Motor de Email Marketing B2B, Tracking de Clics e Inbox CRM (SMTP + IMAP)

Capacidades incluidas:
  1. Envío de campaña personalizada con galería visual (CID Inline Images).
  2. Tracking de Clics por Empresa (?utm_source=email_b2b&empresa=...) conectado a GA4 y alertas en vivo.
  3. Botón de WhatsApp pre-identificado con el nombre de la constructora.
  4. Registro automático de envíos en `campana_log.csv`.
  5. Monitoreo CRM (`--crm`) por IMAP para detectar:
     - Quién respondió de la lista de prospectos.
     - Si algún correo rebotó (Mailer-Daemon / Delivery Status).
     - Auto-respuesta humana inmediata (`--crm --auto-reply`) cuando un prospecto contesta.

Comandos principales:
  • Probar correo en info@loscrafters.net:
    python3 .agents/skills/loscrafters-email-marketing/scripts/crafters_mailer.py --test --nicho residencial_punta_cana
  • Enviar campaña completa a las 18 constructoras:
    python3 .agents/skills/loscrafters-email-marketing/scripts/crafters_mailer.py --send
  • Auditar respuestas, rebotes y activar auto-respuesta a interesados:
    python3 .agents/skills/loscrafters-email-marketing/scripts/crafters_mailer.py --crm --auto-reply
"""

import argparse
import csv
from datetime import datetime
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
import urllib.parse
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[4]
ENV_PATH = ROOT_DIR / ".env"
IMAGES_DIR = ROOT_DIR / "assets" / "images"
SCRIPTS_DIR = Path(__file__).resolve().parent
LOG_CSV_PATH = SCRIPTS_DIR / "campana_log.csv"
AUTO_REPLY_LOG = SCRIPTS_DIR / "auto_replies_sent.txt"


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
        "subject": "Señalización para los proyectos de {empresa}",
        "eyebrow": "LOS CRAFTERS",
        "headline": "Señalización a la altura de tus desarrollos.",
        "intro": (
            "En <strong>Los Crafters</strong> acompañamos a constructoras y desarrolladores a vestir sus edificios "
            "y residenciales con señalización moderna, limpia y hecha para durar."
        ),
        "show_gallery": True,
        "bullets": [
            "<strong>Numeración 3D en relieve:</strong> Acabados limpios y resistentes al sol, humedad y salitre.",
            "<strong>Señalética de edificios y áreas comunes:</strong> Niveles, parqueos, lobbies, calles e indicadores.",
            "<strong>Producción e instalación a tiempo:</strong> Taller propio para fabricar en serie y cumplir con tu fecha de entrega."
        ],
        "cta_note": (
            "¿Tienen algún proyecto próximo a entrar en etapa de terminación? "
            "Escríbenos por aquí o por WhatsApp y con gusto les preparamos una propuesta o muestra física."
        )
    },
    "constructora": {
        "subject": "Señalización y letreros para proyectos de {empresa}",
        "eyebrow": "LOS CRAFTERS",
        "headline": "Señalización a la altura de tus desarrollos.",
        "intro": (
            "En <strong>Los Crafters</strong> apoyamos a constructoras e ingenierías desde la señalización de obra "
            "hasta los detalles finales de entrega de cada edificio."
        ),
        "show_gallery": True,
        "bullets": [
            "<strong>Numeración y directorios:</strong> Placas en relieve 3D para apartamentos, villas, pisos y parqueos.",
            "<strong>Identidad de fachada:</strong> Letras corpóreas 3D en acrílico, ACM y acero con o sin luz LED.",
            "<strong>Fabricación + instalación:</strong> Entrega puntual en obra con facturación con Comprobante Fiscal."
        ],
        "cta_note": (
            "¿Tienen algún proyecto en etapa de terminación donde podamos cotizarles? "
            "Respóndenos este correo o escríbenos directo por WhatsApp."
        )
    },
    "colegio": {
        "subject": "Señalización y letras 3D para {empresa}",
        "eyebrow": "LOS CRAFTERS",
        "headline": "Espacios que inspiran desde la entrada.",
        "intro": (
            "Ayudamos a instituciones educativas a renovar su imagen con letreros corpóreos 3D, "
            "murales e identificación limpia para cada área del plantel."
        ),
        "show_gallery": False,
        "bullets": [
            "<strong>Escudos y letras 3D:</strong> Para fachadas, recepciones y auditorios.",
            "<strong>Murales decorativos:</strong> Vinil de alta durabilidad para aulas y pasillos.",
            "<strong>Señalización interna:</strong> Identificación de cursos, laboratorios y rutas."
        ],
        "cta_note": "Si planean renovar algún área del plantel, escríbenos para coordinar un levantamiento sin costo."
    },
    "flotilla": {
        "subject": "Rotulación vehicular para la flota de {empresa}",
        "eyebrow": "LOS CRAFTERS",
        "headline": "Tu marca en movimiento todos los días.",
        "intro": (
            "Convertimos los vehículos comerciales de <strong>{empresa}</strong> en publicidad activa "
            "con materiales que no se levantan ni pierden color con el sol."
        ),
        "show_gallery": False,
        "bullets": [
            "<strong>Vinil automotriz con protección UV:</strong> Larga vida útil y acabado impecable.",
            "<strong>Camiones, furgonetas y flotas:</strong> Rotulación completa, parcial o microperforado.",
            "<strong>Instalación ágil:</strong> Nos adaptamos a tu horario para no frenar tus rutas."
        ],
        "cta_note": "¿Cuántas unidades manejan actualmente? Respóndenos y te cotizamos hoy mismo."
    },
    "seguimiento": {
        "subject": "Re: Señalización para los proyectos de {empresa}",
        "eyebrow": "LOS CRAFTERS",
        "headline": "Seguimiento rápido a tus próximos proyectos.",
        "intro": (
            "Te escribo brevemente para confirmar que hayas podido ver nuestro correo anterior sobre "
            "señalización y letreros 3D para los desarrollos de <strong>{empresa}</strong>."
        ),
        "show_gallery": True,
        "bullets": [
            "<strong>Muestras físicas sin compromiso:</strong> Podemos llevarles muestras de nuestros acabados en relieve 3D a su oficina.",
            "<strong>Cotización sobre planos:</strong> Cotizamos partidas completas de señalética residencial y letreros de entrada.",
            "<strong>Facturación formal:</strong> Comprobante Fiscal (B01 / E-CF) y garantía de instalación."
        ],
        "cta_note": "¿Tienen algún edificio o residencial próximo a entrega donde podamos presentarles propuesta?"
    }
}


def build_html_email(
    nombre: str,
    empresa: str,
    nicho: str,
    servicio: str = "Señalización de Proyectos",
    zona: str = "",
    use_cid: bool = True
) -> tuple[str, str]:
    tpl = TEMPLATES.get(nicho, TEMPLATES["residencial_punta_cana"])
    subject = tpl["subject"].format(nombre=nombre, empresa=empresa, servicio=servicio)
    intro_html = tpl["intro"].format(nombre=nombre, empresa=empresa, servicio=servicio)
    cta_note = tpl["cta_note"].format(nombre=nombre, empresa=empresa, servicio=servicio)
    bullets_html = "".join(f'<li style="margin-bottom: 8px;">{b}</li>' for b in tpl["bullets"])

    empresa_param = urllib.parse.quote_plus(empresa)
    tracked_portfolio_url = f"https://www.loscrafters.net/?utm_source=email_b2b&utm_medium=email&utm_campaign={nicho}&empresa={empresa_param}#portafolio"
    tracked_home_url = f"https://www.loscrafters.net/?utm_source=email_b2b&utm_medium=email&utm_campaign={nicho}&empresa={empresa_param}"
    wa_text = urllib.parse.quote(f"Hola Los Crafters, les escribo de {empresa}. Vi su correo sobre señalización de proyectos y me gustaría cotizar.")
    wa_url = f"https://wa.me/18095686663?text={wa_text}"

    if use_cid:
        img_sundistrict = "cid:sun_district"
        img_closeup = "cid:pc_detalle"
        img_basalto = "cid:via_basalto"
    else:
        img_sundistrict = "https://www.loscrafters.net/assets/images/email-sun-district.jpg"
        img_closeup = "https://www.loscrafters.net/assets/images/email-punta-cana-2.jpg"
        img_basalto = "https://www.loscrafters.net/assets/images/email-via-basalto.jpg"

    gallery_html = ""
    if tpl.get("show_gallery", True):
        gallery_html = f"""
              <!-- Galería de Trabajos Reales -->
              <div style="margin:20px 0;background-color:#101929;border:1px solid #1C2E47;border-radius:8px;padding:16px;">
                <div style="font-size:11px;font-weight:800;letter-spacing:1.4px;color:#5BA3F5;text-transform:uppercase;margin-bottom:10px;">
                  PROYECTOS Y SEÑALIZACIÓN REALIZADOS
                </div>
                <!-- Imagen Principal: Entrada Sun District -->
                <div style="margin-bottom:12px;">
                  <a href="{tracked_portfolio_url}" target="_blank" style="text-decoration:none;">
                    <img src="{img_sundistrict}" alt="Letrero Monumental 3D en Entrada de Proyecto Residencial Sun District" width="502" style="width:100%;max-width:502px;height:auto;border-radius:6px;border:1px solid #3265A6;display:block;">
                  </a>
                  <div style="font-size:12px;color:#8BA4C2;margin-top:6px;">Identidad y letrero corpóreo 3D para entrada principal de proyecto residencial</div>
                </div>
                <!-- 2 imágenes en simetría: Close-up 108 + Señalización Vial -->
                <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="margin-top:10px;">
                  <tr>
                    <td width="49%" valign="top" style="padding-right:5px;">
                      <a href="{tracked_portfolio_url}" target="_blank" style="text-decoration:none;">
                        <img src="{img_closeup}" alt="Detalle de Numeración 3D en Relieve" width="246" style="width:100%;max-width:246px;height:auto;border-radius:6px;border:1px solid #1C2E47;display:block;">
                      </a>
                      <div style="font-size:11px;color:#8BA4C2;margin-top:5px;">Numeración 3D en relieve (acrílico y aluminio)</div>
                    </td>
                    <td width="49%" valign="top" style="padding-left:5px;">
                      <a href="{tracked_portfolio_url}" target="_blank" style="text-decoration:none;">
                        <img src="{img_basalto}" alt="Señalización Vial y de Proyectos" width="246" style="width:100%;max-width:246px;height:auto;border-radius:6px;border:1px solid #1C2E47;display:block;">
                      </a>
                      <div style="font-size:11px;color:#8BA4C2;margin-top:5px;">Señalización vial e interna de proyectos</div>
                    </td>
                  </tr>
                </table>
              </div>
        """

    html = f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<title>{subject}</title>
</head>
<body style="margin:0;padding:0;font-family:'Segoe UI',Arial,sans-serif;">
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="padding:16px 8px;">
    <tr>
      <td align="center">
        <table role="presentation" width="600" cellspacing="0" cellpadding="0" style="max-width:600px;width:100%;background-color:#0A0F1A;border:1px solid #1C2E47;border-radius:10px;overflow:hidden;">
          <!-- Header -->
          <tr>
            <td style="padding:24px 30px;background:linear-gradient(135deg,#0A0F1A 0%,#1A3F6F 100%);border-bottom:2px solid #3265A6;">
              <div style="font-size:11px;font-weight:800;letter-spacing:1.8px;color:#5BA3F5;text-transform:uppercase;">{tpl["eyebrow"]}</div>
              <h1 style="margin:6px 0 0;font-size:21px;line-height:1.3;color:#F0F6FF;font-weight:800;">{tpl["headline"]}</h1>
            </td>
          </tr>
          <!-- Body -->
          <tr>
            <td style="padding:24px 30px;color:#F0F6FF;font-size:15px;line-height:1.6;">
              <p style="margin:0 0 10px;">Hola <strong>{nombre}</strong>, ¿qué tal?</p>
              <p style="margin:0 0 16px;color:#dbeafe;">{intro_html}</p>
              {gallery_html}
              <div style="background-color:#101929;border-left:3px solid #5BA3F5;padding:14px 18px;margin:18px 0;border-radius:4px;">
                <ul style="margin:0;padding-left:18px;color:#dbeafe;font-size:14px;line-height:1.5;">
                  {bullets_html}
                </ul>
              </div>
              <p style="margin:16px 0;color:#dbeafe;">{cta_note}</p>
              <!-- CTA Buttons -->
              <table role="presentation" cellspacing="0" cellpadding="0" style="margin:20px 0 6px;">
                <tr>
                  <td style="border-radius:4px;background-color:#25D366;">
                    <a href="{wa_url}" target="_blank" style="display:inline-block;padding:12px 18px;color:#050505;text-decoration:none;font-weight:bold;font-size:13px;text-transform:uppercase;letter-spacing:0.6px;">Escribir por WhatsApp →</a>
                  </td>
                  <td width="12"></td>
                  <td style="border-radius:4px;background-color:#3265A6;">
                    <a href="https://drive.google.com/file/d/1S1DoP-ZQEbCIRiCjIFdfrzE1bGpqKmhf/view?usp=sharing" target="_blank" style="display:inline-block;padding:12px 18px;color:#F0F6FF;text-decoration:none;font-weight:bold;font-size:13px;text-transform:uppercase;letter-spacing:0.6px;">Ver Catálogo</a>
                  </td>
                </tr>
              </table>
            </td>
          </tr>
          <!-- Footer -->
          <tr>
            <td style="padding:18px 30px;background-color:#080E18;border-top:1px solid #1C2E47;color:#8BA4C2;font-size:12px;line-height:1.6;">
              <strong style="color:#F0F6FF;">Los Crafters SRL</strong><br>
              📞 Teléfono y WhatsApp: +1 (809) 568-6663<br>
              🌐 <a href="{tracked_home_url}" style="color:#5BA3F5;text-decoration:none;">www.loscrafters.net</a> · ✉️ <a href="mailto:info@loscrafters.net" style="color:#5BA3F5;text-decoration:none;">info@loscrafters.net</a>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""
    return subject, html


def build_auto_reply_html(empresa: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="es">
<head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;font-family:'Segoe UI',Arial,sans-serif;">
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="padding:16px 8px;">
    <tr>
      <td align="center">
        <table role="presentation" width="580" cellspacing="0" cellpadding="0" style="max-width:580px;width:100%;background-color:#0A0F1A;border:1px solid #1C2E47;border-radius:10px;overflow:hidden;">
          <tr>
            <td style="padding:22px 28px;color:#F0F6FF;font-size:15px;line-height:1.6;">
              <p style="margin:0 0 12px;">¡Hola! Muchas gracias por respondernos.</p>
              <p style="margin:0 0 12px;color:#dbeafe;">
                Acabamos de recibir tu mensaje de <strong>{empresa}</strong> y nuestro equipo de proyectos ya lo está revisando para darte respuesta hoy mismo.
              </p>
              <p style="margin:0 0 16px;color:#dbeafe;">
                Si deseas adelantarnos algún listado de unidades, planos o medidas directamente por WhatsApp, estamos disponibles en el <strong>+1 (809) 568-6663</strong>.
              </p>
              <p style="margin:0;color:#8BA4C2;font-size:13px;">
                Un cordial saludo,<br>
                <strong style="color:#F0F6FF;">Equipo de Proyectos · Los Crafters SRL</strong><br>
                📞 Teléfono y WhatsApp: +1 (809) 568-6663
              </p>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""


def attach_inline_images(msg_root: MIMEMultipart):
    inline_map = {
        "sun_district": IMAGES_DIR / "email-sun-district.jpg",
        "pc_detalle": IMAGES_DIR / "email-punta-cana-2.jpg",
        "via_basalto": IMAGES_DIR / "email-via-basalto.jpg",
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


def log_sent_email(empresa: str, correo: str, nicho: str, subject: str, status: str = "ENVIADO"):
    file_exists = LOG_CSV_PATH.exists()
    with open(LOG_CSV_PATH, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["fecha_hora", "empresa", "correo", "nicho", "asunto", "estado"])
        writer.writerow([datetime.now().strftime("%Y-%m-%d %H:%M:%S"), empresa, correo, nicho, subject, status])


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


def audit_crm_inbox(imap_host, smtp_host, smtp_port, smtp_user, smtp_pass, csv_path: Path, auto_reply: bool = False):
    """Revisa por IMAP quién respondió de la lista de prospectos, si hubo rebotes, y envía acuse automático si se solicita."""
    prospects = {}
    if csv_path.exists():
        with open(csv_path, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                em = row.get("correo", "").strip().lower()
                if em:
                    prospects[em] = row.get("empresa", "su empresa").strip()

    already_replied = set()
    if AUTO_REPLY_LOG.exists():
        already_replied = set(AUTO_REPLY_LOG.read_text(encoding="utf-8").splitlines())

    mail = imaplib.IMAP4_SSL(imap_host, ssl_context=get_ssl_context())
    mail.login(smtp_user, smtp_pass)
    mail.select("INBOX")
    status, messages = mail.search(None, "ALL")
    if status != "OK" or not messages[0]:
        print("Bandeja vacía.")
        return

    ids = messages[0].split()[-80:][::-1]
    replies_found = []
    bounces_found = []
    clicks_found = []

    for num in ids:
        res, msg_data = mail.fetch(num, "(RFC822.HEADER)")
        for response_part in msg_data:
            if not isinstance(response_part, tuple):
                continue
            msg = email.message_from_bytes(response_part[1])
            subj = decode_mime_words(msg.get("Subject", ""))
            sender = decode_mime_words(msg.get("From", ""))
            sender_lower = sender.lower()
            date = msg.get("Date", "")

            if "[clic en correo]" in subj.lower():
                clicks_found.append((subj, date))
            elif "mailer-daemon" in sender_lower or "delivery status" in subj.lower() or "undeliverable" in subj.lower():
                bounces_found.append((sender, subj, date))
            else:
                for p_email, p_emp in prospects.items():
                    if p_email in sender_lower:
                        replies_found.append((p_emp, p_email, subj, date))
                        if auto_reply and p_email not in already_replied:
                            reply_subj = subj if subj.lower().startswith("re:") else f"Re: {subj}"
                            ack_html = build_auto_reply_html(p_emp)
                            send_single_email(smtp_host, smtp_port, smtp_user, smtp_pass, p_email, reply_subj, ack_html, include_images=False)
                            already_replied.add(p_email)
                            with open(AUTO_REPLY_LOG, "a", encoding="utf-8") as af:
                                af.write(p_email + "\n")
                            print(f"🤖 Auto-respuesta inmediata enviada a {p_emp} (<{p_email}>)")

    mail.logout()

    print("📊 REPORTE CRM DE CAMPAÑA B2B — LOS CRAFTERS SRL")
    print("=" * 68)
    print(f"• Prospectos monitoreados en base de datos: {len(prospects)}")
    print(f"• Clics hacia el portafolio detectados:     {len(clicks_found)}")
    for c_subj, c_date in clicks_found[:10]:
        print(f"   🔔 {c_subj} ({c_date})")
    print(f"• Respuestas directas de constructoras:     {len(replies_found)}")
    for emp, em, s, d in replies_found:
        print(f"   💬 {emp} (<{em}>) — '{s}' ({d})")
    print(f"• Rebotes / Correos no entregados:          {len(bounces_found)}")
    for b_s, b_subj, b_d in bounces_found[:5]:
        print(f"   ⚠️ {b_subj} ({b_d})")


def main():
    load_dotenv()
    parser = argparse.ArgumentParser(description="Motor de Email Marketing B2B e Inbox CRM — Los Crafters SRL")
    parser.add_argument("--preview", action="store_true", help="Genera archivo HTML de vista previa sin enviar correo")
    parser.add_argument("--test", action="store_true", help="Envía un correo real de prueba a info@loscrafters.net")
    parser.add_argument("--send-one", action="store_true", help="Envía un correo individual personalizado")
    parser.add_argument("--send", action="store_true", help="Envía los correos de la lista CSV por SMTP")
    parser.add_argument("--inbox", action="store_true", help="Lista los últimos correos recibidos en info@loscrafters.net")
    parser.add_argument("--crm", action="store_true", help="Audita clics, respuestas de prospectos y rebotes en el inbox")
    parser.add_argument("--auto-reply", action="store_true", help="Con --crm, responde automáticamente con acuse cálido a los prospectos que contesten")
    parser.add_argument("--limit", type=int, default=8, help="Cantidad de correos a mostrar con --inbox")
    parser.add_argument("--to", default="", help="Correo destino para --send-one o --test")
    parser.add_argument("--nombre", default="Equipo de Proyectos", help="Nombre del contacto")
    parser.add_argument("--empresa", default="su constructora", help="Nombre de la empresa")
    parser.add_argument("--zona", default="", help="Parámetro interno de zona (no se imprime en el correo)")
    parser.add_argument("--servicio", default="Señalización de Proyectos", help="Servicio")
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

    if args.crm:
        audit_crm_inbox(imap_host, smtp_host, smtp_port, smtp_user, smtp_pass, Path(args.csv), auto_reply=args.auto_reply)
        return

    tpl_info = TEMPLATES.get(args.nicho, TEMPLATES["residencial_punta_cana"])
    inc_imgs = bool(tpl_info.get("show_gallery", True))

    if args.test:
        target = args.to or smtp_user
        subject, html = build_html_email(args.nombre, args.empresa, args.nicho, args.servicio, args.zona, use_cid=True)
        send_single_email(smtp_host, smtp_port, smtp_user, smtp_pass, target, f"[PRUEBA] {subject}", html, include_images=inc_imgs)
        print(f"✅ Correo de prueba enviado exitosamente a {target}!")
        print(f"   Asunto: [PRUEBA] {subject}")
        return

    if args.send_one:
        if not args.to:
            print("❌ Debes indicar --to correo@destino.com")
            return
        subject, html = build_html_email(args.nombre, args.empresa, args.nicho, args.servicio, args.zona, use_cid=True)
        send_single_email(smtp_host, smtp_port, smtp_user, smtp_pass, args.to, subject, html, include_images=inc_imgs)
        log_sent_email(args.empresa, args.to, args.nicho, subject, "ENVIADO_INDIVIDUAL")
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
                nombre = row.get("nombre", "Equipo de Proyectos").strip()
                empresa = row.get("empresa", "su constructora").strip()
                nicho = row.get("nicho", args.nicho).strip()
                servicio = row.get("servicio", "Señalización de Proyectos").strip()
                zona = row.get("zona", "").strip()

                tpl_row = TEMPLATES.get(nicho, TEMPLATES["residencial_punta_cana"])
                row_imgs = bool(tpl_row.get("show_gallery", True))
                subject, html = build_html_email(nombre, empresa, nicho, servicio, zona, use_cid=True)
                msg_root = create_mime_message(smtp_user, email_to, subject, html, include_images=row_imgs)

                server.sendmail(smtp_user, email_to, msg_root.as_string())
                log_sent_email(empresa, email_to, nicho, subject, "ENVIADO_CAMPANA")
                print(f"📨 Enviado a {nombre} ({empresa}) <{email_to}> [{nicho}]")
                time.sleep(5)


if __name__ == "__main__":
    main()
