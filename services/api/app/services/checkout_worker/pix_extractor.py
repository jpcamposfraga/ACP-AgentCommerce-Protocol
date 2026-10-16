import re
from typing import Optional


class PixExtractor:
    """
    Extrai o código Pix Copia-e-Cola (padrão EMV QRCPS-MPM do Banco Central)
    a partir de conteúdo HTML, atributos de botões de cópia ou campos de texto.
    """

    @classmethod
    def extract_payload(cls, text_or_html: str) -> Optional[str]:
        if not text_or_html:
            return None

        # 1. Checa por data-clipboard-text ou value
        clipboard_match = re.search(r'data-clipboard-text=["\']([^"\']+)["\']', text_or_html)
        if clipboard_match:
            candidate = clipboard_match.group(1).strip()
            if "br.gov.bcb.pix" in candidate:
                return candidate

        # 2. Busca padrão EMV Banco Central: inicia com 00020126 e termina no checksum 6304XXXX
        emv_match = re.search(r"00020126.*?6304[0-9a-zA-Z]{4}", text_or_html, re.DOTALL)
        if emv_match:
            candidate = emv_match.group(0).replace("\n", "").replace("\r", "").strip()
            if "br.gov.bcb.pix" in candidate:
                return candidate

        # 3. Busca ampla caso falte checksum formal
        broad_match = re.search(r"00020126[A-Za-z0-9\.\-\_\@\*\:\/\=\+\s]{30,}", text_or_html)
        if broad_match:
            candidate = broad_match.group(0).replace("\n", "").replace("\r", "").strip()
            if "br.gov.bcb.pix" in candidate:
                return candidate

        return None
