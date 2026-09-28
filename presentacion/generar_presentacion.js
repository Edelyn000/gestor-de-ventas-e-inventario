const pptxgen = require('pptxgenjs');
const path = require('path');
const fs = require('fs');

const html2pptx = require('./html2pptx.js');

const BASE = __dirname;
const IMG = path.join(BASE, 'img');
const TEMP = path.join(BASE, 'temp_slides');

const W = 720, H = 405;
const TOTAL = 26;

function imgURL(fileName) {
  // Use relative path from temp_slides/ to img/
  return '../img/' + fileName;
}

const COLORS = {
  navy: '#1a2744',
  gold: '#c9a84c',
  white: '#ffffff',
  light: '#f5f6fa',
  text: '#2c2c2c',
  gray: '#555555',
  bggray: '#e8e8e8',
};

function escudoHTML(size) {
  return `<img src="${imgURL('escudo_fec.png')}" style="width:${size}; height:${size};">`;
}

function slideCSS(specificCSS) {
  return `
html { background: ${COLORS.white}; }
body {
  width: ${W}pt; height: ${H}pt; margin: 0; padding: 0;
  font-family: Arial, Helvetica, sans-serif;
  display: flex; flex-direction: column;
}
.header {
  width: ${W}pt; height: 42pt; background: ${COLORS.navy};
  display: flex; align-items: center; position: relative;
}
.header img { height: 28pt; margin-left: 12pt; }
.header p {
  color: #ffffff; font-size: 16pt; font-weight: bold;
  margin: 0 0 0 10pt;
}
.header .num {
  position: absolute; right: 15pt;
  color: rgba(255,255,255,0.5); font-size: 10pt;
  margin: 0;
}
.titlebar {
  width: ${W}pt; height: 28pt; background: ${COLORS.gold};
  display: flex; align-items: center;
}
.titlebar p {
  color: #ffffff; font-size: 13pt; font-weight: bold;
  margin: 0 0 0 15pt;
}
.content {
  flex: 1; width: ${W}pt;
  background: ${COLORS.white};
  padding: 12pt 22pt; box-sizing: border-box;
  overflow: hidden;
}
.content ul { margin: 3pt 0; padding-left: 18pt; }
.content li { font-size: 10.5pt; color: ${COLORS.text}; margin: 2pt 0; line-height: 1.35; }
.content p { font-size: 10.5pt; color: ${COLORS.text}; margin: 4pt 0; line-height: 1.35; }
.content h2 { font-size: 12pt; color: ${COLORS.navy}; margin: 6pt 0 3pt 0; }
.content .subtitle { font-size: 11pt; color: ${COLORS.navy}; font-weight: bold; margin: 6pt 0 2pt 0; }
.content .gold { color: ${COLORS.gold}; font-weight: bold; }
.footer {
  width: ${W}pt; height: 14pt; background: ${COLORS.light};
  display: flex; align-items: center; justify-content: space-between;
}
.footer p { font-size: 7pt; color: #999; margin: 0 12pt; }
${specificCSS || ''}
`;
}

function writeHTML(name, html) {
  const filePath = path.join(TEMP, name);
  fs.writeFileSync(filePath, html, 'utf-8');
  return filePath;
}

async function addSlide(pres, title, contentHTML, slideNum) {
  const html = `<!DOCTYPE html>
<html><head><meta charset="utf-8"><style>${slideCSS()}</style></head>
<body>
<div class="header">${escudoHTML('28pt')}<p>PROYECTO FINAL</p><p class="num">${slideNum}/${TOTAL}</p></div>
<div class="titlebar"><p>${title}</p></div>
<div class="content">${contentHTML}</div>
<div class="footer"><p>Sistema Financiero</p><p>Hernández, Edelyn - CI: 28109107</p></div>
</body></html>`;

  const filePath = writeHTML(`slide_${String(slideNum).padStart(2, '0')}.html`, html);
  const { slide } = await html2pptx(filePath, pres);
  return slide;
}

async function addSlideCompact(pres, title, contentHTML, slideNum) {
  const css = slideCSS() + `
.header { height: 30pt; }
.header img { height: 20pt; }
.header p { font-size: 12pt; }
.titlebar { height: 20pt; }
.titlebar p { font-size: 11pt; }
.footer { height: 10pt; }
.content { padding: 2pt 6pt; }`;
  const html = `<!DOCTYPE html>
<html><head><meta charset="utf-8"><style>${css}</style></head>
<body>
<div class="header">${escudoHTML('20pt')}<p>PROYECTO FINAL</p><p class="num">${slideNum}/${TOTAL}</p></div>
<div class="titlebar"><p>${title}</p></div>
<div class="content">${contentHTML}</div>
<div class="footer"><p>Sistema Financiero</p><p>Hernández, Edelyn - CI: 28109107</p></div>
</body></html>`;

  const filePath = writeHTML(`slide_${String(slideNum).padStart(2, '0')}.html`, html);
  const { slide } = await html2pptx(filePath, pres);
  return slide;
}

