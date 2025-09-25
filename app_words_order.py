import random
import pandas as pd
import streamlit as st
import time
from datetime import datetime, timedelta, timezone
import io
from streamlit_sortables import sortable

# ==== 日本時間 ====
try:
    from zoneinfo import ZoneInfo
    JST = ZoneInfo("Asia/Tokyo")
except Exception:
    JST = timezone(timedelta(hours=9))

now = datetime.now(JST)

# ==== 利用制限 ====
if 0 <= now.hour < 6:
    st.error("本アプリは深夜0時～朝6時まで利用できません。")
    st.stop()

if now.date() >= datetime(2025, 11, 1, tzinfo=JST).date():
    st.error("本アプリの利用期限は2025年10月31日までです。")
    st.stop()

# ==== スタイル調整 ====
st.markdown(
    """
<style>
h1, h2, h3, h4, h5, h6 {margin-top: 0.2em; margin-bottom: 0.2em;}
p, div, label {margin-top: 0.05em; margin-bottom: 0.05em; line-height: 1.1;}
button, .stButton>button {
    padding: 0.4em;
    margin: 0.05em 0;
    font-size:20px;
    width:100%;
}
.stTextInput>div>div>input {padding: 0.2em; font-size: 16px;}
.translation {color:gray; font-size:16px; line-height:1.2; margin-bottom:0.8em;}
.choice-header {margin-top:0.8em;}
</style>
""",
    unsafe_allow_html=True,
)

# ==== タイトル ====
st.markdown("<h1 style='font-size:22px;'>英文並べ替えクイズ（スマホ対応・CSV版）</h1>", unsafe_allow_html=True)

# ==== ファイルアップロード ====
uploaded_file = st.file_uploader(
    "単語リスト（CSV, UTF-8推奨, 列名：単語・意味・例文・和訳）をアップロードしてください （利用期限25-10-31）",
    type=["csv"],
    key="file_uploader",
)

# ==== 初期化関数 ====
def reset_all():
    for key in list(st.session_state.keys()):
        if key != "file_uploader":
            del st.session_state[key]

if uploaded_file is None:
    reset_all()
    st.info("まずは CSV をアップロードしてください。")
    st.stop()

# ==== CSV読み込み ====
try:
    df = pd.read_csv(uploaded_file, encoding="utf-8")
except UnicodeDecodeError:
    df = pd.read_csv(uploaded_file, encoding="shift-jis")

required_cols = {"単語", "意味", "例文", "和訳"}
if not required_cols.issubset(df.columns):
    st.error("CSVには『単語』『意味』『例文』『和訳』列が必要です。")
    st.stop()

# ==== セッション初期化 ====
ss = st.session_state
if "remaining" not in ss:
    ss.remaining = df.to_dict("records")
if "current" not in ss:
    ss.current = None
if "phase" not in ss:
    ss.phase = "menu"
if "last_outcome" not in ss:
    ss.last_outcome = None
if "segment_start" not in ss:
    ss.segment_start = time.time()
if "total_elapsed" not in ss:
    ss.total_elapsed = 0
if "history" not in ss:
    ss.history = []
if "show_save_ui" not in ss:
    ss.show_save_ui = False
if "user_name" not in ss:
    ss.user_name = ""
if "q_start_time" not in ss:
    ss.q_start_time = time.time()

# ==== 次の問題 ====
def next_question():
    if not ss.remaining:
        ss.current = None
        ss.phase = "done"
        return
    ss.current = random.choice(ss.remaining)
    ss.remaining = [q for q in ss.remaining if q != ss.current]
    ss.last_outcome = None
    ss.q_start_time = tim
