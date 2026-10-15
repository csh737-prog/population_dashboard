import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st


# --------------------------------------------------
# 1. 페이지 기본 설정 및 따뜻한 톤의 디자인
# --------------------------------------------------
st.set_page_config(
    page_title="동네별 인구 피라미드",
    page_icon="🏘️",
    layout="wide",
)

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
    """ZIP 파일을 읽고 최신 연도의 인구 데이터만 정리합니다."""

    df = pd.read_csv(
        DATA_URL,
        compression="zip",
        encoding="utf-8",
        low_memory=False,
    )

    # 열 이름 앞뒤에 공백이 있다면 제거합니다.
    df.columns = df.columns.astype(str).str.strip()

    # 지역 및 연도 열이 있는지 확인합니다.
    required_columns = ["연도", "시도", "시군구", "동"]
    missing_columns = [
        col for col in required_columns if col not in df.columns
    ]

    if missing_columns:
        raise ValueError(
            f"필수 열이 없습니다: {missing_columns}\n"
            f"실제 열 이름: {df.columns.tolist()[:20]}"
        )

    # 연도를 숫자로 바꾸고 최신 연도만 선택합니다.
    df["연도"] = pd.to_numeric(df["연도"], errors="coerce")
    df = df.dropna(subset=["연도"]).copy()
    df["연도"] = df["연도"].astype(int)

    latest_year = int(df["연도"].max())
    df = df.loc[df["연도"] == latest_year].copy()

    # 나이 라벨을 0세부터 100세 이상까지 고정합니다.
    age_labels = [f"{age}세" for age in range(101)]
    age_labels[-1] = "100세 이상"

    male_columns = [f"남_{age}" for age in age_labels]
    female_columns = [f"여_{age}" for age in age_labels]
    population_columns = male_columns + female_columns

    missing_age_columns = [
        col for col in population_columns if col not in df.columns
    ]

    if missing_age_columns:
        raise ValueError(
            "일부 나이별 인구 열을 찾을 수 없습니다.\n"
            f"누락된 열: {missing_age_columns[:10]}"
        )

    # 인구 값은 숫자로 바꾸고 빈 값은 0으로 처리합니다.
    for col in population_columns:
        df[col] = pd.to_numeric(
            df[col], errors="coerce"
        ).fillna(0)

    # 지역 이름을 문자열로 통일합니다.
    for col in ["시도", "시군구", "동"]:
        df[col] = df[col].fillna("").astype(str).str.strip()

    df = df.loc[df["시도"] != ""].copy()

    return df, latest_year, age_labels, male_columns, female_columns


# --------------------------------------------------
# 3. 데이터 로드 오류 처리
# --------------------------------------------------
try:
    (
        df,
        latest_year,
        age_labels,
        male_columns,
        female_columns,
    ) = load_data()

except Exception as e:
    st.error("인구 데이터를 불러오거나 정리하지 못했습니다.")
    st.info(
        "데이터 주소, CSV 열 이름, ZIP 내부 파일 구성을 확인해 주세요."
    )
    st.exception(e)
    st.stop()


# --------------------------------------------------
# 4. 앱 제목
# --------------------------------------------------
st.title("🏘️ 동네별 인구 피라미드")

st.markdown(
    """
    우리 동네에는 어떤 연령대의 주민이 많을까요?

    지역을 선택하면 최신 연도의 인구 지표와 남녀별 인구 분포를
    한눈에 확인할 수 있습니다.
    """
)

st.caption(f"📅 분석 기준 연도: {latest_year}년")


# --------------------------------------------------
# 5. 시도 → 시군구 → 동 선택
# --------------------------------------------------
st.subheader("📍 지역 선택")

col1, col2, col3 = st.columns(3)

# 첫 번째 드롭다운: 시도
sido_list = sorted(df["시도"].unique().tolist())

with col1:
    selected_sido = st.selectbox(
        "① 시도",
        options=sido_list,
        key="selected_sido",
    )

# 선택한 시도에 속하는 시군구만 보여 줍니다.
sigungu_df = df.loc[df["시도"] == selected_sido]
sigungu_list = sorted(sigungu_df["시군구"].unique().tolist())

