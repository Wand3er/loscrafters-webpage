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
import urllib.request
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[4]
ENV_PATH = ROOT_DIR / ".env"
IMAGES_DIR = ROOT_DIR / "assets" / "images"
SCRIPTS_DIR = Path(__file__).resolve().parent
LOG_CSV_PATH = SCRIPTS_DIR / "campana_log.csv"
AUTO_REPLY_LOG = SCRIPTS_DIR / "auto_replies_sent.txt"
BOUNCES_SEEN_LOG = SCRIPTS_DIR / "bounces_seen.txt"
PVC_CAMPAIGN_DIR = Path("/Users/wandermarte/Documents/REPOSITORIOS/loscrafters-video-studio/email-campaigns/pvc-letreros")
ROTULACION_CAMPAIGN_DIR = Path("/Users/wandermarte/Documents/REPOSITORIOS/loscrafters-video-studio/email-campaigns/rotulacion-vehicular")
CUSTOM_HTML_ASSETS = {
    "pvc_letreros": {
        "img/logo-lc.png": ("pvc_logo", PVC_CAMPAIGN_DIR / "img" / "logo-lc.png"),
        "img/elenma-solo-hd.jpg": ("pvc_elenma", PVC_CAMPAIGN_DIR / "img" / "elenma-solo-hd.jpg"),
        "img/boshi-pvc.jpg": ("pvc_boshi", PVC_CAMPAIGN_DIR / "img" / "boshi-pvc.jpg"),
        "img/afschool-full.jpg": ("pvc_afschool", PVC_CAMPAIGN_DIR / "img" / "afschool-full.jpg"),
        "img/onestop-pvc.jpg": ("pvc_onestop", PVC_CAMPAIGN_DIR / "img" / "onestop-pvc.jpg"),
    },
    "flotilla": {
        "img/logo-lc.png": ("rot_logo", ROTULACION_CAMPAIGN_DIR / "img" / "logo-lc.png"),
        "img/medlog-hero.jpg": ("rot_medlog", ROTULACION_CAMPAIGN_DIR / "img" / "medlog-hero.jpg"),
        "img/retzy-camion.jpg": ("rot_retzy", ROTULACION_CAMPAIGN_DIR / "img" / "retzy-camion.jpg"),
        "img/kuno-van.jpg": ("rot_kuno", ROTULACION_CAMPAIGN_DIR / "img" / "kuno-van.jpg"),
    },
}
NTFY_TOPICS = ["loscrafters-alertas-8294109362", "loscrafters-vip-alertas-8095686663"]


