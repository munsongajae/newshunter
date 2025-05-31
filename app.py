import streamlit as st
import pandas as pd
from datetime import datetime, timezone, timedelta
import io
import base64
from news_collector import NewsCollector
from naver_search import NaverNewsSearcher
import google.generativeai as genai
from typing import List, Dict
import json
import requests
from bs4 import BeautifulSoup
from stock_market import display_stock_market_tab, get_ticker_from_name, display_trading_value
from pykrx import stock
import time
import plotly.graph_objects as go
import numpy as np
import os
import FinanceDataReader as fdr
from streamlit_option_menu import option_menu
import re

# 페이지 설정
st.set_page_config(
    page_title="신문 기사 수집기",
    page_icon="📰",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 세션 상태 초기화
if 'newspaper_articles' not in st.session_state:
    st.session_state['newspaper_articles'] = None
if 'paper_date' not in st.session_state:
    st.session_state['paper_date'] = None
if 'search_articles' not in st.session_state:
    st.session_state['search_articles'] = None
if 'current_search_keyword' not in st.session_state:
    st.session_state['current_search_keyword'] = None
if 'filtered_articles' not in st.session_state:
    st.session_state['filtered_articles'] = None
if 'ai_report' not in st.session_state:
    st.session_state['ai_report'] = None
if 'stock_data' not in st.session_state:
    st.session_state['stock_data'] = None
if 'stock_date' not in st.session_state:
    st.session_state['stock_date'] = None
if 'stock_filtered_data' not in st.session_state:
    st.session_state['stock_filtered_data'] = None

# CSS 스타일링
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1f77b4;
        text-align: center;
        margin-bottom: 2rem;
    }
    .category-header {
        font-size: 1.2rem;
        font-weight: bold;
        color: #333;
        margin: 1rem 0 0.5rem 0;
        background-color: #f0f2f6;
        padding: 0.5rem;
        border-radius: 5px;
    }
    .article-item {
        background-color: #f8f9fa;
        padding: 1rem;
        margin: 0.5rem 0;
        border-radius: 5px;
        border-left: 4px solid #1f77b4;
    }
    .search-box {
        background-color: #e9ecef;
        padding: 1rem;
        border-radius: 5px;
        margin: 1rem 0;
    }
    .newspaper-section {
        border: 1px solid #ddd;
        border-radius: 5px;
        padding: 1rem;
        margin: 0.5rem 0;
    }
    .stButton > button {
        width: 100%;
    }
    .ai-report {
        background-color: #f8f9fa;
        padding: 2rem;
        margin: 1rem 0;
        border-radius: 10px;
        border: 1px solid #e9ecef;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }
    .ai-report h3 {
        color: #1f77b4;
        margin-bottom: 1.5rem;
    }
    .ai-report p {
        line-height: 1.6;
        margin-bottom: 1rem;
    }
    .ai-report ul {
        margin-left: 1.5rem;
        margin-bottom: 1rem;
    }
    .ai-report li {
        margin-bottom: 0.5rem;
    }
    /* 사이드바 메뉴 스타일링 */
    .css-1d391kg {
        padding: 0.5rem 0;
    }
    .css-1d391kg .stRadio > div {
        padding: 0.5rem 1rem;
    }
    .css-1d391kg .stRadio > div:hover {
        background-color: #f0f2f6;
        border-radius: 5px;
    }
</style>
""", unsafe_allow_html=True)

def check_secrets():
    """secrets 설정 확인 - 화면에 노출하지 않음"""
    missing_secrets = []
    api_available = False
    
    try:
        client_id = st.secrets["naver_api"]["client_id"]
        client_secret = st.secrets["naver_api"]["client_secret"]
        if client_id and client_secret:
            api_available = True
    except KeyError:
        missing_secrets.append("네이버 API 키")
    
    return api_available, missing_secrets

def remove_duplicates(articles):
    """중복 기사 제거"""
    seen_urls = set()
    unique_articles = []
    
    for article in articles:
        if article['url'] not in seen_urls:
            seen_urls.add(article['url'])
            unique_articles.append(article)
    
    return unique_articles

def create_excel_download(articles):
    """엑셀 파일 생성"""
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

def create_text_download(articles, date):
    """텍스트 파일 생성"""
    if articles is None:
        return "수집된 기사가 없습니다."
        
    text_content = f"📰 {date.strftime('%Y년 %m월 %d일')}의 신문 게재 기사 모음\n\n"
    
    newspaper_groups = {}
    for article in articles:
        newspaper = article['newspaper']
        if newspaper not in newspaper_groups:
            newspaper_groups[newspaper] = []
        newspaper_groups[newspaper].append(article)
    
    for newspaper, articles_list in newspaper_groups.items():
        text_content += f"📌 [{newspaper}]\n"
        for article in articles_list:
            page_info = f"[{article['page']}] " if article['page'] else ""
            text_content += f"🔹 {page_info}{article['title']}\n   {article['url']}\n"
        text_content += "\n"
    
    return text_content

def create_search_excel_download(articles):
    """검색 결과 엑셀 파일 생성"""
    df = pd.DataFrame(articles)
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='검색결과')
    return output.getvalue()

def create_search_csv_download(articles):
    """검색 결과 CSV 파일 생성"""
    df = pd.DataFrame(articles)
    return df.to_csv(index=False).encode('utf-8-sig')

def create_search_text_download(articles, keyword):
    """검색 결과 텍스트 파일 생성"""
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

def generate_ai_report(articles: List[Dict], date: datetime) -> str:
    """AI를 사용하여 기사 요약 보고서 생성"""
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
        prompt = f"""
        ### 🎯 작업 목표
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

        **🔥 오늘의 Top 이슈 (5개 헤드라인)**
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
        
        ### 📝 각 기사 작성 형식
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
        
        # AI 요약 생성
        response = model.generate_content(prompt)
        return response.text
        
    except Exception as e:
        return f"보고서 생성 중 오류가 발생했습니다: {str(e)}"

def create_ai_report_download(articles, date):
    """AI 보고서 텍스트 파일 생성"""
    if articles is None:
        return "수집된 기사가 없습니다."
        
    report_content = f"📊 {date.strftime('%Y년 %m월 %d일')} 신문 기사 AI 요약 보고서\n\n"
    report_content += generate_ai_report(articles, date)
    return report_content

def newspaper_collection_tab():
    st.markdown("### 신문 게재 기사 수집")
    st.markdown("종이 신문에 실제로 실린 기사만 수집하여 제공합니다.")
    
    # 날짜 선택을 맨 위로 이동
    KST = timezone(timedelta(hours=9))
    current_date = datetime.now(KST).date()
    
    selected_date = st.date_input(
        "📅 수집할 날짜 선택",
        value=current_date,
        max_value=current_date,
        help="수집하고 싶은 신문 발행일을 선택하세요",
        key="date_picker"
    )
    
    st.markdown("---")
    
    # 신문사 선택 섹션
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown('<div class="category-header">📊 경제 신문</div>', unsafe_allow_html=True)
        with st.container():
            economic_papers = {
                "매일경제": "009",
                "머니투데이": "008", 
                "서울경제": "011",
                "이데일리": "018",
                "파이낸셜뉴스": "014",
                "한국경제": "015"
            }
            
            economic_all = st.checkbox("전체 선택", key="economic_all")
            economic_selected = []
            
            for paper, oid in economic_papers.items():
                checked = st.checkbox(paper, value=economic_all, key=f"economic_{oid}")
                if checked:
                    economic_selected.append((paper, oid))
    
    with col2:
        st.markdown('<div class="category-header">📋 종합일간지(조간)</div>', unsafe_allow_html=True)
        with st.container():
            general_papers = {
                "경향신문": "032",
                "국민일보": "005",
                "동아일보": "020",
                "서울신문": "081",
                "세계일보": "022",
                "조선일보": "023",
                "중앙일보": "025",
                "한겨레": "028",
                "한국일보": "469",
                "디지털타임스": "029",
                "전자신문": "030"
            }
            
            general_all = st.checkbox("전체 선택", key="general_all")
            general_selected = []
            
            for paper, oid in general_papers.items():
                checked = st.checkbox(paper, value=general_all, key=f"general_{oid}")
                if checked:
                    general_selected.append((paper, oid))
    
    with col3:
        st.markdown('<div class="category-header">🌆 석간 신문</div>', unsafe_allow_html=True)
        with st.container():
            evening_papers = {
                "문화일보": "021",
                "헤럴드경제": "016", 
                "아시아경제": "277"
            }
            
            evening_all = st.checkbox("전체 선택", key="evening_all")
            evening_selected = []
            
            for paper, oid in evening_papers.items():
                checked = st.checkbox(paper, value=evening_all, key=f"evening_{oid}")
                if checked:
                    evening_selected.append((paper, oid))
    
    st.markdown("---")
    
    # 크롤링 시작 버튼
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        if st.button("🚀 크롤링 시작", type="primary", use_container_width=True, key="btn_start_crawling"):
            all_selected = economic_selected + general_selected + evening_selected
            
            if not all_selected:
                st.error("❌ 최소 하나의 신문사를 선택해주세요.")
                return
            
            # 진행 상황 표시
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            collector = NewsCollector()
            
            try:
                status_text.text(f"🚀 {len(all_selected)}개 신문사 병렬 수집 시작...")
                progress_bar.progress(20)
                
                # 병렬 처리로 빠르게 수집 (테이블 형태로 상태 표시)
                all_articles = collector.crawl_multiple_papers(all_selected, selected_date.strftime("%Y%m%d"))
                
                progress_bar.progress(80)
                
                # 중복 제거
                unique_articles = remove_duplicates(all_articles)
                
                # 세션 상태에 저장
                st.session_state['newspaper_articles'] = unique_articles
                st.session_state['paper_date'] = selected_date
                
                status_text.text(f"✅ 수집 완료! 총 {len(unique_articles)}개 기사")
                progress_bar.progress(100)
                
                if len(unique_articles) == 0:
                    st.warning("⚠️ 수집된 기사가 없습니다. 다른 날짜나 신문사를 선택해보세요.")
                else:
                    st.success(f"🎉 {len(all_selected)}개 신문사에서 총 {len(unique_articles)}개의 기사를 성공적으로 수집했습니다!")
                    
            except Exception as e:
                st.error(f"❌ 크롤링 중 오류: {str(e)}")
            finally:
                collector.close()
    
    # 결과 표시
    if 'newspaper_articles' in st.session_state:
        display_newspaper_results()

def display_newspaper_results():
    articles = st.session_state['newspaper_articles']
    paper_date = st.session_state['paper_date']
    
    st.markdown("---")
    
    # articles가 None이면 함수 종료
    if articles is None:
        st.info("수집된 기사가 없습니다. 신문사를 선택하고 크롤링을 시작해주세요.")
        return
    
    # 결과 표시 (검색 기능을 아래로 이동)
    if paper_date is not None:
        st.markdown(f"### 📰 {paper_date.strftime('%Y년 %m월 %d일')}의 신문 게재 기사 모음")
    else:
        st.markdown("### 📰 신문 게재 기사 모음")
    
    st.markdown(f"**총 {len(articles)}개 기사**")
    
    if len(articles) == 0:
        st.info("수집된 기사가 없습니다.")
        return
    
    # 검색 기능 (버튼 정렬 수정)
    col1, col2, col3 = st.columns([3, 1, 1])

    with col1:
        search_term = st.text_input("🔍 기사 검색", placeholder="제목으로 검색...", key="input_search_articles_newspaper")

    with col2:
        # 라벨을 추가하여 높이 맞춤
        st.markdown("&nbsp;", unsafe_allow_html=True)  # 빈 공간
        if st.button("검색", key="btn_search_articles_newspaper", use_container_width=True):
            if search_term:
                filtered_articles = [
                    article for article in articles 
                    if search_term.lower() in article['title'].lower()
                ]
                st.session_state['filtered_articles'] = filtered_articles
            else:
                st.session_state['filtered_articles'] = articles

    with col3:
        # 라벨을 추가하여 높이 맞춤
        st.markdown("&nbsp;", unsafe_allow_html=True)  # 빈 공간
        if st.button("초기화", key="btn_reset_articles_newspaper", use_container_width=True):
            st.session_state['filtered_articles'] = articles
            st.rerun()
    
    st.markdown('</div>', unsafe_allow_html=True)
    
    # 표시할 기사 결정
    display_articles = st.session_state.get('filtered_articles', articles)
    
    # display_articles가 None이면 articles 사용
    if display_articles is None:
        display_articles = articles
    
    # 다운로드 기능을 검색 기능 아래로 이동
    st.markdown("### 💾 다운로드")
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        excel_data = create_excel_download(display_articles)
        st.download_button(
            label="📊 엑셀 다운로드",
            data=excel_data,
            file_name=f"newspaper_articles_{paper_date.strftime('%Y%m%d') if paper_date else datetime.now().strftime('%Y%m%d')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key="btn_download_newspaper_excel"
        )
    
    with col2:
        text_data = create_text_download(display_articles, paper_date if paper_date else datetime.now())
        st.download_button(
            label="📄 텍스트 다운로드",
            data=text_data,
            file_name=f"newspaper_articles_{paper_date.strftime('%Y%m%d') if paper_date else datetime.now().strftime('%Y%m%d')}.txt",
            mime="text/plain",
            key="btn_download_newspaper_text"
        )
    
    with col3:
        if st.button("📋 클립보드 복사", key="btn_copy_newspaper_text"):
            copy_text = create_text_download(display_articles, paper_date if paper_date else datetime.now())
            st.code(copy_text, language="text")
            st.success("✅ 텍스트가 준비되었습니다. 위 내용을 복사하세요.")
    
    with col4:
        if st.button("🤖 AI 보고서 생성", key="btn_generate_ai_report"):
            with st.spinner("AI가 기사를 분석하고 보고서를 생성하는 중..."):
                report_text = create_ai_report_download(display_articles, paper_date if paper_date else datetime.now())
                st.session_state['ai_report'] = report_text
                st.success("✅ AI 보고서가 생성되었습니다.")
                st.rerun()
    
    st.markdown("---")
    
    # AI 보고서가 있으면 표시
    if 'ai_report' in st.session_state and st.session_state['ai_report'] is not None:
        st.markdown("### 📊 AI 요약 보고서")
        st.markdown(st.session_state['ai_report'])
        st.download_button(
            label="📑 AI 보고서 다운로드",
            data=st.session_state['ai_report'],
            file_name=f"ai_report_{paper_date.strftime('%Y%m%d') if paper_date else datetime.now().strftime('%Y%m%d')}.txt",
            mime="text/plain",
            key="btn_download_ai_report"
        )
        st.markdown("---")
    
    # 신문사별로 그룹화
    newspaper_groups = {}
    for article in display_articles:
        newspaper = article['newspaper']
        if newspaper not in newspaper_groups:
            newspaper_groups[newspaper] = []
        newspaper_groups[newspaper].append(article)
    
    # 신문사별 기사 표시
    for newspaper, articles_list in newspaper_groups.items():
        st.markdown(f"#### 📌 [{newspaper}] ({len(articles_list)}개)")
        for article in articles_list:
            page_info = f"[{article['page']}] " if article['page'] else ""
            st.markdown(f"🔹 {page_info}[{article['title']}]({article['url']})")

def naver_search_tab():
    st.markdown("### 네이버 뉴스 검색")
    st.markdown("네이버 검색 API를 이용하여 뉴스를 검색합니다.")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        keyword = st.text_input("🔍 검색 키워드", placeholder="검색할 키워드를 입력하세요...", key="input_search_keyword")
    
    with col2:
        # selectbox를 number_input으로 변경
        max_articles = st.number_input(
            "최대 기사 수", 
            min_value=1, 
            max_value=1000, 
            value=100, 
            step=1, 
            key="input_max_articles",
            help="1부터 1000까지 입력 가능합니다"
        )
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        if st.button("🔍 검색 시작", type="primary", use_container_width=True, key="btn_start_search"):
            if not keyword:
                st.error("❌ 검색 키워드를 입력해주세요.")
                return
            
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            searcher = NaverNewsSearcher()
            
            try:
                status_text.text("🔍 네이버 뉴스 검색 중...")
                progress_bar.progress(50)
                
                articles = searcher.search_news(keyword, max_articles)
                
                progress_bar.progress(100)
                status_text.text(f"✅ 검색 완료! 총 {len(articles)}개 기사")
                
                # 세션 상태에 저장
                st.session_state['search_articles'] = articles
                st.session_state['current_search_keyword'] = keyword
                
                if len(articles) == 0:
                    st.warning("⚠️ 검색 결과가 없습니다. 다른 키워드로 시도해보세요.")
                else:
                    st.success(f"🎉 '{keyword}'에 대한 {len(articles)}개의 기사를 찾았습니다!")
                
            except Exception as e:
                st.error(f"❌ 검색 중 오류가 발생했습니다: {str(e)}")
                progress_bar.progress(0)
                status_text.text("")
    
    # 검색 결과 표시
    if 'search_articles' in st.session_state:
        display_search_results()

def display_search_results():
    articles = st.session_state['search_articles']
    keyword = st.session_state['current_search_keyword']
    
    st.markdown("---")
    
    # articles가 None이면 함수 종료
    if articles is None:
        st.info("검색 결과가 없습니다. 키워드를 입력하고 검색을 시작해주세요.")
        return
        
    st.markdown(f"### 🔍 '{keyword}' 검색 결과 ({len(articles)}개)")
    
    if len(articles) == 0:
        st.info("검색 결과가 없습니다.")
        return
    
    # 다운로드 기능을 상단으로 이동
    st.markdown("### 💾 다운로드")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        excel_data = create_search_excel_download(articles)
        st.download_button(
            label="📊 엑셀 다운로드",
            data=excel_data,
            file_name=f"search_results_{keyword}_{datetime.now().strftime('%Y%m%d')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key="btn_download_naver_search_excel"
        )
    
    with col2:
        csv_data = create_search_csv_download(articles)
        st.download_button(
            label="📊 CSV 다운로드",
            data=csv_data,
            file_name=f"search_results_{keyword}_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv",
            key="btn_download_naver_search_csv"
        )
    
    with col3:
        text_data = create_search_text_download(articles, keyword)
        st.download_button(
            label="📄 텍스트 다운로드",
            data=text_data,
            file_name=f"search_results_{keyword}_{datetime.now().strftime('%Y%m%d')}.txt",
            mime="text/plain",
            key="btn_download_naver_search_text"
        )
    
    st.markdown("---")
    
    # 결과 표시 옵션
    display_mode = st.radio("표시 방식", ["요약 보기", "전체 보기"], horizontal=True, key="radio_display_mode")
    
    if display_mode == "요약 보기":
        # 간단한 리스트 형태로 표시
        for i, article in enumerate(articles, 1):
            st.markdown(f"**{i}.** [{article['title']}]({article['link']})")
            st.caption(f"📅 {article['pubDate']} | 📰 {article.get('source', '알 수 없음')}")
            if article.get('description'):
                st.write(f"💬 {article['description'][:100]}...")
            st.markdown("---")
    else:
        # 상세한 expander 형태로 표시
        for i, article in enumerate(articles, 1):
            with st.expander(f"{i}. {article['title']}", expanded=False):
                st.markdown(f"**요약:** {article['description']}")
                st.markdown(f"**발행일:** {article['pubDate']}")
                st.markdown(f"**출처:** {article.get('source', '알 수 없음')}")
                st.markdown(f"**링크:** [기사 보기]({article['link']})")

def get_industry_info():
    """업종 및 주요제품 정보 수집"""
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

def collect_market_data(market: str, date: str) -> pd.DataFrame:
    """시장 데이터 수집"""
    try:
        # 1. 가격 변동 데이터 수집 (이 데이터에 모든 필요한 정보가 포함되어 있음)
        df = stock.get_market_price_change(date, date, market=market)
        time.sleep(0.3)  # API 호출 간 딜레이
        
        # 2. OHLCV 데이터 수집 (고가, 저가, 시가총액 정보)
        df_ohlcv = stock.get_market_ohlcv(date, market=market)
        time.sleep(0.3)  # API 호출 간 딜레이
        
        # 3. 기본 지표 데이터 수집
        df_fundamental = stock.get_market_fundamental(date, market=market)
        time.sleep(0.3)  # API 호출 간 딜레이
        
        # 4. 업종 정보 수집
        df_industry = get_industry_info()
        
        # 5. OHLCV 데이터 병합 (고가, 저가, 시가총액)
        if not df_ohlcv.empty:
            # 필요한 컬럼만 선택하여 병합
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

def display_market_analysis(df: pd.DataFrame, date: datetime):
    """시장 데이터 분석 결과 표시"""
    # 현재 시간 표시
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    st.success(f"✅ {len(df)}개 종목의 데이터를 조회했습니다! (최종 업데이트: {current_time})")
    
    # 요약 정보
    st.markdown("### 📊 시장 요약")
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("총 종목 수", f"{len(df):,}개")
    with col2:
        avg_trading_value = df['거래대금'].mean()
        st.metric("평균 거래대금", f"{avg_trading_value/100000000:.0f}억원")
    with col3:
        st.metric("평균 시가총액", f"{df['시가총액'].mean()/100000000:.0f}억원")
    with col4:
        st.metric("평균 등락률", f"{df['등락률'].mean():.2f}%")
    
    # 등락률 분포 차트
    st.markdown("### 📈 등락률 분포")
    fig = go.Figure(data=[go.Histogram(x=df['등락률'], nbinsx=50)])
    fig.update_layout(
        title="등락률 분포도",
        xaxis_title="등락률 (%)",
        yaxis_title="종목 수"
    )
    st.plotly_chart(fig, use_container_width=True)
    
    # 시장별 종목 수
    market_counts = df['시장구분'].value_counts()
    fig = go.Figure(data=[go.Pie(
        labels=market_counts.index,
        values=market_counts.values,
        hole=.3
    )])
    fig.update_layout(title="시장별 종목 분포")
    st.plotly_chart(fig, use_container_width=True)
    
    # 상세 데이터 표시
    st.markdown("### 📋 종목 상세 정보")
    
    # 정렬 옵션
    sort_column = st.selectbox(
        "정렬 기준",
        options=['종가', '거래량', '등락률', '시가총액', '변동폭', 'PER', 'PBR', 'EPS', 'BPS', 'DIV', 'DPS'],
        index=3
    )
    
    df = df.sort_values(by=sort_column, ascending=False)
    
    # 데이터 포맷팅
    display_df = df.copy()
    display_df['시가총액'] = display_df['시가총액'].apply(lambda x: f"{x/100000000:.0f}억원")
    display_df['거래대금'] = display_df['거래대금'].apply(lambda x: f"{x/100000000:.0f}억원")
    display_df['거래량'] = display_df['거래량'].apply(lambda x: f"{x:,}")
    display_df['변동폭'] = display_df['변동폭'].apply(lambda x: f"{x:,}")
    display_df['등락률'] = display_df['등락률'].apply(lambda x: f"{x:.2f}%")
    
    # 기본 지표 포맷팅
    for col in ['PER', 'PBR', 'EPS', 'BPS', 'DIV', 'DPS']:
        if col in display_df.columns:
            display_df[col] = display_df[col].apply(lambda x: f"{x:.2f}" if pd.notnull(x) else "-")
    
    # 표시할 열 선택
    columns_to_display = [
        '종목명', '시장구분', '업종', '주요제품', '시가', '고가', '저가', '종가', 
        '거래량', '거래대금', '등락률', '변동폭', '시가총액',
        'PER', 'PBR', 'EPS', 'BPS', 'DIV', 'DPS'
    ]
    
    # 데이터 테이블 표시
    st.dataframe(
        display_df[columns_to_display],
        use_container_width=True,
        hide_index=True
    )
    
    # CSV 다운로드
    csv = df[columns_to_display].to_csv(index=False).encode('utf-8-sig')
    st.download_button(
        label="📥 CSV 다운로드",
        data=csv,
        file_name=f"stock_data_{date.strftime('%Y%m%d')}.csv",
        mime="text/csv"
    )
    
    # 지표 설명
    st.markdown("### 📊 주요 지표 설명")
    st.markdown("""
    - **PER (주가수익비율)**: 주가를 주당순이익(EPS)으로 나눈 값으로, 기업의 수익성과 주가의 관계를 나타냅니다. 낮을수록 저평가된 주식으로 볼 수 있습니다.
    - **PBR (주가순자산비율)**: 주가를 주당순자산(BPS)으로 나눈 값으로, 기업의 순자산 대비 주가의 수준을 나타냅니다. 1 미만이면 순자산보다 저평가된 것으로 볼 수 있습니다.
    - **EPS (주당순이익)**: 기업의 순이익을 발행주식수로 나눈 값으로, 주주가 받을 수 있는 이익을 나타냅니다.
    - **BPS (주당순자산)**: 기업의 순자산을 발행주식수로 나눈 값으로, 주주가 받을 수 있는 순자산을 나타냅니다.
    - **DIV (배당수익률)**: 주당배당금(DPS)을 주가로 나눈 값으로, 투자금액 대비 배당수익을 나타냅니다.
    - **DPS (주당배당금)**: 기업이 주주에게 지급하는 배당금을 발행주식수로 나눈 값입니다.
    """)

def display_stock_data():
    """전체 종목 시세 조회"""
    st.markdown("### 📊 전체 종목 시세 조회")
    
    # 날짜 선택
    today = datetime.now()
    max_date = today.strftime("%Y%m%d")
    
    # 주말인 경우 금요일을 기본값으로
    if today.weekday() >= 5:  # 5: 토요일, 6: 일요일
        days_to_subtract = today.weekday() - 4
        today = today - timedelta(days=days_to_subtract)
    
    # 날짜 선택 위젯
    selected_date = st.date_input(
        "조회 날짜",
        value=today,
        max_value=today,
        help="조회할 날짜를 선택하세요"
    )
    
    # 필터링 옵션
    col1, col2, col3 = st.columns([2, 5, 1])
    
    with col1:
        market_filter = st.multiselect(
            "시장 선택",
            options=['KOSPI', 'KOSDAQ'],
            default=['KOSPI', 'KOSDAQ']
        )
    
    with col2:
        st.markdown("주가 범위")
        price_col1, price_col2 = st.columns(2)
        with price_col1:
            min_price = st.number_input(
                "최소 주가",
                min_value=0,
                max_value=1500000,
                value=0,
                step=1000,
                help="최소 주가를 입력하세요"
            )
        with price_col2:
            max_price = st.number_input(
                "최대 주가",
                min_value=0,
                max_value=1500000,
                value=1500000,
                step=1000,
                help="최대 주가를 입력하세요"
            )
        
        # 슬라이더는 입력된 값과 동기화
        price_range = st.slider(
            "",
            min_value=0,
            max_value=1500000,
            value=(min_price, max_price),
            step=1000,
            help="원하는 주가 범위를 선택하세요"
        )
    
    with col3:
        volume_filter = st.number_input(
            "최소 거래량",
            min_value=0,
            value=0,
            step=1000
        )
    
    # 데이터 조회 버튼
    if st.button("🔍 데이터 조회", type="primary"):
        with st.spinner('데이터를 수집하는 중입니다...'):
            try:
                # KOSPI 데이터 수집
                kospi_df = collect_market_data("KOSPI", selected_date.strftime("%Y%m%d"))
                time.sleep(1)  # API 호출 간 딜레이
                
                # KOSDAQ 데이터 수집
                kosdaq_df = collect_market_data("KOSDAQ", selected_date.strftime("%Y%m%d"))
                
                # 데이터 합치기
                df = pd.concat([kospi_df, kosdaq_df])
                
                # 필터링
                filtered_df = df[
                    (df['시장구분'].isin(market_filter)) &
                    (df['종가'].between(price_range[0], price_range[1])) &
                    (df['거래량'] >= volume_filter)
                ]
                
                # 세션 상태에 저장
                st.session_state['stock_data'] = df
                st.session_state['stock_filtered_data'] = filtered_df
                st.session_state['stock_date'] = selected_date
                
                if len(filtered_df) > 0:
                    display_market_analysis(filtered_df, selected_date)
                else:
                    st.warning("선택한 조건에 해당하는 종목이 없습니다.")
                
            except Exception as e:
                st.error(f"데이터 조회 중 오류가 발생했습니다: {str(e)}")
    else:
        # 저장된 데이터가 있으면 표시
        if st.session_state['stock_filtered_data'] is not None:
            display_market_analysis(st.session_state['stock_filtered_data'], st.session_state['stock_date'])

def display_stock_market_tab():
    """오늘의 증시 탭 표시"""
    st.markdown("### 📈 오늘의 증시(종료일 기준)")
    
    # 날짜 선택
    today = datetime.now()
    max_date = today.strftime("%Y%m%d")
    
    # 주말인 경우 금요일을 기본값으로
    if today.weekday() >= 5:  # 5: 토요일, 6: 일요일
        days_to_subtract = today.weekday() - 4
        today = today - timedelta(days=days_to_subtract)
    
    # 날짜 선택 위젯
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
            value=today,
            max_value=today,
            help="조회 종료일을 선택하세요"
        )
    
    # 1. 주요 지수 시세
    st.markdown("#### 📊 주요 지수")
    index_codes = {
        'KOSPI': 'KS11',
        'KOSDAQ': 'KQ11',
        'S&P 500': 'US500',
        'NASDAQ': 'IXIC',
        '다우존스': 'DJI',
        '니케이225': 'N225',
        '항셍지수': 'HSI'
    }

    cols = st.columns(len(index_codes))
    for i, (name, code) in enumerate(index_codes.items()):
        try:
            df = fdr.DataReader(code, start_date, end_date)
            delta = df['Close'].pct_change().iloc[-1] * 100
            cols[i].metric(label=name, value=f"{df['Close'].iloc[-1]:,.2f}", delta=f"{delta:.2f}%")
        except Exception as e:
            cols[i].error(f"{name} 지수 오류: {e}")
    
    st.markdown("---")
    
    # 2. 거래실적 데이터 표시
    display_trading_value(start_date, end_date)
    
    # 3. 환율 & 원자재 시세
    st.markdown("#### 💱 환율 및 원자재 가격")
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("##### 환율")
        fx_codes = {'미국 달러 (USD/KRW)': 'USD/KRW', '일본 엔화 (JPY/KRW)': 'JPY/KRW'}
        for label, code in fx_codes.items():
            try:
                fx = fdr.DataReader(code, start_date, end_date)
                if not fx.empty:
                    st.line_chart(fx['Close'].rename(label), height=150)
                else:
                    st.warning(f"{label} 데이터가 존재하지 않습니다.")
            except Exception as e:
                st.error(f"{label} 데이터 오류: {e}")

    with col2:
        st.markdown("##### 원자재")
        cm_codes = {'서부텍사스산 원유 (WTI)': 'WTI', '금 (GOLD)': 'GOLD'}
        for label, code in cm_codes.items():
            try:
                cm = fdr.DataReader(code, start_date, end_date)
                if not cm.empty:
                    st.line_chart(cm['Close'].rename(label), height=150)
                else:
                    st.warning(f"{label} 데이터가 존재하지 않습니다.")
            except Exception as e:
                st.error(f"{label} 데이터 오류: {e}")
    
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

