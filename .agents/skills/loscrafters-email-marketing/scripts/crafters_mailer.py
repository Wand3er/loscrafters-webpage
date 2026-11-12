#!/usr/bin/env python3
"""
LOS CRAFTERS SRL — Motor Completo de Email Marketing B2B e Inbox CRM (SMTP + IMAP)
Conecta directamente con info@loscrafters.net vía Google Workspace (smtp.gmail.com / imap.gmail.com)
leyendo automáticamente las credenciales desde el archivo .env en la raíz del proyecto.

Comandos disponibles:
  1. Enviar correo de prueba real a info@loscrafters.net:
     python3 .agents/skills/loscrafters-email-marketing/scripts/crafters_mailer.py --test --nicho constructora

  2. Enviar un correo personalizado individual:
     python3 .agents/skills/loscrafters-email-marketing/scripts/crafters_mailer.py --send-one --to cliente@empresa.com --nombre "Ing. Pérez" --empresa "Constructora Pérez" --nicho constructora

  3. Enviar campaña masiva desde el CSV de prospectos:
     python3 .agents/skills/loscrafters-email-marketing/scripts/crafters_mailer.py --send --csv .agents/skills/loscrafters-email-marketing/scripts/prospectos_b2b_rd.csv

  4. Revisar últimos correos / leads recibidos en la bandeja de entrada (IMAP):
     python3 .agents/skills/loscrafters-email-marketing/scripts/crafters_mailer.py --inbox --limit 10
"""

import argparse
import csv
import email
from email.header import decode_header
import imaplib
import os
import smtplib
import ssl
import time
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[4]
ENV_PATH = ROOT_DIR / ".env"


def load_dotenv():
    if ENV_PATH.exists():
        for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


TEMPLATES = {
    "constructora": {
        "subject": "Señalética arquitectónica y letreros 3D para proyectos de {empresa}",
        "headline": "Señalización de Obra y Letreros Corpóreos 3D",
        "intro": (
            "Vi los desarrollos recientes de <strong>{empresa}</strong> y quise contactarte directamente "
            "porque en <strong>Los Crafters SRL</strong> apoyamos a constructoras e ingenierías en República Dominicana "
            "(como <em>Elenma Construcciones</em>) desde el cierre perimetral hasta la entrega de la torre o plaza."
        ),
        "bullets": [
            "<strong>Etapa de Obra:</strong> Vallas perimetrales en gran formato, señalización de seguridad industrial y rotulación de maquinaria/flotillas.",
            "<strong>Etapa de Entrega y Lobby:</strong> Letras corpóreas 3D en acero inoxidable, acrílico y aluminio con iluminación LED cálida/fría.",
            "<strong>Señalética Arquitectónica:</strong> Numeración de niveles/apartamentos, directorios de lobby y señalización vial de parqueos."
        ],
        "cta_note": "¿Tienen algún proyecto próximo en etapa de terminación donde podamos cotizarles una partida comparativa con Comprobante Fiscal?"
    },
    "colegio": {
        "subject": "Renovación visual, murales y letras corpóreas 3D para {empresa}",
        "headline": "Espacios Educativos que Inspiran y Comunican",
        "intro": (
            "Recientemente fabricamos e instalamos los emblemas corpóreos 3D y murales interiores para "
            "instituciones educativas en Santo Domingo (como <em>AF School</em>, que puedes ver en la portada de nuestra web)."
        ),
        "bullets": [
            "<strong>Escudos y Letras Corpóreas 3D:</strong> Máxima durabilidad para fachadas, recepciones y salones de actos.",
            "<strong>Rotulación Mural en Vinil Mate:</strong> Ambientación educativa e institucional de gran formato para aulas, pasillos y bibliotecas.",
            "<strong>Señalización de Plantel:</strong> Identificación de aulas, laboratorios, áreas deportivas y rutas de evacuación."
        ],
        "cta_note": "Si planean renovar áreas del centro educativo, podemos coordinar una visita técnica de levantamiento en Santo Domingo sin costo."
    },
    "flotilla": {
        "subject": "Rotulación vehicular de alta durabilidad para la flota de {empresa}",
        "headline": "Convierte tu Flotilla en Publicidad en Movimiento",
        "intro": (
            "Cada vehículo comercial de <strong>{empresa}</strong> recorre miles de kilómetros al mes en la ciudad. "
            "Bien rotulado, es una valla publicitaria móvil trabajando las 24 horas sin pagar renta mensual."
        ),
        "bullets": [
            "<strong>Vinil Grado Automotriz + Laminado UV:</strong> Máxima resistencia al sol del Caribe y al lavado frecuente sin decolorarse ni levantarse.",
            "<strong>Camiones, Furgonetas y Flotas Ligeras:</strong> Rotulación integral (wrapping), parcial o microperforado homologado.",
            "<strong>Instalación Programada:</strong> Trabajamos por turnos o fines de semana para no detener la operación de tus rutas."
        ],
        "cta_note": "¿Cuántas unidades manejan actualmente en {empresa}? Respóndenos con el modelo o una foto y te preparamos una propuesta formal hoy mismo."
    },
    "seguimiento": {
        "subject": "Seguimiento a tu solicitud de cotización — {empresa} | Los Crafters SRL",
        "headline": "Propuesta Técnica y Disponibilidad de Taller",
        "intro": (
            "Te escribo brevemente para confirmar que hayas recibido nuestra información sobre el proyecto de "
            "<strong>{servicio}</strong> para <strong>{empresa}</strong>."
        ),
        "bullets": [
            "<strong>Taller Propio en Santo Domingo:</strong> Control total de calidad en corte láser/CNC, estructura metálica, pintura e impresión.",
            "<strong>Materiales Certificados:</strong> ACM de 4mm, acrílico importado, vinil cast automotriz y módulos LED IP67 a prueba de agua.",
            "<strong>Facturación Corporativa:</strong> Emisión de Comprobante Fiscal (B01 / E-CF) y garantía escrita de instalación."
        ],
        "cta_note": "Actualmente contamos con espacio en nuestra agenda de producción de esta semana. ¿Deseas que ajustemos alguna medida o coordinemos el levantamiento técnico?"
    }
}


