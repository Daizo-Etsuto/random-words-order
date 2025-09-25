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
st.markdown("""
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
""", unsafe_allow_html=True)

# ==== タイトル ====
st.markdown("<h1 style='font-size:22px;'>英文並べ替えクイズ（スマホ対応・CSV版）</h1>", unsafe_allow_html=True)

# ==== ファイルアップロード ====
uploaded_file = st.file_uploader(
    "単語リスト（CSV, UTF-8推奨, 列名：単語・意味・例文・和訳）をアップロードしてください （利用期限25-10-31）",
    type=["csv"],
    key="file_uploader"
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
if "remaining" not in ss: ss.remaining = df.to_dict("records")
if "current" not in ss: ss.current = None
if "phase" not in ss: ss.phase = "menu"
if "last_outcome" not in ss: ss.last_outcome = None
if "segment_start" not in ss: ss.segment_start = time.time()
if "total_elapsed" not in ss: ss.total_elapsed = 0
if "history" not in ss: ss.history = []
if "show_save_ui" not in ss: ss.show_save_ui = False
if "user_name" not in ss: ss.user_name = ""
if "q_start_time" not in ss: ss.q_start_time = time.time()

# ==== 次の問題 ====
def next_question():
    if not ss.remaining:
        ss.current = None
        ss.phase = "done"
        return
    ss.current = random.choice(ss.remaining)
    ss.remaining = [q for q in ss.remaining if q != ss.current]
    ss.last_outcome = None
    ss.q_start_time = time.time()
    ss.phase = "quiz"

def reset_quiz_to_menu():
    ss.remaining = df.to_dict("records")
    ss.current = None
    ss.phase = "menu"
    ss.last_outcome = None

def prepare_csv():
    timestamp = datetime.now(JST).strftime("%Y%m%d_%H%M%S")
    filename = f"{ss.user_name}_{timestamp}.csv"
    history_df = pd.DataFrame(ss.history)

    # 累積総学習時間
    total_seconds = int(ss.total_elapsed + (time.time() - ss.segment_start))
    minutes = total_seconds // 60
    seconds = total_seconds % 60
    history_df["総学習時間"] = f"{minutes}分{seconds}秒"

    csv_buffer = io.StringIO()
    history_df.to_csv(csv_buffer, index=False, encoding="utf-8-sig")
    csv_data = csv_buffer.getvalue().encode("utf-8-sig")
    return filename, csv_data

# ==== メニュー ====
if ss.phase == "menu":
    if st.button("開始"):
        ss.segment_start = time.time()
        next_question()
        st.rerun()

# ==== 全問終了 ====
if ss.phase == "done":
    st.success("全問終了！お疲れさまでした🎉")

    # 今回の所要時間
    elapsed = int(time.time() - ss.segment_start)
    minutes = elapsed // 60
    seconds = elapsed % 60
    st.info(f"今回の所要時間: {minutes}分 {seconds}秒")

    # 累積総時間
    total_seconds = int(ss.total_elapsed + elapsed)
    tmin = total_seconds // 60
    tsec = total_seconds % 60
    st.info(f"累積総時間: {tmin}分 {tsec}秒")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("もう一回"):
            ss.total_elapsed += elapsed
            ss.segment_start = time.time()
            reset_quiz_to_menu()
            st.rerun()
    with col2:
        if st.button("終了"):
            ss.show_save_ui = True
            ss.phase = "finished"
            st.rerun()
    st.stop()

# ==== 終了後の保存UI ====
if ss.phase == "finished" and ss.show_save_ui:
    st.subheader("学習履歴の保存")
    ss.user_name = st.text_input("氏名を入力してください", value=ss.user_name)
    if ss.user_name:
        filename, csv_data = prepare_csv()
        if st.download_button(
            "📥 保存（ダウンロード）",
            data=csv_data,
            file_name=filename,
            mime="text/csv"
        ):
            reset_all()
            st.success("保存しました。新しい学習を始められます。")
            st.rerun()
... # ==== 出題 ====
... if ss.phase == "quiz" and ss.current:
...     current = ss.current
...     sentence = current["例文"].strip()   # 並べ替え対象は「例文」
...     words = sentence.split()
...     shuffled = random.sample(words, len(words))
... 
...     st.subheader("和訳:")
...     st.write(current["和訳"])
... 
...     st.subheader("単語を並べ替えてください")
...     sorted_words = sortable(shuffled, direction="horizontal", key=f"q_{len(ss.history)}")
... 
...     if st.button("採点"):
...         elapsed_q = int(time.time() - ss.q_start_time)
...         if sorted_words == words:
...             status = "正解"
...             st.success(f"正解！ {' '.join(words)}")
...         else:
...             status = "不正解"
...             st.error(f"不正解… 正解は {' '.join(words)}")
... 
...         # 履歴に追加
...         ss.history.append({
...             "英文": sentence,
...             "出題形式": "並べ替え",
...             "結果": status,
...             "経過秒": elapsed_q
...         })
...         time.sleep(1)
...         next_question()
...         st.rerun()


