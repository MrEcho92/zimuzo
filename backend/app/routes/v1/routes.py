from fastapi import APIRouter

from app.routes.v1 import attachment as attachment_router
from app.routes.v1 import draft as draft_router
from app.routes.v1 import inbound_resend as inbound_resend_router
from app.routes.v1 import inbox as input_router
from app.routes.v1 import message as message_router
from app.routes.v1 import parse as parse_router
from app.routes.v1 import tag as tag_router
from app.routes.v1 import thread as thread_router
from app.routes.v1 import users as user_router
from app.routes.v1 import webhooks as webhooks_router

api_router = APIRouter()
api_router.include_router(user_router.router)
api_router.include_router(input_router.router)
api_router.include_router(thread_router.router)
api_router.include_router(message_router.router)
api_router.include_router(draft_router.router)
api_router.include_router(attachment_router.router)
api_router.include_router(tag_router.router)
api_router.include_router(inbound_resend_router.router)
api_router.include_router(webhooks_router.router)
api_router.include_router(parse_router.router)