def build_html_email(nombre: str, empresa: str, nicho: str, servicio: str = "Letreros y Rotulación") -> tuple[str, str]:
    tpl = TEMPLATES.get(nicho, TEMPLATES["constructora"])
    subject = tpl["subject"].format(nombre=nombre, empresa=empresa, servicio=servicio)
    intro_html = tpl["intro"].format(nombre=nombre, empresa=empresa, servicio=servicio)
    cta_note = tpl["cta_note"].format(nombre=nombre, empresa=empresa, servicio=servicio)
    bullets_html = "".join(f'<li style="margin-bottom: 10px;">{b}</li>' for b in tpl["bullets"])

    html = f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<title>{subject}</title>
</head>
<body style="margin:0;padding:0;background-color:#080E18;font-family:'Segoe UI',Arial,sans-serif;">
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background-color:#080E18;padding:32px 16px;">
    <tr>
      <td align="center">
        <table role="presentation" width="600" cellspacing="0" cellpadding="0" style="max-width:600px;width:100%;background-color:#0A0F1A;border:1px solid #1C2E47;border-radius:10px;overflow:hidden;">
          <!-- Header -->
          <tr>
            <td style="padding:28px 32px;background:linear-gradient(135deg,#0A0F1A 0%,#1A3F6F 100%);border-bottom:3px solid #3265A6;">
              <div style="font-size:11px;font-weight:800;letter-spacing:2px;color:#5BA3F5;text-transform:uppercase;">LOS CRAFTERS SRL · TALLER PUBLICITARIO</div>
              <h1 style="margin:8px 0 0;font-size:22px;line-height:1.25;color:#F0F6FF;font-weight:800;">{tpl["headline"]}</h1>
            </td>
          </tr>
          <!-- Body -->
          <tr>
            <td style="padding:32px;color:#F0F6FF;font-size:15px;line-height:1.7;">
              <p style="margin-top:0;">Hola <strong>{nombre}</strong>, espero que estés muy bien.</p>
              <p>{intro_html}</p>
              <div style="background-color:#101929;border-left:3px solid #5BA3F5;padding:18px 20px;margin:22px 0;border-radius:4px;">
                <ul style="margin:0;padding-left:18px;color:#dbeafe;">
                  {bullets_html}
                </ul>
              </div>
              <p>{cta_note}</p>
              <!-- CTA Buttons -->
              <table role="presentation" cellspacing="0" cellpadding="0" style="margin:28px 0 12px;">
                <tr>
                  <td style="border-radius:4px;background-color:#3265A6;">
                    <a href="https://drive.google.com/file/d/1S1DoP-ZQEbCIRiCjIFdfrzE1bGpqKmhf/view?usp=sharing" target="_blank" style="display:inline-block;padding:13px 22px;color:#F0F6FF;text-decoration:none;font-weight:bold;font-size:13px;text-transform:uppercase;letter-spacing:0.8px;">Ver Catálogo Digital</a>
                  </td>
                  <td width="12"></td>
                  <td style="border-radius:4px;background-color:#25D366;">
                    <a href="https://wa.me/18294109362?text=Hola%20Los%20Crafters,%20recib%C3%AD%20su%20correo%20y%20me%20gustar%C3%ADa%20cotizar%20un%20proyecto." target="_blank" style="display:inline-block;padding:13px 22px;color:#050505;text-decoration:none;font-weight:bold;font-size:13px;text-transform:uppercase;letter-spacing:0.8px;">Cotizar por WhatsApp →</a>
                  </td>
                </tr>
              </table>
            </td>
          </tr>
          <!-- Footer -->
          <tr>
            <td style="padding:20px 32px;background-color:#080E18;border-top:1px solid #1C2E47;color:#8BA4C2;font-size:12px;line-height:1.6;">
              <strong>Los Crafters SRL</strong> · Soluciones Visuales y Publicidad en República Dominicana<br>
              📍 Santo Domingo, RD · 📞 +1 (809) 568-6663 · 💬 WhatsApp: +1 (829) 410-9362<br>
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


