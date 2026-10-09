# 路由汇总
from fastapi import APIRouter

from app.api import docs, system
from app.api.v1 import agent, data, graph, search, stats, user

router = APIRouter()

# 系统路由 - /
router.include_router(system.router)

# 文档路由 - /docs
router.include_router(docs.router)

# 业务路由 - /api/v1
v1_router = APIRouter(prefix="/api/v1")
v1_router.include_router(search.router, prefix="/search")
v1_router.include_router(agent.router, prefix="/agent")
v1_router.include_router(user.router, prefix="/user")
v1_router.include_router(stats.router)
v1_router.include_router(graph.router)
v1_router.include_router(data.router)
router.include_router(v1_router)
