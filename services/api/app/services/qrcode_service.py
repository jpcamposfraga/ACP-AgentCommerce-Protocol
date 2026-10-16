import io
import segno


def render_terminal_qr(payload: str) -> str:
    """
    Gera representação compacta em blocos UTF-8 para renderização direta em terminal ou chat.
    Utiliza io.StringIO para evitar problemas com encodings não-UTF-8 padrão de consoles Windows.
    """
    qr = segno.make(payload)
    buf = io.StringIO()
    qr.terminal(out=buf, compact=True)
    return buf.getvalue()


def render_png_qr(payload: str, scale: int = 6) -> bytes:
    """
    Gera os bytes brutos de imagem PNG do QR Code utilizando o encoder nativo do segno.
    Não requer Pillow nem dependências binárias C.
    """
    qr = segno.make(payload)
    buf = io.BytesIO()
    qr.save(buf, kind="png", scale=scale)
    return buf.getvalue()