with col2:
    selected_sigungu = st.selectbox(
        "② 시군구",
        options=sigungu_list,
        key="selected_sigungu",
    )

# 선택한 시군구에 속하는 동만 보여 줍니다.
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
# 6. 선택한 지역의 연령별 인구 계산
# --------------------------------------------------
selected_df = df.loc[
    (df["시도"] == selected_sido)
    & (df["시군구"] == selected_sigungu)
    & (df["동"] == selected_dong)
].copy()

if selected_df.empty:
    st.warning("선택한 지역의 인구 데이터가 없습니다.")
    st.stop()

# 같은 지역이 여러 행이면 연령별로 합산합니다.
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

# 두 성별 인구를 합쳐 연령별 전체 인구를 계산합니다.
age_population = male_population + female_population

total_male = int(male_population.sum())
total_female = int(female_population.sum())
total_population = total_male + total_female


# --------------------------------------------------
# 7. 핵심 지표 계산
# --------------------------------------------------

# 평균연령: 각 나이에 해당 인구를 곱해 가중평균을 구합니다.
# 100세 이상은 실제 나이를 알 수 없으므로 계산상 100세로 봅니다.
age_numbers = np.arange(101, dtype=float)

if total_population > 0:
    average_age = float(
        np.dot(age_numbers, age_population) / total_population
    )
else:
    average_age = 0.0

# 고령화율: 전체 인구 중 65세 이상 인구의 비율입니다.
# 인덱스 65부터 마지막인 100세 이상까지 합산합니다.
elderly_population = float(age_population[65:].sum())

if total_population > 0:
    aging_rate = elderly_population / total_population * 100
else:
    aging_rate = 0.0

# 아이 비율: 전체 인구 중 0~14세 인구의 비율입니다.
children_population = float(age_population[:15].sum())

if total_population > 0:
    children_rate = children_population / total_population * 100
else:
    children_rate = 0.0


# --------------------------------------------------
# 8. 지표 카드 3개
# --------------------------------------------------
st.subheader(
    f"📊 {selected_sido} {selected_sigungu} {selected_dong} 핵심 지표"
)

metric1, metric2, metric3 = st.columns(3)

with metric1:
    st.metric(
        label="👥 총인구",
        value=f"{total_population:,}명",
    )

with metric2:
    if total_population > 0:
        average_label = f"{average_age:.1f}세"
    else:
        average_label = "계산 불가"

    st.metric(
        label="🎂 평균연령",
        value=average_label,
    )

with metric3:
    # 고령화율이 20%를 초과할 때만 주의 표시를 붙입니다.
    card_col, warning_col = st.columns(
        [4, 1],
        vertical_alignment="center",
    )

    with card_col:
        st.metric(
            label="👵 고령화율",
            value=f"{aging_rate:.1f}%",
        )

    with warning_col:
        if aging_rate > 20:
            st.markdown(
                """
                <div style="
                    background-color: #FCE8D5;
                    border: 1px solid #E9B27E;
                    border-radius: 10px;
                    padding: 8px 4px;
                    text-align: center;
                    color: #9B4D19;
                    font-weight: bold;
                    font-size: 13px;
                ">
                    ⚠️<br>주의
                </div>
                """,
                unsafe_allow_html=True,
            )

# 고령화율 주의 기준을 설명합니다.
if aging_rate > 20:
    st.warning(
        "고령화율이 20%를 초과합니다. "
        "전체 인구에서 65세 이상 주민이 차지하는 비중이 높습니다."
    )


# --------------------------------------------------
# 9. 인구 피라미드 그래프
# --------------------------------------------------
st.subheader("📈 연령별 인구 피라미드")

# 남성은 음수로 바꾸어 왼쪽에 표시합니다.
male_left = -male_population

# 여성은 양수 그대로 오른쪽에 표시합니다.
female_right = female_population

# 양쪽 막대가 대칭으로 보이도록 가로축 범위를 설정합니다.
max_population = max(
    float(male_population.max()),
    float(female_population.max()),
    1.0,
)

axis_limit = int(np.ceil(max_population / 10) * 10)
axis_limit = max(axis_limit, 10)

tick_step = max(1, int(np.ceil(axis_limit / 5)))

