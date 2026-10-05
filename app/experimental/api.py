"""Experimental router composition, separate from the frozen API module."""
from fastapi import APIRouter
from .flags import flag_status

router = APIRouter()

@router.get('/experimental/features')
def features():
    return flag_status()
