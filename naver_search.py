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