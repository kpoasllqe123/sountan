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

    return total_days, len(all_items), unique_pairs_count, rules_df, sorted(list(all_items))


# 데이터 가져오기
total_days, num_items, num_pairs, rules_df, menu_options = load_and_process_data()

# 앱 헤더
st.title("🍚 송탄고 급식 메뉴 연관 규칙 탐색기")

# 요약 정보 표시
st.write(
    f"**급식 일수:** {total_days}일 | **메뉴 종류 수:** {num_items}개 | **함께 나온 적이 있는 메뉴 쌍의 수:** {num_pairs}쌍"
)
st.divider()

# 레이아웃 구성: 사이드바 컨트롤
st.sidebar.header("조회 및 정렬 설정")

# 메뉴 필터링 옵션
selected_menu = st.sidebar.selectbox(
    "특정 메뉴 선택 (전체 보기는 '전체')", ["전체"] + menu_options
)

# 정렬 기준 선택
sort_option = st.sidebar.radio(
    "정렬 기준 선택", options=["향상도", "신뢰도", "동시"], index=0
)

# 데이터 필터링 적용
if selected_menu != "전체":
    filtered_df = rules_df[
        (rules_df["조건"] == selected_menu) | (rules_df["결과"] == selected_menu)
    ].copy()
else:
    filtered_df = rules_df.copy()

# 정렬 적용
filtered_df = filtered_df.sort_values(by=sort_option, ascending=False).reset_index(
    drop=True
)

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
    st.info("조건에 해당하는 규칙이 없습니다.")

# 연관 규칙 데이터 프레임 출력
st.subheader("📋 연관 규칙 목록")
st.dataframe(filtered_df, use_container_width=True)
