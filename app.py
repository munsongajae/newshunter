import streamlit as st
import pandas as pd
from datetime import datetime
import io
import base64
from news_collector import NewsCollector
from naver_search import NaverNewsSearcher

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

def main():
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
        
        **네이버 뉴스 검색:**
        1. 키워드 입력
        2. 최대 기사 수 선택
        3. 검색 시작
        """)
        
        st.markdown("---")
        st.markdown("### 📊 통계")
        if 'newspaper_articles' in st.session_state:
            st.metric("수집된 신문 기사", len(st.session_state['newspaper_articles']))
        if 'search_articles' in st.session_state:
            st.metric("검색된 기사", len(st.session_state['search_articles']))
    
    # 탭 생성
    tab1, tab2 = st.tabs(["📰 신문 게재 기사 수집", "🔍 네이버 뉴스 검색"])
    
    with tab1:
        newspaper_collection_tab()
    
    with tab2:
        naver_search_tab()

def newspaper_collection_tab():
    st.markdown("### 신문 게재 기사 수집")
    st.markdown("신문에 게재된 기사만 수집하여 제공합니다.")
    
    # 날짜 선택을 맨 위로 이동
    selected_date = st.date_input(
        "📅 수집할 날짜 선택",
        value=datetime.now().date(),
        max_value=datetime.now().date(),
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
    
    # 다운로드 기능을 상단으로 (기존 위치 유지)
    st.markdown("### 💾 다운로드")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        excel_data = create_excel_download(articles)
        st.download_button(
            label="📊 엑셀 다운로드",
            data=excel_data,
            file_name=f"newspaper_articles_{st.session_state['paper_date'].strftime('%Y%m%d')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key="btn_download_newspaper_excel"
        )
    
    with col2:
        text_data = create_text_download(articles, st.session_state['paper_date'])
        st.download_button(
            label="📄 텍스트 다운로드",
            data=text_data,
            file_name=f"newspaper_articles_{st.session_state['paper_date'].strftime('%Y%m%d')}.txt",
            mime="text/plain",
            key="btn_download_newspaper_text"
        )
    
    with col3:
        if st.button("📋 클립보드 복사", key="btn_copy_newspaper_text"):
            copy_text = create_text_download(articles, st.session_state['paper_date'])
            st.code(copy_text, language="text")
            st.success("✅ 텍스트가 준비되었습니다. 위 내용을 복사하세요.")
    
    st.markdown("---")
    
    # 검색 기능을 다운로드 아래로 이동
    st.markdown('<div class="search-box">', unsafe_allow_html=True)
    col1, col2, col3 = st.columns([3, 1, 1])
    
    with col1:
        search_term = st.text_input("🔍 기사 검색", placeholder="제목으로 검색...", key="input_search_articles_newspaper")
    
    with col2:
        if st.button("검색", key="btn_search_articles_newspaper"):
            if search_term:
                filtered_articles = [
                    article for article in articles 
                    if search_term.lower() in article['title'].lower()
                ]
                st.session_state['filtered_articles'] = filtered_articles
            else:
                st.session_state['filtered_articles'] = articles
    
    with col3:
        if st.button("초기화", key="btn_reset_articles_newspaper"):
            st.session_state['filtered_articles'] = articles
            st.rerun()
    
    st.markdown('</div>', unsafe_allow_html=True)
    
    # 표시할 기사 결정
    display_articles = st.session_state.get('filtered_articles', articles)
    
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

# 헬퍼 함수들
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

if __name__ == "__main__":
    main()