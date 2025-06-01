import requests
import json
from datetime import datetime, timedelta
import time
import streamlit as st
import re
from urllib.parse import quote
from bs4 import BeautifulSoup
import pandas as pd

class NaverNewsSearcher:
    def __init__(self):
        # Streamlit secrets에서 API 키 로드
        try:
            self.client_id = st.secrets["naver_api"]["client_id"]
            self.client_secret = st.secrets["naver_api"]["client_secret"]
            self.api_available = True
        except KeyError:
            st.warning("⚠️ 네이버 API 키가 설정되지 않았습니다. 웹 크롤링 방식으로 동작합니다.")
            self.client_id = None
            self.client_secret = None
            self.api_available = False
        
        self.base_url = "https://openapi.naver.com/v1/search/news.json"
        
        # 설정값 로드
        try:
            self.max_articles_per_request = st.secrets["app_settings"]["max_articles_per_request"]
            self.request_delay = st.secrets["app_settings"]["request_delay"]
        except KeyError:
            self.max_articles_per_request = 100
            self.request_delay = 0.1

        # 세션 설정
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'ko-KR,ko;q=0.9,en;q=0.8',
        })

    def search_news(self, keyword, max_results=100):
        """네이버 뉴스 검색 - API 우선, 실패시 크롤링"""
        if self.api_available:
            try:
                return self.search_news_api(keyword, max_results)
            except Exception as e:
                st.warning(f"API 검색 실패: {e}. 웹 크롤링으로 전환합니다.")
                return self.search_news_fallback(keyword, max_results)
        else:
            return self.search_news_fallback(keyword, max_results)

    def search_news_api(self, keyword, max_results=100):
        """네이버 뉴스 API를 사용한 검색"""
        articles = []
        display = min(self.max_articles_per_request, 100)
        
        total_requests = (max_results + display - 1) // display
        
        for i in range(total_requests):
            start = i * display + 1
            current_display = min(display, max_results - len(articles))
            
            if current_display <= 0:
                break
            
            params = {
                'query': keyword,
                'display': current_display,
                'start': start,
                'sort': 'date'
            }
            
            headers = {
                'X-Naver-Client-Id': self.client_id,
                'X-Naver-Client-Secret': self.client_secret,
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            
            response = requests.get(self.base_url, params=params, headers=headers)
            
            if response.status_code == 200:
                data = response.json()
                items = data.get('items', [])
                
                for item in items:
                    article = {
                        'title': self.clean_html_tags(item['title']),
                        'link': item['link'],
                        'description': self.clean_html_tags(item['description']),
                        'pubDate': self.format_date(item['pubDate']),
                        'source': self.extract_source(item.get('link', ''))
                    }
                    articles.append(article)
                
                if len(items) < current_display:
                    break
                    
            else:
                raise Exception(f"API 요청 실패: {response.status_code}")
            
            time.sleep(self.request_delay)
        
        return articles[:max_results]

    def search_news_fallback(self, keyword, max_results=100):
        """API 키가 없는 경우 웹 크롤링으로 대체"""
        articles = []
        
        try:
            page_size = 10
            total_pages = (max_results + page_size - 1) // page_size
            
            for page_num in range(1, total_pages + 1):
                if len(articles) >= max_results:
                    break
                
                start = (page_num - 1) * page_size + 1
                search_url = f"https://search.naver.com/search.naver?where=news&query={quote(keyword)}&start={start}"
                
                try:
                    response = self.session.get(search_url, timeout=30)
                    response.raise_for_status()
                    
                    soup = BeautifulSoup(response.content, 'html.parser')
                    news_items = soup.find_all('div', class_='news_area')
                    
                    if not news_items:
                        break
                    
                    for item in news_items:
                        if len(articles) >= max_results:
                            break
                        
                        try:
                            title_element = item.find('a', class_='news_tit')
                            if not title_element:
                                continue
                            
                            title = title_element.get_text().strip()
                            link = title_element.get('href')
                            
                            desc_element = item.find('div', class_='news_dsc')
                            description = desc_element.get_text().strip() if desc_element else ''
                            
                            info_element = item.find('span', class_='info')
                            source = ''
                            pub_date = ''
                            
                            if info_element:
                                info_text = info_element.get_text()
                                parts = info_text.split('·')
                                if len(parts) >= 2:
                                    source = parts[0].strip()
                                    pub_date = parts[-1].strip()
                            
                            articles.append({
                                'title': title,
                                'link': link,
                                'description': description,
                                'pubDate': pub_date,
                                'source': source
                            })
                            
                        except Exception as e:
                            continue
                    
                    time.sleep(1)
                    
                except Exception as e:
                    st.warning(f"페이지 {page_num} 크롤링 중 오류: {e}")
                    continue
                
        except Exception as e:
            st.error(f"웹 크롤링 중 오류: {e}")
        
        return articles[:max_results]

    def clean_html_tags(self, text):
        """HTML 태그 제거"""
        if not text:
            return ""
        clean = re.compile('<.*?>')
        return re.sub(clean, '', text)

    def format_date(self, date_str):
        """날짜 포맷 변환"""
        try:
            from email.utils import parsedate_to_datetime
            dt = parsedate_to_datetime(date_str)
            return dt.strftime('%Y.%m.%d %H:%M')
        except:
            return date_str

    def extract_source(self, url):
        """URL에서 출처 추출"""
        try:
            if 'news.naver.com' in url:
                return '네이버뉴스'
            elif 'chosun.com' in url:
                return '조선일보'
            elif 'joongang.co.kr' in url:
                return '중앙일보'
            elif 'donga.com' in url:
                return '동아일보'
            elif 'hankyung.com' in url:
                return '한국경제'
            elif 'mk.co.kr' in url:
                return '매일경제'
            elif 'hani.co.kr' in url:
                return '한겨레'
            elif 'khan.co.kr' in url:
                return '경향신문'
            else:
                return '기타'
        except:
            return '알 수 없음'

    def search_stock_news(self, keywords, selected_date, max_articles):
        """특징주 관련 뉴스 검색"""
        try:
            all_results = []
            display = min(self.max_articles_per_request, 100)  # API 한 번 호출당 최대 100개
            
            # 각 키워드별로 동일한 수의 기사 검색
            articles_per_keyword = max_articles // len(keywords)
            
            # 각 키워드별로 검색
            for keyword in keywords:
                keyword_results = []
                total_requests = (articles_per_keyword + display - 1) // display
                
                for i in range(total_requests):
                    start = i * display + 1
                    current_display = min(display, articles_per_keyword - len(keyword_results))
                    
                    if current_display <= 0:
                        break
                    
                    # API 호출 파라미터 설정
                    params = {
                        "query": keyword,
                        "display": current_display,
                        "start": start,
                        "sort": "date"   # 최신순 정렬
                    }
                    
                    # API 호출
                    headers = {
                        'X-Naver-Client-Id': self.client_id,
                        'X-Naver-Client-Secret': self.client_secret
                    }
                    
                    response = requests.get(self.base_url, headers=headers, params=params)
                    response.raise_for_status()
                    
                    # 응답 파싱
                    data = response.json()
                    items = data.get("items", [])
                    
                    # 기사 정보 추출
                    for item in items:
                        # HTML 태그 제거
                        title = re.sub(r'<[^>]+>', '', item.get("title", ""))
                        description = re.sub(r'<[^>]+>', '', item.get("description", ""))
                        
                        # 발행일 파싱
                        pub_date = item.get("pubDate", "")
                        try:
                            pub_date = datetime.strptime(pub_date, "%a, %d %b %Y %H:%M:%S +0900")
                            
                            # 선택된 날짜와 일치하는 기사만 필터링
                            if pub_date.date() != selected_date:
                                continue
                            
                        except ValueError:
                            continue
                        
                        keyword_results.append({
                            "title": title,
                            "description": description,
                            "link": item.get("link", ""),
                            "pubDate": pub_date,
                            "keyword": keyword  # 키워드 정보 추가
                        })
                    
                    if len(items) < current_display:
                        break
                    
                    time.sleep(self.request_delay)  # API 호출 간격 조절
                
                # 각 키워드별 결과를 전체 결과에 추가
                all_results.extend(keyword_results[:articles_per_keyword])
            
            # 중복 제거 (제목 기준)
            seen_titles = set()
            unique_results = []
            for result in all_results:
                if result['title'] not in seen_titles:
                    seen_titles.add(result['title'])
                    unique_results.append(result)
            
            # 발행일 기준으로 정렬
            unique_results.sort(key=lambda x: x['pubDate'], reverse=True)
            
            return unique_results[:max_articles]  # 요청한 최대 개수만큼 반환
            
        except Exception as e:
            st.error(f"뉴스 검색 중 오류 발생: {str(e)}")
            return []

def display_stock_news_tab():
    """특징주 포착 탭 표시"""
    st.markdown("### 📈 특징주 포착")
    
    # 검색 키워드 선택
    default_keywords = ["특징주", "급등주", "상한가", "하한가", "급등세", "급락세", 
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
        "검색 키워드 선택(10개 이하)",
        options=default_keywords,
        default=default_keywords[:3]
    )
    
    # 조회 날짜 선택 (시장 데이터용)
    today = datetime.now()
    # 주말인 경우 금요일을 기본값으로
    if today.weekday() >= 5:  # 5: 토요일, 6: 일요일
        days_to_subtract = today.weekday() - 4
        today = today - timedelta(days=days_to_subtract)
    
    selected_date = st.date_input(
        "시장 데이터 조회 날짜",
        value=today,
        max_value=today,
        help="시장 데이터를 조회할 날짜를 선택하세요"
    )
    
    # 최대 기사 수 입력
    max_articles = st.number_input(
        "최대 기사 수(100개 이하)",
        min_value=10,
        max_value=1000,
        value=100,
        step=10
    )
    
    if st.button("🔍 검색 시작", type="primary"):
        with st.spinner("뉴스 검색 및 분석 중..."):
            # 1. 뉴스 검색 (날짜 제한 없음)
            searcher = NaverNewsSearcher()
            articles = searcher.search_stock_news(selected_keywords, selected_date, max_articles)
            
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
                    # app.py의 collect_market_data 함수를 import하여 사용
                    from app import collect_market_data
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
                            '주요제품': stock['주요제품'],
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