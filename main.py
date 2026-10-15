
import re

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st


# --------------------------------------------------
# 1. 페이지 기본 설정
# --------------------------------------------------
st.set_page_config(
    page_title="동네별 인구 피라미드",
    page_icon="🏘️",
    layout="wide",
)

# 따뜻한 색감의 화면 디자인
st.markdown(
    """
    <style>
    .stApp {
        background-color: #FFF9F2;
    }

    h1, h2, h3 {
        color: #71452F;
    }

    div[data-testid="stMetric"] {
        background-color: #FFF0DF;
        border: 1px solid #F0D8BF;
        padding: 14px;
        border-radius: 12px;
    }

    div[data-testid="stSelectbox"] label {
        color: #71452F;
        font-weight: 600;
    }

    </style>
    """,
    unsafe_allow_html=True,
)


# --------------------------------------------------
# 2. 데이터 불러오기
# --------------------------------------------------
DATA_URL = (
    "https://raw.githubusercontent.com/"
    "csh737-prog/population_dashboard/"
    "main/population_ts_yearly_gender.zip"
)


@st.cache_data(show_spinner="전국 인구 데이터를 불러오는 중입니다...")
def load_data():
    """ZIP 파일을 읽고 인구 데이터를 정리합니다."""

    # GitHub의 원본 ZIP 주소에서 압축 CSV를 읽습니다.
    # ZIP 내부에 CSV 파일이 하나 들어 있어야 합니다.
    df = pd.read_csv(
        DATA_URL,
        compression="zip",
        encoding="utf-8",
        low_memory=False,
    )

    # 열 이름 앞뒤에 공백이 있다면 제거합니다.
    df.columns = df.columns.astype(str).str.strip()

    # 필수 지역 및 연도 열이 있는지 확인합니다.
    required_columns = ["연도", "시도", "시군구", "동"]
    missing_columns = [
        col for col in required_columns if col not in df.columns
    ]

    if missing_columns:
        raise ValueError(
            f"필수 열을 찾을 수 없습니다: {missing_columns}\n"
            f"실제 열 이름: {df.columns.tolist()[:20]}"
        )

    # 연도는 숫자로 통일합니다.
    df["연도"] = pd.to_numeric(df["연도"], errors="coerce")
    df = df.dropna(subset=["연도"]).copy()
    df["연도"] = df["연도"].astype(int)

    # 데이터에 실제로 존재하는 가장 최신 연도만 사용합니다.
    latest_year = int(df["연도"].max())
    df = df.loc[df["연도"] == latest_year].copy()

    # 나이 라벨을 항상 0세부터 100세 이상까지 같은 순서로 만듭니다.
    age_labels = [f"{age}세" for age in range(101)]
    age_labels[-1] = "100세 이상"

    # 남녀 인구 열 이름을 자동으로 확인합니다.
    male_columns = [f"남_{age}" for age in age_labels]
    female_columns = [f"여_{age}" for age in age_labels]

    # 데이터의 열 이름과 일치하는지 검사합니다.
    missing_age_columns = [
        col
        for col in male_columns + female_columns
        if col not in df.columns
    ]

    if missing_age_columns:
        raise ValueError(
            "일부 나이별 인구 열을 찾을 수 없습니다.\n"
            f"누락된 열 예시: {missing_age_columns[:10]}"
        )

    # 인구 값은 숫자로 변환하고, 비어 있는 값은 0으로 처리합니다.
    population_columns = male_columns + female_columns

    for col in population_columns:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    # 지역 이름을 문자열로 통일합니다.
    for col in ["시도", "시군구", "동"]:
        df[col] = df[col].fillna("").astype(str).str.strip()

    # 선택 목록에 불필요한 빈 지역이 섞이지 않도록 정리합니다.
    df = df.loc[df["시도"] != ""].copy()

    return df, latest_year, age_labels, male_columns, female_columns


# --------------------------------------------------
# 3. 데이터 로드 및 오류 안내
# --------------------------------------------------
try:
    df, latest_year, age_labels, male_columns, female_columns = load_data()
