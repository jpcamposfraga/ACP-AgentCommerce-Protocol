from pydantic import BaseModel, Field

class ClassificationResult(BaseModel):
    is_valid_product: bool = Field(..., description="Se o item corresponde ao produto desejado e não é spam/acessório")
    trust_score: float = Field(..., ge=0.0, le=1.0, description="Score de confiança calibrado (0 a 1)")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Nível de certeza da classificação")
    risk_flags: list[str] = Field(default_factory=list, description="Lista de alertas de risco identificados")

class JevClassifier:
    """
    Camada de Decisão Rápida baseada na arquitetura do modelo Jev (TypeSafe AI).
    Executa decisões não-autoregressivas em < 100ms para filtrar ruídos,
    detectar honeypots de preços irreais e calcular reputação calibrada.
    """

    ACCESSORY_KEYWORDS = {
        "capinha", "película", "pelicula", "case", "bumper",
        "skin", "adesivo", "cordão", "pulseira"
    }

    # Atributos legítimos de produtos que contêm a palavra "capa" mas não são acessórios avulsos
    INTEGRATED_ATTRIBUTES = {
        "capa dura", "capa flexivel", "capa flexível", "capa cartao", "capa cartão",
        "capa de couro", "capa comum", "capa cristal"
    }

    SYNONYM_GROUPS = [
        {"caderno para desenho", "caderno de desenho", "caderno desenho", "sketchbook", "bloco de desenho", "bloco desenho", "bloco canson", "caderno artistico", "croqui"},
        {"celular", "smartphone", "telefone", "aparelho celular"},
        {"fone de ouvido", "headphone", "headset", "earphone", "earbuds", "fone bluetooth"},
        {"notebook", "laptop", "computador portatil"},
    ]

    HIGH_TRUST_LEVELS = {"platinum", "gold", "leader", "official_store", "mercado_lider_platinum"}

    def classify_listing(
        self,
        title: str,
        price: float,
        seller_info: dict | None = None,
        target_query: str = ""
    ) -> ClassificationResult:
        seller_info = seller_info or {}
        risk_flags: list[str] = []
        lower_title = title.lower()
        lower_query = target_query.lower()

        # 1. Detecção de falso positivo / incompatibilidade de acessório
        is_valid_product = True
        
        # Sanitiza atributos integrados legítimos (ex: "capa dura") para evitar falso positivo
        sanitized_title = lower_title
        for attr in self.INTEGRATED_ATTRIBUTES:
            sanitized_title = sanitized_title.replace(attr, "attr_integrado")

        words_in_title = set(sanitized_title.replace("-", " ").replace("/", " ").split())
        matched_accessory = words_in_title.intersection(self.ACCESSORY_KEYWORDS)

        # "capa" avulsa com preposição de destinação (ex: "capa para caderno") é acessório real
        if "capa para " in lower_title or "capa p/ " in lower_title or ("capa" in words_in_title and "para" in words_in_title):
            matched_accessory.add("capa")
        elif "capa" in words_in_title and not any(kw in lower_query for kw in ["livro", "caderno", "agenda", "biblia", "bíblia"]):
            matched_accessory.add("capa")
        
        if matched_accessory and not any(kw in lower_query for kw in self.ACCESSORY_KEYWORDS | {"capa"}):
            is_valid_product = False
            risk_flags.append("ACCESSORY_MISMATCH")

        # 2. Detecção de preço irreal (possível Honeypot / Golpe)
        # Produtos de alta demanda (ex: iPhone, MacBook, PS5) com preço absurdamente baixo
        if ("iphone" in lower_title or "macbook" in lower_title or "ps5" in lower_title) and price < 600.0:
            risk_flags.append("UNREALISTIC_PRICE")

        # 3. Cálculo de Reputação e Confiança Calibrada
        rep_level = str(seller_info.get("reputation_level", "")).lower()
        sales_count = int(seller_info.get("sales_count", 0))

        trust = 0.50
        if rep_level in self.HIGH_TRUST_LEVELS:
            trust += 0.35
            if sales_count >= 100:
                trust += 0.10
        elif rep_level in {"new", "none", "unknown", ""} or sales_count < 10:
            trust = 0.45
            risk_flags.append("LOW_SELLER_REPUTATION")

        if "UNREALISTIC_PRICE" in risk_flags:
            trust = min(trust, 0.25)

        trust_score = round(max(0.05, min(0.99, trust)), 2)
        confidence = 0.90 if is_valid_product else 0.95

        return ClassificationResult(
            is_valid_product=is_valid_product,
            trust_score=trust_score,
            confidence=confidence,
            risk_flags=risk_flags
        )
