import streamlit as st
import FinanceDataReader as fdr
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta, timezone
from pykrx import stock

def get_ticker_from_name(name):
    """종목명으로 티커 찾기"""
    try:
        # 한국 주식 목록 가져오기
        krx = fdr.StockListing('KRX')
        # 종목명으로 검색
        result = krx[krx['Name'].str.contains(name, case=False, na=False)]
        if not result.empty:
            return result.iloc[0]['Code']
        
        # 미국 주식 목록 가져오기
        nasdaq = fdr.StockListing('NASDAQ')
        nyse = fdr.StockListing('NYSE')
        amex = fdr.StockListing('AMEX')
        
        # 각 거래소에서 검색
        for market in [nasdaq, nyse, amex]:
            if market is not None:
                result = market[market['Name'].str.contains(name, case=False, na=False)]
                if not result.empty:
                    return result.iloc[0]['Symbol']
        
        return None
    except Exception as e:
        st.warning(f"종목 검색 중 오류가 발생했습니다: {e}")
        return None

def display_trading_value(start_date, end_date):
    """거래실적 데이터 표시"""
    try:
        # 날짜 형식 변환
        start_date_str = start_date.strftime("%Y%m%d")
        end_date_str = end_date.strftime("%Y%m%d")
        
        # 코스피 거래실적
        kospi_trading = stock.get_market_trading_value_by_date(start_date_str, end_date_str, "KOSPI")
        # 코스닥 거래실적
        kosdaq_trading = stock.get_market_trading_value_by_date(start_date_str, end_date_str, "KOSDAQ")
        
        # 거래실적 표시
        st.markdown("#### 💰 거래실적")
        
        if not kospi_trading.empty and not kosdaq_trading.empty:
            # KOSPI와 KOSDAQ 거래실적 (종료일 데이터만)
            kospi_data = kospi_trading.iloc[-1]
            kosdaq_data = kosdaq_trading.iloc[-1]
            
            # KOSPI 거래실적
            st.markdown("##### KOSPI")
            col1, col2, col3, col4, col5 = st.columns(5)
            with col1:
                st.metric("기관", f"{kospi_data['기관합계']/100000000:,.0f}억원")
            with col2:
                st.metric("기타법인", f"{kospi_data['기타법인']/100000000:,.0f}억원")
            with col3:
                st.metric("개인", f"{kospi_data['개인']/100000000:,.0f}억원")
            with col4:
                st.metric("외국인", f"{kospi_data['외국인합계']/100000000:,.0f}억원")
            with col5:
                st.metric("전체", f"{kospi_data['전체']/100000000:,.0f}억원")
            
            # KOSDAQ 거래실적
            st.markdown("##### KOSDAQ")
            col1, col2, col3, col4, col5 = st.columns(5)
            with col1:
                st.metric("기관", f"{kosdaq_data['기관합계']/100000000:,.0f}억원")
            with col2:
                st.metric("기타법인", f"{kosdaq_data['기타법인']/100000000:,.0f}억원")
            with col3:
                st.metric("개인", f"{kosdaq_data['개인']/100000000:,.0f}억원")
            with col4:
                st.metric("외국인", f"{kosdaq_data['외국인합계']/100000000:,.0f}억원")
            with col5:
                st.metric("전체", f"{kosdaq_data['전체']/100000000:,.0f}억원")
        else:
            st.info("거래실적 데이터가 없습니다.")
        
        st.markdown("---")
        
    except Exception as e:
        st.error(f"거래실적 데이터 수집 중 오류 발생: {str(e)}")

