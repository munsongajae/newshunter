import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
from pykrx import stock
import time
from datetime import datetime
from typing import Dict, Optional

class DataCollector:
    """데이터 수집 관련 기능을 관리하는 클래스"""
    
    @staticmethod
    def collect_market_data(market: str, date: str) -> pd.DataFrame:
        """
        시장 데이터 수집
        
        Args:
            market: 시장 구분 (KOSPI, KOSDAQ)
            date: 날짜 (YYYYMMDD)
            
        Returns:
            pd.DataFrame: 수집된 시장 데이터
        """
        try:
            # 1. 가격 변동 데이터 수집
            df = stock.get_market_price_change(date, date, market=market)
            time.sleep(0.3)  # API 호출 간 딜레이
            
            # 2. OHLCV 데이터 수집
            df_ohlcv = stock.get_market_ohlcv(date, market=market)
            time.sleep(0.3)
            
            # 3. 기본 지표 데이터 수집
            df_fundamental = stock.get_market_fundamental(date, market=market)
            time.sleep(0.3)
            
            # 4. 업종 정보 수집
            df_industry = DataCollector.get_industry_info()
            
            # 5. OHLCV 데이터 병합
            if not df_ohlcv.empty:
                df = df.merge(df_ohlcv[['고가', '저가', '시가총액']], 
                            left_index=True, 
                            right_index=True, 
                            how='left')
            
            # 6. 기본 지표 데이터 병합
            if not df_fundamental.empty:
                df = df.merge(df_fundamental, 
                            left_index=True, 
                            right_index=True, 
                            how='left')
            
            # 7. 업종 정보 병합
            if not df_industry.empty:
                df = df.merge(df_industry, 
                            left_index=True, 
                            right_on='종목코드', 
                            how='left')
                df = df.drop('종목코드', axis=1)
            else:
                df['업종'] = ''
                df['주요제품'] = ''
            
            # 8. 시장구분 추가
            df['시장구분'] = market
            
            return df
            
        except Exception as e:
            st.error(f"{market} 데이터 수집 중 오류: {str(e)}")
            return pd.DataFrame()

    @staticmethod
    def get_industry_info() -> pd.DataFrame:
        """
        업종 및 주요제품 정보 수집
        
        Returns:
            pd.DataFrame: 업종 정보 데이터
        """
        try:
            # KRX KIND 시스템 상장법인목록 URL
            url = "https://kind.krx.co.kr/corpgeneral/corpList.do"
            params = {
                "method": "download",
                "searchType": "13"
            }
            
            # 파일 다운로드
            response = requests.get(url, params=params)
            response.raise_for_status()
            
            # HTML 파싱
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # 테이블 찾기
            table = soup.find('table')
            if not table:
                raise ValueError("상장법인목록 테이블을 찾을 수 없습니다.")
            
            # 데이터 추출
            data = []
            rows = table.find_all('tr')[1:]  # 헤더 제외
            
            for row in rows:
                cols = row.find_all('td')
                if len(cols) >= 3:  # 최소 3개 컬럼 확인
                    stock_code = cols[1].text.strip()  # 종목코드
                    industry = cols[2].text.strip()    # 업종
                    main_product = cols[3].text.strip() if len(cols) > 3 else ''  # 주요제품
                    
                    data.append({
                        '종목코드': stock_code,
                        '업종': industry,
                        '주요제품': main_product
                    })
            
            # DataFrame 생성
            df = pd.DataFrame(data)
            
            # 종목코드 포맷팅
            df['종목코드'] = df['종목코드'].astype(str).str.zfill(6)
            
            return df
            
        except Exception as e:
            st.error(f"업종 정보 수집 중 오류 발생: {str(e)}")
            return pd.DataFrame()

    @staticmethod
    def filter_market_data(df: pd.DataFrame, 
                          market_filter: list, 
                          price_range: tuple, 
                          volume_filter: int) -> pd.DataFrame:
        """
        시장 데이터 필터링
        
        Args:
            df: 원본 데이터
            market_filter: 시장 필터 리스트
            price_range: 가격 범위 (min, max)
            volume_filter: 최소 거래량
            
        Returns:
            pd.DataFrame: 필터링된 데이터
        """
        return df[
            (df['시장구분'].isin(market_filter)) &
            (df['종가'].between(price_range[0], price_range[1])) &
            (df['거래량'] >= volume_filter)
        ]
