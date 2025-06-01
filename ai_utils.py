import streamlit as st
import google.generativeai as genai
from typing import List, Dict
from datetime import datetime
import json

class AIManager:
    """AI 관련 기능을 관리하는 클래스"""
    
    @staticmethod
    def generate_ai_report(articles: List[Dict], date: datetime) -> str:
        """
        AI를 사용하여 기사 요약 보고서 생성
        
        Args:
            articles: 기사 데이터 리스트
            date: 날짜
            
        Returns:
            str: AI가 생성한 보고서 텍스트
        """
        try:
            # Google API 키 확인
            if 'google_api' not in st.secrets or 'api_key' not in st.secrets['google_api']:
                raise ValueError("Google API 키가 설정되지 않았습니다.")
            
            # Gemini API 설정
            genai.configure(api_key=st.secrets['google_api']['api_key'])
            model = genai.GenerativeModel('gemini-1.5-flash')
            
            # 기사 데이터 준비
            articles_text = []
            for article in articles:
                articles_text.append(f"제목: {article['title']}\n신문사: {article['newspaper']}\n링크: {article['url']}\n")
            
            # 프롬프트 생성
            prompt = AIManager._create_report_prompt(articles_text)
            
            # AI 요약 생성
            response = model.generate_content(prompt)
            return response.text
            
        except Exception as e:
            return f"보고서 생성 중 오류가 발생했습니다: {str(e)}"
    
    @staticmethod
    def _create_report_prompt(articles_text: List[str]) -> str:
        """
        보고서 생성을 위한 프롬프트 생성
        
        Args:
            articles_text: 기사 텍스트 리스트
            
        Returns:
            str: 프롬프트 텍스트
        """
        return f"""
        ### 작업 목표
        조간신문에 게재된 기사들을 종합 분석하여 독자들이 쉽게 이해할 수 있는 블로그 글을 작성합니다.

        ### 📋 입력 데이터
        - 조간 신문에 게재된 기사 목록
        - 각 기사의 제목, 신문사, 링크 정보 포함

        ### 🏗️ 출력 구조

        #### 1. 전체 글 제목 작성
        - 형식: "📰 [날짜] 조간신문 종합 - [주요 이슈 2-3개 키워드]"
        - 예시: "📰 2025년 5월 28일 조간신문 종합 - 대선 막판 네거티브 공세와 경제 회복 신호"

        #### 2. 전체 요약문 작성 (150-200자)
        - 당일 가장 중요한 이슈 3-4개를 포함
        - 정치, 경제, 사회, 국제 분야의 균형 있는 요약
        - 독자의 관심을 끌 수 있는 핵심 내용 중심

        #### 3. 섹션별 기사 분류 및 작성

        **오늘의 Top 이슈 (5개 헤드라인)**
        - 선정 기준: 
          * 여러 언론사에서 공통으로 다룬 기사
          * 사회적 파급력이 큰 사건
          * 국민 생활에 직접적 영향을 미치는 이슈
        - 각 기사의 제목만 작성

        **🏛️ 정치/사회 (5개 기사)**
        - 대선, 정치인 동향, 정책 발표, 사회 이슈 포함
        - 내란 수사, 선거 관련, 사회 제도 변화 등

        **💰 경제/산업 (5개 기사)**
        - 기업 실적, 경제 지표, 산업 동향, 금융 정책
        - 수출입, 주식시장, 부동산, 소비 트렌드 등

        **🤖 기술/AI (5개 기사)**
        - IT, 인공지능, 사이버보안, 통신, 혁신 기술
        - 기업의 기술 개발, 디지털 전환 관련
        
        **🌍 국제/글로벌 (5개 기사)**
        - 해외 정치, 국제 경제, 외교 관계
        - 미국, 중국, 일본 등 주요국 동향

        **🎤 연예/문화 (5개 기사)**
        - 연예계 소식, 문화 행사, 한류, 예술 관련
        - K-컬처, 엔터테인먼트 산업 동향

        **🏌️ 스포츠 (5개 기사)**
        - 프로스포츠, 국제대회, 선수 동향
        - 야구, 축구, 골프 등 주요 스포츠 이슈
        
        ### 각 기사 작성 형식
        ### [순번]. [기사 제목]
        **요약**: [핵심 내용을 50자 이내로 요약]
        **링크**: [원문 링크]
        ### 가독성 있게 줄바꿈을 이용할 것.     
        ### 여러 기사링크르 통합할 경우 첫번째 기사 링크를 넣어줄 것.  

        ### 🏷️ 해시태그 작성 (30개)
        - 주요 인물명, 기관명, 이슈 키워드 포함
        - 트렌딩 가능한 키워드 우선 선택
        - 정치, 경제, 사회, 문화 분야 균형 있게 배치
        - 한글 해시태그로 작성 (#대선2025, #경제회복 등)

        ### 🎨 작성 스타일 가이드
        - **객관적 톤**: 특정 정치적 성향 배제
        - **독자 친화적**: 전문 용어 최소화, 쉬운 설명
        - **간결성**: 핵심만 추려서 전달
        - **균형성**: 다양한 분야의 이슈를 고르게 다룸
        - **시의성**: 당일 가장 중요한 이슈 우선 배치

        ### 🔍 기사 선별 기준
        1. **중요도**: 사회적 파급력과 관심도
        2. **신뢰성**: 주요 언론사 보도 여부
        3. **다양성**: 분야별 균형 있는 선택
        4. **독창성**: 새로운 정보나 관점 제공
        5. **연관성**: 독자의 일상생활과의 관련성

        ### ⚠️ 주의사항
        - 사실 확인이 어려운 추측성 내용 배제
        - 균형 잡힌 시각으로 이슈 전달
        - 링크는 반드시 정확한 URL 사용

        기사 목록:
        {json.dumps(articles_text, ensure_ascii=False, indent=2)}
        """
