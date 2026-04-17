"""
app.py — NuCana (NCNA) 투자 분석 대시보드 (Streamlit)
"""

import json
import os
from pathlib import Path
from datetime import datetime

import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd

# ── 설정 ─────────────────────────────────────────
st.set_page_config(
    page_title="NCNA 투자 분석",
    page_icon="🧬",
    layout="wide",
    initial_sidebar_state="collapsed",
)

DATA_DIR = Path(__file__).parent / "data"

# ── 데이터 로드 ──────────────────────────────────
@st.cache_data(ttl=1800)
def load(name: str) -> dict:
    path = DATA_DIR / f"{name}.json"
    if path.exists():
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return {}


def load_all():
    return {
        "market":      load("market"),
        "financials":  load("financials"),
        "pipeline":    load("pipeline"),
        "filings":     load("filings"),
        "news":        load("news"),
        "fundamental": load("fundamental"),
        "catalyst":    load("catalyst"),
        "risk":        load("risk"),
        "summary":     load("summary"),
    }


# ── 헬퍼 ─────────────────────────────────────────
def fmt_usd(val, unit=""):
    if val is None:
        return "N/A"
    if abs(val) >= 1_000_000_000:
        return f"${val/1_000_000_000:.2f}B{unit}"
    if abs(val) >= 1_000_000:
        return f"${val/1_000_000:.2f}M{unit}"
    if abs(val) >= 1_000:
        return f"${val/1_000:.1f}K{unit}"
    return f"${val:.2f}{unit}"


def updated_str(data: dict) -> str:
    ts = data.get("updated_at", "")
    if ts:
        try:
            dt = datetime.fromisoformat(ts)
            return dt.strftime("%Y-%m-%d %H:%M UTC")
        except Exception:
            return ts
    return "N/A"


def risk_color(level: str) -> str:
    return {"critical": "#ff4b4b", "high": "#ff8c00", "medium": "#ffd700", "low": "#00cc88"}.get(level, "#888")


def sentiment_color(s: str) -> str:
    return {"positive": "🟢", "negative": "🔴", "neutral": "⚪"}.get(s, "⚪")


