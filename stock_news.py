# stock_news.py
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from download_utils import DownloadManager

# DownloadManager 인스턴스 생성
download_manager = DownloadManager()

def display_stock_news_results(results, selected_keywords, keyword_article_counts, matched_stocks, selected_date):
    """특징주 포착 결과 표시"""
    # 5. 검색 결과 통계 표시
    st.markdown("### 📊 검색 결과 통계")
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("#### 키워드별 기사 수")
        for keyword, count in keyword_article_counts.items():
            st.write(f"- {keyword}: {count}개")
    
    with col2:
        st.markdown("#### 매칭된 종목 수")
        st.write(f"- 총 {len(matched_stocks)}개 종목이 매칭되었습니다.")
        # 종목별 기사 수 분포
        article_counts = [len(articles) for articles in results]
        if article_counts:
            st.write(f"- 평균 {sum(article_counts)/len(article_counts):.1f}개의 기사가 매칭되었습니다.")
            st.write(f"- 최대 {max(article_counts)}개의 기사가 매칭된 종목이 있습니다.")
    
    # 6. 결과 표시
    if results:
        st.markdown("### 📈 매칭된 종목 정보")
        df_results = pd.DataFrame(results)
        
        # 데이터 포맷팅
        df_results['현재가'] = df_results['현재가'].apply(lambda x: f"{x:,}원")
        df_results['등락률'] = df_results['등락률'].apply(lambda x: f"{x:.2f}%")
        df_results['거래량'] = df_results['거래량'].apply(lambda x: f"{x:,}")
        df_results['시가총액'] = df_results['시가총액'].apply(lambda x: f"{x/100000000:.0f}억원")
        
        # 결과 테이블 표시
        st.dataframe(
            df_results,
            use_container_width=True,
            hide_index=True
        )
        
        # CSV 다운로드
        csv_data = download_manager.create_stock_data_download(df_results, selected_date)
        st.download_button(
            label="📥 CSV 다운로드",
            data=csv_data,
            file_name=f"stock_news_{selected_date.strftime('%Y%m%d')}.csv",
            mime="text/csv"
        )
    else:
        st.warning("검색 결과가 없습니다.")