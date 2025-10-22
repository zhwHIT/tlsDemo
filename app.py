import streamlit as st
import pandas as pd
import datetime
from txtry import tlsByQianFan
# app.py


st.set_page_config(page_title="事件脉络分析 Demo", layout="wide")

st.title("🕸️ 事件脉络分析 Demo")

st.markdown("""
输入 **Topic** 与时间范围，自动分析事件，并展示时间线。
""")

# ===== 输入区域 =====
topic = st.text_input("Topic（主题）", "中菲海上冲突")
start_time_input = st.text_input("开始时间（字符串或数字，默认 -1）", "")
end_time = st.text_input("结束时间（字符串，默认 2025-10）", "2025-10")

# 默认值处理
start_time = start_time_input.strip() if start_time_input.strip() else "-1"

# ===== 按钮触发分析 =====
if st.button("开始分析 🚀"):
    with st.spinner("正在分析中，请稍候..."):
        tl, refer = tlsByQianFan(topic, start_time, end_time, [])

    # ===== 建立 refer_id -> url 映射表 =====
    refer_dict = {r["id"]: r["url"] for r in refer if "id" in r and "url" in r}

    # ===== 将 refer 替换为对应 url =====
    for item in tl:
        ref_ids = item.get("refer", [])
        if isinstance(ref_ids, list):
            urls = [refer_dict.get(i, "") for i in ref_ids if i in refer_dict]
            item["refer"] = "; ".join(urls)
        elif isinstance(ref_ids, int):
            item["refer"] = refer_dict.get(ref_ids, "")
        else:
            item["refer"] = ""

    # ===== 转换为 DataFrame =====
    df_tl = pd.DataFrame(tl)
    st.subheader("📜 事件时间线")
    st.dataframe(df_tl, use_container_width=True)

    # ===== 下载按钮 =====
    st.download_button(
        label="📥 下载时间线数据 (CSV)",
        data=df_tl.to_csv(index=False).encode("utf-8-sig"),
        file_name=f"{topic}_timeline.csv",
        mime="text/csv",
    )
