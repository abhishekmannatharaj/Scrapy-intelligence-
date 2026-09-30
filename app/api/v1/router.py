from fastapi import APIRouter

from app.api.v1.endpoints import jobs, products

api_router = APIRouter()
api_router.include_router(jobs.router, prefix="/jobs", tags=["jobs"])
api_router.include_router(products.router, prefix="/products", tags=["products"])
