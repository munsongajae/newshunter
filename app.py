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
from stock_market import display_stock_market_tab

# 페이지 설정
st.set_page_config(
    page_title="신문 기사 수집기",
    page_icon="📰",
    layout="wide",
    initial_sidebar_state="expanded"
)

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
    df = pd.DataFrame(articles)
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='신문기사')
    return output.getvalue()

def create_text_download(articles, date):
    """텍스트 파일 생성"""
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

def create_ai_report_download(articles: List[Dict], date: datetime) -> str:
    """AI 보고서 텍스트 파일 생성"""
    report_content = f"📊 {date.strftime('%Y년 %m월 %d일')} 신문 기사 AI 요약 보고서\n\n"
    report_content += generate_ai_report(articles, date)
    return report_content

def newspaper_collection_tab():
    st.markdown("### 신문 게재 기사 수집")
    st.markdown("신문에 게재된 기사만 수집하여 제공합니다.")
    
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
    
    st.markdown("---")
    
    # 결과 표시 (검색 기능을 아래로 이동)
    st.markdown(f"### 📰 {st.session_state['paper_date'].strftime('%Y년 %m월 %d일')}의 신문 게재 기사 모음")
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
    
    # 다운로드 기능을 검색 기능 아래로 이동
    st.markdown("### 💾 다운로드")
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        excel_data = create_excel_download(display_articles)
        st.download_button(
            label="📊 엑셀 다운로드",
            data=excel_data,
            file_name=f"newspaper_articles_{st.session_state['paper_date'].strftime('%Y%m%d')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key="btn_download_newspaper_excel"
        )
    
    with col2:
        text_data = create_text_download(display_articles, st.session_state['paper_date'])
        st.download_button(
            label="📄 텍스트 다운로드",
            data=text_data,
            file_name=f"newspaper_articles_{st.session_state['paper_date'].strftime('%Y%m%d')}.txt",
            mime="text/plain",
            key="btn_download_newspaper_text"
        )
    
    with col3:
        if st.button("📋 클립보드 복사", key="btn_copy_newspaper_text"):
            copy_text = create_text_download(display_articles, st.session_state['paper_date'])
            st.code(copy_text, language="text")
            st.success("✅ 텍스트가 준비되었습니다. 위 내용을 복사하세요.")
    
    with col4:
        if st.button("🤖 AI 보고서 생성", key="btn_generate_ai_report"):
            with st.spinner("AI가 기사를 분석하고 보고서를 생성하는 중..."):
                report_text = create_ai_report_download(display_articles, st.session_state['paper_date'])
                st.session_state['ai_report'] = report_text
                st.success("✅ AI 보고서가 생성되었습니다.")
                st.rerun()
    
    st.markdown("---")
    
    # AI 보고서가 있으면 표시
    if 'ai_report' in st.session_state:
        st.markdown("### 📊 AI 요약 보고서")
        st.markdown(st.session_state['ai_report'])
        st.download_button(
            label="📑 AI 보고서 다운로드",
            data=st.session_state['ai_report'],
            file_name=f"ai_report_{st.session_state['paper_date'].strftime('%Y%m%d')}.txt",
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

# secrets 확인 (보안)
api_available, missing_secrets = check_secrets()

if missing_secrets:
    st.sidebar.warning(f"⚠️ 설정되지 않은 항목: {', '.join(missing_secrets)}")
    st.sidebar.info("일부 기능이 제한될 수 있습니다.")

st.markdown('<h1 class="main-header">📰 신문 기사 수집기</h1>', unsafe_allow_html=True)

# 사이드바에 설정 정보 표시 (보안 정보 숨김)
with st.sidebar:
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
    1. 오늘의 증시 보기
    """)
    
    st.markdown("---")
    st.markdown("### 📊 통계")
    if 'newspaper_articles' in st.session_state:
        st.metric("수집된 신문 기사", len(st.session_state['newspaper_articles']))
    if 'search_articles' in st.session_state:
        st.metric("검색된 기사", len(st.session_state['search_articles']))

# 탭 생성
tab1, tab2, tab3 = st.tabs(["📰 신문 게재 기사 수집", "🔍 네이버 뉴스 검색", "📈 오늘의 증시"])

with tab1:
    newspaper_collection_tab()

with tab2:
    naver_search_tab()
    
with tab3:
    display_stock_market_tab()