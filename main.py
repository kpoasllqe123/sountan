import re
from itertools import combinations
import pandas as pd
import plotly.express as px
import streamlit as st

st.set_page_config(page_title="급식 규칙 찾기", layout="wide")

# 1. 데이터 로드 및 전처리
DATA_URL = "https://raw.githubusercontent.com/it-teacher-go/data-share-/main/songtan_meals_184.csv"


@st.cache_data
def load_and_process_data():
    # CSV 로드
    df = pd.read_csv(DATA_URL, encoding="utf-8")

    # 괄호 및 괄호 안 내용 제거 함수
    def clean_menu_item(item):
        cleaned = re.sub(r"\(.*?\)", "", item).strip()
        return cleaned

    # 트랜잭션(하루 식단 목록) 구성
    transactions = []
    all_items = set()

    for raw_menu in df["메뉴"].dropna():
        # 세로줄(|) 구분자로 분리 후 청소
        items = [clean_menu_item(x) for x in str(raw_menu).split("|")]
        # 빈 문자열 제거 및 중복 제거
        unique_items = set(filter(None, items))
        if unique_items:
            transactions.append(unique_items)
            all_items.update(unique_items)

    total_days = len(transactions)

    # 단일 품목 출현 빈도 계산
    item_counts = {}
    for t in transactions:
        for item in t:
            item_counts[item] = item_counts.get(item, 0) + 1

    # 동시 출현 메뉴 쌍(2-itemset) 빈도 계산
    pair_counts = {}
    for t in transactions:
        if len(t) >= 2:
            for item1, item2 in combinations(sorted(t), 2):
                pair_counts[(item1, item2)] = (
                    pair_counts.get((item1, item2), 0) + 1
                )

    # 연관 규칙 생성 (A -> B 및 B -> A)
    rules_list = []
    for (item1, item2), count in pair_counts.items():
        # A -> B
        supp_ab = count / total_days
        conf_a_b = count / item_counts[item1]
        lift_a_b = conf_a_b / (item_counts[item2] / total_days)

        rules_list.append(
            {
                "조건": item1,
                "결과": item2,
                "동시": count,
                "지지도": round(supp_ab, 4),
                "신뢰도": round(conf_a_b, 4),
                "향상도": round(lift_a_b, 4),
            }
        )

        # B -> A
        conf_b_a = count / item_counts[item2]
        lift_b_a = conf_b_a / (item_counts[item1] / total_days)

        rules_list.append(
            {
                "조건": item2,
                "결과": item1,
                "동시": count,
                "지지도": round(supp_ab, 4),
                "신뢰도": round(conf_b_a, 4),
                "향상도": round(lift_b_a, 4),
            }
        )

    rules_df = pd.DataFrame(rules_list)
    unique_pairs_count = len(pair_counts)

    return (
        total_days,
        len(all_items),
        unique_pairs_count,
        rules_df,
        sorted(list(all_items)),
        item_counts,
        pair_counts,
    )


# 데이터 가져오기
(
    total_days,
    num_items,
    num_pairs,
    rules_df,
    menu_options,
    item_counts,
    pair_counts,
) = load_and_process_data()

# 앱 헤더
st.title("🍚 송탄고 급식 메뉴 연관 규칙 탐색기")

# 요약 정보 표시
st.write(
    f"**급식 일수:** {total_days}일 | **메뉴 종류 수:** {num_items}개 | **함께 나온 적이 있는 메뉴 쌍의 수:** {num_pairs}쌍"
)
st.divider()

# 사이드바 컨트롤
st.sidebar.header("조회 및 정렬 설정")

# 메뉴 필터링 옵션
selected_menu = st.sidebar.selectbox(
    "특정 메뉴 선택 (전체 보기는 '전체')", ["전체"] + menu_options
)

# 최소 동시 일수 슬라이더 추가 (1~10, 기본값 1)
min_cooccurrence = st.sidebar.slider(
    "최소 동시 출현 일수", min_value=1, max_value=10, value=1
)

# 정렬 기준 선택
sort_option = st.sidebar.radio(
    "정렬 기준 선택", options=["향상도", "신뢰도", "동시"], index=0
)

# 1. 최소 동시 일수 필터링
filtered_df = rules_df[rules_df["동시"] >= min_cooccurrence].copy()

# 2. 특정 메뉴 필터링
if selected_menu != "전체":
    filtered_df = filtered_df[
        (filtered_df["조건"] == selected_menu) | (filtered_df["결과"] == selected_menu)
    ].copy()

# 3. 정렬 적용
filtered_df = filtered_df.sort_values(by=sort_option, ascending=False).reset_index(
    drop=True
)

# 슬라이더 및 조건 필터링 결과 개수 출력
st.info(f"🔍 현재 조건(최소 동시 일수 {min_cooccurrence}일 이상)을 만족하는 규칙 수: **{len(filtered_df)}개**")

# Plotly 가로 막대그래프 (향상도 상위 10개)
st.subheader("📊 향상도 상위 10개 규칙")
top10_df = filtered_df.sort_values(by="향상도", ascending=False).head(10).copy()

if not top10_df.empty:
    top10_df["규칙"] = top10_df["조건"] + " ➔ " + top10_df["결과"]
    top10_df = top10_df.sort_values(by="향상도", ascending=True)

    fig = px.bar(
        top10_df,
        x="향상도",
        y="규칙",
        orientation="h",
        text="향상도",
        color="향상도",
        color_continuous_scale="Viridis",
        labels={"향상도": "향상도 (Lift)", "규칙": "연관 규칙"},
    )
    fig.update_layout(height=400, showlegend=False)
    st.plotly_chart(fig, use_container_width=True)
else:
    st.warning("조건에 해당하는 규칙이 없습니다.")

# 연관 규칙 데이터 프레임 출력
st.subheader("📋 연관 규칙 목록")
st.dataframe(filtered_df, use_container_width=True)

st.divider()

# --- 함께 나온 적 없는 짝 화면 ---
st.subheader("❓ 함께 나온 적 없는 짝 찾기")
st.write(
    "특정 메뉴를 선택하면, 해당 메뉴와 **한 번도 함께 나오지 않았으면서 혼자서는 10일 이상 나온 메뉴** 목록을 보여줍니다."
)

target_menu = st.selectbox(
    "조회할 대상 메뉴를 선택하세요",
    menu_options,
    key="unpaired_menu_select",
)

target_days = item_counts.get(target_menu, 0)
st.write(f"👉 **선택한 메뉴 [{target_menu}] (이)가 급식에 나온 총 횟수:** {target_days}일")

# 함께 나온 적 없는 메뉴 탐색
unpaired_list = []
for other_menu, count in item_counts.items():
    if other_menu == target_menu:
        continue

    # 혼자 10일 이상 나온 메뉴만 대상
    if count >= 10:
        # 두 메뉴의 쌍 확인 (알파벳/가나다 순으로 pair_counts 키가 저장됨)
        pair_key = tuple(sorted([target_menu, other_menu]))

        # 동시 출현 횟수가 0인 경우 (pair_counts에 키가 없음)
        if pair_key not in pair_counts:
            unpaired_list.append({"메뉴": other_menu, "출현 일수": count})

if unpaired_list:
    unpaired_df = pd.DataFrame(unpaired_list)
    unpaired_df = unpaired_df.sort_values(by="출현 일수", ascending=False).reset_index(
        drop=True
    )
    st.dataframe(unpaired_df, use_container_width=True)
else:
    st.write("조건(10일 이상 출현 및 동시 출현 0회)을 만족하는 함께 나온 적 없는 짝 메뉴가 없습니다.")
