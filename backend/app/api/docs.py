# API 文档配置
from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter(tags=["文档"])


@router.get("/docs", include_in_schema=False)
async def scalar_docs():
    """Scalar API 文档页面"""
    return HTMLResponse(content="""
<!doctype html>
<html>
  <head>
    <title>刑事法律服务助手 API 文档</title>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
  </head>
  <body>
    <script
      id="api-reference"
      data-url="/openapi.json"
      data-configuration='{
        "theme": "default",
        "layout": "modern",
        "darkMode": false
      }'></script>
    <script src="https://cdn.jsdelivr.net/npm/@scalar/api-reference"></script>
  </body>
</html>
    """)
