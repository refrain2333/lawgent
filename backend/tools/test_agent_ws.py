"""
Agent WebSocket 全链路测试脚本

自动完成完整流程：S1 多轮对话 → 确认 → S2 检索 → S3 补充 → 确认 → S4 报告

用法：
    $env:NO_PROXY="localhost,127.0.0.1"
    cd backend && uv run python tools/test_agent_ws.py
"""

import asyncio
import json

import httpx
import websockets

BASE_URL = "http://127.0.0.1:5006"
WS_BASE  = "ws://127.0.0.1:5006"
EMAIL    = "test@example.com"
PASSWORD = "test123456"

FIRST_MESSAGE = "我朋友昨晚在酒吧被人用酒瓶打破了头，缝了5针，对方已经逃跑了"

FOLLOWUP_MESSAGES = [
    "医院诊断是头部裂伤，目前还没做伤情鉴定，但医生说可能是轻伤二级",
    "事情发生在朝阳区一家酒吧，大概晚上11点左右，双方之前不认识，对方喝醉了主动找茬",
    "对方是故意的，用啤酒瓶直接砸的额头，目前还没有抓到人",
    "我朋友没有前科，对方看起来也是第一次这样",
    "对方没有道歉也没有赔偿，我朋友已经报警了",
]

S3_MESSAGES = [
    "对方没有自首，也没有赔偿，我朋友还在住院观察",
    "没有其他量刑情节了",
]


def fmt(msg: dict) -> str:
    t = msg.get("type", "?")
    if t == "token":
        return msg.get("content", "")
    if t == "stage":
        return f"\n{'='*50}\n[STAGE] {msg.get('stage')} — {msg.get('label', '')}\n{'='*50}"
    if t == "confirm_request":
        return (
            f"\n[CONFIRM_REQUEST]\n"
            f"  摘要: {msg.get('summary', '')[:200]}\n"
            f"  facts: {json.dumps(msg.get('facts', {}), ensure_ascii=False)[:300]}"
        )
    if t == "search_progress":
        return f"  [SEARCH] {msg.get('path')} → {msg.get('status')}"
    if t == "fusion_result":
        return f"  [FUSION] 法条 {len(msg.get('articles', []))} 条, 案例 {len(msg.get('cases', []))} 条"
    if t == "report":
        return f"\n[REPORT]\n{json.dumps(msg.get('content', {}), ensure_ascii=False, indent=2)[:500]}"
    if t == "done":
        return f"\n[DONE] conversation_id={msg.get('conversation_id')}"
    if t == "error":
        return f"\n[ERROR] {msg.get('code')}: {msg.get('message')}"
    if t == "init":
        return f"[INIT] id={msg.get('conversation_id')}, stage={msg.get('stage')}, interrupted={msg.get('interrupted')}"
    if t == "pong":
        return ""
    return f"[{t.upper()}] {json.dumps(msg, ensure_ascii=False)[:200]}"


async def get_token() -> str:
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=15) as c:
        r = await c.post("/api/v1/user/login", json={"email": EMAIL, "password": PASSWORD})
        if r.status_code == 200:
            return r.json()["access_token"]
        r2 = await c.post("/api/v1/user/register", json={"email": EMAIL, "password": PASSWORD, "username": "tester"})
        if r2.status_code in (200, 201):
            return r2.json()["access_token"]
        raise RuntimeError(f"Auth failed: {r.status_code} / {r2.status_code} {r2.text}")


async def recv_until_idle(ws, timeout: float = 90.0) -> dict | None:
    """持续接收消息，直到收到 confirm_request / done / error / 超时（LLM 输出完毕等待用户输入）。

    Returns: 最后一条非 token 消息，或 None（超时）
    """
    last_significant = None
    token_buf = []

    while True:
        try:
            raw = await asyncio.wait_for(ws.recv(), timeout=timeout)
        except asyncio.TimeoutError:
            if token_buf:
                print("".join(token_buf), flush=True)
                token_buf.clear()
            print("[TIMEOUT] 等待超时，LLM 可能还在等用户输入")
            return last_significant

        msg = json.loads(raw)
        t = msg.get("type")

        if t == "token":
            token_buf.append(msg.get("content", ""))
            continue

        # 非 token 消息：先刷新 token 缓冲区
        if token_buf:
            print("".join(token_buf), flush=True)
            token_buf.clear()

        text = fmt(msg)
        if text:
            print(text, flush=True)

        if t in ("confirm_request", "done", "error"):
            return msg

        last_significant = msg

        if t == "stage":
            timeout = 90.0


async def run_test(token: str) -> None:
    uri = f"{WS_BASE}/api/v1/agent/ws?token={token}"
    print(f"\n[WS] Connecting to {uri[:60]}...")

    async with websockets.connect(uri, ping_interval=20) as ws:
        init_raw = await ws.recv()
        init = json.loads(init_raw)
        print(fmt(init))

        if init.get("interrupted"):
            cr = json.loads(await ws.recv())
            print(fmt(cr))

        # S1: 发送初始消息
        print(f"\n[SEND] {FIRST_MESSAGE}")
        await ws.send(json.dumps({"type": "message", "content": FIRST_MESSAGE}))

        followup_idx = 0
        s3_idx = 0

        while True:
            result = await recv_until_idle(ws)

            if result is None:
                # 超时说明 LLM 追问后等待用户，发补充信息
                pass
            else:
                msg_type = result.get("type")

                if msg_type == "done":
                    print("\n全链路测试完成!")
                    return

                if msg_type == "error":
                    print(f"\n测试中断: {result}")
                    return

                if msg_type == "confirm_request":
                    print("\n[AUTO] 发送确认: accepted=True")
                    await ws.send(json.dumps({"type": "confirm", "accepted": True}))
                    continue

                result.get("stage", "unknown")

            # LLM 在等用户输入（END 状态），发补充消息
            if followup_idx < len(FOLLOWUP_MESSAGES):
                msg_text = FOLLOWUP_MESSAGES[followup_idx]
                followup_idx += 1
                print(f"\n[SEND] (S1 补充 #{followup_idx}) {msg_text}")
                await ws.send(json.dumps({"type": "message", "content": msg_text}))
            elif s3_idx < len(S3_MESSAGES):
                msg_text = S3_MESSAGES[s3_idx]
                s3_idx += 1
                print(f"\n[SEND] (S3 补充 #{s3_idx}) {msg_text}")
                await ws.send(json.dumps({"type": "message", "content": msg_text}))
            else:
                print("\n[WARN] 所有补充消息已用完，退出")
                return


async def main():
    print("=" * 60)
    print("  Agent WebSocket 全链路测试")
    print("=" * 60)

    token = await get_token()
    print(f"[AUTH] token={token[:20]}...")

    await run_test(token)


if __name__ == "__main__":
    asyncio.run(main())
