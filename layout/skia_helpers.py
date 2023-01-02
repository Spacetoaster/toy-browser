import skia

scale_factor = None

def parse_color(color):
    if color == "white":
        return skia.ColorWHITE
    elif color == "blue":
        return skia.ColorSetARGB(0xFF, 0x00, 0x00, 0xFF)
    elif color == "orange":
        return skia.ColorSetARGB(0xFF, 0xFF, 0xA5, 0x00)
    elif color == "lightblue":
        return skia.ColorSetARGB(0xFF, 0xAD, 0xD8, 0xE6)
    elif color == "gray":
        return skia.ColorSetARGB(0xFF, 0x80, 0x80, 0x80)
    elif color == "yellow":
        return skia.ColorSetARGB(0xFF, 0xFF, 0xFF, 0x00)
    else:
        return skia.ColorBLACK

def draw_line(canvas, x1, y1, x2, y2):
    path = skia.Path().moveTo(x1 * scale_factor, y1 * scale_factor).lineTo(x2 * scale_factor, y2 * scale_factor)
    paint = skia.Paint(Color=skia.ColorBLACK)
    paint.setStyle(skia.Paint.kStroke_Style)
    paint.setStrokeWidth(1)
    canvas.drawPath(path, paint)

def draw_text(canvas, x, y, text, font, color=None):
    sk_color = parse_color(color)
    paint = skia.Paint(AntiAlias=True, Color=sk_color)
    scaled_font = font.makeWithSize(font.getSize() * scale_factor)
    canvas.drawString(text, scale_factor * float(x), scale_factor * (y - font.getMetrics().fAscent), scaled_font, paint)

def draw_rect(canvas, l, t, r, b, fill=None, width=1):
    paint = skia.Paint()
    if fill:
        paint.setStrokeWidth(width)
        paint.setColor(parse_color(fill))
    else:
        paint.setStyle(skia.Paint.kStroke_Style)
        paint.setStrokeWidth(1)
        paint.setColor(skia.ColorBLACK)
    rect = skia.Rect.MakeLTRB(l * scale_factor, t * scale_factor, r * scale_factor, b * scale_factor)
    canvas.drawRect(rect, paint)

def scale_rrect(rrect, radius):
    scaled_rect = skia.Rect.MakeLTRB(
        scale_factor * rrect.rect().left(),
        scale_factor * rrect.rect().top(),
        scale_factor * rrect.rect().right(),
        scale_factor * rrect.rect().bottom(),
    )
    scaled_rrect = skia.RRect.MakeRectXY(scaled_rect, scale_factor * radius, scale_factor * radius)
    return scaled_rrect

def draw_rrect(canvas, rrect, radius, color=None):
    scaled_rrect = scale_rrect(rrect, radius)
    sk_color = parse_color(color)
    canvas.drawRRect(scaled_rrect, paint=skia.Paint(Color=sk_color))