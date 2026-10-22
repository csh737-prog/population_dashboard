import json
import numpy as np
import pandas as pd
import plotly.express as px
import requests
import streamlit as st


# --------------------------------------------------
# 기본 설정
# --------------------------------------------------
st.set_page_config(
    page_title="전국 고령화 단계구분도",
    page_icon="🗺️",
    layout="wide",
)

POPULATION_URL = (
    "https://raw.githubusercontent.com/first2022-cyber/"
    "contents//main/population_ts_yearly_gender.zip"
)
GEOJSON_URL = (
    "https://raw.githubusercontent.com/first2022-cyber/"
    "contents//main/sigungu_kr.geojson"
)

TARGET_YEAR = "2026"


# --------------------------------------------------
# 데이터 불러오기
# --------------------------------------------------
@st.cache_data(show_spinner="인구 데이터를 불러오는 중...")
def load_population():
    # 코드 열은 문자열로 읽어 앞자리 0을 보존
    df = pd.read_csv(
        POPULATION_URL,
        compression="zip",
        dtype={"코드": "string"},
        low_memory=False,
    )

    required = {"연도", "코드"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(
            f"인구 데이터에 필요한 열이 없습니다: {sorted(missing)}"
        )

    # 2026년 자료만 사용
    year = (
        df["연도"]
        .astype("string")
        .str.extract(r"(\d{4})", expand=False)
    )
    df = df.loc[year.eq(TARGET_YEAR)].copy()

    if df.empty:
        raise ValueError(
            "인구 데이터에서 2026년 자료를 찾지 못했습니다."
        )

    # 동 코드를 문자열로 유지하고 앞 5자리로 시군구 코드 생성
    df["코드"] = df["코드"].astype("string").str.strip()
    df["시군구코드"] = df["코드"].str[:5]

    # '계_'로 시작하는 열만 집계 (남/여 열은 제외)
    total_cols = [
        col for col in df.columns
        if col.startswith("계_")
    ]

    # 65세 이상: 65세부터 100세 이상까지
    senior_cols = [
        col for col in total_cols
        if (
            col == "계_100세 이상"
            or (
                col.startswith("계_")
                and col.endswith("세")
                and col[2:-1].isdigit()
                and int(col[2:-1]) >= 65
            )
        )
    ]

    if not total_cols or not senior_cols:
        raise ValueError(
            "전체 인구 또는 65세 이상 인구 열을 찾지 못했습니다."
        )

    # 비숫자 값은 결측치로 처리하고 숫자로 변환
    df[total_cols] = df[total_cols].apply(
        pd.to_numeric, errors="coerce"
    )
    df[total_cols] = df[total_cols].fillna(0)

    # 읍·면·동별 전체 인구와 고령 인구를 먼저 계산한 뒤
    # 시군구 코드 앞 5자리 기준으로 합산
    df["전체인구"] = df[total_cols].sum(axis=1)
    df["65세이상인구"] = df[senior_cols].sum(axis=1)

    result = (
        df.groupby("시군구코드", as_index=False)
        .agg(
            전체인구=("전체인구", "sum"),
            65세이상인구=("65세이상인구", "sum"),
        )
    )

    # 전체 인구가 0인 지역은 비율을 계산하지 않음
    result["고령화율"] = np.where(
        result["전체인구"] > 0,
        result["65세이상인구"] / result["전체인구"] * 100,
        np.nan,
    )

    return result


@st.cache_data(show_spinner="시군구 경계를 불러오는 중...")
def load_geojson():
    response = requests.get(GEOJSON_URL, timeout=60)
    response.raise_for_status()
    geojson = response.json()

    # 경계 속성의 코드도 문자열로 통일
    for feature in geojson["features"]:
        properties = feature["properties"]
        code = str(properties["코드"]).strip()
        properties["코드"] = code.zfill(5)

    return geojson


# --------------------------------------------------
# 화면
# --------------------------------------------------
st.title("전국 고령화 단계구분도")
st.caption(
    "2026년 6월 기준 · 전국 시군구별 65세 이상 인구 비율"
)

try:
    population = load_population()
    geojson = load_geojson()

except Exception as exc:
    st.error(f"데이터를 불러오거나 처리하지 못했습니다: {exc}")
    st.stop()


# 경계 파일의 코드와 인구 집계 코드가 일치하는지 확인
boundary_codes = {
    feature["properties"]["코드"]
    for feature in geojson["features"]
}

population["시군구코드"] = (
    population["시군구코드"].astype("string").str.strip().str.zfill(5)
)

# 이름이 아니라 5자리 코드로 결합
map_df = population[
    population["시군구코드"].isin(boundary_codes)
].copy()

if map_df.empty:
    st.error(
        "인구 데이터와 경계 GeoJSON의 코드가 일치하지 않습니다. "
        "두 파일의 코드 형식을 확인해 주세요."
    )
    st.stop()

# GeoJSON 속성에서 시군구 이름을 가져옴
name_by_code = {
    feature["properties"]["코드"]: feature["properties"]["시군구"]
    for feature in geojson["features"]
}

map_df["시군구"] = map_df["시군구코드"].map(name_by_code)
map_df = map_df.dropna(subset=["고령화율"])

if map_df.empty:
    st.error("표시할 수 있는 고령화율 데이터가 없습니다.")
    st.stop()


# --------------------------------------------------
# 요약 지표
# --------------------------------------------------
col1, col2, col3 = st.columns(3)

with col1:
    st.metric("매칭된 시군구", f"{len(map_df):,}개")

with col2:
    st.metric(
        "평균 고령화율",
        f"{map_df['고령화율'].mean():.2f}%",
    )

with col3:
    max_idx = map_df["고령화율"].idxmax()
    st.metric(
        "고령화율 최고 지역",
        map_df.loc[max_idx, "시군구"],
        f"{map_df.loc[max_idx, '고령화율']:.2f}%",
    )


# --------------------------------------------------
# Plotly 단계구분도
# --------------------------------------------------
fig = px.choropleth(
    map_df,
    geojson=geojson,
    locations="시군구코드",
    featureidkey="properties.코드",
    color="고령화율",
    color_continuous_scale=[
        "#fff5eb",
        "#fdd0a2",
        "#f16913",
        "#a63603",
        "#67000d",
    ],
    range_color=(0, float(map_df["고령화율"].max())),
    custom_data=["시군구", "고령화율"],
    labels={"고령화율": "고령화율 (%)"},
    hover_name="시군구",
)

fig.update_traces(
    marker_line_color="#777777",
    marker_line_width=0.45,
    hovertemplate=(
        "<b>%{customdata[0]}</b><br>"
        "고령화율: %{customdata[1]:.2f}%"
        "<extra></extra>"
    ),
    colorbar={
        "title": "고령화율 (%)",
        "ticksuffix": "%",
    },
)

# 타일 배경 없이 경계만 표시
fig.update_geos(
    visible=False,
    fitbounds="locations",
    showcountries=False,
    showcoastlines=False,
    showland=False,
    showframe=False,
)

fig.update_layout(
    height=780,
    margin={"l": 0, "r": 0, "t": 20, "b": 0},
    paper_bgcolor="white",
    plot_bgcolor="white",
)

st.plotly_chart(fig, use_container_width=True)

# --------------------------------------------------
# 데이터 표
# --------------------------------------------------
with st.expander("시군구별 고령화율 데이터 보기"):
    table = map_df[
        ["시군구코드", "시군구", "전체인구", "65세이상인구", "고령화율"]
    ].copy()

    table = table.sort_values("고령화율", ascending=False)
    table = table.rename(
        columns={
            "시군구코드": "코드",
            "전체인구": "전체 인구",
            "65세이상인구": "65세 이상 인구",
            "고령화율": "고령화율 (%)",
        }
    )

    st.dataframe(
        table.style.format(
            {
                "전체 인구": "{:,.0f}",
                "65세 이상 인구": "{:,.0f}",
                "고령화율 (%)": "{:.2f}",
            }
        ),
        use_container_width=True,
        hide_index=True,
    )

    st.download_button(
        "CSV 다운로드",
        data=table.to_csv(index=False).encode("utf-8-sig"),
        file_name="전국_시군구별_고령화율_2026.csv",
        mime="text/csv",
    )