def extract_stock_names(text):
    """텍스트에서 종목명 추출"""
    # 종목명 패턴 (한글 2-10자)
    pattern = r'[가-힣]{2,10}(?:주식|증권|기업|회사|주)'
    matches = re.findall(pattern, text)
    return [match.replace('주식', '').replace('증권', '').replace('기업', '').replace('회사', '').replace('주', '') for match in matches]


def search_stock_news(keywords, start_date, end_date, max_articles):
    """특징주 관련 뉴스 검색"""
    searcher = NaverNewsSearcher()
    return searcher.search_stock_news(keywords, start_date, max_articles)

def display_stock_news_tab():
    """특징주 포착 탭 표시"""
    st.markdown("### 📈 특징주 포착")
    
    # 검색 키워드 선택
    default_keywords = ["특징주", "급등주", "상한가", "급등세", "급락세", 
                       "강세", "약세", "거래량 증가", "신고가", "신저가"]
    
    # 사용자 정의 키워드 입력
    custom_keyword = st.text_input(
        "추가 검색 키워드 입력",
        help="원하는 검색 키워드를 입력하세요. 입력 후 Enter를 누르면 키워드가 추가됩니다."
    )
    
    # 사용자 정의 키워드가 입력되면 default_keywords에 추가
    if custom_keyword and custom_keyword not in default_keywords:
        default_keywords.append(custom_keyword)
    
    # 키워드 선택 (기본 키워드 + 사용자 정의 키워드)
    selected_keywords = st.multiselect(
        "검색 키워드 선택",
        options=default_keywords,
        default=default_keywords[:3]
    )
    
    # 조회 날짜 선택
    today = datetime.now()
    # 주말인 경우 금요일을 기본값으로
    if today.weekday() >= 5:  # 5: 토요일, 6: 일요일
        days_to_subtract = today.weekday() - 4
        today = today - timedelta(days=days_to_subtract)
    
    selected_date = st.date_input(
        "조회 날짜",
        value=today,
        max_value=today,
        help="조회할 날짜를 선택하세요"
    )
    
    # 최대 기사 수 입력
    max_articles = st.number_input(
        "최대 기사 수",
        min_value=10,
        max_value=1000,
        value=100,
        step=10
    )
    
    if st.button("🔍 검색 시작", type="primary"):
        with st.spinner("뉴스 검색 및 분석 중..."):
            # 1. 뉴스 검색
            articles = search_stock_news(selected_keywords, selected_date, None, max_articles)
            
            # 키워드별 기사 수 계산
            keyword_article_counts = {}
            for keyword in selected_keywords:
                count = sum(1 for article in articles if keyword in article['title'] or keyword in article['description'])
                keyword_article_counts[keyword] = count
            
            # 2. 시장 데이터 수집 (선택한 날짜 기준)
            market_data = {}
            all_stock_names = set()  # 모든 종목명을 저장할 set
            
            for market in ['KOSPI', 'KOSDAQ']:
                try:
                    df = collect_market_data(market, selected_date.strftime("%Y%m%d"))
                    market_data[market] = df
                    # 시장 데이터에서 종목명 추출
                    all_stock_names.update(df['종목명'].tolist())
                except Exception as e:
                    st.error(f"{market} 데이터 수집 중 오류: {str(e)}")
            
            # 3. 뉴스 기사에서 종목명 매칭
            stock_articles = {}  # 종목별 기사를 저장할 딕셔너리
            stock_keywords = {}  # 종목별 매칭된 키워드를 저장할 딕셔너리
            matched_stocks = set()  # 매칭된 종목을 추적하기 위한 set
            
            for article in articles:
                # 기사 제목과 내용에서 종목명 찾기
                text = article['title'] + " " + article['description']
                
                # 기사에 포함된 키워드 찾기
                matched_keywords = [keyword for keyword in selected_keywords if keyword in text]
                
                # 시장 데이터의 모든 종목명과 매칭
                for stock_name in all_stock_names:
                    if stock_name in text:
                        if stock_name not in stock_articles:
                            stock_articles[stock_name] = []
                            stock_keywords[stock_name] = set()
                        stock_articles[stock_name].append(article)
                        stock_keywords[stock_name].update(matched_keywords)
                        matched_stocks.add(stock_name)
            
            # 4. 결과 생성
            results = []
            for stock_name, articles in stock_articles.items():
                # 해당 종목의 시장 데이터 찾기
                for market, df in market_data.items():
                    stock_data = df[df['종목명'] == stock_name]
                    if not stock_data.empty:
                        stock = stock_data.iloc[0]
                        # 결과 데이터 구성
                        result = {
                            '종목명': stock['종목명'],
                            '시장구분': market,
                            '업종': stock['업종'],
                            '주요제품': stock['주요제품'],  # 주요제품 컬럼 추가
                            '현재가': stock['종가'],
                            '등락률': stock['등락률'],
                            '거래량': stock['거래량'],
                            '시가총액': stock['시가총액'],
                            '관련기사수': len(articles),
                            '매칭키워드': ', '.join(sorted(stock_keywords[stock_name]))
                        }
                        
                        # 기사 정보 추가 (최대 3개)
                        for i, article in enumerate(articles[:3], 1):
                            result.update({
                                f'기사제목{i}': article['title'],
                                f'기사요약{i}': article['description'],
                                f'기사링크{i}': article['link']
                            })
                        
                        results.append(result)
            
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
                article_counts = [len(articles) for articles in stock_articles.values()]
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
                csv = df_results.to_csv(index=False).encode('utf-8-sig')
                st.download_button(
                    label="📥 CSV 다운로드",
                    data=csv,
                    file_name=f"stock_news_{selected_date.strftime('%Y%m%d')}.csv",
                    mime="text/csv"
                )
            else:
                st.warning("검색 결과가 없습니다.")

