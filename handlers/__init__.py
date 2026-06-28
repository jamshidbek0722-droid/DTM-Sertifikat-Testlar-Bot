from aiogram import Router
from .admin import admin_router
from .user import user_router

router = Router()
router.include_router(admin_router)
router.include_router(user_router)
