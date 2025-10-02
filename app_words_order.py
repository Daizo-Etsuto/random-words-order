import random
import pandas as pd
import streamlit as st
import time
from datetime import datetime, timedelta, timezone
import io

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
    }
    .stTextInput>div>div>input {padding: 0.2em; font-size: 16px;}
    .translation {color:gray; font-size:16px; line-height:1.2; margin-bottom:0.8em;}
    .choice-header {margin-top:0.8em;}
    .progress {font-weight:bold; margin: 0.5rem 0;}

    /* 単語ボタンを横並び＋折り返し */
    div.word-wrap {
        display: flex;
        flex-wrap: wrap;
        justify-content: flex-start;
    }
    div.word-wrap > div {
        margin: 0.2em;
    }
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
def reset_all(keep_history=False):
    keep_keys = {"file_uploader"}
    if keep_history:
        keep_keys.update({"history", "total_elapsed"})
    for key in list(st.session_state.keys()):
        if key not in keep_keys:
            del st.session_state[key]

if uploaded_file is None:
    reset_all(keep_history=True)
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
ss.setdefault("phase", "menu")
ss.setdefault("history", [])
ss.setdefault("total_elapsed", 0)

ss.setdefault("question_pool", [])
ss.setdefault("run_total_questions", 0)
ss.setdefault("run_answered", 0)
ss.setdefault("current", None)
ss.setdefault("selected_words", [])
ss.setdefault("remaining_words", [])
ss.setdefault("q_start_time", time.time())
ss.setdefault("segment_start", time.time())
ss.setdefault("total_elapsed_before_run", 0)
ss.setdefault("user_name", "")

# ==== ユーティリティ ====
def human_time(sec: int) -> str:
    m = sec // 60
    s = sec % 60
    return f"{m}分{s}秒"

def pick_question_pool(n: int):
    n = max(1, min(n, len(df)))
    records = df.sample(n=n, replace=False, random_state=None).to_dict("records")
    ss.question_pool = records
    ss.run_total_questions = n
    ss.run_answered = 0

def start_run():
    ss.total_elapsed_before_run = int(ss.total_elapsed)
    ss.segment_start = time.time()
    ss.q_start_time = time.time()
    ss.current = None
    next_question()

def next_question():
    if not ss.question_pool:
        ss.current = None
        ss.phase = "done"
        return
    ss.current = random.choice(ss.question_pool)
    ss.question_pool = [q for q in ss.question_pool if q is not ss.current]
    sentence = ss.current["例文"].strip()
    words = sentence.split()
    shuffled = random.sample(words, len(words))
    ss.selected_words = []
    ss.remaining_words = shuffled[:]
    ss.q_start_time = time.time()
    ss.phase = "quiz"

def prepare_csv():
    history_df = pd.DataFrame(ss.history)
    for col in ["所要時間"]:
        if col in history_df.columns:
            history_df = history_df.drop(columns=[col])
    total_seconds = int(ss.total_elapsed)
    history_df["累計時間"] = human_time(total_seconds)
    desired_cols = ["出題形式", "英文", "結果", "経過秒", "累計時間"]
    for c in desired_cols:
        if c not in history_df.columns:
            history_df[c] = pd.NA
    history_df = history_df[desired_cols]
    timestamp = datetime.now(JST).strftime("%Y%m%d_%H%M%S")
    filename = f"{ss.user_name}_{timestamp}.csv" if ss.user_name else f"history_{timestamp}.csv"
    csv_buffer = io.StringIO()
    history_df.to_csv(csv_buffer, index=False, encoding="utf-8-sig")
    csv_data = csv_buffer.getvalue().encode("utf-8-sig")
    return filename, csv_data

