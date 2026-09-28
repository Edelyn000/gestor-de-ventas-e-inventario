from PIL import Image, ImageDraw, ImageFont
import os

OUTPUT = os.path.dirname(os.path.abspath(__file__))

# --- Scale factor: generate at 2x for crisp output ---
SCALE = 2

# --- Colors ---
BLUE       = "#3a75c4"
LIGHT_BLUE = "#e8f0fe"
WHITE      = "#ffffff"
ROW_ALT    = "#f2f5f9"
BORDER     = "#b0b0b0"
TEXT_DARK  = "#1a1a1a"
TEXT_GRAY  = "#444444"
PK_GOLD    = "#b8860b"

def get_font(size, bold=False):
    paths = [
        "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/calibrib.ttf" if bold else "C:/Windows/Fonts/calibri.ttf",
    ]
    for p in paths:
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()

def s(v):
    return v * SCALE

def gen_table_image(filename, title, fields):
    # Column widths (logical pixels, will be scaled)
    col_w = [160, 110, 280]
    total_w = sum(col_w)
    row_h = 28
    title_h = 30
    hdr_h = 28
    pad_x = 10
    pad_y = 7
    border = 1

    total_h = title_h + hdr_h + row_h * len(fields) + border * 2

    # Create at 2x
    img = Image.new("RGB", (s(total_w), s(total_h)), WHITE)
    draw = ImageDraw.Draw(img)

    font_title = get_font(s(13), True)
    font_hdr   = get_font(s(11), True)
    font_cell  = get_font(s(10))
    font_pk    = get_font(s(9), True)

    x0 = 0
    y0 = 0

    # --- Outer border ---
    draw.rectangle([x0, y0, x0 + s(total_w) - 1, y0 + s(total_h) - 1], outline=BORDER, width=s(border))

    # --- Title bar ---
    draw.rectangle([x0 + s(border), y0 + s(border), x0 + s(total_w) - s(border), y0 + s(title_h)], fill=LIGHT_BLUE)
    draw.text((x0 + s(pad_x), y0 + s(8)), title, font=font_title, fill=BLUE)

    # --- Header row ---
    hy = y0 + s(title_h)
    cx = x0 + s(border)
    for hdr_text, w in zip(["Campo", "Tipo", "Descripción"], col_w):
        draw.rectangle([cx, hy, cx + s(w), hy + s(hdr_h)], fill=BLUE)
        draw.text((cx + s(pad_x), hy + s(8)), hdr_text, font=font_hdr, fill=WHITE)
        # Vertical separator
        cx += s(w)
        if cx < x0 + s(total_w) - s(border):
            draw.line([cx, hy, cx, hy + s(hdr_h)], fill=BORDER, width=s(border))

    # --- Data rows ---
    ry = hy + s(hdr_h)
    for idx, (campo, tipo, desc, is_pk) in enumerate(fields):
        bg = WHITE if idx % 2 == 0 else ROW_ALT
        draw.rectangle([x0 + s(border), ry, x0 + s(total_w) - s(border), ry + s(row_h)], fill=bg)

        # Bottom row line
        draw.line([x0 + s(border), ry + s(row_h), x0 + s(total_w) - s(border), ry + s(row_h)], fill=BORDER, width=s(border))

        # Cell text
        cx = x0 + s(border)
        texts = [campo, tipo, desc]
        colors = [TEXT_DARK, TEXT_GRAY, TEXT_DARK]
        for text, w, color in zip(texts, col_w, colors):
            draw.text((cx + s(pad_x), ry + s(pad_y)), text, font=font_cell, fill=color)
            cx += s(w)
            # Vertical separator
            if cx < x0 + s(total_w) - s(border):
                draw.line([cx, ry, cx, ry + s(row_h)], fill=BORDER, width=s(border))

        # PK badge
        if is_pk:
            tw = draw.textlength(campo, font=font_cell)
            pk_x = x0 + s(border) + s(pad_x) + int(tw) + s(6)
            pk_y = ry + s(pad_y) + s(1)
            draw.text((pk_x, pk_y), "PK", font=font_pk, fill=PK_GOLD)

        ry += s(row_h)

    # --- Left/right vertical borders ---
    draw.line([x0 + s(border), y0 + s(title_h), x0 + s(border), ry], fill=BORDER, width=s(border))
    draw.line([x0 + s(total_w) - s(border) - 1, y0 + s(title_h), x0 + s(total_w) - s(border) - 1, ry], fill=BORDER, width=s(border))

    # --- Column separators full height ---
    cx = x0 + s(border)
    for w in col_w[:-1]:
        cx += s(w)
        draw.line([cx, y0 + s(title_h), cx, ry], fill=BORDER, width=s(border))

    path = os.path.join(OUTPUT, filename)
    img.save(path, "PNG", dpi=(300, 300))
    print(f"  -> {filename} ({img.size[0]}x{img.size[1]}px @300dpi)")

