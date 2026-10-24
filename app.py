"""校园统筹 Agent —— Streamlit 主应用。

基于多 Agent 协作的会议/活动组织工具：
- 注册/登录（SQLite 持久化）
- 创建任务：自然语言需求 -> 多Agent协作 -> 会议通知/待办/时间线/风险
- 我的任务：保存与查看历史
- 设置：配置 OpenAI 兼容大模型 API
"""
import streamlit as st

from core import db, auth
from core.agents import run_pipeline
from core.llm import PROVIDERS, is_configured

st.set_page_config(page_title="校园统筹 Agent", page_icon="🎓", layout="wide")
db.init_db()

if "user" not in st.session_state:
    st.session_state.user = None
if "last_result" not in st.session_state:
    st.session_state.last_result = None
if "last_input" not in st.session_state:
    st.session_state.last_input = ""


def _default_title(raw: str) -> str:
    line = (raw.strip().splitlines() or [""])[0]
    return (line or "校园活动")[:30]


# ---------------- 登录 / 注册 ----------------
def auth_view():
    st.title("🎓 校园统筹 Agent")
    st.caption("基于多 Agent 协作的会议 / 活动组织工具")
    st.markdown(
        "用一句话描述你的会议或活动需求，多个智能体协作为你生成"
        "**正式会议通知、待办清单、筹备时间线与风险提示**。"
    )
    col_l, col_r = st.columns([1, 1])
    with col_l:
        st.subheader("🔐 登录")
        with st.form("login_form"):
            lu = st.text_input("用户名")
            lp = st.text_input("密码", type="password")
            if st.form_submit_button("登录", use_container_width=True):
                ok, msg, user = auth.login(lu, lp)
                if ok:
                    st.session_state.user = user
                    st.rerun()
                else:
                    st.error(msg)
    with col_r:
        st.subheader("📝 注册")
        with st.form("reg_form"):
            ru = st.text_input("用户名（3~20 字符）")
            rp = st.text_input("密码（至少 6 位）", type="password")
            if st.form_submit_button("注册", use_container_width=True):
                ok, msg = auth.register(ru, rp)
                if ok:
                    st.success(msg)
                else:
                    st.error(msg)
    st.divider()
    st.markdown(
        "💡 **提示**：首次使用请先注册账号。登录后在【设置】页配置大模型 API "
        "（支持 OpenAI / DeepSeek / 通义千问 / 智谱 / Kimi 等兼容接口）；"
        "未配置时将以本地规则演示模式运行。"
    )


# ---------------- 创建任务 ----------------
def create_page(user):
    st.header("📝 创建会议 / 活动任务")
    cfg = db.get_config(user["id"])
    if is_configured(cfg):
        st.success(f"已接入大模型：{cfg['model']} @ {cfg['provider']}")
    else:
        st.warning("当前为演示模式（未配置大模型 API）。结果由本地规则生成，请在【设置】页配置 API 以获得完整能力。")

    st.markdown("##### 描述你的需求")
    raw = st.text_area(
        "活动需求描述",
        height=180,
        placeholder=(
            "例如：下周三下午2点在学术报告厅召开学院学生会换届选举大会，"
            "需要全体学生干部参加，提前布置会场并准备选票……"
        ),
        label_visibility="collapsed",
    )

    if st.button("🚀 生成会议通知与待办", type="primary", use_container_width=True):
        if not raw.strip():
            st.error("请先输入活动需求描述")
            return
        with st.spinner("多 Agent 协作中：统筹 → 通知 / 待办 / 时间线 / 风险 ……"):
            result = run_pipeline(raw, cfg)
        st.session_state.last_result = result
        st.session_state.last_input = raw

    result = st.session_state.last_result
    if result:
        st.divider()
        st.subheader("🤖 协作结果")
        tab1, tab2, tab3, tab4, tab5 = st.tabs(
            ["📋 统筹摘要", "📨 会议通知", "✅ 待办事项", "📅 时间线", "⚠️ 风险提示"]
        )
        with tab1:
            st.markdown(result["summary"])
        with tab2:
            st.markdown(result["notice"])
        with tab3:
            st.markdown(result["todos"])
        with tab4:
            st.markdown(result["timeline"])
        with tab5:
            st.markdown(result["risks"])

        st.divider()
        with st.form("save_form"):
            title = st.text_input(
                "任务标题", value=_default_title(st.session_state.last_input)
            )
            if st.form_submit_button("💾 保存到我的任务", type="primary"):
                tid = db.save_task(
                    user["id"], title, st.session_state.last_input, result
                )
                st.toast(f"已保存任务 #{tid}")
                st.session_state.last_result = None
                st.session_state.last_input = ""


