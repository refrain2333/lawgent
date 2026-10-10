# 日志配置
import json
import logging
import re
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import parse_qsl, urlencode

from loguru import logger

from app.core.config import settings

# 基础日志目录 (backend/logs)
BASE_DIR = Path(__file__).resolve().parent.parent.parent
BASE_LOG_DIR = BASE_DIR / "logs"

# 启动时间戳（全局，确保同一次启动的 AI 日志写同一个文件）
_STARTUP_TS = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")


class _InterceptHandler(logging.Handler):
    """将标准 logging 桥接到 loguru"""
    def emit(self, record: logging.LogRecord) -> None:
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno
        try:
            frame, depth = sys._getframe(6), 6
        except ValueError:
            frame, depth = sys._getframe(1), 1
        while frame and frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1
        message = record.getMessage()
        if record.name == "uvicorn.access":
            def _redact_query(match: re.Match[str]) -> str:
                query = parse_qsl(match.group()[1:], keep_blank_values=True)
                private_keys = {"token", "q", "query", "vector", "bm25", "kg", "query2doc", "hyde"}
                if not any(key in private_keys for key, _ in query):
                    return match.group()
                return "?" + urlencode([
                    (key, "REDACTED" if key in private_keys else value) for key, value in query
                ])

            # 只处理格式化后的副本，保留原 LogRecord 的参数供其他 handler 使用。
            message = re.sub(r'\?[^\s"]+', _redact_query, message)
        logger.opt(depth=depth, exception=record.exc_info).log(level, message)


# 配置控制台日志
logger.remove()
logger.add(
    sys.stdout,
    level="DEBUG",
    colorize=True,
    diagnose=False,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    )

# 拦截 uvicorn / fastapi / sqlalchemy 的标准 logging，全部转给 loguru
logging.basicConfig(handlers=[_InterceptHandler()], level=logging.INFO, force=True)
for _name in ("openai", "httpx", "httpcore", "langchain", "langchain_openai"):
    logging.getLogger(_name).setLevel(logging.WARNING)
for _name in ("uvicorn", "uvicorn.error", "uvicorn.access", "fastapi", "sqlalchemy.engine"):
    _log = logging.getLogger(_name)
    _log.handlers = [_InterceptHandler()]
    _log.propagate = False


def init_file_logging():
    """初始化文件日志（lifespan 调用）"""
    now = datetime.now()
    log_dir = BASE_LOG_DIR / "run" / now.strftime("%m") / now.strftime("%d")
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / "{time:YYYY-MM-DD_HH-mm-ss}.log"

    logger.add(
        str(log_path),
        rotation="00:00",
        retention="30 days",
        level="INFO",
        encoding="utf-8",
        enqueue=True,
        diagnose=False,
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
        )


def log_ai_call(
    stage: str,
    thread_id: str,
    input_messages: list,
    output: str,
    extra: dict | None = None,
    ) -> None:
    """将一次 AI 输入输出记录为 JSONL，写入 logs/ai/MM/DD/ai_YYYY-MM-DD.jsonl"""
    now = datetime.now()
    mm = now.strftime("%m")
    dd = now.strftime("%d")

    log_dir = BASE_LOG_DIR / "ai" / mm / dd
    log_file = log_dir / f"ai_{_STARTUP_TS}.jsonl"

    # 序列化 input_messages
    def _serialize_msg(m) -> dict:
        if isinstance(m, dict):
            return m
        role = getattr(m, "type", None) or getattr(m, "role", "unknown")
        content = getattr(m, "content", str(m))
        # tool_calls
        tool_calls = getattr(m, "tool_calls", None)
        d = {"role": role, "content": content}
        if tool_calls:
            d["tool_calls"] = tool_calls
        return d

    record = {
        "ts": now.isoformat(),
        "stage": stage,
        "thread_id": thread_id,
    }
    if settings.LOG_AI_CONTENT:
        record["input"] = [_serialize_msg(m) for m in input_messages]
        record["output"] = output
    else:
        record["input_count"] = len(input_messages)
        record["output_chars"] = len(output)
    if extra:
        record.update(extra)

    try:
        log_dir.mkdir(parents=True, exist_ok=True)
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception as e:
        logger.warning(f"AI 日志写入失败: {e}")