except Exception as e:
    st.error("인구 데이터를 불러오거나 정리하지 못했습니다.")
    st.info(
        "GitHub 저장소의 ZIP 주소, CSV 열 이름, "
        "ZIP 내부 파일 구성을 확인해 주세요."
    )
    st.exception(e)
    st.stop()


# --------------------------------------------------
# 4. 화면 제목
# --------------------------------------------------
st.title("🏘️ 동네별 인구 피라미드")
st.markdown(
    """
    우리 동네에는 어떤 연령대의 주민이 많을까요?

    시도, 시군구, 동을 차례로 선택하면 최신 연도의
    남녀별 인구 분포를 확인할 수 있습니다.
    """
)

st.caption(f"📅 분석 기준 연도: {latest_year}년")


# --------------------------------------------------
# 5. 지역 선택 드롭다운 3개
# --------------------------------------------------
st.subheader("📍 지역 선택")

col1, col2, col3 = st.columns(3)

# 첫 번째: 시도 선택
sido_list = sorted(df["시도"].unique().tolist())

with col1:
    selected_sido = st.selectbox(
        "① 시도",
        options=sido_list,
        key="selected_sido",
    )

# 두 번째: 선택한 시도에 속한 시군구만 표시
sigungu_df = df.loc[df["시도"] == selected_sido]
sigungu_list = sorted(sigungu_df["시군구"].unique().tolist())

with col2:
    selected_sigungu = st.selectbox(
        "② 시군구",
        options=sigungu_list,
        key="selected_sigungu",
    )

# 세 번째: 선택한 시군구에 속한 동만 표시
dong_df = sigungu_df.loc[
    sigungu_df["시군구"] == selected_sigungu
]
dong_list = sorted(dong_df["동"].unique().tolist())

with col3:
    selected_dong = st.selectbox(
        "③ 동",
        options=dong_list,
        key="selected_dong",
    )


# --------------------------------------------------
# 6. 선택한 동네의 인구 데이터 추출
# --------------------------------------------------
selected_df = df.loc[
    (df["시도"] == selected_sido)
    & (df["시군구"] == selected_sigungu)
    & (df["동"] == selected_dong)
].copy()

if selected_df.empty:
    st.warning("선택한 지역의 인구 데이터가 없습니다.")
    st.stop()

# 같은 지역이 여러 행으로 존재할 경우 연령별로 합산합니다.
male_population = (
    selected_df[male_columns]
    .sum(axis=0)
    .to_numpy(dtype=float)
)

female_population = (
    selected_df[female_columns]
    .sum(axis=0)
    .to_numpy(dtype=float)
)

# 남성은 왼쪽에 표시하도록 음수로 변환합니다.
male_left = -male_population
female_right = female_population

total_male = int(male_population.sum())
total_female = int(female_population.sum())
total_population = total_male + total_female


# --------------------------------------------------
# 7. 요약 지표 표시
# --------------------------------------------------
st.subheader(
    f"📊 {selected_sido} {selected_sigungu} {selected_dong}"
)

metric1, metric2, metric3 = st.columns(3)

metric1.metric("전체 인구", f"{total_population:,}명")
metric2.metric("남성 인구", f"{total_male:,}명")
metric3.metric("여성 인구", f"{total_female:,}명")


# --------------------------------------------------
# 8. 인구 피라미드 그리기
# --------------------------------------------------
fig = go.Figure()

# 남성: 왼쪽 막대
fig.add_trace(
    go.Bar(
        name="남성",
        y=age_labels,
        x=male_left,
        orientation="h",
        marker_color="#D98265",
        hovertemplate=(
            "나이: %{y}<br>"
            "남성 인구: %{customdata:,}명"
            "<extra></extra>"
        ),
        customdata=male_population,
    )
)

# 여성: 오른쪽 막대
fig.add_trace(
    go.Bar(
        name="여성",
        y=age_labels,
        x=female_right,
        orientation="h",
        marker_color="#E8B65C",
        hovertemplate=(
            "나이: %{y}<br>"
            "여성 인구: %{x:,}명"
            "<extra></extra>"
        ),
    )
)

# 양쪽 막대 길이를 비교하기 쉽도록 대칭 축을 사용합니다.
max_population = max(
    float(male_population.max()) if len(male_population) else 0,
    float(female_population.max()) if len(female_population) else 0,
    1,
)