# ── 메인 ─────────────────────────────────────────
def main():
    d = load_all()
    market     = d["market"]
    financials = d["financials"]
    pipeline   = d["pipeline"]
    filings    = d["filings"]
    news       = d["news"]
    fundamental = d["fundamental"]
    catalyst   = d["catalyst"]
    risk       = d["risk"]
    summary    = d["summary"]

    if not market:
        st.error("data/ 폴더에 데이터가 없습니다. `python run_collectors.py`를 먼저 실행하세요.")
        st.stop()

    price   = market.get("price", {})
    tech    = market.get("technicals", {})
    info    = market.get("info", {}) or {}

    # ── 헤더 ─────────────────────────────────────
    h_col1, h_col2 = st.columns([6, 1])
    h_col1.title("🧬 NuCana plc (NCNA) — 투자 분석 대시보드")
    h_col1.caption(f"마지막 업데이트: {updated_str(market)}")
    if h_col2.button("🔄 새로고침", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

    # ── 상단 KPI 카드 ─────────────────────────────
    col1, col2, col3, col4, col5, col6 = st.columns(6)
    current = price.get("current", 0)
    chg = price.get("change_pct", 0)
    chg_color = "normal" if chg >= 0 else "inverse"

    col1.metric("현재가", f"${current}", f"{chg:+.2f}%", delta_color=chg_color)
    col2.metric("시가총액", fmt_usd(info.get("market_cap")))
    col3.metric("52주 고가 대비", f"{price.get('pct_from_52w_high', 0):.1f}%")

    runway = (financials.get("runway") or {})
    runway_months = runway.get("months")
    col4.metric("Cash Runway", f"{runway_months:.0f}개월" if runway_months else "N/A",
                runway.get("assessment", ""))

    risk_score = risk.get("risk_score", 0)
    col5.metric("리스크 점수", f"{risk_score}/10",
                risk.get("risk_summary", {}).get("overall_level", ""))

    catalyst_score = catalyst.get("catalyst_score", 0)
    col6.metric("카탈리스트 점수", f"{catalyst_score}/10")

    st.divider()

    # ── 탭 ───────────────────────────────────────
    tabs = st.tabs(["📈 기술적 분석", "💰 재무 분석", "🔬 파이프라인", "📋 공시", "📰 뉴스", "⚠️ 리스크", "🤖 AI 요약"])

    # ═══════════════════════════════════════════
    # TAB 1: 기술적 분석
    # ═══════════════════════════════════════════
    with tabs[0]:
        st.subheader("주가 차트 (1년)")

        history = market.get("history", [])
        if history:
            df = pd.DataFrame(history)
            df["date"] = pd.to_datetime(df["date"])

            fig = go.Figure()

            # 캔들 대신 라인 (데이터 단순화)
            fig.add_trace(go.Scatter(
                x=df["date"], y=df["close"],
                name="종가", line=dict(color="#00b4d8", width=2)
            ))

            # SMA
            if tech.get("sma_20"):
                sma20_val = tech["sma_20"]
                fig.add_hline(y=sma20_val, line_dash="dot", line_color="#ffd700",
                              annotation_text=f"SMA20 ${sma20_val:.2f}")
            if tech.get("sma_50"):
                sma50_val = tech["sma_50"]
                fig.add_hline(y=sma50_val, line_dash="dot", line_color="#ff8c00",
                              annotation_text=f"SMA50 ${sma50_val:.2f}")

            # 볼린저밴드
            if tech.get("bb_upper") and tech.get("bb_lower"):
                fig.add_hrect(y0=tech["bb_lower"], y1=tech["bb_upper"],
                              fillcolor="rgba(0,180,216,0.07)", line_width=0,
                              annotation_text="볼린저밴드")

            fig.update_layout(
                height=400, template="plotly_dark",
                margin=dict(l=0, r=0, t=10, b=0),
                xaxis_title="날짜", yaxis_title="가격 ($)",
                legend=dict(orientation="h", y=1.02),
            )
            st.plotly_chart(fig, use_container_width=True)

            # 거래량
            vol_fig = go.Figure(go.Bar(
                x=df["date"], y=df["volume"],
                marker_color="#00b4d8", opacity=0.6, name="거래량"
            ))
            vol_fig.update_layout(
                height=150, template="plotly_dark",
                margin=dict(l=0, r=0, t=0, b=0),
                showlegend=False,
            )
            st.plotly_chart(vol_fig, use_container_width=True)

        # 기술 지표
        st.subheader("기술 지표")
        t_col1, t_col2, t_col3, t_col4 = st.columns(4)
        rsi = tech.get("rsi_14")
        rsi_status = "과매도" if rsi and rsi < 30 else ("과매수" if rsi and rsi > 70 else "중립")
        t_col1.metric("RSI (14)", f"{rsi:.1f}" if rsi else "N/A", rsi_status)
        t_col2.metric("MACD", f"{tech.get('macd', 0):.4f}" if tech.get('macd') else "N/A",
                      f"Signal: {tech.get('macd_signal', 0):.4f}" if tech.get('macd_signal') else "")
        t_col3.metric("볼린저 상단", f"${tech.get('bb_upper', 0):.3f}" if tech.get('bb_upper') else "N/A")
        t_col4.metric("볼린저 하단", f"${tech.get('bb_lower', 0):.3f}" if tech.get('bb_lower') else "N/A")

        # 신호
        signals = market.get("signals", [])
        if signals:
            st.subheader("기술적 신호")
            for sig in signals:
                icon = "🟢" if sig["type"] == "bullish" else "🔴"
                st.write(f"{icon} **{sig['indicator']}**: {sig['note']}")

    # ═══════════════════════════════════════════
    # TAB 2: 재무 분석
    # ═══════════════════════════════════════════
    with tabs[1]:
        f_col1, f_col2 = st.columns(2)

        with f_col1:
            st.subheader("현금 & Runway")
            bs = financials.get("balance_sheet", {}) or {}
            burn = financials.get("burn_rate", {}) or {}
            km = financials.get("key_metrics", {}) or {}

            st.metric("최근 현금 잔고", fmt_usd(bs.get("latest_cash")),
                      f"기준: {bs.get('latest_date', 'N/A')}")
            st.metric("월 평균 소각률", fmt_usd(abs(burn.get("avg_monthly_burn", 0) or 0)),
                      "소각 중" if burn.get("is_cash_burning") else "양전환")

            if runway_months:
                # Runway 게이지
                gauge = go.Figure(go.Indicator(
                    mode="gauge+number",
                    value=runway_months,
                    title={"text": "Cash Runway (개월)"},
                    gauge={
                        "axis": {"range": [0, 36]},
                        "bar": {"color": "#00cc88" if runway_months >= 18 else ("#ffd700" if runway_months >= 12 else "#ff4b4b")},
                        "steps": [
                            {"range": [0, 6], "color": "rgba(255,75,75,0.2)"},
                            {"range": [6, 12], "color": "rgba(255,140,0,0.2)"},
                            {"range": [12, 24], "color": "rgba(255,215,0,0.2)"},
                            {"range": [24, 36], "color": "rgba(0,204,136,0.2)"},
                        ],
                    },
                    number={"suffix": "개월"},
                ))
                gauge.update_layout(height=250, template="plotly_dark", margin=dict(l=20, r=20, t=40, b=0))
                st.plotly_chart(gauge, use_container_width=True)

        with f_col2:
            st.subheader("핵심 재무 지표")
            st.metric("시가총액", fmt_usd(km.get("market_cap")))
            st.metric("총 현금 (info)", fmt_usd(km.get("total_cash")))
            st.metric("총 부채", fmt_usd(km.get("total_debt")))
            st.metric("잉여현금흐름 (TTM)", fmt_usd(km.get("free_cash_flow")))
            st.metric("임직원 수", f"{km.get('employees', 'N/A')}명" if km.get('employees') else "N/A")

        # 펀더멘털 플래그
        flags = fundamental.get("flags", [])
        if flags:
            st.subheader("펀더멘털 신호")
            for flag in flags:
                icon = {"bullish": "🟢", "bearish": "🔴", "warning": "🟡", "neutral": "⚪", "critical": "🚨"}.get(flag["type"], "⚪")
                st.write(f"{icon} [{flag['category']}] {flag['note']}")

        # 분기별 현금흐름
        cf = (financials.get("cash_flow") or {}).get("quarterly_operating_cf", {})
        if cf:
            st.subheader("분기별 영업현금흐름")
            cf_df = pd.DataFrame(list(cf.items()), columns=["분기", "금액"])
            cf_df["색상"] = cf_df["금액"].apply(lambda x: "#ff4b4b" if x < 0 else "#00cc88")
            cf_fig = go.Figure(go.Bar(
                x=cf_df["분기"], y=cf_df["금액"],
                marker_color=cf_df["색상"],
            ))
            cf_fig.update_layout(height=250, template="plotly_dark",
                                  margin=dict(l=0, r=0, t=10, b=0),
                                  yaxis_title="USD")
            st.plotly_chart(cf_fig, use_container_width=True)

    # ═══════════════════════════════════════════
    # TAB 3: 파이프라인
    # ═══════════════════════════════════════════
    with tabs[2]:
        st.subheader("임상 파이프라인 현황")

        p_summary = pipeline.get("summary", {})
        studies = pipeline.get("studies", [])

        p_col1, p_col2, p_col3 = st.columns(3)
        p_col1.metric("총 임상 건수", p_summary.get("total", 0))
        p_col2.metric("현재 모집 중", len(p_summary.get("recruiting", [])))
        p_col3.metric("완료된 임상", len(p_summary.get("completed", [])))

        # 단계별 파이차트
        if p_summary.get("by_phase"):
            ph_fig = px.pie(
                names=list(p_summary["by_phase"].keys()),
                values=list(p_summary["by_phase"].values()),
                title="임상 단계별 분포",
                template="plotly_dark",
                color_discrete_sequence=px.colors.sequential.Blues_r,
            )
            ph_fig.update_layout(height=300, margin=dict(l=0, r=0, t=40, b=0))
            st.plotly_chart(ph_fig, use_container_width=True)

        # 임상 상세 테이블
        st.subheader("임상 상세")
        STATUS_EMOJI = {
            "RECRUITING": "🟢 모집 중",
            "COMPLETED": "✅ 완료",
            "TERMINATED": "❌ 중단",
            "SUSPENDED": "⏸️ 중지",
            "ACTIVE, NOT RECRUITING": "🔵 진행 중",
            "NOT YET RECRUITING": "⏳ 미시작",
        }
        for s in studies:
            status_raw = (s.get("status") or "").upper()
            status_label = STATUS_EMOJI.get(status_raw, s.get("status", ""))
            phase = s.get("phase", "N/A")
            drug = s.get("drug") or "NuCana"

            with st.expander(f"{status_label} | {phase} | {s.get('title', '')[:80]}"):
                c1, c2 = st.columns(2)
                c1.write(f"**NCT ID**: [{s.get('nct_id')}]({s.get('url')})")
                c1.write(f"**약물**: {drug}")
                c1.write(f"**적응증**: {', '.join(s.get('conditions', []))}")
                c1.write(f"**등록 목표**: {s.get('enrollment', 'N/A')}명")
                c2.write(f"**시작**: {s.get('start_date', 'N/A')}")
                c2.write(f"**Primary 완료 예정**: {s.get('primary_completion', 'N/A')}")
                c2.write(f"**스폰서**: {s.get('sponsor', 'N/A')}")
                c2.write(f"**최근 업데이트**: {s.get('last_updated', 'N/A')}")
                if s.get("summary"):
                    st.caption(s["summary"][:400])

        # 카탈리스트 캘린더
        upcoming = catalyst.get("upcoming_catalysts", [])
        if upcoming:
            st.subheader("📅 카탈리스트 캘린더 (예정)")
            for c in upcoming[:5]:
                days = c.get("days_until_completion")
                label = f"D-{days}" if days else "진행 중"
                st.info(f"**{label}** | {c.get('drug')} | {c.get('phase')} | {c.get('primary_completion', 'TBD')} | [{c.get('nct_id')}]({c.get('url')})")

    # ═══════════════════════════════════════════
    # TAB 4: 공시
    # ═══════════════════════════════════════════
    with tabs[3]:
        st.subheader("SEC 공시 (NuCana plc)")

        ci = filings.get("company_info", {})
        fi_col1, fi_col2, fi_col3 = st.columns(3)
        fi_col1.metric("회사명", ci.get("name", "N/A"))
        fi_col2.metric("티커 (SEC)", ci.get("ticker", "N/A"))
        fi_col3.metric("회계연도 종료", ci.get("fiscal_year_end", "N/A"))

        key = filings.get("key_filings", {})

        st.subheader("연간보고서 (20-F)")
        for f in key.get("annual_reports", [])[:5]:
            st.write(f"📄 [{f['date']}] [{f['form']}]({f['url']}) — {f.get('description', '')}")

        st.subheader("수시공시 (6-K)")
        for f in key.get("current_reports", [])[:10]:
            st.write(f"📌 [{f['date']}] [{f['form']}]({f['url']}) — {f.get('description', '')}")

        atm = filings.get("atm_signals", [])
        if atm:
            st.subheader("⚠️ 희석 이벤트 감지 (ATM/Shelf)")
            for a in atm:
                st.warning(f"[{a['date']}] {a['form']} — [링크]({a['url']})")
        else:
            st.success("최근 ATM/Shelf Offering 감지 없음")

    # ═══════════════════════════════════════════
    # TAB 5: 뉴스
    # ═══════════════════════════════════════════
    with tabs[4]:
        st.subheader("최신 뉴스 & 센티멘트")

        sent = news.get("sentiment_summary", {})
        n_col1, n_col2, n_col3, n_col4 = st.columns(4)
        n_col1.metric("전체 기사", sent.get("total", 0))
        n_col2.metric("🟢 긍정", sent.get("positive", 0))
        n_col3.metric("🔴 부정", sent.get("negative", 0))
        n_col4.metric("센티멘트 점수", f"{sent.get('score', 0):.2f}")

        articles = news.get("articles", [])
        if articles:
            st.subheader("기사 목록")
            for a in articles[:30]:
                icon = sentiment_color(a.get("sentiment", "neutral"))
                title = a.get("title", "")
                url = a.get("url", "#")
                date = a.get("published", "")[:10] if a.get("published") else ""
                source = a.get("source", "")
                st.write(f"{icon} [{title}]({url}) — {source} {date}")

    # ═══════════════════════════════════════════
    # TAB 6: 리스크
    # ═══════════════════════════════════════════
    with tabs[5]:
        st.subheader("리스크 분석")

        r_summary = risk.get("risk_summary", {})
        r_col1, r_col2, r_col3, r_col4 = st.columns(4)
        r_col1.metric("리스크 점수", f"{risk.get('risk_score', 0)}/10")
        r_col2.metric("종합 수준", r_summary.get("overall_level", "N/A"))
        r_col3.metric("Critical", r_summary.get("critical", 0))
        r_col4.metric("High", r_summary.get("high", 0))

        # 리스크 목록
        risks = risk.get("risks", [])
        LEVEL_CONFIG = {
            "critical": ("🚨", "#ff4b4b"),
            "high":     ("🔴", "#ff8c00"),
            "medium":   ("🟡", "#ffd700"),
            "low":      ("🟢", "#00cc88"),
        }
        for r in risks:
            icon, color = LEVEL_CONFIG.get(r["level"], ("⚪", "#888"))
            with st.expander(f"{icon} [{r['level'].upper()}] {r['title']}"):
                st.write(r.get("detail", ""))
                st.caption(f"카테고리: {r.get('category')} | 점수 기여: +{r.get('score', 0)}")

        # 리스크 카테고리 바차트
        if risks:
            categories = {}
            for r in risks:
                cat = r.get("category", "기타")
                categories[cat] = categories.get(cat, 0) + r.get("score", 0)
            risk_fig = go.Figure(go.Bar(
                x=list(categories.keys()),
                y=list(categories.values()),
                marker_color="#ff8c00",
            ))
            risk_fig.update_layout(
                title="카테고리별 리스크 기여도",
                height=250, template="plotly_dark",
                margin=dict(l=0, r=0, t=40, b=0),
            )
            st.plotly_chart(risk_fig, use_container_width=True)

    # ═══════════════════════════════════════════
    # TAB 7: AI 요약
    # ═══════════════════════════════════════════
    with tabs[6]:
        st.subheader("🤖 Gemini AI 투자 분석 요약")

        if summary.get("error"):
            st.warning(f"AI 요약 생성 실패: {summary['error']}")
            st.info("Gemini API 키를 확인하세요. 나머지 탭의 데이터는 정상입니다.")
        elif summary.get("one_liner"):
            st.info(f"**한줄 요약**: {summary['one_liner']}")

            s_col1, s_col2 = st.columns(2)
            with s_col1:
                st.subheader("✅ 강점")
                for i, s in enumerate(summary.get("strengths", []), 1):
                    st.write(f"{i}. {s}")

            with s_col2:
                st.subheader("⚠️ 리스크")
                for i, r in enumerate(summary.get("risks", []), 1):
                    st.write(f"{i}. {r}")

            st.subheader("🎯 핵심 카탈리스트")
            for c in summary.get("key_catalysts", []):
                st.write(f"• {c}")

            st.subheader("📊 투자 관점 종합")
            st.write(summary.get("investment_view", ""))

            st.caption(f"모델: {summary.get('model', 'N/A')} | 생성: {updated_str(summary)}")
            st.caption(f"⚠️ {summary.get('disclaimer', '본 분석은 투자 권유가 아닙니다.')}")
        else:
            st.info("AI 요약 데이터가 없습니다. `python run_collectors.py`를 실행하세요.")


if __name__ == "__main__":
    main()