def get_ssl_context():
    cafile = "/etc/ssl/cert.pem" if Path("/etc/ssl/cert.pem").exists() else None
    return ssl.create_default_context(cafile=cafile)


def send_single_email(smtp_host, smtp_port, smtp_user, smtp_pass, to_email, subject, html):
    context = get_ssl_context()
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"Los Crafters SRL <{smtp_user}>"
    msg["To"] = to_email
    msg["Reply-To"] = smtp_user
    msg.attach(MIMEText(html, "html", "utf-8"))

    with smtplib.SMTP_SSL(smtp_host, smtp_port, context=context) as server:
        server.login(smtp_user, smtp_pass)
        server.sendmail(smtp_user, to_email, msg.as_string())


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
    parser.add_argument("--nombre", default="Ing. Carlos Méndez", help="Nombre del contacto")
    parser.add_argument("--empresa", default="Constructora del Caribe SRL", help="Nombre de la empresa")
    parser.add_argument("--servicio", default="Letreros Corpóreos 3D y Señalización", help="Servicio")
    parser.add_argument("--nicho", default="constructora", choices=list(TEMPLATES.keys()), help="Plantilla de nicho a usar")
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

    if args.test:
        target = args.to or smtp_user
        subject, html = build_html_email(args.nombre, args.empresa, args.nicho, args.servicio)
        send_single_email(smtp_host, smtp_port, smtp_user, smtp_pass, target, f"[PRUEBA CAMPAÑA] {subject}", html)
        print(f"✅ Correo de prueba enviado exitosamente desde {smtp_user} hacia {target}!")
        print(f"   Asunto: [PRUEBA CAMPAÑA] {subject}")
        return

    if args.send_one:
        if not args.to:
            print("❌ Debes indicar --to correo@destino.com")
            return
        subject, html = build_html_email(args.nombre, args.empresa, args.nicho, args.servicio)
        send_single_email(smtp_host, smtp_port, smtp_user, smtp_pass, args.to, subject, html)
        print(f"✅ Correo enviado exitosamente a {args.nombre} ({args.empresa}) <{args.to}>!")
        return

    if args.preview or not args.send:
        subject, html = build_html_email(args.nombre, args.empresa, args.nicho, args.servicio)
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
                nombre = row.get("nombre", "Estimado/a").strip()
                empresa = row.get("empresa", "su empresa").strip()
                nicho = row.get("nicho", args.nicho).strip()
                servicio = row.get("servicio", "Letreros y Rotulación").strip()

                subject, html = build_html_email(nombre, empresa, nicho, servicio)
                msg = MIMEMultipart("alternative")
                msg["Subject"] = subject
                msg["From"] = f"Los Crafters SRL <{smtp_user}>"
                msg["To"] = email_to
                msg["Reply-To"] = smtp_user
                msg.attach(MIMEText(html, "html", "utf-8"))

                server.sendmail(smtp_user, email_to, msg.as_string())
                print(f"📨 Enviado a {nombre} ({empresa}) <{email_to}> [{nicho}]")
                time.sleep(3)


if __name__ == "__main__":
    main()
