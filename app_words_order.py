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
        width:100%;
    }
    .stTextInput>div>div>input {padding: 0.2em; font-size: 16px;}
    .translation {color:gray; font-size:16px; line-height:1.2; margin-bottom:0.8em;}
    .choice-header {margin-top:0.8em;}
    .progress {font-weight:bold; margin: 0.5rem 0;}
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
    """全体の状態を初期化。keep_history=True のときは累積履歴/時間は維持。"""
    keep_keys = {"file_uploader"}
    if keep_history:
        keep_keys.update({"history", "total_elapsed"})
    for key in list(st.session_state.keys()):
        if key not in keep_keys:
            del st.session_state[key]

# ==== CSV未アップロード時 ====
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
ss.setdefault("phase", "menu")                   # menu / quiz / done
ss.setdefault("history", [])                      # 累積（全ラン）
ss.setdefault("total_elapsed", 0)                 # 累積（秒）

# ランごとの状態
ss.setdefault("question_pool", [])                # 今回出題する問題の配列
ss.setdefault("run_total_questions", 0)           # 今回の問題数
ss.setdefault("run_answered", 0)                  # 今回 解答済み数
ss.setdefault("current", None)
ss.setdefault("selected_words", [])
ss.setdefault("remaining_words", [])
ss.setdefault("q_start_time", time.time())
ss.setdefault("segment_start", time.time())       # 今回の学習開始時刻
ss.setdefault("user_name", "")

# ==== ユーティリティ ====
def pick_question_pool(n: int):
    """df から n件サンプリングして question_pool を作る"""
    n = max(1, min(n, len(df)))
    records = df.sample(n=n, replace=False, random_state=None).to_dict("records")
    ss.question_pool = records
    ss.run_total_questions = n
    ss.run_answered = 0


def start_run():
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
    ss.remaining_words = shuffled[:]  # 未選択の単語
    ss.q_start_time = time.time()
    ss.phase = "quiz"


def human_time(sec: int) -> str:
    m = sec // 60
    s = sec % 60
    return f"{m}分{s}秒"


def prepare_csv():
    history_df = pd.DataFrame(ss.history)

    # 旧カラムがあれば削除
    for col in ["所要時間"]:
        if col in history_df.columns:
            history_df = history_df.drop(columns=[col])

    # 累積総学習時間を可読表記で付与（全行に同値）
    total_seconds = int(ss.total_elapsed)
    history_df["累計時間"] = human_time(total_seconds)

    # 列順そろえ
    desired_cols = ["出題形式", "英文", "結果", "経過秒", "累計時間"]
    for c in desired_cols:
        if c not in history_df.columns:
            history_df[c] = pd.NA
    history_df = history_df[desired_cols]

    # CSVへ
    timestamp = datetime.now(JST).strftime("%Y%m%d_%H%M%S")
    filename = f"{ss.user_name}_{timestamp}.csv" if ss.user_name else f"history_{timestamp}.csv"
    csv_buffer = io.StringIO()
    history_df.to_csv(csv_buffer, index=False, encoding="utf-8-sig")
    csv_data = csv_buffer.getvalue().encode("utf-8-sig")
    return filename, csv_data

# ==== メニュー：問題数の選択（ラジオ） ====
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

    # 進捗
    st.markdown(f"<div class='progress'>進捗: {ss.run_answered+1}/{ss.run_total_questions} 問</div>", unsafe_allow_html=True)

    # 表示文言（要望に合わせて）
    st.subheader("和訳")
    st.subheader("単語を並べ替えてください")
    st.write(current.get("", ""))  # 空キー参照の要望に合わせ安全に取得

    # 選択UI（ボタン：選んだら候補から消える）
    cols = st.columns(max(1, min(6, len(ss.remaining_words))))
    for i, w in enumerate(ss.remaining_words[:]):
        with cols[i % len(cols)]:
            # 重複単語でも key が衝突しないよう i を含める
            if st.button(w, key=f"pick_{ss.run_answered}_{i}"):
                ss.selected_words.append(w)
                ss.remaining_words.remove(w)
                st.rerun()

    st.write("あなたの並べ替え:", " ".join(ss.selected_words))

    c1, c2, c3 = st.columns(3)
    with c1:
        if st.button("やり直し", key=f"retry_{ss.run_answered}"):
            # 初期化（再シャッフル）
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
                st.success(f"正解！ {' '.join(words)}")
            else:
                st.error(f"不正解… 正解は {' '.join(words)}")

            # 履歴に追記（経過秒を保存、所要時間は保存しない）
            ss.history.append(
                {
                    "出題形式": "並べ替え",
                    "英文": sentence,
                    "結果": status,
                    "経過秒": elapsed_q,
                }
            )

            # 今回分の経過時間を累積へ
            ss.total_elapsed += elapsed_q
            ss.run_answered += 1

            time.sleep(0.6)
            if ss.run_answered >= ss.run_total_questions:
                ss.phase = "done"
                st.rerun()
            else:
                next_question()
                st.rerun()

# ==== 全問終了（今回のランの終了画面） ====
if ss.phase == "done":
    st.success("全問終了！お疲れさまでした🎉")

    # 今回のラン時間
    this_run_seconds = int(time.time() - ss.segment_start)
    def human_time(sec: int) -> str:
        m = sec // 60
        s = sec % 60
        return f"{m}分{s}秒"
    st.info(f"今回の所要時間: {human_time(this_run_seconds)}")

    # 累計時間
    st.info(f"累積総時間: {human_time(ss.total_elapsed)}")

    # 保存UI（氏名＋CSV ダウンロード）
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
            # 履歴・累計は維持して再スタート
            ss.phase = "menu"
            # ラン単位の状態だけ初期化
            for k in ["question_pool", "run_total_questions", "run_answered", "current", "selected_words", "remaining_words"]:
                if k in ss:
                    del ss[k]
            st.rerun()
    with c2:
        if st.button("終了", key="finish"):
            st.stop()
