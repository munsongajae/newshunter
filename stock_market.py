import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import FinanceDataReader as fdr

def get_stock_market_info():
    """주식시장 정보 수집"""
    try:
        # 캐시된 데이터 확인
        today = datetime.now().strftime('%Y-%m-%d')
        cache_key = f"stock_market_data_{today}"
        if cache_key in st.session_state:
            cached_data = st.session_state[cache_key]
            # 캐시된 데이터가 1시간 이내인 경우 재사용
            if datetime.now() - cached_data['timestamp'] < timedelta(hours=1):
                return cached_data

        # 국내 지수 정보
        domestic_indices = {
            "KOSPI": "KS11",
            "KOSDAQ": "KQ11",
            "KOSPI200": "KS200"
        }
        
        def get_index_data(indices_dict):
            data = {}
            for name, ticker in indices_dict.items():
                try:
                    df = fdr.DataReader(ticker, today, today)
                    if not df.empty:
                        data[name] = {
                            "현재가": df['Close'].iloc[-1],
                            "전일대비": df['Change'].iloc[-1],
                            "등락률": df['Change'].iloc[-1] / df['Close'].iloc[-1] * 100
                        }
                except Exception as e:
                    st.warning(f"{name} 지수 데이터를 가져오는 중 오류가 발생했습니다: {str(e)}")
            return data
        
        market_data = {
            "indices": get_index_data(domestic_indices),
            "timestamp": datetime.now()
        }
        
        # 데이터 캐싱
        st.session_state[cache_key] = market_data
        return market_data
        
    except Exception as e:
        st.error(f"주식시장 정보를 가져오는 중 오류가 발생했습니다: {str(e)}")
        return None

def display_market_section(title, data):
    """시장 섹션 표시"""
    if not data:
        st.warning(f"{title} 데이터를 가져오지 못했습니다.")
        return
    
    st.markdown(f"#### {title}")
    num_cols = len(data)
    if num_cols > 0:
        cols = st.columns(num_cols)
        for idx, (name, values) in enumerate(data.items()):
            with cols[idx]:
                st.metric(
                    name,
                    f"{values['현재가']:,.2f}",
                    f"{values['등락률']:+.2f}%",
                    delta_color="normal" if values['등락률'] > 0 else "inverse"
                )

def display_stock_market_tab():
    """주식시장 정보 표시"""
    st.markdown("### 📈 국내 증시")
    
    # 주식시장 정보 가져오기
    market_info = get_stock_market_info()
    
    if market_info:
        # 지수 정보 표시
        display_market_section("주요 지수", market_info['indices'])
        
        # 시장 요약
        st.markdown("#### 📊 시장 요약")
        
        def get_market_summary(market_data):
            if not market_data:
                return [], []
            rising = [name for name, data in market_data.items() if data['등락률'] > 0]
            falling = [name for name, data in market_data.items() if data['등락률'] < 0]
            return rising, falling
        
        rising, falling = get_market_summary(market_info['indices'])
        
        summary = f"""
        **주요 지수 동향**
        - 상승: {', '.join(rising) if rising else '없음'}
        - 하락: {', '.join(falling) if falling else '없음'}
        """
        st.markdown(summary)
        
        # 데이터 갱신 시간 표시
        if 'timestamp' in market_info:
            last_update = market_info['timestamp']
            st.caption(f"마지막 업데이트: {last_update.strftime('%Y-%m-%d %H:%M:%S')}") 