def notify_phone(title: str, message: str, priority: str = "5"):
    for topic in NTFY_TOPICS:
        try:
            req = urllib.request.Request(
                f"https://ntfy.sh/{topic}",
                data=message.encode("utf-8"),
                headers={"Title": title, "Priority": priority, "Tags": "incoming_envelope,fire"},
                method="POST"
            )
            urllib.request.urlopen(req, timeout=6, context=get_ssl_context())
        except Exception:
            pass


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
        "subject": "Señalización y letreros 3D para los proyectos de {empresa}",
        "eyebrow": "LOS CRAFTERS",
        "headline": "Señalización a la altura de tus desarrollos.",
        "intro": (
            "En <strong>Los Crafters</strong> acompañamos a constructoras y desarrolladores a vestir sus proyectos "
            "—desde el letrero principal de entrada y áreas comerciales hasta la numeración de cada unidad— "
            "con acabados modernos, limpios y hechos para durar."
        ),
        "show_gallery": True,
        "bullets": [
            "<strong>Entradas y fachadas:</strong> Letras corpóreas 3D y tótems en acrílico, ACM y metales con o sin luz LED.",
            "<strong>Numeración y señalética:</strong> Placas en relieve 3D para apartamentos, villas, niveles, parqueos y áreas comunes.",
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
        "subject": "Rotulación para los vehículos y flotilla de {empresa}",
        "eyebrow": "LOS CRAFTERS",
        "headline": "Tu marca en movimiento todos los días.",
        "intro": (
            "En <strong>Los Crafters</strong> acompañamos a empresas de distribución y servicios a convertir "
            "sus camiones, furgonetas y flotillas en publicidad activa, con materiales hechos para aguantar "
            "el sol diario y el lavado frecuente sin despegarse ni perder color."
        ),
        "show_gallery": True,
        "bullets": [
            "<strong>Vinil grado automotriz + laminado UV:</strong> No se cuartea, no se levanta ni pierde intensidad con el sol.",
            "<strong>Camiones, furgonetas y camionetas:</strong> Rotulación completa, parcial, en corte o microperforado.",
            "<strong>Instalación ágil sin frenar tu operación:</strong> Coordinamos por unidades o en fin de semana para que tus rutas no paren."
        ],
        "cta_note": (
            "¿Tienen unidades nuevas por rotular o vehículos cuya imagen quieran renovar? "
            "Escríbenos por aquí o por WhatsApp y con gusto les preparamos una propuesta."
        ),
        "custom_html": ROTULACION_CAMPAIGN_DIR / "correo_rotulacion_b2b.html",
    },
    "seguimiento": {
        "subject": "Seguimiento cordial — Los Crafters SRL | {empresa}",
        "eyebrow": "SEGUIMIENTO · LOS CRAFTERS SRL",
        "headline": "Seguimos a su disposición.",
        "intro": "",
        "show_gallery": False,
        "bullets": [],
        "cta_note": ""
    },
    "pvc_letreros": {
        "subject": "Letreros en PVC para {empresa}",
        "eyebrow": "LOS CRAFTERS",
        "headline": "Letreros en PVC para tu negocio o institución",
        "intro": "",
        "show_gallery": True,
        "bullets": [],
        "cta_note": "",
        "custom_html": PVC_CAMPAIGN_DIR / "correo_pvc_b2b.html",
    }
}


def _resolve_seguimiento_servicio(servicio: str) -> str:
    s = (servicio or "").lower()
    if "rotulac" in s or "flotilla" in s or "vehic" in s:
        return "rotulación vehicular y branding para su flotilla"
    if "pvc" in s:
        return "letreros corpóreos en PVC para su negocio o institución"
    if "señal" in s or "senal" in s or "residencial" in s or "proyecto" in s:
        return "señalización y letreros 3D para sus proyectos"
    return "letreros, rotulación y señalización corporativa"


def build_seguimiento_kanban_html(
    empresa: str,
    subject: str,
    servicio: str,
    tracked_home_url: str,
    use_cid: bool = True,
) -> str:
    logo_src = "cid:logo_lc" if use_cid else (IMAGES_DIR / "Logo-LC-12.png").as_uri()
    servicio_texto = _resolve_seguimiento_servicio(servicio)
    wa_text = urllib.parse.quote(
        f"Hola Los Crafters, les escribo de {empresa} en seguimiento al correo que nos enviaron."
    )
    wa_url = f"https://wa.me/18095686663?text={wa_text}"
    mailto_subj = urllib.parse.quote(f"Consulta / Cotización - {empresa}", safe="")
    mailto_body = urllib.parse.quote(
        f"Hola equipo de Los Crafters,\n\nLes escribimos de {empresa} respecto al correo de seguimiento.\n"
    )
    mailto_url = f"mailto:ventas@loscrafters.net?subject={mailto_subj}&body={mailto_body}"

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>{subject}</title>
  <style>
    @media only screen and (max-width: 520px) {{
      .kanban-cell {{
        display: block !important;
        width: 100% !important;
        text-align: left !important;
      }}
      .kanban-cta {{
        padding-top: 12px !important;
        text-align: left !important;
      }}
    }}
  </style>