async function addSlideCustom(pres, bodyCSS, bodyContent) {
  const html = `<!DOCTYPE html>
<html><head><meta charset="utf-8"><style>${bodyCSS}</style></head>
<body>${bodyContent}</body></html>`;

  const filePath = writeHTML(`custom_${Date.now()}.html`, html);
  const { slide } = await html2pptx(filePath, pres);
  return slide;
}

function makeBullets(items) {
  return '<ul>' + items.map(i => `<li>${i}</li>`).join('') + '</ul>';
}

function makeCols(leftHTML, rightHTML, leftPct) {
  leftPct = leftPct || 50;
  return `<div style="display:flex; gap:15pt; width:100%;">
<div style="flex:${leftPct}; min-width:0;">${leftHTML}</div>
<div style="flex:${100-leftPct}; min-width:0;">${rightHTML}</div>
</div>`;
}

async function main() {
  const pres = new pptxgen();
  pres.layout = 'LAYOUT_16x9';
  pres.author = 'Hernández, Edelyn';
  pres.title = 'Sistema Financiero - Proyecto Final';

  // --- Section presentations (copies of slides) ---
  const LAMINAS_DIR = path.join(BASE, 'Laminas_Individuales');
  fs.mkdirSync(LAMINAS_DIR, { recursive: true });

  function newSec(title) {
    const p = new pptxgen();
    p.layout = 'LAYOUT_16x9';
    p.author = 'Hernández, Edelyn';
    p.title = title;
    return p;
  }

  const sec = {
    eps:        newSec('Entradas, Procesos y Salidas'),
    ciclo:      newSec('Ciclo de Vida'),
    tecnologia: newSec('Tecnologías'),
    dfd:        newSec('Diagramas de Flujo de Datos'),
    diccDFD:    newSec('Diccionario de Datos DFD'),
    er:         newSec('Diagrama E-R y Diccionario'),
    interfaces: newSec('Interfaces'),
    pruebas:    newSec('Pruebas'),
    mant:       newSec('Mantenimiento'),
    conc:       newSec('Conclusiones'),
  };
  // Set slide totals per section
  sec.eps._total = 1;
  sec.ciclo._total = 1;
  sec.tecnologia._total = 1;
  sec.dfd._total = 7;
  sec.diccDFD._total = 7;
  sec.er._total = 3;
  sec.interfaces._total = 1;
  sec.pruebas._total = 1;
  sec.mant._total = 1;
  sec.conc._total = 1;

  // Helper: add slide to main + section
  async function addSlideTo(presObj, title, contentHTML, slideNum, total, secKey) {
    const slide = await addSlide(presObj, title, contentHTML, slideNum, total);
    if (secKey && sec[secKey]) {
      const secNum = sec[secKey]._num = (sec[secKey]._num || 0) + 1;
      const secTotal = sec[secKey]._total || 1;
      await addSlide(sec[secKey], title, contentHTML, secNum, secTotal);
    }
    return slide;
  }
  async function addSlideCompactTo(presObj, title, contentHTML, slideNum, total, secKey) {
    const slide = await addSlideCompact(presObj, title, contentHTML, slideNum, total);
    if (secKey && sec[secKey]) {
      const secNum = sec[secKey]._num = (sec[secKey]._num || 0) + 1;
      const secTotal = sec[secKey]._total || 1;
      await addSlideCompact(sec[secKey], title, contentHTML, secNum, secTotal);
    }
    return slide;
  }

  fs.mkdirSync(TEMP, { recursive: true });

  // ===========================
  // SLIDE 1 - Portada
  // ===========================
  const portadaCSS = `
html, body {
  width: ${W}pt; height: ${H}pt; margin: 0; padding: 0;
  font-family: Arial, Helvetica, sans-serif;
  background: ${COLORS.navy};
}
.wrapper {
  width: ${W}pt; height: ${H}pt; position: relative;
  display: flex; flex-direction: column; align-items: center; justify-content: center;
}
.logo-left { position: absolute; left: 25pt; top: 22pt; }
.logo-right { position: absolute; right: 25pt; top: 22pt; }
.uni {
  color: ${COLORS.gold}; font-size: 12pt; text-align: center;
  margin: 0 0 5pt 0; line-height: 1.6;
}
.line { width: 150pt; height: 1.5pt; background: ${COLORS.gold}; margin: 8pt 0; }
.titulo {
  color: #ffffff; font-size: 17pt; font-weight: bold;
  margin: 3pt 0; text-align: center; letter-spacing: 3pt;
}
.subtitulo {
  color: ${COLORS.gold}; font-size: 13pt; margin: 2pt 0; text-align: center;
  letter-spacing: 1pt;
}
.label { color: rgba(255,255,255,0.45); font-size: 9pt; margin: 10pt 0 2pt 0; text-align: center; }
.nombre { color: #ffffff; font-size: 12pt; font-weight: bold; margin: 1pt 0; text-align: center; }
.ci { color: #aaa; font-size: 9pt; margin: 1pt 0; text-align: center; }
.periodo { color: ${COLORS.gold}; font-size: 10pt; margin: 6pt 0 0 0; text-align: center; }`;

  const portadaContent = `
<div class="wrapper">
<div class="logo-left">${escudoHTML('60pt')}</div>
<div class="logo-right"><img src="${imgURL('image1.png')}" style="width:38pt; height:44pt;"></div>
<p class="uni">UNIVERSIDAD DEL ZULIA<br>FACULTAD EXPERIMENTAL DE CIENCIAS<br>DIVISIÓN DE PROGRAMAS ESPECIALES<br>LICENCIATURA EN COMPUTACIÓN</p>
<div class="line"></div>
<p class="titulo">DESARROLLO DE SISTEMAS</p>
<p class="subtitulo">Sistema Financiero</p>
<div class="line"></div>
<p class="label">Presentado por</p>
<p class="nombre">Hernández, Edelyn</p>
<p class="ci">CI: 28109107</p>
<p class="periodo">PERIODO II - 2026</p>
</div>`;

  await addSlideCustom(pres, portadaCSS, portadaContent);
  console.log('Slide 1: Portada');

  // ===========================
  // SLIDE 2 - Agenda
  // ===========================
  const agendaItems = [
    'Identificar: entradas, procesos y salidas',
    'Ciclo de Vida seleccionado (resumen)',
    'Tecnologías y Herramientas de Desarrollo',
    'Diagrama de Flujo de Datos (DFD)',
    'Diccionario de Datos (DFD)',
    'Diagrama Entidad – Relación',
    'Diccionario de Datos (Diagrama E-R)',
    'Interfaces de Entrada / Salida',
    'Demostración de Pruebas al SI',
    'Plan de Mantenimiento',
    'Personal que participó (soporte - minuta)',
  ];
  await addSlide(pres, 'AGENDA', makeBullets(agendaItems), 2);
  console.log('Slide 2: Agenda');

  // ===========================
  // SLIDE 3 - Entradas → Procesos → Salidas
  // ===========================
  const entradasList = `<ul>
    <li>Ingresar producto (nombre, categoría, precio, stock mínimo)</li>
    <li>Ingresar cantidades (stock inicial, movimientos)</li>
    <li>Ingresar precio (VES o USD)</li>
    <li>Ingresar tipos de pago (efectivo BS/USD, pago móvil, tarjeta, bio-pago)</li>
    <li>Registrar usuarios (credenciales)</li>
    <li>Fecha de compra/venta</li>
    <li>Cambios del día (tasa BCV automática)</li>
    <li>Movimientos de inventario (compras, ajustes, mermas, devoluciones)</li>
  </ul>`;
  const procesosList = `<ul>
    <li>Validar existencia del producto e inventario suficiente</li>
    <li>Convertir precio USD a bolívares (tasa BCV)</li>
    <li>Calcular total de venta (subtotales + total)</li>
    <li>Registrar tipo de pago (5 métodos, pagos mixtos VES/USD)</li>
    <li>Registrar tasa BCV aplicada en la venta</li>
    <li>Actualizar inventario con auditoría de movimientos</li>
    <li>Generar factura (FAC-YYYYMMDD-NNN)</li>
    <li>Autenticar usuarios con bcrypt</li>
    <li>CRUD completo de productos (crear, editar, eliminar)</li>
    <li>Control de inventario (compra, venta, merma, ajuste, devolución)</li>
    <li>Generar reporte diario consolidado</li>
    <li>Exportar reporte a Excel</li>
  </ul>`;
  const salidasList = `<ul>
    <li>Comprobante de venta: productos, precio BCV, tipo de pago, tasa aplicada, fecha/hora</li>
    <li>Factura detallada con formato FAC-YYYYMMDD-NNN</li>
    <li>Inventarios actualizados por producto</li>
    <li>Reportes diarios consolidados (ventas, movimientos, tasas)</li>
    <li>Reporte exportable a Excel</li>
    <li>Dashboard: ventas hoy, stock bajo, sin stock, tasa BCV</li>
    <li>Tabla de productos con alerta de stock bajo</li>
    <li>Historial completo de ventas</li>
    <li>Alertas visuales de stock bajo / sin stock</li>
  </ul>`;

  const epsContent = `
  <div style="display:flex; gap:6pt; align-items:stretch; height:100%;">
    <div style="flex:2.5; background:#f5f6fa; padding:6pt 8pt; border-radius:4pt; display:flex; flex-direction:column;">
      <p style="font-weight:bold; color:${COLORS.gold}; font-size:10pt; text-align:center; margin:0 0 4pt 0;">ENTRADAS</p>
      <div style="font-size:8.5pt;">${entradasList}</div>
    </div>
    <div style="flex:0.5; display:flex; align-items:center; justify-content:center;">
      <p style="font-size:18pt; color:${COLORS.gold}; margin:0;">→</p>
    </div>
    <div style="flex:4; background:${COLORS.navy}; padding:6pt 10pt; border-radius:4pt; display:flex; flex-direction:column;">
      <p style="font-weight:bold; color:#ffffff; font-size:10pt; text-align:center; margin:0 0 4pt 0;">PROCESOS</p>
      <div style="font-size:8.5pt; color:#ffffff;">${procesosList.replace(/<li>/g, '<li style="color:#ffffff;">')}</div>
    </div>
    <div style="flex:0.5; display:flex; align-items:center; justify-content:center;">
      <p style="font-size:18pt; color:${COLORS.gold}; margin:0;">→</p>
    </div>
    <div style="flex:2.5; background:#f5f6fa; padding:6pt 8pt; border-radius:4pt; display:flex; flex-direction:column;">
      <p style="font-weight:bold; color:${COLORS.gold}; font-size:10pt; text-align:center; margin:0 0 4pt 0;">SALIDAS</p>
      <div style="font-size:8.5pt;">${salidasList}</div>
    </div>
  </div>`;

  await addSlideTo(pres, 'ENTRADAS → PROCESOS → SALIDAS', epsContent, 3, TOTAL, 'eps');
  console.log('Slide 3: Entradas → Procesos → Salidas');

  // ===========================
  // SLIDE 4 - Ciclo de Vida
  // ===========================
  const cicloContent = makeCols(
    `<p class="subtitle">Metodología Seleccionada:</p>
     <p>Ciclo de Vida de Llorens Fábregas (II) (Modelo Cascada/Secuencial). Seleccionado por su estructura predecible para proyectos de mediana complejidad con requisitos predefinidos.</p>
     <p class="subtitle">Problema Actual en el Abasto:</p>
     <ul>
       <li>Inexistencia de un control de inventario sistemático.</li>
       <li>Pérdida de tiempo en cálculos manuales de conversión VES / USD.</li>
       <li>Dificultad para auditar y controlar el total de las ventas diarias.</li>
     </ul>
     <p class="subtitle">Ventajas y Desventajas:</p>
     <ul>
       <li><span style="color:#2e7d32;">✔</span> Gestión ordenada por fases secuenciales y requisitos estables.</li>
       <li><span style="color:#2e7d32;">✔</span> Énfasis en diseño de BD para evitar fallas a largo plazo.</li>
       <li><span style="color:#c62828;">✘</span> Feedback tardío del cliente (mitigado con un robusto plan de pruebas previo al despliegue).</li>
     </ul>`,
    `<p class="subtitle">Fases del Ciclo de Vida Aplicadas:</p>
     <p><b>1. Requisitos:</b><br>Definición de necesidades: registro diario de ventas, alertas de stock bajo, cálculo bimonetario con tasa del día y actualización de inventario por compras.</p>
     <p><b>2. Análisis y Diseño:</b><br>Migración de los procesos manuales del abasto a un menú interactivo simple (CRUD de productos, facturación, tasa y reporte diario).</p>
     <p><b>3. Construcción:</b><br>Creación del esquema relacional de base de datos SQLite y codificación de las interfaces en PyQt6.</p>
     <p><b>4. Pruebas y Mantenimiento:</b><br>Verificación de la conversión de monedas, registro contable correcto y monitoreo continuo de fallas en el local comercial.</p>`,
    50
  );

  await addSlideTo(pres, 'CICLO DE VIDA SELECCIONADO', cicloContent, 4, TOTAL, 'ciclo');
  console.log('Slide 4: Ciclo de Vida');

  // ===========================
  // SLIDE 5 - Tecnologías
  // ===========================
  const tecContent = `
  <div style="display:flex; gap:12pt;">
    <div style="flex:1;">
      <p class="subtitle">Lenguajes de Programación:</p>
      <p>Python >=3.14: Desarrollo moderno, rápido, con tipado estático y alta legibilidad.</p>
      <p class="subtitle">Frameworks Frontend / Backend:</p>
      <p>PyQt6 (>=6.11): Biblioteca industrial de interfaz gráfica de escritorio. Proporciona controles reactivos, layouts dinámicos y procesamiento multihilo.</p>
      <p class="subtitle">Base de Datos:</p>
      <p>SQLite: Base de datos relacional ligera, embebida y de archivo único. No requiere administración de servidores externos.</p>
      <p>SQLModel (>=0.0.38): ORM híbrido (hijo de Pydantic y SQLAlchemy) que unifica el tipado de Python con el esquema de tablas SQL.</p>
    </div>
    <div style="flex:1;">
      <p class="subtitle">Herramientas de Apoyo e Integración:</p>
      <ul>
        <li><span style="color:#2e7d32;">✔</span> scraper-bcv: Consulta de tasas BCV del día en tiempo real.</li>
        <li><span style="color:#2e7d32;">✔</span> bcrypt: Hasheo seguro y encriptación de claves de usuario.</li>
        <li><span style="color:#2e7d32;">✔</span> openpyxl: Generación programática de informes en Excel.</li>
        <li><span style="color:#2e7d32;">✔</span> pyqtgraph: Renderizado rápido de gráficos de ventas semanales.</li>
      </ul>
      <p class="subtitle">Herramientas Compartidas y Calidad:</p>
      <p>pytest y pytest-qt (Pruebas unitarias/UI), Ruff (Linter) y Mypy (Tipos).</p>
    </div>
  </div>`;

  await addSlideTo(pres, 'TECNOLOGÍAS Y HERRAMIENTAS DE DESARROLLO', tecContent, 5, TOTAL, 'tecnologia');
  console.log('Slide 5: Tecnologías');

  // ===========================
  // SLIDE 6 - DFD Contexto
  // ===========================
  function dfdSlide(imageName) {
    return `<div style="display:flex; justify-content:center; align-items:center; height:100%; width:100%;">
<img src="${imgURL(imageName)}" style="max-width:100%; max-height:100%; object-fit:contain;">
</div>`;
  }
  await addSlideTo(pres, 'DIAGRAMA DE FLUJO DE DATOS - DFD: Nivel 0 (Contexto)', dfdSlide('Nivel_0_Contexto.png'), 6, TOTAL, 'dfd');
  console.log('Slide 6: DFD Contexto');

  // ===========================
  // SLIDE 7 - DFD Nivel 1
  // ===========================
  await addSlideTo(pres, 'DIAGRAMA DE FLUJO DE DATOS - DFD: Nivel 1', dfdSlide('Nivel_1.png'), 7, TOTAL, 'dfd');
  console.log('Slide 7: DFD Nivel 1');

  // ===========================
  // SLIDE 8 - DFD Nivel 2 (Gestión Inventario)
  // ===========================
  await addSlideTo(pres, 'DIAGRAMA DE FLUJO DE DATOS - DFD: Nivel 2 (Gestión de Inventario)', dfdSlide('Nivel_2_1_Gestionar_Inventario.png'), 8, TOTAL, 'dfd');
  console.log('Slide 8: DFD Nivel 2 (Gestión Inventario)');

  // ===========================
  // SLIDE 9 - DFD Nivel 2 (Procesar Ventas)
  // ===========================
  await addSlideTo(pres, 'DIAGRAMA DE FLUJO DE DATOS - DFD: Nivel 2 (Procesar Ventas)', dfdSlide('Nivel_2_2_Procesar_Ventas.png'), 9, TOTAL, 'dfd');
  console.log('Slide 9: DFD Nivel 2 (Procesar Ventas)');

  // ===========================
  // SLIDE 10 - DFD Nivel 2 (Actualizar Tasa BCV)
  // ===========================
  await addSlideTo(pres, 'DIAGRAMA DE FLUJO DE DATOS - DFD: Nivel 2 (Actualizar Tasa BCV)', dfdSlide('Nivel_2_3_Actualizar_Tasa_BCV.png'), 10, TOTAL, 'dfd');
  console.log('Slide 10: DFD Nivel 2 (Actualizar Tasa BCV)');

  // ===========================
  // SLIDE 11 - DFD Nivel 2 (Generar Reportes)
  // ===========================
  await addSlideTo(pres, 'DIAGRAMA DE FLUJO DE DATOS - DFD: Nivel 2 (Generar Reportes)', dfdSlide('Nivel_2_5_Generar_Reportes.png'), 11, TOTAL, 'dfd');
  console.log('Slide 11: DFD Nivel 2 (Generar Reportes)');

  // ===========================
  // SLIDE 12 - DFD Nivel 2 (Gestionar Usuarios)
  // ===========================
  await addSlideTo(pres, 'DIAGRAMA DE FLUJO DE DATOS - DFD: Nivel 2 (Gestionar Usuarios)', dfdSlide('Nivel_2_6_Gestionar_Usuarios.png'), 12, TOTAL, 'dfd');
  console.log('Slide 12: DFD Nivel 2 (Gestionar Usuarios)');

  // ===========================
  // Helper: fichas por página (vertical)
  // ===========================
  function diccPage(images, maxH) {
    maxH = maxH || 88;
    const gap = images.length > 3 ? 6 : 10;
    const imgs = images.map(img =>
      `<img src="${imgURL(img)}" style="max-width:95%; max-height:${maxH}pt; object-fit:contain;">`
    ).join('');
    return `<div style="display:flex; flex-direction:column; justify-content:center; align-items:center; gap:${gap}pt; height:100%;">${imgs}</div>`;
  }

  function diccGrid(images) {
    const rows = [];
    for (let i = 0; i < images.length; i += 2) {
      const chunk = images.slice(i, i + 2);
      const single = chunk.length === 1;
      const imgs = chunk.map(img =>
        single
          ? `<div style="width:50%; display:flex; justify-content:center; align-items:center; margin:0 auto; overflow:hidden;">
              <img src="${imgURL(img)}" style="width:100%; height:100%; object-fit:contain;">
            </div>`
          : `<div style="flex:1; display:flex; justify-content:center; align-items:center; min-width:0; overflow:hidden;">
              <img src="${imgURL(img)}" style="width:100%; height:100%; object-fit:contain;">
            </div>`
      ).join('');
      rows.push(`<div style="display:flex; gap:8pt; width:100%; flex:1; min-height:0; overflow:hidden;">${imgs}</div>`);
    }
    return `<div style="display:flex; flex-direction:column; gap:4pt; width:100%; height:100%; overflow:hidden;">${rows.join('')}</div>`;
  }

  let sNum = 13;

  // SLIDE 13 - Diccionario DFD: Entidades
  await addSlideCompactTo(pres, 'DICCIONARIO DE DATOS DFD – ENTIDADES EXTERNAS',
    diccGrid(['EN_E1_Administrador.png', 'EN_E2_Vendedor.png', 'EN_E3_Cliente.png']), sNum++, TOTAL, 'diccDFD');
  console.log(`Slide ${sNum-1}: Diccionario DFD – Entidades`);

  // SLIDE 14 - Diccionario DFD: Procesos I
  await addSlideCompactTo(pres, 'DICCIONARIO DE DATOS DFD – PROCESOS (1/2)',
    diccGrid(['P0_Sistema_Gestion_Inventario_Finanzas.png', 'P1_Gestionar_Inventario.png', 'P2_Procesar_Ventas.png']), sNum++, TOTAL, 'diccDFD');
  console.log(`Slide ${sNum-1}: Diccionario DFD – Procesos I`);

  // SLIDE 15 - Diccionario DFD: Procesos II
  await addSlideCompactTo(pres, 'DICCIONARIO DE DATOS DFD – PROCESOS (2/2)',
    diccGrid(['P3_Registrar_Compras.png', 'P4_Actualizar_Tasa_BCV.png', 'P5_Generar_Reportes.png', 'P6_Gestionar_Usuarios.png']), sNum++, TOTAL, 'diccDFD');
  console.log(`Slide ${sNum-1}: Diccionario DFD – Procesos II`);

  // SLIDE 16 - Diccionario DFD: Almacenes I
  await addSlideCompactTo(pres, 'DICCIONARIO DE DATOS DFD – ALMACENES DE DATOS (1/2)',
    diccGrid(['AL_D1_Productos.png', 'AL_D2_Ventas.png', 'AL_D3_Movimiento_Inventario.png']), sNum++, TOTAL, 'diccDFD');
  console.log(`Slide ${sNum-1}: Diccionario DFD – Almacenes I`);

  // SLIDE 17 - Diccionario DFD: Almacenes II
  await addSlideCompactTo(pres, 'DICCIONARIO DE DATOS DFD – ALMACENES DE DATOS (2/2)',
    diccGrid(['AL_D4_Tasas_BCV.png', 'AL_D5_Reportes.png', 'AL_D6_Usuario.png']), sNum++, TOTAL, 'diccDFD');
  console.log(`Slide ${sNum-1}: Diccionario DFD – Almacenes II`);

  // SLIDE 18 - Diccionario DFD: Flujos I
  await addSlideCompactTo(pres, 'DICCIONARIO DE DATOS DFD – FLUJOS DE DATOS (1/2)',
    diccGrid(['FD_FD1_Datos_de_Venta.png', 'FD_FD2_Datos_de_Inventario.png', 'FD_FD3_Datos_de_Compra.png']), sNum++, TOTAL, 'diccDFD');
  console.log(`Slide ${sNum-1}: Diccionario DFD – Flujos I`);

  // SLIDE 19 - Diccionario DFD: Flujos II
  await addSlideCompactTo(pres, 'DICCIONARIO DE DATOS DFD – FLUJOS DE DATOS (2/2)',
    diccGrid(['FD_FD4_Tasa_BCV.png', 'FD_FD5_Reportes_Generados.png', 'FD_FD6_Datos_de_Usuario.png']), sNum++, TOTAL, 'diccDFD');
  console.log(`Slide ${sNum-1}: Diccionario DFD – Flujos II`);

  // Resume sequential numbering from sNum (20)

  // ===========================
  // SLIDE 14 - Diagrama Entidad-Relación
  // ===========================
  const erContent = `
  <div style="display:flex; flex-direction:column; justify-content:center; align-items:center; height:100%;">
    <img src="../img/diagrama_entidad_relacion.png" style="max-width:95%; max-height:95%; object-fit:contain;">
  </div>`;

  await addSlideTo(pres, 'DIAGRAMA ENTIDAD – RELACIÓN', erContent, 20, TOTAL, 'er');
  console.log('Slide 20: Diagrama Entidad-Relación');

  // ===========================
  // SLIDE 21-22 - Diccionario E-R (2 arriba, 2 abajo)
  // ===========================
  await addSlideCompactTo(pres, 'DICCIONARIO DE DATOS (E-R) — 1/2',
    diccGrid(['DB_PRODUCTOS.png', 'DB_VENTAS.png', 'DB_VENTA_DETALLES.png', 'DB_MOV_INVENTARIO.png']), 21, TOTAL, 'er');
  console.log('Slide 21: Diccionario E-R (1/2)');

  await addSlideCompactTo(pres, 'DICCIONARIO DE DATOS (E-R) — 2/2',
    diccGrid(['DB_TASAS_CAMBIO.png', 'DB_USUARIOS.png', 'DB_REPORTES_DIARIOS.png']), 22, TOTAL, 'er');
  console.log('Slide 22: Diccionario E-R (2/2)');

  // ===========================
  // SLIDE 16 - Interfaces Entrada/Salida
  // ===========================
  const ifContent = makeCols(
    `<p class="subtitle">Interfaces de Entrada de Datos:</p>
     <ul>
       <li><b>Ventana de Login (Entrada):</b><br>Captura credenciales de usuario y restringe accesos no autorizados mediante bcrypt.</li>
       <li><b>Formulario Producto (Entrada):</b><br>Permite ingresar y editar códigos, nombres, categorías, precios bimonetarios y stock inicial de mercancía.</li>
       <li><b>Registrar Venta / POS (Entrada):</b><br>Panel interactivo donde se escanean productos, se introduce la tasa de cambio y se desglosa el monto cobrado por cada método de pago.</li>
     </ul>`,
    `<p class="subtitle">Interfaces de Salida (Informes y Consultas):</p>
     <ul>
       <li><b>Dashboard / Pantalla de Inicio (Salida):</b><br>Resumen ejecutivo con totales de venta en VES y USD, indicador reactivo de tasa BCV y gráfico dinámico de ventas semanales (pyqtgraph).</li>
       <li><b>Alertas de Stock Bajo (Salida):</b><br>Panel del inventario resalta automáticamente en color de advertencia los productos con stock inferior al mínimo.</li>
       <li><b>Reporte de Cierre Diario en Excel (Salida):</b><br>Generación y descarga de archivo de hoja de cálculo formateado con resúmenes por método de pago para control administrativo.</li>
     </ul>`,
    50
  );

  await addSlideTo(pres, 'INTERFACES DE ENTRADA / SALIDA', ifContent, 23, TOTAL, 'interfaces');
  console.log('Slide 23: Interfaces');

  // ===========================
  // SLIDE 17 - Pruebas
  // ===========================
  const pruebasContent = `
  <div style="background:#f0f0f0; padding:6pt 10pt; border-left:4pt solid ${COLORS.gold}; margin-bottom:6pt;">
    <p><b>Pruebas Funcionales (POS e Inventario):</b><br>
    Verificación completa del registro de ventas en bolívares y dólares, validando el cálculo exacto del cambio a entregar y el decremento inmediato en el almacén de stock.</p>
  </div>
  <div style="background:#f0f0f0; padding:6pt 10pt; border-left:4pt solid ${COLORS.gold}; margin-bottom:6pt;">
    <p><b>Pruebas No Funcionales (Seguridad y Rendimiento):</b><br>
    Hasheo de contraseñas de usuarios con bcrypt para impedir lecturas en texto plano en la BD. Validación de tiempos de respuesta menores a 100ms en la UI ante búsquedas en caliente.</p>
  </div>
  <div style="background:#f0f0f0; padding:6pt 10pt; border-left:4pt solid ${COLORS.gold};">
    <p><b>Pruebas Unitarias y de UI Automatizadas (pytest):</b></p>
    <ul style="margin-bottom:0;">
      <li><span style="color:#2e7d32;">✔</span> <b>Total de la Suite:</b> 172 tests unitarios ejecutados mediante integración continua.</li>
      <li><span style="color:#2e7d32;">✔</span> <b>Pruebas de Interfaz (pytest-qt):</b> 36 pruebas automatizadas de UI que simulan las acciones físicas del cajero (tipeo, selección y clics) y validan que las pantallas reaccionen correctamente sin fallas.</li>
    </ul>
  </div>`;

  await addSlideTo(pres, 'PRUEBAS DE SISTEMAS DE INFORMACIÓN', pruebasContent, 24, TOTAL, 'pruebas');
  console.log('Slide 24: Pruebas');

  // ===========================
  // SLIDE 18 - Plan de Mantenimiento
  // ===========================
  const mantContent = makeCols(
    `<div style="background:#f0f0f0; padding:6pt 10pt; border-left:4pt solid ${COLORS.gold}; margin-bottom:6pt;">
      <p><b>Mantenimiento Correctivo (Resolución de fallas):</b><br>
      Implementación de bitácoras de logs automáticos localizadas en 'logs/'. Registra conexiones con el BCV y fallas internas del sistema PyQt6 para reparaciones inmediatas.</p>
    </div>
    <div style="background:#f0f0f0; padding:6pt 10pt; border-left:4pt solid ${COLORS.gold};">
      <p><b>Mantenimiento Adaptativo (Cambios del entorno):</b><br>
      Integración de Alembic para realizar migraciones de esquemas en la base de datos local SQLite, permitiendo agregar columnas y tablas en el futuro sin borrar las ventas anteriores.</p>
    </div>`,
    `<div style="background:#f0f0f0; padding:6pt 10pt; border-left:4pt solid ${COLORS.gold}; margin-bottom:6pt;">
      <p><b>Mantenimiento Perfectivo (Nuevas funcionalidades):</b><br>
      Planificación de mejoras del software como impresión de tickets en impresoras térmicas de 80mm y soporte de cuentas por pagar a proveedores.</p>
    </div>
    <div style="background:#f0f0f0; padding:6pt 10pt; border-left:4pt solid ${COLORS.gold};">
      <p><b>Mantenimiento Preventivo (Protección de datos):</b><br>
      Copias de seguridad diarias del archivo físico único 'database/database.db' de manera automatizada hacia una unidad de almacenamiento externa o nube privada.</p>
    </div>`,
    50
  );

  await addSlideTo(pres, 'PLAN DE MANTENIMIENTO', mantContent, 25, TOTAL, 'mant');
  console.log('Slide 25: Mantenimiento');

  // ===========================
  // SLIDE 19 - Conclusiones
  // ===========================
  const conclContent = makeCols(
    `<p class="subtitle">Conclusiones del Proyecto:</p>
     <ul>
       <li><span style="color:#2e7d32;">✔</span> <b>Solución Transaccional Bimonetaria:</b><br>El sistema resuelve la complejidad del cobro multimoneda en bolívares y dólares mediante consulta automática de la tasa BCV diaria.</li>
       <li><span style="color:#2e7d32;">✔</span> <b>Auditoría de Inventarios Rigurosa:</b><br>La bitácora detallada de movimientos reduce pérdidas de stock inexplicables por merma.</li>
       <li><span style="color:#2e7d32;">✔</span> <b>Calidad Certificada en Código:</b><br>La implementación de 172 pruebas garantiza robustez contable en producción.</li>
     </ul>`,
    `<p class="subtitle">Recomendaciones para el Negocio:</p>
     <ul>
       <li><b>Impresión de Facturas Física:</b><br>Implementar el soporte de tickeras de 80mm para entregar recibos rápidos en el POS.</li>
       <li><b>Módulo de Cuentas por Pagar:</b><br>Agregar control de deudas para gestionar compras a crédito de proveedores.</li>
       <li><b>Centralización Sincronizada:</b><br>Migrar la base de datos a PostgreSQL en un servidor en la nube si el abasto se expande a múltiples tiendas físicas.</li>
     </ul>`,
    50
  );

  await addSlideTo(pres, 'CONCLUSIONES', conclContent, 26, TOTAL, 'conc');
  console.log('Slide 26: Conclusiones');

  // ===========================
  // SAVE
  // ===========================
  const outPath = path.join(BASE, 'Presentacion_Sistema_Financiero.pptx');
  await pres.writeFile({ fileName: outPath });
  console.log(`\nPresentation saved to: ${outPath}`);

  // Save section presentations
  const sectionFiles = [
    ['01_Entradas_Procesos_Salidas.pptx', sec.eps],
    ['02_Ciclo_de_Vida.pptx', sec.ciclo],
    ['03_Tecnologias.pptx', sec.tecnologia],
    ['04_DFD_Todos.pptx', sec.dfd],
    ['05_Diccionario_DFD.pptx', sec.diccDFD],
    ['06_Diagrama_ER_y_Diccionario.pptx', sec.er],
    ['07_Interfaces.pptx', sec.interfaces],
    ['08_Pruebas.pptx', sec.pruebas],
    ['09_Mantenimiento.pptx', sec.mant],
    ['10_Conclusiones.pptx', sec.conc],
  ];
  for (const [file, presObj] of sectionFiles) {
    const fp = path.join(LAMINAS_DIR, file);
    await presObj.writeFile({ fileName: fp });
    console.log(`Section: ${file}`);
  }
  console.log(`\nSection files saved to: ${LAMINAS_DIR}`);

  // Cleanup temp files
  fs.rmSync(TEMP, { recursive: true, force: true });
  console.log('Temp files cleaned up');
}

main().catch(err => {
  console.error('Error:', err);
  process.exit(1);
});
