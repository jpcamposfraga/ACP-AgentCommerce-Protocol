import pytest
from app.services.classifier import JevClassifier, ClassificationResult

def test_classifier_identifies_valid_product_and_high_trust_seller():
    classifier = JevClassifier()
    result = classifier.classify_listing(
        title="Apple iPhone 15 128GB Preto Novo Lacrado",
        price=4800.0,
        seller_info={"reputation_level": "platinum", "sales_count": 1200},
        target_query="iPhone 15"
    )
    assert isinstance(result, ClassificationResult)
    assert result.is_valid_product is True
    assert result.trust_score >= 0.90
    assert result.confidence >= 0.80
    assert len(result.risk_flags) == 0

def test_classifier_detects_unrealistic_low_price_honeypot():
    classifier = JevClassifier()
    # iPhone 15 por R$ 350,00 é sinal clássico de golpe / honeypot
    result = classifier.classify_listing(
        title="iPhone 15 128GB Original",
        price=350.0,
        seller_info={"reputation_level": "new", "sales_count": 0},
        target_query="iPhone 15"
    )
    assert "UNREALISTIC_PRICE" in result.risk_flags
    assert result.trust_score < 0.40

def test_classifier_detects_accessory_mismatch():
    classifier = JevClassifier()
    # Busca por iPhone 15, mas anúncio é capinha ou película
    result = classifier.classify_listing(
        title="Capa Capinha Anti-impacto Silicone Para iPhone 15 Pro",
        price=39.90,
        seller_info={"reputation_level": "gold", "sales_count": 500},
        target_query="iPhone 15"
    )
    assert result.is_valid_product is False
    assert "ACCESSORY_MISMATCH" in result.risk_flags

def test_classifier_evaluates_unknown_or_low_reputation_seller():
    classifier = JevClassifier()
    result = classifier.classify_listing(
        title="iPhone 15 128GB Azul Usado",
        price=4200.0,
        seller_info={"reputation_level": "none", "sales_count": 2},
        target_query="iPhone 15"
    )
    assert result.is_valid_product is True
    assert result.trust_score <= 0.60
    assert "LOW_SELLER_REPUTATION" in result.risk_flags


def test_classifier_allows_capa_dura_in_stationery_and_books():
    classifier = JevClassifier()
    # "Capa dura" em caderno não é acessório de celular
    result = classifier.classify_listing(
        title="Caderno De Desenho Capa Dura Spiral 80 Fls",
        price=29.90,
        seller_info={"reputation_level": "gold", "sales_count": 300},
        target_query="caderno para desenho"
    )
    assert result.is_valid_product is True
    assert "ACCESSORY_MISMATCH" not in result.risk_flags


def test_classifier_still_blocks_real_notebook_cover_accessories():
    classifier = JevClassifier()
    # Capa avulsa para caderno deve ser bloqueada quando a busca é pelo caderno
    result = classifier.classify_listing(
        title="Capa Para Caderno Universitário Transparente Pct C/ 10",
        price=15.90,
        seller_info={"reputation_level": "gold", "sales_count": 200},
        target_query="caderno para desenho"
    )
    assert result.is_valid_product is False
    assert "ACCESSORY_MISMATCH" in result.risk_flags


def test_classifier_understands_synonyms():
    classifier = JevClassifier()
    # Sketchbook é sinônimo válido para caderno de desenho
    result = classifier.classify_listing(
        title="Sketchbook Artístico Profissional A4 200g",
        price=45.00,
        seller_info={"reputation_level": "platinum", "sales_count": 1000},
        target_query="caderno para desenho"
    )
    assert result.is_valid_product is True
    assert result.trust_score >= 0.85