# 왼쪽은 음수, 오른쪽은 양수 눈금을 사용하되
# 라벨에는 양쪽 모두 인구의 절댓값을 표시합니다.
positive_ticks = list(range(0, axis_limit + 1, tick_step))

tick_values = (
    [-value for value in reversed(positive_ticks) if value != 0]
    + positive_ticks
)

tick_text = [f"{abs(value):,}" for value in tick_values]

fig = go.Figure()

# 남성 막대: 왼쪽
fig.add_trace(
    go.Bar(
        name="남성",
        y=age_labels,
        x=male_left,
        orientation="h",
        marker_color="#D98265",
        customdata=male_population,
        hovertemplate=(
            "나이: %{y}<br>"
            "남성 인구: %{customdata:,.0f}명"
            "<extra></extra>"
        ),
    )
)

# 여성 막대: 오른쪽
fig.add_trace(
    go.Bar(
        name="여성",
        y=age_labels,
        x=female_right,
        orientation="h",
        marker_color="#E8B65C",
        hovertemplate=(
            "나이: %{y}<br>"
            "여성 인구: %{x:,.0f}명"
            "<extra></extra>"
        ),
    )
)

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
        # 나이 라벨을 지정한 순서대로 고정합니다.
        # 값 크기순 정렬이나 축 전체 뒤집기는 사용하지 않습니다.
        "categoryorder": "array",
        "categoryarray": age_labels,
        "showgrid": False,
        "automargin": True,
    },
)

# 축 순서 검증: 0세가 첫 항목이고 100세 이상이 마지막 항목입니다.
assert age_labels[0] == "0세"
assert age_labels[-1] == "100세 이상"
assert fig.layout.yaxis.categoryorder == "array"
assert list(fig.layout.yaxis.categoryarray) == age_labels

st.plotly_chart(fig, use_container_width=True)


# --------------------------------------------------
# 10. 동네 특징 한 줄 자동 설명
# --------------------------------------------------
st.subheader("💬 우리 동네 한 줄 분석")

# 0~14세와 65세 이상 인구의 비율을 비교합니다.
# 차이가 2%p 이내라면 두 연령대의 비중이 비슷하다고 설명합니다.
rate_difference = children_rate - aging_rate

if total_population == 0:
    neighborhood_comment = (
        "인구 데이터가 없어 동네의 연령 구성을 분석하기 어렵습니다."
    )

elif abs(rate_difference) <= 2:
    neighborhood_comment = (
        f"아이 비율은 {children_rate:.1f}%, "
        f"어르신 비율은 {aging_rate:.1f}%로 "
        "두 연령대의 비중이 비슷한 편입니다."
    )

elif rate_difference > 0:
    neighborhood_comment = (
        f"아이 비율은 {children_rate:.1f}%, "
        f"어르신 비율은 {aging_rate:.1f}%입니다. "
        "65세 이상 주민보다 0~14세 아이들의 비중이 높은 편입니다."
    )

else:
    neighborhood_comment = (
        f"아이 비율은 {children_rate:.1f}%, "
        f"어르신 비율은 {aging_rate:.1f}%입니다. "
        "0~14세 아이들보다 65세 이상 어르신의 비중이 높은 편입니다."
    )

st.info(
    f"**이 동네는 아이가 많은 편인가요, 어르신이 많은 편인가요?** "
    f"{neighborhood_comment}"
)


# --------------------------------------------------
# 11. 연령별 인구표 및 CSV 다운로드
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


# --------------------------------------------------
# 12. 데이터 출처 및 계산 기준
# --------------------------------------------------
st.divider()

st.caption(
    "데이터 출처: csh737-prog/population_dashboard GitHub 저장소"
)

st.caption(
    "고령화율 = 65세 이상 인구 ÷ 총인구 × 100. "
    "주의 표시는 고령화율이 20%를 초과할 때 나타납니다."
)

st.caption(
    "평균연령은 연령별 인구 가중평균이며, "
    "100세 이상 인구는 계산상 100세로 처리합니다."
)

st.caption(
    "한 줄 분석은 0~14세와 65세 이상 인구의 비율을 비교합니다. "
    "두 비율의 차이가 2%p 이내이면 비중이 비슷한 편으로 표시합니다."
)
