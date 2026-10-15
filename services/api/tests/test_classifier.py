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