</head>
<body style="margin:0; padding:0; background-color:#E9EFF6; font-family:'Open Sans', Arial, Helvetica, sans-serif; color:#0F172A; -webkit-font-smoothing:antialiased;">
  <div style="display:none; max-height:0; overflow:hidden; mso-hide:all; font-size:1px; line-height:1px; color:#E9EFF6;">
    Un saludo breve de Los Crafters SRL con nuestros canales de contacto rápido: WhatsApp, correo y página web.
  </div>

  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background-color:#E9EFF6; padding:24px 10px;">
    <tr>
      <td align="center">
        <table role="presentation" width="600" cellpadding="0" cellspacing="0" border="0" style="width:100%; max-width:600px; background-color:#FFFFFF; border-radius:20px; overflow:hidden; border:1px solid #D8E2EE;">

          <!-- HEADER -->
          <tr>
            <td align="center" style="background:linear-gradient(135deg, #0A0F1A 0%, #1A3F6F 70%, #3265A6 100%); background-color:#1A3F6F; padding:26px 28px 24px 28px; text-align:center;">
              <a href="{tracked_home_url}" target="_blank" style="display:inline-block; text-decoration:none; border:0; margin-bottom:14px;">
                <img src="{logo_src}" alt="Los Crafters SRL" width="132" style="display:block; width:132px; height:auto; border:0;" />
              </a>
              <div style="font-family:'Montserrat', Arial, sans-serif; font-size:11px; font-weight:800; letter-spacing:0.14em; text-transform:uppercase; color:#7EC8F7; margin-bottom:6px;">
                SEGUIMIENTO CORDIAL
              </div>
              <h1 style="margin:0; font-family:'Montserrat', Arial, sans-serif; font-size:24px; line-height:1.22; font-weight:800; color:#FFFFFF; text-align:center;">
                Seguimos a su disposición
              </h1>
            </td>
          </tr>

          <!-- SALUDO CORTO -->
          <tr>
            <td style="padding:28px 30px 18px 30px; color:#1E293B; font-size:15px; line-height:1.65;">
              <p style="margin:0 0 12px 0; font-size:16px; color:#0A0F1A;">
                Hola, equipo de <strong>{empresa}</strong>:
              </p>
              <p style="margin:0 0 12px 0; color:#334155;">
                Les enviamos un saludo cordial para dar seguimiento breve al correo que les compartimos la semana pasada sobre <strong>{servicio_texto}</strong>.
              </p>
              <p style="margin:0; color:#334155;">
                Si tienen algún proyecto en agenda o desean solicitar una cotización rápida, pueden contactarnos directo por cualquiera de estas opciones:
              </p>
            </td>
          </tr>

          <!-- TABLERO KANBAN DE CONTACTO RÁPIDO -->
          <tr>
            <td style="padding:4px 26px 28px 26px;">
              <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background-color:#F1F5F9; border:1px solid #DCE5F0; border-radius:16px;">
                <tr>
                  <td style="padding:14px 14px 10px 14px;">
                    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">
                      <tr>
                        <td style="font-family:'Montserrat', Arial, sans-serif; font-size:11px; font-weight:800; letter-spacing:0.10em; text-transform:uppercase; color:#1A3F6F;">
                          CANALES DE CONTACTO DIRECTO
                        </td>
                        <td align="right">
                          <span style="display:inline-block; background-color:#DCE8F7; color:#1A3F6F; font-family:'Montserrat', Arial, sans-serif; font-size:10px; font-weight:800; letter-spacing:0.06em; text-transform:uppercase; padding:4px 10px; border-radius:999px;">
                            3 OPCIONES
                          </span>
                        </td>
                      </tr>
                    </table>
                  </td>
                </tr>

                <!-- TARJETA 1: WHATSAPP -->
                <tr>
                  <td style="padding:0 14px 10px 14px;">
                    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background-color:#FFFFFF; border:1px solid #DCE5F0; border-left:5px solid #25D366; border-radius:12px;">
                      <tr>
                        <td style="padding:14px 16px;">
                          <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">
                            <tr>
                              <td class="kanban-cell" valign="middle">
                                <span style="display:inline-block; background-color:#DCFCE7; color:#166534; font-family:'Montserrat', Arial, sans-serif; font-size:10px; font-weight:800; letter-spacing:0.08em; text-transform:uppercase; padding:3px 9px; border-radius:999px; margin-bottom:6px;">
                                  ● WHATSAPP DIRECTO
                                </span>
                                <div style="font-family:'Montserrat', Arial, sans-serif; font-size:17px; font-weight:800; color:#0A0F1A; line-height:1.25;">
                                  <a href="{wa_url}" target="_blank" style="color:#0A0F1A; text-decoration:none;">(809) 568-6663</a>
                                </div>
                                <div style="font-family:'Open Sans', Arial, sans-serif; font-size:12px; color:#64748B; margin-top:2px;">
                                  Respuesta ágil para consultas, fotos o medidas
                                </div>
                              </td>
                              <td class="kanban-cell kanban-cta" valign="middle" align="right" width="150">
                                <a href="{wa_url}" target="_blank" style="display:inline-block; min-width:136px; text-align:center; box-sizing:border-box; background-color:#16A34A; color:#FFFFFF; font-family:'Montserrat', Arial, sans-serif; font-size:11px; font-weight:800; letter-spacing:0.05em; text-transform:uppercase; padding:10px 14px; border-radius:999px; text-decoration:none; white-space:nowrap;">
                                  Escribir →
                                </a>
                              </td>
                            </tr>
                          </table>
                        </td>
                      </tr>
                    </table>
                  </td>
                </tr>

                <!-- TARJETA 2: CORREO -->
                <tr>
                  <td style="padding:0 14px 10px 14px;">
                    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background-color:#FFFFFF; border:1px solid #DCE5F0; border-left:5px solid #3265A6; border-radius:12px;">
                      <tr>
                        <td style="padding:14px 16px;">
                          <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">
                            <tr>
                              <td class="kanban-cell" valign="middle">
                                <span style="display:inline-block; background-color:#DBEAFE; color:#1E40AF; font-family:'Montserrat', Arial, sans-serif; font-size:10px; font-weight:800; letter-spacing:0.08em; text-transform:uppercase; padding:3px 9px; border-radius:999px; margin-bottom:6px;">
                                  ● CORREO ELECTRÓNICO
                                </span>
                                <div style="font-family:'Montserrat', Arial, sans-serif; font-size:16px; font-weight:800; color:#0A0F1A; line-height:1.25;">
                                  <a href="{mailto_url}" style="color:#0A0F1A; text-decoration:none;">ventas@loscrafters.net</a>
                                </div>
                                <div style="font-family:'Open Sans', Arial, sans-serif; font-size:12px; color:#64748B; margin-top:2px;">
                                  Envíanos tu logo, medidas o solicitud de cotización
                                </div>
                              </td>
                              <td class="kanban-cell kanban-cta" valign="middle" align="right" width="150">
                                <a href="{mailto_url}" style="display:inline-block; min-width:136px; text-align:center; box-sizing:border-box; background-color:#3265A6; color:#FFFFFF; font-family:'Montserrat', Arial, sans-serif; font-size:11px; font-weight:800; letter-spacing:0.05em; text-transform:uppercase; padding:10px 14px; border-radius:999px; text-decoration:none; white-space:nowrap;">
                                  Enviar correo →
                                </a>
                              </td>
                            </tr>
                          </table>
                        </td>
                      </tr>
                    </table>
                  </td>
                </tr>

                <!-- TARJETA 3: PÁGINA WEB -->
                <tr>
                  <td style="padding:0 14px 14px 14px;">
                    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background-color:#FFFFFF; border:1px solid #DCE5F0; border-left:5px solid #5BA3F5; border-radius:12px;">
                      <tr>
                        <td style="padding:14px 16px;">
                          <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">
                            <tr>
                              <td class="kanban-cell" valign="middle">
                                <span style="display:inline-block; background-color:#E2E8F0; color:#0F172A; font-family:'Montserrat', Arial, sans-serif; font-size:10px; font-weight:800; letter-spacing:0.08em; text-transform:uppercase; padding:3px 9px; border-radius:999px; margin-bottom:6px;">
                                  ● PORTAFOLIO Y SERVICIOS
                                </span>
                                <div style="font-family:'Montserrat', Arial, sans-serif; font-size:16px; font-weight:800; color:#0A0F1A; line-height:1.25;">
                                  <a href="{tracked_home_url}" target="_blank" style="color:#0A0F1A; text-decoration:none;">www.loscrafters.net</a>
                                </div>
                                <div style="font-family:'Open Sans', Arial, sans-serif; font-size:12px; color:#64748B; margin-top:2px;">
                                  Explora nuestros proyectos recientes y catálogo
                                </div>
                              </td>
                              <td class="kanban-cell kanban-cta" valign="middle" align="right" width="150">
                                <a href="{tracked_home_url}" target="_blank" style="display:inline-block; min-width:136px; text-align:center; box-sizing:border-box; background-color:#0A0F1A; color:#FFFFFF; font-family:'Montserrat', Arial, sans-serif; font-size:11px; font-weight:800; letter-spacing:0.05em; text-transform:uppercase; padding:10px 14px; border-radius:999px; text-decoration:none; white-space:nowrap;">
                                  Visitar web →
                                </a>
                              </td>
                            </tr>
                          </table>
                        </td>
                      </tr>
                    </table>
                  </td>
                </tr>
              </table>
            </td>
          </tr>

          <!-- FOOTER -->
          <tr>
            <td align="center" style="background-color:#0A0F1A; padding:20px 28px; text-align:center;">
              <p style="margin:0 0 6px 0; font-family:'Montserrat', Arial, sans-serif; font-size:12px; font-weight:700; color:#F0F6FF;">
                Un cordial saludo · Los Crafters SRL
              </p>
              <p style="margin:0 0 8px 0; font-family:'Open Sans', Arial, sans-serif; font-size:12px; color:#8BA4C2;">
                Santo Domingo, República Dominicana
              </p>
              <p style="margin:0; font-size:11px; color:#64748B;">
                Si no deseas recibir más correos de seguimiento, responde con la palabra <strong>BAJA</strong>.
              </p>
            </td>
          </tr>

        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""


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

    empresa_param = urllib.parse.quote_plus(empresa)
    tracked_portfolio_url = f"https://www.loscrafters.net/?utm_source=email_b2b&utm_medium=email&utm_campaign={nicho}&empresa={empresa_param}#portafolio"
    tracked_home_url = f"https://www.loscrafters.net/?utm_source=email_b2b&utm_medium=email&utm_campaign={nicho}&empresa={empresa_param}"

    if nicho == "seguimiento":
        return subject, build_seguimiento_kanban_html(empresa, subject, servicio, tracked_home_url, use_cid=use_cid)

    custom_html_path = tpl.get("custom_html")
    if custom_html_path and Path(custom_html_path).exists():
        html = Path(custom_html_path).read_text(encoding="utf-8")
        html = html.replace("[Nombre]", nombre)
        html = html.replace("https://www.loscrafters.net/#portafolio", tracked_portfolio_url)
        html = html.replace('href="https://www.loscrafters.net/"', f'href="{tracked_home_url}"')
        for rel_src, (cid, img_path) in CUSTOM_HTML_ASSETS.get(nicho, {}).items():
            target_src = f"cid:{cid}" if use_cid else img_path.as_uri()
            html = html.replace(f'src="{rel_src}"', f'src="{target_src}"')
        return subject, html

    intro_html = tpl["intro"].format(nombre=nombre, empresa=empresa, servicio=servicio)
    cta_note = tpl["cta_note"].format(nombre=nombre, empresa=empresa, servicio=servicio)
    bullets_html = "".join(f'<li style="margin-bottom: 8px;">{b}</li>' for b in tpl["bullets"])

    wa_text = urllib.parse.quote(f"Hola Los Crafters, les escribo de {empresa}. Vi su correo sobre señalización de proyectos y me gustaría cotizar.")
    wa_url = f"https://wa.me/18095686663?text={wa_text}"

    if use_cid:
        img_sundistrict = "cid:sun_district"
        img_closeup = "cid:num_02"
        img_onestop = "cid:onestop_3d"
    else:
        img_sundistrict = "https://www.loscrafters.net/assets/images/email-sun-district.jpg"
        img_closeup = "https://www.loscrafters.net/assets/images/email-numeracion-02.jpg"
        img_onestop = "https://www.loscrafters.net/assets/images/email-letrero-3d-onestop.jpg"

    gallery_html = ""
    if tpl.get("show_gallery", True):
        if nicho == "flotilla":
            img_camion = "cid:flota_camion" if use_cid else "https://www.loscrafters.net/assets/images/email-flota-camion.jpg"
            img_van = "cid:flota_van" if use_cid else "https://www.loscrafters.net/assets/images/email-flota-furgoneta.jpg"
            gallery_html = f"""
              <!-- Galería de Branding Vehicular -->
              <div style="margin:20px 0;background-color:#101929;border:1px solid #1C2E47;border-radius:8px;padding:16px;">
                <div style="font-size:11px;font-weight:800;letter-spacing:1.4px;color:#5BA3F5;text-transform:uppercase;margin-bottom:10px;">
                  TRABAJOS DE BRANDING VEHICULAR REALIZADOS
                </div>
                <div style="margin-bottom:12px;">
                  <a href="{tracked_portfolio_url}" target="_blank" style="text-decoration:none;">
                    <img src="{img_camion}" alt="Rotulación Integral de Camión Furgón Comercial" width="502" style="width:100%;max-width:502px;height:auto;border-radius:6px;border:1px solid #3265A6;display:block;">
                  </a>
                  <div style="font-size:12px;color:#8BA4C2;margin-top:6px;">Rotulación integral de camiones y furgones con laminado protector UV</div>
                </div>
                <div style="margin-top:10px;">
                  <a href="{tracked_portfolio_url}" target="_blank" style="text-decoration:none;">
                    <img src="{img_van}" alt="Rotulación de Furgonetas y Vehículos de Reparto" width="502" style="width:100%;max-width:502px;height:auto;border-radius:6px;border:1px solid #1C2E47;display:block;">
                  </a>
                  <div style="font-size:12px;color:#8BA4C2;margin-top:6px;">Rotulación en vinil de alta durabilidad para furgonetas de reparto y servicio técnico</div>
                </div>
              </div>
            """
        else:
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
                  <div style="font-size:12px;color:#8BA4C2;margin-top:6px;">Identidad y letrero corpóreo 3D para entrada principal de proyecto</div>
                </div>
                <!-- 2 imágenes en simetría: Numeración 02 + Letras 3D -->
                <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="margin-top:10px;">
                  <tr>
                    <td width="49%" valign="top" style="padding-right:5px;">
                      <a href="{tracked_portfolio_url}" target="_blank" style="text-decoration:none;">
                        <img src="{img_closeup}" alt="Detalle de Numeración 3D en Relieve" width="246" style="width:100%;max-width:246px;height:auto;border-radius:6px;border:1px solid #1C2E47;display:block;">
                      </a>
                      <div style="font-size:11px;color:#8BA4C2;margin-top:5px;">Numeración 3D en relieve para unidades</div>
                    </td>
                    <td width="49%" valign="top" style="padding-left:5px;">
                      <a href="{tracked_portfolio_url}" target="_blank" style="text-decoration:none;">
                        <img src="{img_onestop}" alt="Letras Corpóreas 3D para Fachadas y Locales" width="246" style="width:100%;max-width:246px;height:auto;border-radius:6px;border:1px solid #1C2E47;display:block;">
                      </a>
                      <div style="font-size:11px;color:#8BA4C2;margin-top:5px;">Letras corpóreas 3D para fachadas y locales</div>
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


