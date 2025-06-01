import streamlit as st
import pandas as pd
import io
from datetime import datetime
from typing import List, Dict, Optional, Union

class DownloadManager:
    """다운로드 관련 기능을 관리하는 클래스"""
    
    @staticmethod
    def create_excel_download(articles: Optional[List[Dict]]) -> bytes:
        """
        엑셀 파일 생성
        
        Args:
            articles: 기사 데이터 리스트
            
        Returns:
            bytes: 엑셀 파일 데이터
        """
        if articles is None:
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                pd.DataFrame().to_excel(writer, index=False)
            return output.getvalue()
            
        df = pd.DataFrame(articles)
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='신문기사')
        return output.getvalue()

    @staticmethod
    def create_text_download(articles: Optional[List[Dict]], date: datetime) -> str:
        """
        텍스트 파일 생성
        
        Args:
            articles: 기사 데이터 리스트
            date: 날짜
            
        Returns:
            str: 텍스트 파일 내용
        """
        if articles is None:
            return "수집된 기사가 없습니다."
            
        text_content = f"📰 {date.strftime('%Y년 %m월 %d일')}의 신문 게재 기사 모음\n\n"
        
        # 신문사별로 기사 그룹화
        newspaper_groups = {}
        for article in articles:
            newspaper = article['newspaper']
            if newspaper not in newspaper_groups:
                newspaper_groups[newspaper] = []
            newspaper_groups[newspaper].append(article)
        
        # 신문사별로 기사 내용 작성
        for newspaper, articles_list in newspaper_groups.items():
            text_content += f"📌 [{newspaper}]\n"
            for article in articles_list:
                page_info = f"[{article['page']}] " if article['page'] else ""
                text_content += f"🔹 {page_info}{article['title']}\n   {article['url']}\n"
            text_content += "\n"
        
        return text_content

    @staticmethod
    def create_search_excel_download(articles: List[Dict]) -> bytes:
        """
        검색 결과 엑셀 파일 생성
        
        Args:
            articles: 검색 결과 기사 데이터 리스트
            
        Returns:
            bytes: 엑셀 파일 데이터
        """
        df = pd.DataFrame(articles)
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='검색결과')
        return output.getvalue()

    @staticmethod
    def create_search_csv_download(articles: List[Dict]) -> bytes:
        """
        검색 결과 CSV 파일 생성
        
        Args:
            articles: 검색 결과 기사 데이터 리스트
            
        Returns:
            bytes: CSV 파일 데이터
        """
        df = pd.DataFrame(articles)
        return df.to_csv(index=False).encode('utf-8-sig')

    @staticmethod
    def create_search_text_download(articles: List[Dict], keyword: str) -> str:
        """
        검색 결과 텍스트 파일 생성
        
        Args:
            articles: 검색 결과 기사 데이터 리스트
            keyword: 검색 키워드
            
        Returns:
            str: 텍스트 파일 내용
        """
        text_content = f"🔍 '{keyword}' 검색 결과\n"
        text_content += f"검색일시: {datetime.now().strftime('%Y년 %m월 %d일 %H시 %M분')}\n"
        text_content += f"총 {len(articles)}개 기사\n\n"
        
        for i, article in enumerate(articles, 1):
            text_content += f"{i}. {article['title']}\n"
            text_content += f"   요약: {article['description']}\n"
            text_content += f"   발행일: {article['pubDate']}\n"
            text_content += f"   출처: {article.get('source', '알 수 없음')}\n"
            text_content += f"   링크: {article['link']}\n\n"
        
        return text_content

    @staticmethod
    def create_stock_data_download(df: pd.DataFrame, date: datetime) -> bytes:
        """
        주식 데이터 CSV 파일 생성
        
        Args:
            df: 주식 데이터 DataFrame
            date: 날짜
            
        Returns:
            bytes: CSV 파일 데이터
        """
        return df.to_csv(index=False).encode('utf-8-sig')

    @staticmethod
    def create_ai_report_download(report_text: str, date: datetime) -> str:
        """
        AI 보고서 텍스트 파일 생성
        
        Args:
            report_text: AI 보고서 텍스트
            date: 날짜
            
        Returns:
            str: 텍스트 파일 내용
        """
        return f"📊 {date.strftime('%Y년 %m월 %d일')} 신문 기사 AI 요약 보고서\n\n{report_text}"