def display_stock_market_tab():
    """주식시장 정보 표시"""
    st.title("📈 주요 지수 동향")

    # 한국 시간 설정
    KST = timezone(timedelta(hours=9))
    today = datetime.now(KST).date()
    
    # 주말인 경우 금요일을 기본값으로
    if today.weekday() >= 5:  # 5: 토요일, 6: 일요일
        days_to_subtract = today.weekday() - 4
        today = today - timedelta(days=days_to_subtract)
        
    # 날짜 선택
    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input(
            "시작일",
            value=today - timedelta(days=90),  # 90일 전으로 기본값 설정
            max_value=today,
            help="조회 시작일을 선택하세요"
        )
    with col2:
        end_date = st.date_input(
            "종료일",
            value=today,  # 오늘을 기본값으로 설정
            max_value=today,
            help="조회 종료일을 선택하세요"
        )

    # 날짜가 변경되었는지 확인
    date_changed = (start_date != st.session_state.get('market_start_date') or 
                   end_date != st.session_state.get('market_end_date'))

    if date_changed or st.session_state['market_data'] is None:
        # 날짜가 변경되었거나 데이터가 없는 경우에만 데이터 수집
        with st.spinner('데이터를 수집하는 중입니다...'):
            try:
                # 1. 주요 지수 시세
                index_codes = {
                    'KOSPI': 'KS11',
                    'KOSDAQ': 'KQ11',
                    'S&P 500': 'US500',
                    'NASDAQ': 'IXIC',
                    '다우존스': 'DJI',
                    '니케이225': 'N225',
                    '항셍지수': 'HSI'
                }

                market_data = {}
                for name, code in index_codes.items():
                    try:
                        df = fdr.DataReader(code, start_date, end_date)
                        market_data[name] = df
                    except Exception as e:
                        st.error(f"{name} 지수 오류: {e}")

                # 2. 거래실적 데이터
                trading_data = {}
                try:
                    trading_data['KOSPI'] = stock.get_market_trading_value_by_date(
                        start_date.strftime("%Y%m%d"), 
                        end_date.strftime("%Y%m%d"), 
                        "KOSPI"
                    )
                    trading_data['KOSDAQ'] = stock.get_market_trading_value_by_date(
                        start_date.strftime("%Y%m%d"), 
                        end_date.strftime("%Y%m%d"), 
                        "KOSDAQ"
                    )
                except Exception as e:
                    st.error(f"거래실적 데이터 수집 중 오류: {e}")

                # 3. 환율 & 원자재 시세
                fx_data = {}
                cm_data = {}
                try:
                    fx_codes = {'미국 달러 (USD/KRW)': 'USD/KRW', '일본 엔화 (JPY/KRW)': 'JPY/KRW'}
                    for label, code in fx_codes.items():
                        fx = fdr.DataReader(code, start_date, end_date)
                        if not fx.empty:
                            fx_data[label] = fx

                    cm_codes = {'서부텍사스산 원유 (WTI)': 'WTI', '금 (GOLD)': 'GOLD'}
                    for label, code in cm_codes.items():
                        cm = fdr.DataReader(code, start_date, end_date)
                        if not cm.empty:
                            cm_data[label] = cm
                except Exception as e:
                    st.error(f"환율/원자재 데이터 수집 중 오류: {e}")

                # 세션 상태에 저장
                st.session_state['market_data'] = {
                    'index_data': market_data,
                    'trading_data': trading_data,
                    'fx_data': fx_data,
                    'cm_data': cm_data
                }
                st.session_state['market_start_date'] = start_date
                st.session_state['market_end_date'] = end_date

            except Exception as e:
                st.error(f"데이터 수집 중 오류가 발생했습니다: {e}")
                return

    # 저장된 데이터 표시
    market_data = st.session_state['market_data']
    if market_data:
        # 1. 주요 지수 시세 표시
        st.markdown("#### 📊 주요 지수")
        cols = st.columns(len(market_data['index_data']))
        for i, (name, df) in enumerate(market_data['index_data'].items()):
            if not df.empty:
                delta = df['Close'].pct_change().iloc[-1] * 100
                cols[i].metric(label=name, value=f"{df['Close'].iloc[-1]:,.2f}", delta=f"{delta:.2f}%")

        st.markdown("---")

        # 2. 거래실적 데이터 표시
        display_trading_value(start_date, end_date)

        # 3. 환율 & 원자재 시세 표시
        st.markdown("#### 💱 환율 및 원자재 가격")
        col1, col2 = st.columns(2)

        with col1:
            st.markdown("##### 환율")
            for label, df in market_data['fx_data'].items():
                if not df.empty:
                    st.line_chart(df['Close'].rename(label), height=150)

        with col2:
            st.markdown("##### 원자재")
            for label, df in market_data['cm_data'].items():
                if not df.empty:
                    st.line_chart(df['Close'].rename(label), height=150)

        st.markdown("---")

        # 4. 개별 종목 조회
        st.markdown("#### 🔍 개별 종목/ETF 조회")
        code_input = st.text_input("종목코드, 티커 또는 종목명 입력 (예: 005930, AAPL, 삼성전자 등)", value="005930")
        if code_input:
            try:
                # 입력값이 티커/코드가 아닌 경우 종목명으로 검색
                if not any(c.isdigit() for c in code_input) and not code_input.isupper():
                    ticker = get_ticker_from_name(code_input)
                    if ticker:
                        st.info(f"'{code_input}'의 티커/코드: {ticker}")
                        code_input = ticker
                    else:
                        st.warning(f"'{code_input}'에 해당하는 종목을 찾을 수 없습니다.")
                        return

                df_stock = fdr.DataReader(code_input, start_date, end_date)
                if df_stock.empty:
                    st.warning(f"{code_input}에 대한 데이터가 없습니다.")
                else:
                    fig = go.Figure()
                    fig.add_trace(go.Scatter(x=df_stock.index, y=df_stock['Close'], mode='lines', name='종가'))
                    fig.update_layout(title=f"{code_input} 주가 추이", xaxis_title="날짜", yaxis_title="가격")
                    st.plotly_chart(fig, use_container_width=True)

                    with st.expander("📊 기술적 지표 보기"):
                        df_stock['SMA20'] = df_stock['Close'].rolling(window=20).mean()
                        df_stock['SMA60'] = df_stock['Close'].rolling(window=60).mean()
                        df_stock['EMA20'] = df_stock['Close'].ewm(span=20).mean()
                        df_stock['EMA60'] = df_stock['Close'].ewm(span=60).mean()

                        delta = df_stock['Close'].diff()
                        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
                        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
                        rs = gain / loss
                        df_stock['RSI'] = 100 - (100 / (1 + rs))

                        ema12 = df_stock['Close'].ewm(span=12).mean()
                        ema26 = df_stock['Close'].ewm(span=26).mean()
                        df_stock['MACD'] = ema12 - ema26
                        df_stock['Signal'] = df_stock['MACD'].ewm(span=9).mean()

                        fig2 = go.Figure()
                        fig2.add_trace(go.Scatter(x=df_stock.index, y=df_stock['Close'], name='종가'))
                        fig2.add_trace(go.Scatter(x=df_stock.index, y=df_stock['SMA20'], name='SMA20'))
                        fig2.add_trace(go.Scatter(x=df_stock.index, y=df_stock['SMA60'], name='SMA60'))
                        fig2.add_trace(go.Scatter(x=df_stock.index, y=df_stock['EMA20'], name='EMA20'))
                        fig2.add_trace(go.Scatter(x=df_stock.index, y=df_stock['EMA60'], name='EMA60'))
                        fig2.update_layout(title=f"{code_input} 이동평균선 비교", xaxis_title="날짜", yaxis_title="가격")
                        st.plotly_chart(fig2, use_container_width=True)

                        fig3 = go.Figure()
                        fig3.add_trace(go.Scatter(x=df_stock.index, y=df_stock['MACD'], name='MACD'))
                        fig3.add_trace(go.Scatter(x=df_stock.index, y=df_stock['Signal'], name='Signal'))
                        fig3.update_layout(title=f"{code_input} MACD", xaxis_title="날짜", yaxis_title="값")
                        st.plotly_chart(fig3, use_container_width=True)

                        fig4 = go.Figure()
                        fig4.add_trace(go.Scatter(x=df_stock.index, y=df_stock['RSI'], name='RSI'))
                        fig4.add_hline(y=70, line=dict(dash='dash', color='red'))
                        fig4.add_hline(y=30, line=dict(dash='dash', color='green'))
                        fig4.update_layout(title=f"{code_input} RSI", xaxis_title="날짜", yaxis_title="RSI 값")
                        st.plotly_chart(fig4, use_container_width=True)

            except Exception as e:
                st.error(f"{code_input} 데이터 조회 중 오류가 발생했습니다: {e}") 