# === TABLE DATA ===
tables = [
    ("DB_PRODUCTOS.png", "1. PRODUCTOS", [
        ("idproducto", "INT", "Clave PK, autoincrement", True),
        ("nombre_producto", "VARCHAR(100)", "Nombre del producto", False),
        ("categoria", "VARCHAR(50)", "Categoría del producto", False),
        ("precio_compra", "DECIMAL(10,2)", "Precio de compra", False),
        ("precio_venta_bs", "DECIMAL(10,2)", "Precio venta en BS", False),
        ("precio_venta_usd", "DECIMAL(10,2)", "Precio venta en USD", False),
        ("stock_actual", "INT", "Stock actual en almacén", False),
        ("stock_minimo", "INT", "Stock mínimo permitido", False),
        ("unidad", "VARCHAR(20)", "Unidad de medida", False),
        ("fecha_ingreso", "DATETIME", "Fecha de ingreso", False),
    ]),
    ("DB_VENTAS.png", "2. VENTAS", [
        ("idventa", "INT", "Clave PK, autoincrement", True),
        ("usuario_id", "INT", "FK → usuarios", False),
        ("numero_factura", "TEXT", "Nro. factura (UNIQUE)", False),
        ("fecha_venta", "DATETIME", "Fecha y hora venta", False),
        ("total_bs", "NUMERIC", "Total en bolívares", False),
        ("total_usd", "NUMERIC", "Total en dólares", False),
        ("tasa_cambio", "NUMERIC", "Tasa BCV del día", False),
        ("efectivo_bs", "NUMERIC", "Efectivo en BS", False),
        ("efectivo_usd", "NUMERIC", "Efectivo en USD", False),
        ("tarjeta", "NUMERIC", "Pago con tarjeta", False),
        ("pago_movil", "NUMERIC", "Pago móvil", False),
        ("bio_pago", "NUMERIC", "Biopago", False),
        ("estado", "TEXT", "ACTIVA / ANULADA", False),
    ]),
    ("DB_VENTA_DETALLES.png", "3. VENTA_DETALLES", [
        ("id", "INT", "Clave PK, autoincrement", True),
        ("venta_id", "INT", "FK → ventas", False),
        ("producto_id", "INT", "FK → productos", False),
        ("cantidad", "INT", "Cantidad vendida", False),
        ("precio_unitario_bs", "DECIMAL(10,2)", "Precio unitario BS", False),
        ("subtotal_bs", "DECIMAL(10,2)", "Subtotal línea", False),
    ]),
    ("DB_MOV_INVENTARIO.png", "4. MOVIMIENTOS_INVENTARIO", [
        ("id", "INT", "Clave PK, autoincrement", True),
        ("producto_id", "INT", "FK → productos", False),
        ("usuario_id", "INT", "FK → usuarios", False),
        ("tipo", "TEXT", "ENTRADA/SALIDA/AJUSTE", False),
        ("motivo", "TEXT", "Motivo del movimiento", False),
        ("cantidad", "INT", "Cantidad movida", False),
        ("stock_anterior", "INT", "Stock antes", False),
        ("stock_nuevo", "INT", "Stock después", False),
        ("referencia_id", "INT", "ID referencia", False),
        ("observaciones", "TEXT", "Observaciones", False),
        ("fecha_movimiento", "DATETIME", "Fecha movimiento", False),
    ]),
    ("DB_TASAS_CAMBIO.png", "5. TASAS_CAMBIO", [
        ("id", "INT", "Clave PK, autoincrement", True),
        ("fecha", "DATE", "Fecha (UNIQUE)", False),
        ("tasa_venta", "NUMERIC", "Tasa venta BCV", False),
        ("tasa_compra", "NUMERIC", "Tasa compra BCV", False),
        ("activa", "INT", "1=activa, 0=inactiva", False),
    ]),
    ("DB_USUARIOS.png", "6. USUARIOS", [
        ("id", "INT", "Clave PK, autoincrement", True),
        ("usuario", "TEXT", "Usuario (UNIQUE)", False),
        ("contrasena", "TEXT", "Contraseña bcrypt", False),
        ("nombre_completo", "TEXT", "Nombre completo", False),
        ("activo", "INT", "1=activo, 0=inactivo", False),
        ("fecha_creacion", "DATETIME", "Fecha creación", False),
    ]),
    ("DB_REPORTES_DIARIOS.png", "7. REPORTES_DIARIOS", [
        ("id", "INT", "Clave PK, autoincrement", True),
        ("fecha", "DATE", "Fecha (UNIQUE)", False),
        ("total_ventas_bs", "NUMERIC", "Total ventas BS", False),
        ("total_ventas_usd", "NUMERIC", "Total ventas USD", False),
        ("cantidad_ventas", "INT", "Nro. transacciones", False),
        ("cantidad_productos_vendidos", "INT", "Unidades vendidas", False),
    ]),
]

print("Generando tablas E-R (2x alta resolución)...")
for fname, title, fields in tables:
    gen_table_image(fname, title, fields)
print("Listo!")
