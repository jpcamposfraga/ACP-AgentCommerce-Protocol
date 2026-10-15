import uuid
from fastapi import APIRouter
from app.schemas.tracker import TrackerRequest, TrackerResponse

router = APIRouter(prefix="/api/v1/trackers", tags=["trackers"])

MIN_CHECK_INTERVAL_SECONDS = 60


@router.post("", response_model=TrackerResponse)
async def create_price_tracker(request: TrackerRequest):
    # Trava de governança: intervalo mínimo de 60 segundos
    if request.check_interval_seconds < MIN_CHECK_INTERVAL_SECONDS:
        effective_interval = MIN_CHECK_INTERVAL_SECONDS
        warning = (
            f"Intervalo ajustado para o limite mínimo de segurança ({MIN_CHECK_INTERVAL_SECONDS} segundos) "
            "para evitar bloqueio anti-bot."
        )
    else:
        effective_interval = request.check_interval_seconds
        warning = None

    # Simulação da cotação atual do produto
    if "1001" in request.product_url_or_id:
        current_best_price = 4769.0
    elif "1002" in request.product_url_or_id:
        current_best_price = 5499.0
    else:
        current_best_price = round(request.target_price * 1.08, 2)

    tracker_id = f"tr_{uuid.uuid4().hex[:8]}"

    return TrackerResponse(
        tracker_id=tracker_id,
        status="active",
        product_url_or_id=request.product_url_or_id,
        target_price=request.target_price,
        current_best_price=current_best_price,
        check_interval_seconds=effective_interval,
        warning=warning,
    )