# 보기 좋은 단위로 축 범위를 올림합니다.
axis_limit = int(np.ceil(max_population / 10) * 10)
if axis_limit <= 0:
    axis_limit = 10

# 천 단위 구분 기호를 포함한 눈금 라벨을 양쪽에 표시합니다.
tick_step = max(1, int(np.ceil(axis_limit / 5)))
tick_values_positive = list(range(0, axis_limit + 1, tick_step))

# 왼쪽 축은 실제 음수 값이지만 라벨에는 양수 인구수를 표시합니다.
tick_values = (
    [-value for value in reversed(tick_values_positive) if value != 0]
    + tick_values_positive
)

tick_text = [
    f"{abs(value):,}" for value in tick_values
]

fig.update_layout(
    title={
        "text": f"{selected_dong} 연령별 남녀 인구",
        "x": 0.5,
        "xanchor": "center",
    },
    barmode="relative",
    bargap=0.12,
    height=1100,
    paper_bgcolor="#FFF9F2",
    plot_bgcolor="#FFF9F2",
    font={
        "family": "Arial, sans-serif",
        "size": 12,
        "color": "#5B4636",
    },
    legend={
        "title": "성별",
        "orientation": "h",
        "yanchor": "bottom",
        "y": 1.01,
        "xanchor": "center",
        "x": 0.5,
    },
    margin={
        "l": 100,
        "r": 40,
        "t": 100,
        "b": 80,
    },
    xaxis={
        "title": "인구수 (명)",
        "range": [-axis_limit, axis_limit],
        "tickmode": "array",
        "tickvals": tick_values,
        "ticktext": tick_text,
        "zeroline": True,
        "zerolinewidth": 2,
        "zerolinecolor": "#B9A18B",
        "gridcolor": "#EADFD3",
    },
    yaxis={
        "title": "나이",
        # 나이 라벨을 0세부터 100세 이상까지 명시적으로 고정합니다.
        # categoryorder=array이므로 값 크기순으로 정렬되지 않습니다.
        "categoryorder": "array",
        "categoryarray": age_labels,
        # 축 전체를 뒤집는 autorange='reversed'는 사용하지 않습니다.
        "showgrid": False,
        "automargin": True,
    },
)

# 그래프를 만들고 난 뒤에도 나이 순서 설정을 확인합니다.
# categoryarray의 첫 항목은 0세, 마지막 항목은 100세 이상이어야 합니다.
assert age_labels[0] == "0세"
assert age_labels[-1] == "100세 이상"
assert fig.layout.yaxis.categoryorder == "array"
assert list(fig.layout.yaxis.categoryarray) == age_labels

# Plotly 그래프 출력
st.plotly_chart(fig, use_container_width=True)

st.caption(
    "※ 남성은 왼쪽(음수), 여성은 오른쪽(양수)입니다. "
    "가로축의 숫자는 비교하기 쉽도록 절댓값으로 표시합니다."
)

# --------------------------------------------------
# 9. 연령별 인구표
# --------------------------------------------------
with st.expander("📋 연령별 남녀 인구표 보기"):
    population_table = pd.DataFrame(
        {
            "나이": age_labels,
            "남성 인구": male_population.astype(int),
            "여성 인구": female_population.astype(int),
        }
    )
    population_table["전체 인구"] = (
        population_table["남성 인구"]
        + population_table["여성 인구"]
    )

    st.dataframe(
        population_table,
        hide_index=True,
        use_container_width=True,
    )

    # 필요하면 선택 지역의 연령별 인구표를 CSV로 저장할 수 있습니다.
    csv_data = population_table.to_csv(
        index=False,
        encoding="utf-8-sig",
    )

    st.download_button(
        label="📥 연령별 인구표 CSV 다운로드",
        data=csv_data,
        file_name=(
            f"{latest_year}_{selected_sido}_"
            f"{selected_sigungu}_{selected_dong}_인구표.csv"
        ),
        mime="text/csv",
    )

st.divider()
st.caption(
    "데이터 출처: "
    "csh737-prog/population_dashboard GitHub 저장소"
)
