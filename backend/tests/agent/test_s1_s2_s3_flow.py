# 生命周期：集成测试完成后删除
# 测试 S1→S2→S3 完整流程（不依赖 HTTP，直接调 service 层）
import asyncio
import json


# ---------- S1 ----------
async def test_s1():
    from app.agent.service.s1 import chat_s1

    print("\n========== S1 案情收集 ==========")
    history = []
    conversations = [
        "我朋友昨晚在酒吧打了人",
        "对方轻伤二级，有鉴定报告",
        "昨晚11点，在市中心一家酒吧",
        "因为口角冲突，我朋友动手打了人，徒手",
        "已经报警了",
    ]

    case_ready_summary = None
    for user_msg in conversations:
        print(f"\n[用户]: {user_msg}")
        ai_reply = ""
        async for chunk in chat_s1(user_msg, history, thread_id="test"):
            if chunk.startswith("data: "):
                data = json.loads(chunk[6:])
                if data["type"] == "token":
                    ai_reply += data["content"]
                elif data["type"] == "case_ready":
                    case_ready_summary = data["summary"]
                    print(f"[AI]: {ai_reply}")
                    print(f"\n>>> CASE_READY 触发，摘要: {case_ready_summary}")
                    break
        else:
            print(f"[AI]: {ai_reply}")
            history.append({"role": "user", "content": user_msg})
            history.append({"role": "assistant", "content": ai_reply})

        if case_ready_summary:
            break

    if not case_ready_summary:
        print("\n[警告] 所有消息发完后 CASE_READY 未触发")

    return case_ready_summary, history


# ---------- S2 ----------
async def test_s2(summary: str):
    from app.agent.service.s2 import gen_checklist, run_s2

    print("\n========== S2 检索 ==========")
    print(f"案情摘要: {summary}")

    print("\n[S2] 执行检索...")
    search_result = await run_s2(summary, thread_id="test")

    fused = search_result.get("fused", {})
    articles = fused.get("articles", [])
    cases = fused.get("cases", [])
    print(f"[S2] 检索完成 - 法条: {len(articles)} 条，案例: {len(cases)} 条")
    for a in articles[:3]:
        print(f"  法条: {a.get('title', '')}")
    for c in cases[:3]:
        print(f"  案例: {'、'.join(c.get('accusations', []))}，{c.get('sentence_months', '未知')}个月")

    print("\n[S2] 生成量刑清单...")
    checklist = await gen_checklist(summary, search_result, thread_id="test")
    crime = checklist.get("crime", "")
    items = checklist.get("checklist", [])
    print(f"[S2] 罪名: {crime}，清单共 {len(items)} 项")
    for item in items:
        print(f"  [{item.get('importance')}] {item.get('label')}: {item.get('question')}")

    return search_result, checklist


# ---------- S3 ----------
async def test_s3(summary: str, s2_data: dict, checklist: dict):
    from app.agent.service.s3 import chat_s3

    print("\n========== S3 量刑情节收集 ==========")
    history = []
    conversations = [
        "开始吧",
        "是对方先挑衅的，我朋友是被激怒了",
        "还没有赔偿，还在谈",
        "是主动去派出所配合调查的",
        "认罪了",
        "没有前科",
        "已经成年了，28岁",
    ]

    for user_msg in conversations:
        print(f"\n[用户]: {user_msg}")
        ai_reply = ""
        async for chunk in chat_s3(user_msg, history, summary=summary, s2_data=s2_data, checklist=checklist, thread_id="test"):
            if chunk.startswith("data: "):
                data = json.loads(chunk[6:])
                if data["type"] == "token":
                    ai_reply += data["content"]
        print(f"[AI]: {ai_reply}")
        history.append({"role": "user", "content": user_msg})
        history.append({"role": "assistant", "content": ai_reply})

        if "量刑情节汇总" in ai_reply or "点击确认" in ai_reply:
            print("\n>>> S3 汇总已生成，流程完成")
            break


# ---------- 主入口 ----------
async def main():
    # S1
    summary, _ = await test_s1()
    if not summary:
        print("S1 未触发 CASE_READY，终止测试")
        return

    # S2
    s2_data, checklist = await test_s2(summary)

    # S3
    await test_s3(summary, s2_data, checklist)

    print("\n========== 流程测试完成 ==========")


if __name__ == "__main__":
    import os
    import sys
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
    asyncio.run(main())