# ---------------- 我的任务 ----------------
def tasks_page(user):
    st.header("📋 我的任务")
    tasks = db.list_tasks(user["id"])
    if not tasks:
        st.info("还没有保存的任务，去【创建任务】页生成一个吧。")
        return
    for t in tasks:
        with st.expander(f"#{t['id']} · {t['title']}　（{t['created_at'][:16]}）"):
            tabs = st.tabs(
                ["📨 通知", "✅ 待办", "📅 时间线", "⚠️ 风险", "📋 摘要", "原始输入"]
            )
            with tabs[0]:
                st.markdown(t["notice"] or "—")
            with tabs[1]:
                st.markdown(t["todos"] or "—")
            with tabs[2]:
                st.markdown(t["timeline"] or "—")
            with tabs[3]:
                st.markdown(t["risks"] or "—")
            with tabs[4]:
                st.markdown(t["summary"] or "—")
            with tabs[5]:
                st.text(t["raw_input"])
            if st.button("🗑️ 删除", key=f"del_{t['id']}"):
                db.delete_task(user["id"], t["id"])
                st.rerun()


# ---------------- 设置 ----------------
def settings_page(user):
    st.header("⚙️ 大模型 API 设置")
    cfg = db.get_config(user["id"])
    keys = list(PROVIDERS.keys())
    cur_provider = cfg["provider"] if cfg and cfg["provider"] in PROVIDERS else keys[0]
    provider = st.selectbox(
        "服务提供商（选择后自动填充地址与模型）", keys, index=keys.index(cur_provider)
    )
    preset = PROVIDERS[provider]
    col1, col2 = st.columns(2)
    with col1:
        api_base = st.text_input(
            "API Base URL",
            value=(cfg["api_base"] if cfg else "") or preset["api_base"],
        )
    with col2:
        model = st.text_input(
            "模型名称", value=(cfg["model"] if cfg else "") or preset["model"]
        )
    api_key = st.text_input(
        "API Key",
        value=cfg["api_key"] if cfg else "",
        type="password",
        placeholder="sk-...",
    )
    temperature = st.slider(
        "Temperature",
        0.0,
        1.5,
        float(cfg["temperature"]) if cfg else 0.7,
        0.1,
    )
    if st.button("💾 保存配置", type="primary"):
        db.upsert_config(user["id"], provider, api_base, api_key, model, temperature)
        st.toast("配置已保存")
        st.rerun()
    st.divider()
    st.markdown("##### 说明")
    st.markdown(
        "- 本应用采用 **OpenAI 兼容接口**，凡兼容 `/v1/chat/completions` 的服务均可接入。\n"
        "- API Key 仅保存在本地 SQLite 数据库，不会上传任何服务器。\n"
        "- 未填写 API Key 时，应用以**演示模式**运行（本地规则生成）。"
    )


# ---------------- 主流程 ----------------
def main():
    if st.session_state.user is None:
        auth_view()
        return
    user = st.session_state.user
    with st.sidebar:
        st.markdown(f"👤 **{user['username']}**")
        st.caption(f"注册于 {user['created_at'][:10]}")
        page = st.radio("导航", ["📝 创建任务", "📋 我的任务", "⚙️ 设置"])
        st.divider()
        if st.button("🚪 退出登录", use_container_width=True):
            st.session_state.user = None
            st.rerun()
    if page == "📝 创建任务":
        create_page(user)
    elif page == "📋 我的任务":
        tasks_page(user)
    else:
        settings_page(user)


if __name__ == "__main__":
    main()