# ==== メニュー ====
if ss.phase == "menu":
    st.subheader("問題数を選んでください")

    choice = st.radio(
        "出題数を選択",
        ["5題", "10題", "好きな数"],
        index=0,
        horizontal=True,
        key="q_choice",
    )

    if choice == "好きな数":
        num = st.number_input(
            "好きな数",
            min_value=1,
            max_value=len(df),
            value=min(5, len(df)),
            step=1,
            key="custom_num",
        )
        selected_n = int(num)
    else:
        selected_n = 5 if choice == "5題" else 10
        selected_n = min(selected_n, len(df))

    if st.button("開始", use_container_width=True, key="start_run"):
        pick_question_pool(selected_n)
        start_run()
        st.rerun()

    st.stop()

# ==== 出題 ====
if ss.phase == "quiz" and ss.current:
    current = ss.current
    sentence = current["例文"].strip()
    words = sentence.split()

    st.markdown(f"<div class='progress'>進捗: {ss.run_answered+1}/{ss.run_total_questions} 問</div>", unsafe_allow_html=True)
    st.subheader("単語を並べ替えてください")
    st.write(current.get("和訳"))

    # ==== 単語ボタン（横並び・折り返し）====
    st.markdown('<div class="word-wrap">', unsafe_allow_html=True)
    for i, w in enumerate(ss.remaining_words[:]):
        with st.container():
            if st.button(w, key=f"pick_{ss.run_answered}_{i}"):
                ss.selected_words.append(w)
                ss.remaining_words.remove(w)
                st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

    st.write("あなたの並べ替え:", " ".join(ss.selected_words))

    # ==== 操作ボタン ====
    c1, c2, c3 = st.columns([1, 1, 1], gap="small")
    with c1:
        if st.button("やり直し", key=f"retry_{ss.run_answered}"):
            shuffled = random.sample(words, len(words))
            ss.selected_words = []
            ss.remaining_words = shuffled[:]
            st.rerun()
    with c2:
        if st.button("1つ戻す", key=f"undo_{ss.run_answered}"):
            if ss.selected_words:
                last = ss.selected_words.pop()
                ss.remaining_words.append(last)
                st.rerun()
    with c3:
        if st.button("採点", key=f"grade_{ss.run_answered}"):
            elapsed_q = int(time.time() - ss.q_start_time)
            status = "正解" if ss.selected_words == words else "不正解"
            if status == "正解":
                st.success(f"<div style='text-align:left;'>✅ 正解！ {' '.join(words)}</div>", unsafe_allow_html=True)
            else:
                st.error(f"<div style='text-align:left;'>❌ 不正解… 正解は {' '.join(words)}</div>", unsafe_allow_html=True)

            ss.history.append(
                {
                    "出題形式": "並べ替え",
                    "英文": sentence,
                    "結果": status,
                    "経過秒": elapsed_q,
                }
            )
            ss.total_elapsed += elapsed_q
            ss.run_answered += 1

            time.sleep(0.6)
            if ss.run_answered >= ss.run_total_questions:
                ss.phase = "done"
                st.rerun()
            else:
                next_question()
                st.rerun()

# ==== 全問終了 ====
if ss.phase == "done":
    st.success("全問終了！お疲れさまでした🎉")

    this_run_seconds = int(ss.total_elapsed - ss.total_elapsed_before_run)
    st.info(f"今回の所要時間: {human_time(this_run_seconds)}")
    st.info(f"累計総時間: {human_time(int(ss.total_elapsed))}")

    st.subheader("学習履歴の保存")
    ss.user_name = st.text_input("氏名を入力してください", value=ss.user_name)

    if ss.user_name:
        filename, csv_data = prepare_csv()
        st.download_button(
            "📥 保存（ダウンロード）",
            data=csv_data,
            file_name=filename,
            mime="text/csv",
            key="download_done",
        )

    c1, c2 = st.columns(2)
    with c1:
        if st.button("もう一回", key="again"):
            ss.phase = "menu"
            for k in ["question_pool", "run_total_questions", "run_answered", "current", "selected_words", "remaining_words", "total_elapsed_before_run"]:
                if k in ss:
                    del ss[k]
            st.rerun()
    with c2:
        if st.button("終了", key="finish"):
            ss.history = []
            ss.total_elapsed = 0
            reset_all(keep_history=False)
            ss.phase = "menu"
            st.rerun()
