from fastapi import APIRouter
from app.schemas.search import SearchRequest, SearchResponse
from app.services.aggregator import SearchAggregator

router = APIRouter(prefix="/api/v1/search", tags=["search"])
aggregator = SearchAggregator()


@router.post("", response_model=SearchResponse)
async def search_products(request: SearchRequest):
    return await aggregator.search(request)

