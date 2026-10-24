"""多 Agent 协作：统筹协调 + 会议通知 + 待办事项 + 时间线 + 风险提示。"""
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

from .llm import chat

ORCH_SYSTEM = """你是"校园统筹协调Agent"。用户会用自然语言描述一个校园会议或活动需求。
请提取并结构化以下要素，用简洁的中文输出（不要用JSON，用清晰的小标题段落）：
- 活动主题
- 活动类型（会议/活动/赛事/讲座/其他）
- 时间（如未明确给出，标注"待定"并建议一个合理时间）
- 地点（如未明确给出，标注"待定"并建议）
- 主办方/负责人
- 参与对象与规模
- 核心目标
- 关键约束或特殊要求
只做信息梳理，不要生成通知正文。"""

NOTICE_SYSTEM = """你是"会议通知Agent"。基于统筹Agent整理的活动要素，撰写一份正式、得体的校园会议/活动通知。
要求：
- 标题用"关于召开/举办XXX的通知"格式
- 包含：时间、地点、参会人员、议程/内容、要求、联系方式占位
- 语言正式、条理清晰，适合在校园公告栏或群内发布
- 末尾署"XX学院/组织 会务组"及日期占位"""

TODO_SYSTEM = """你是"待办事项Agent"。基于活动要素，拆解出完整的筹备待办清单。
每条待办输出为：`- [ ] 事项内容 | 负责人角色 | 截止节点 | 优先级(高/中/低)`
覆盖：场地预订、物资准备、宣传通知、人员联络、现场布置、应急预案、复盘归档等。
按筹备时间顺序排列。"""

TIMELINE_SYSTEM = """你是"时间线Agent"。基于活动要素，给出从现在到活动结束的关键里程碑时间线。
格式：
- T-7天：xxx
- T-3天：xxx
- T-1天：xxx
- 当天：xxx
- T+1天：复盘
若活动时间待定，以"活动日"为锚点相对描述。"""

RISK_SYSTEM = """你是"风险提示Agent"。基于活动要素，列出可能的风险与应对建议。
格式：`- 风险：xxx → 应对：xxx`
覆盖：天气、人员缺席、设备故障、超时、安全、预算等。"""

_DEMO_NOTE = "\n\n（演示结果，配置API后由大模型生成）"


def _mock_parse(raw: str) -> dict:
    text = raw.strip()
    first_line = text.splitlines()[0] if text else "校园活动"
    topic = first_line[:30] if first_line else "校园活动"
    time_match = re.search(
        r"(\d{1,2}月\d{1,2}日|\d{4}-\d{1,2}-\d{1,2}|下周[一二三四五六日天]|周[一二三四五六日天])",
        text,
    )
    time_str = time_match.group(1) if time_match else "待定（建议本周五下午）"
    loc_match = re.search(
        r"(教室|会议室|报告厅|操场|体育馆|礼堂|图书馆|活动中心|场地)\w*号?", text
    )
    loc_str = loc_match.group(0) if loc_match else "待定（建议申请会议室）"
    return {"topic": topic, "time": time_str, "location": loc_str, "raw": text}


def _mock_notice(info: dict) -> str:
    today = datetime.now().strftime("%Y年%m月%d日")
    return f"""关于举办{info['topic']}的通知

各相关单位、全体同学：

为推进相关工作，现定于 {info['time']} 在 {info['location']} 举办/召开"{info['topic']}"。现将有关事项通知如下：

一、时间：{info['time']}
二、地点：{info['location']}
三、参会/参与人员：相关师生及工作人员
四、主要内容：围绕"{info['topic']}"开展筹备与组织实施
五、要求：请参会人员提前10分钟到场，做好相应准备
六、联系方式：会务组 xxx（电话：xxx）

特此通知。

会务组
{today}"""


def _mock_todos() -> str:
    items = [
        ("成立筹备工作组，明确分工", "总协调", "T-7天", "高"),
        ("申请并确认活动场地", "后勤组", "T-5天", "高"),
        ("制定活动方案与预算", "总协调", "T-5天", "高"),
        ("发布预通知并收集参会回执", "宣传组", "T-3天", "中"),
        ("准备物资（签到表、横幅、设备等）", "后勤组", "T-2天", "中"),
        ("确认议程与发言人员", "总协调", "T-1天", "高"),
        ("现场布置与设备调试", "后勤组", "当天提前1小时", "高"),
        ("活动现场组织与记录", "会务组", "当天", "高"),
        ("整理材料、撰写简报与复盘", "总协调", "T+1天", "中"),
    ]
    return "\n".join(f"- [ ] {a} | {b} | {c} | {d}" for a, b, c, d in items)


def _mock_timeline() -> str:
    return """- T-7天：成立筹备组、明确分工与负责人
- T-5天：完成场地申请、方案与预算审批
- T-3天：发布预通知、收集回执、确认人数
- T-2天：物资到位、宣传推送
- T-1天：确认议程、发言人与流程彩排
- 当天-1h：现场布置、设备调试、签到准备
- 当天：活动执行、现场记录
- T+1天：材料归档、撰写简报、复盘总结"""


def _mock_risk() -> str:
    return """- 风险：场地临时被占用 → 应对：提前锁定并备选1个备用场地
- 风险：关键人员缺席 → 应对：明确替补发言人，重要角色AB角
- 风险：设备/投影故障 → 应对：提前调试并准备备用设备与纸质材料
- 风险：参与人数超预期 → 应对：按1.2倍准备物资与座位
- 风险：活动超时 → 应对：设定时间提醒，议程预留缓冲
- 风险：突发安全事件 → 应对：制定应急预案，明确疏散与联络人"""


def run_pipeline(raw_input: str, config: dict | None) -> dict:
    """运行多 Agent 协作流水线，返回各 Agent 输出。"""
    raw_input = (raw_input or "").strip()
    if not raw_input:
        return {"summary": "", "notice": "", "todos": "", "timeline": "", "risks": ""}

    parsed = chat(config, ORCH_SYSTEM, raw_input)
    context = raw_input if parsed is None else f"{parsed}\n\n【原始需求】\n{raw_input}"

    with ThreadPoolExecutor(max_workers=4) as ex:
        f_notice = ex.submit(chat, config, NOTICE_SYSTEM, context)
        f_todo = ex.submit(chat, config, TODO_SYSTEM, context)
        f_timeline = ex.submit(chat, config, TIMELINE_SYSTEM, context)
        f_risk = ex.submit(chat, config, RISK_SYSTEM, context)
        notice = f_notice.result()
        todos = f_todo.result()
        timeline = f_timeline.result()
        risks = f_risk.result()

    if parsed is None:
        info = _mock_parse(raw_input)
        parsed = (
            f"活动主题：{info['topic']}\n"
            f"活动类型：校园活动\n"
            f"时间：{info['time']}\n"
            f"地点：{info['location']}\n"
            f"参与对象：相关师生\n"
            f"核心目标：顺利组织{info['topic']}\n\n"
            f"（当前未配置大模型API，以上为本地规则解析的演示结果。"
            f"请在【设置】页配置API后获得完整智能生成能力。）"
        )
    if notice is None:
        notice = _mock_notice(_mock_parse(raw_input)) + _DEMO_NOTE
    if todos is None:
        todos = _mock_todos() + _DEMO_NOTE
    if timeline is None:
        timeline = _mock_timeline() + _DEMO_NOTE
    if risks is None:
        risks = _mock_risk() + _DEMO_NOTE

    return {
        "summary": parsed,
        "notice": notice,
        "todos": todos,
        "timeline": timeline,
        "risks": risks,
    }