# secrets 확인 (보안)
api_available, missing_secrets = check_secrets()

if missing_secrets:
    st.sidebar.warning(f"⚠️ 설정되지 않은 항목: {', '.join(missing_secrets)}")
    st.sidebar.info("일부 기능이 제한될 수 있습니다.")

st.markdown('<h1 class="main-header">📰 경제적 자유 프로젝트 </h1>', unsafe_allow_html=True)

# 사이드바 메뉴
with st.sidebar:
    selected = option_menu(
        menu_title="메뉴",
        options=[
            "신문 게재 기사 수집",
            "네이버 뉴스 검색",
            "오늘의 증시",
            "전체 종목 시세",
            "특징주 포착"
        ],
        icons=[
            "newspaper",
            "search",
            "graph-up",
            "bar-chart",
            "bullseye"  # target을 bullseye로 변경
        ],
        menu_icon="list",
        default_index=0,
        styles={
            "container": {"padding": "0!important", "background-color": "transparent"},
            "icon": {"color": "white", "font-size": "16px"},
            "nav-link": {
                "font-size": "16px",
                "text-align": "left",
                "margin": "0px",
                "padding": "10px",
                "color": "white",
                "background-color": "transparent",
                "border": "none",
                "border-radius": "0px",
            },
            "nav-link-selected": {
                "background-color": "#4CAF50",
                "color": "white",
                "font-weight": "bold",
            },
        }
    )
    
    st.markdown("---")
    st.markdown("### 📖 사용법")
    st.markdown("""
    **신문 게재 기사 수집:**
    1. 원하는 신문사 선택
    2. 날짜 선택
    3. 크롤링 시작
    4. AI 요약 보고서 작성(gemini)
    
    **네이버 뉴스 검색:**
    1. 키워드 입력
    2. 최대 기사 수 선택
    3. 검색 시작
        
    **오늘의 증시:**
    1. 주요 지수 동향 
    2. 환율 및 원자재 동향 
    3. 개별 종목 차트 검색 
    4. 종목 기술적 지표 검색
                
    **특징주 포착:**
    1. 키워드 입력
    2. 최대 기사 수 선택
    3. 검색 시작
    """)
    
    st.markdown("---")
    st.markdown("### ⚙️ 설정 정보")
    
    # API 키 값을 노출하지 않고 상태만 표시
    api_status = "✅ 설정됨" if api_available else "❌ 미설정"
    st.info(f"네이버 API: {api_status}")
    
    # 기타 설정 정보 (민감하지 않은 정보만)
    try:
        max_articles = st.secrets["app_settings"]["max_articles_per_request"]
        st.info(f"최대 요청 기사 수: {max_articles}")
    except:
        st.info("기본 설정 사용 중")

# 선택된 탭에 따라 해당 함수 실행
if selected == "신문 게재 기사 수집":
    newspaper_collection_tab()
elif selected == "네이버 뉴스 검색":
    naver_search_tab()
elif selected == "오늘의 증시":
    display_stock_market_tab()
elif selected == "전체 종목 시세":
    display_stock_data()
elif selected == "특징주 포착":
    display_stock_news_tab()