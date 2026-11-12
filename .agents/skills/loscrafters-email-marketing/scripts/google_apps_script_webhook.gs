/**
 * GOOGLE APPS SCRIPT — CRM + AUTO-RESPUESTA DE EMAIL PARA LOS CRAFTERS SRL
 * 
 * Instrucciones:
 * 1. Crea una hoja de cálculo en Google Sheets ("CRM Leads - Los Crafters").
 * 2. Ve a Extensiones > Apps Script y pega este código.
 * 3. Haz clic en Implementar > Nueva implementación > Tipo: Aplicación web.
 *    - Ejecutar como: Yo
 *    - Quién tiene acceso: Cualquier persona
 * 4. Copia la URL de la aplicación web y colócala en index.html en:
 *    window.LOSCRAFTERS_WEBHOOK_URL = 'TU_URL_AQUI';
 */

function doPost(e) {
  try {
    var sheet = SpreadsheetApp.getActiveSpreadsheet().getActiveSheet();
    
    // Crear encabezados si la hoja está vacía
    if (sheet.getLastRow() === 0) {
      sheet.appendRow([
        'Fecha y Hora',
        'Tipo Formulario',
        'Nombre Completo',
        'Empresa',
        'RNC',
        'Correo Electrónico',
        'Servicio de Interés',
        'Descripción del Proyecto',
        'Estado Seguimiento'
      ]);
    }

    var data = JSON.parse(e.postData.contents);
    var fecha = new Date();

    // 1. Guardar el lead en Google Sheets
    sheet.appendRow([
      fecha,
      data.form_type || 'web',
      data.nombre || '',
      data.empresa || '',
      data.rnc || '',
      data.correo || '',
      data.servicio || '',
      data.proyecto || '',
      'NUEVO - PENDIENTE'
    ]);

    // 2. Enviar notificación interna a Los Crafters
    MailApp.sendEmail({
      to: 'info@loscrafters.net',
      subject: '🚀 Nuevo Lead Web: ' + (data.empresa || data.nombre) + ' (' + (data.servicio || 'General') + ')',
      htmlBody:
        '<h2>Nueva Solicitud desde loscrafters.net</h2>' +
        '<p><strong>Nombre:</strong> ' + (data.nombre || '-') + '</p>' +
        '<p><strong>Empresa:</strong> ' + (data.empresa || '-') + '</p>' +
        '<p><strong>RNC:</strong> ' + (data.rnc || '-') + '</p>' +
        '<p><strong>Correo:</strong> ' + (data.correo || '-') + '</p>' +
        '<p><strong>Servicio:</strong> ' + (data.servicio || '-') + '</p>' +
        '<p><strong>Proyecto:</strong><br>' + (data.proyecto || '-') + '</p>'
    });

    // 3. Si el cliente dejó su correo, enviarle respuesta automática inmediata con el catálogo
    if (data.correo && data.correo.indexOf('@') !== -1) {
      var nombreCorto = (data.nombre || 'estimado cliente').split(' ')[0];
      MailApp.sendEmail({
        to: data.correo,
        subject: 'Recibimos tu solicitud en Los Crafters — Catálogo y Próximos Pasos',
        htmlBody:
          '<div style="font-family: Arial, sans-serif; max-width: 600px; color: #0A0F1A; line-height: 1.6;">' +
          '<div style="background: #0A0F1A; padding: 24px; text-align: center; border-bottom: 3px solid #3265A6;">' +
          '<h2 style="color: #F0F6FF; margin: 0; letter-spacing: 1px;">LOS CRAFTERS</h2>' +
          '<p style="color: #5BA3F5; margin: 4px 0 0; font-size: 12px; text-transform: uppercase;">Taller Publicitario · Santo Domingo, RD</p>' +
          '</div>' +
          '<div style="padding: 28px 24px; background: #ffffff; border: 1px solid #e2e8f0;">' +
          '<p>Hola <strong>' + nombreCorto + '</strong>,</p>' +
          '<p>Gracias por contactar a <strong>Los Crafters SRL</strong>. Hemos recibido los detalles de tu requerimiento de <strong>' + (data.servicio || 'publicidad y rotulación') + '</strong> para <strong>' + (data.empresa || 'tu empresa') + '</strong>.</p>' +
          '<p>Para agilizar tu cotización formal (con Comprobante Fiscal), puedes responder directamente a este correo adjuntando:</p>' +
          '<ul>' +
          '<li>Fotografía del área, fachada o vehículo a intervenir.</li>' +
          '<li>Medidas aproximadas (ancho x alto).</li>' +
          '<li>Logo de tu marca en formato vectorial (PDF, AI o EPS).</li>' +
          '</ul>' +
          '<p style="margin: 24px 0;">' +
          '<a href="https://drive.google.com/file/d/1S1DoP-ZQEbCIRiCjIFdfrzE1bGpqKmhf/view?usp=sharing" style="background: #3265A6; color: #ffffff; padding: 12px 22px; text-decoration: none; border-radius: 4px; font-weight: bold; display: inline-block;">Ver Catálogo de Proyectos (PDF)</a>' +
          '</p>' +
          '<p>Si prefieres atención inmediata por WhatsApp, escríbenos al <a href="https://wa.me/18294109362">+1 (829) 410-9362</a> o llámanos al +1 (809) 568-6663.</p>' +
          '<p style="margin-top: 28px;">Atentamente,<br><strong>Equipo Comercial y Producción</strong><br>Los Crafters SRL · <a href="https://www.loscrafters.net">www.loscrafters.net</a></p>' +
          '</div>' +
          '</div>'
      });
    }

    return ContentService.createTextOutput(JSON.stringify({ status: 'ok' })).setMimeType(ContentService.MimeType.JSON);
  } catch (err) {
    return ContentService.createTextOutput(JSON.stringify({ status: 'error', message: err.toString() })).setMimeType(ContentService.MimeType.JSON);
  }
}