def attach_inline_images(msg_root: MIMEMultipart, html: str = ""):
    inline_map = {
        "logo_lc": IMAGES_DIR / "Logo-LC-12.png",
        "sun_district": IMAGES_DIR / "email-sun-district.jpg",
        "num_02": IMAGES_DIR / "email-numeracion-02.jpg",
        "onestop_3d": IMAGES_DIR / "email-letrero-3d-onestop.jpg",
        "flota_camion": IMAGES_DIR / "email-flota-camion.jpg",
        "flota_van": IMAGES_DIR / "email-flota-furgoneta.jpg",
    }
    for assets in CUSTOM_HTML_ASSETS.values():
        for cid, img_path in assets.values():
            inline_map[cid] = img_path
    for cid, img_path in inline_map.items():
        if html and f"cid:{cid}" not in html:
            continue
        if img_path.exists():
            subtype = "png" if img_path.suffix.lower() == ".png" else "jpeg"
            img_part = MIMEImage(img_path.read_bytes(), _subtype=subtype)
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
        attach_inline_images(msg_root, html)

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
        server.sendmail(smtp_user, [to_email], msg_root.as_string())


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
    """Revisa por IMAP quién respondió de todas las listas de prospectos, si hubo rebotes, y envía acuse automático si se solicita."""
    prospects = {}
    for p_file in sorted(SCRIPTS_DIR.glob("prospectos_*.csv")):
        with open(p_file, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                em = row.get("correo", "").strip().lower()
                if em:
                    prospects[em] = row.get("empresa", "su empresa").strip()

    already_replied = set()
    if AUTO_REPLY_LOG.exists():
        already_replied = set(AUTO_REPLY_LOG.read_text(encoding="utf-8").splitlines())

    seen_bounces = set()
    if BOUNCES_SEEN_LOG.exists():
        seen_bounces = set(BOUNCES_SEEN_LOG.read_text(encoding="utf-8").splitlines())

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
                bounce_key = f"{date}|{subj}"
                if bounce_key not in seen_bounces:
                    notify_phone(
                        "Rebote de correo B2B",
                        f"Aviso de entrega fallida ({date}): {subj}"
                    )
                    seen_bounces.add(bounce_key)
                    with open(BOUNCES_SEEN_LOG, "a", encoding="utf-8") as bf:
                        bf.write(bounce_key + "\n")
            else:
                for p_email, p_emp in prospects.items():
                    if p_email in sender_lower:
                        replies_found.append((p_emp, p_email, subj, date))
                        if p_email not in already_replied:
                            notify_phone(
                                f"Respuesta B2B: {p_emp}",
                                f"{p_emp} ({p_email}) acaba de responder al correo: '{subj}'"
                            )
                            if auto_reply:
                                reply_subj = subj if subj.lower().startswith("re:") else f"Re: {subj}"
                                ack_html = build_auto_reply_html(p_emp)
                                send_single_email(smtp_host, smtp_port, smtp_user, smtp_pass, p_email, reply_subj, ack_html, include_images=False)
                                print(f"🤖 Auto-respuesta inmediata enviada a {p_emp} (<{p_email}>)")
                            already_replied.add(p_email)
                            with open(AUTO_REPLY_LOG, "a", encoding="utf-8") as af:
                                af.write(p_email + "\n")

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
    parser.add_argument("--notify", action="store_true", help="Envía resumen por push ntfy al finalizar --send")
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
    base_inc_imgs = bool(tpl_info.get("show_gallery", True))

    if args.test:
        target = args.to or smtp_user
        subject, html = build_html_email(args.nombre, args.empresa, args.nicho, args.servicio, args.zona, use_cid=True)
        send_single_email(smtp_host, smtp_port, smtp_user, smtp_pass, target, f"[PRUEBA] {subject}", html, include_images=base_inc_imgs or ("cid:" in html))
        print(f"✅ Correo de prueba enviado exitosamente a {target}!")
        print(f"   Asunto: [PRUEBA] {subject}")
        return

    if args.send_one:
        if not args.to:
            print("❌ Debes indicar --to correo@destino.com")
            return
        subject, html = build_html_email(args.nombre, args.empresa, args.nicho, args.servicio, args.zona, use_cid=True)
        send_single_email(smtp_host, smtp_port, smtp_user, smtp_pass, args.to, subject, html, include_images=base_inc_imgs or ("cid:" in html))
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
        if args.notify:
            notify_phone("Error en campaña B2B", f"No se encontró el CSV: {csv_path}")
        return

    sent_count = 0
    failed_items = []
    context = get_ssl_context()
    with smtplib.SMTP_SSL(smtp_host, smtp_port, context=context) as server:
        server.login(smtp_user, smtp_pass)
        with open(csv_path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                email_to = row.get("correo", "").strip()
                if not email_to or "@" not in email_to or "ejemplo-" in email_to:
                    continue
                nombre = (row.get("nombre") or "").strip() or "Equipo de Proyectos"
                empresa = (row.get("empresa") or "").strip() or "su empresa"
                nicho = (row.get("nicho") or "").strip() or args.nicho
                servicio = (row.get("servicio") or "").strip() or "Señalización de Proyectos"
                zona = (row.get("zona") or "").strip()

                tpl_row = TEMPLATES.get(nicho, TEMPLATES["residencial_punta_cana"])
                subject, html = build_html_email(nombre, empresa, nicho, servicio, zona, use_cid=True)
                row_imgs = bool(tpl_row.get("show_gallery", True)) or ("cid:" in html)
                msg_root = create_mime_message(smtp_user, email_to, subject, html, include_images=row_imgs)

                try:
                    server.sendmail(smtp_user, [email_to], msg_root.as_string())
                    log_sent_email(empresa, email_to, nicho, subject, "ENVIADO_CAMPANA")
                    sent_count += 1
                    print(f"📨 Enviado a {nombre} ({empresa}) <{email_to}> [{nicho}]")
                except smtplib.SMTPServerDisconnected:
                    try:
                        server.connect(smtp_host, smtp_port)
                        server.login(smtp_user, smtp_pass)
                        server.sendmail(smtp_user, [email_to], msg_root.as_string())
                        log_sent_email(empresa, email_to, nicho, subject, "ENVIADO_CAMPANA")
                        sent_count += 1
                        print(f"📨 Enviado (tras reconexión) a {nombre} ({empresa}) <{email_to}> [{nicho}]")
                    except Exception as retry_exc:
                        log_sent_email(empresa, email_to, nicho, subject, f"ERROR: {retry_exc}")
                        failed_items.append(f"{empresa} <{email_to}>: {retry_exc}")
                        print(f"❌ Error enviando a {email_to}: {retry_exc}")
                except Exception as send_exc:
                    log_sent_email(empresa, email_to, nicho, subject, f"ERROR: {send_exc}")
                    failed_items.append(f"{empresa} <{email_to}>: {send_exc}")
                    print(f"❌ Error enviando a {email_to}: {send_exc}")
                time.sleep(4)

    summary = f"Campaña [{args.nicho}] completada: {sent_count} enviados, {len(failed_items)} errores."
    print(f"✅ {summary}")
    if args.notify:
        details = summary if not failed_items else f"{summary} Fallos: {'; '.join(failed_items[:3])}"
        notify_phone(f"Campaña B2B {args.nicho}", details)


if __name__ == "__main__":
    main()
