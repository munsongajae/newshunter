import warnings
import logging
import concurrent.futures
import threading
from datetime import datetime
import requests
from bs4 import BeautifulSoup
import streamlit as st
import time
import re

# Streamlit 경고 숨기기
warnings.filterwarnings("ignore", message=".*missing ScriptRunContext.*")
logging.getLogger("streamlit").setLevel(logging.ERROR)

class NewsCollector:
    def __init__(self, headless=True):
        # 설정값 로드
        try:
            self.request_delay_min = st.secrets["app_settings"].get("request_delay_min", 0.5)
            self.request_delay_max = st.secrets["app_settings"].get("request_delay_max", 1.0)
            self.max_pages_per_newspaper = st.secrets["app_settings"].get("max_pages_per_newspaper", 10)
            self.max_workers = st.secrets["app_settings"].get("max_workers", 3)
        except:
            self.request_delay_min = 0.5
            self.request_delay_max = 1.0
            self.max_pages_per_newspaper = 10
            self.max_workers = 3

        # 세션 설정 - 더 빠른 설정
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'ko-KR,ko;q=0.9',
            'Connection': 'keep-alive'
        })
        
        # 연결 풀 설정으로 속도 향상
        adapter = requests.adapters.HTTPAdapter(
            pool_connections=10,
            pool_maxsize=20,
            max_retries=2
        )
        self.session.mount('http://', adapter)
        self.session.mount('https://', adapter)

    def crawl_paper_articles(self, oid, date, max_pages=None):
        """기존 app.py와 호환성을 위한 메서드"""
        return self.crawl_single_paper("", oid, date)

    def crawl_multiple_papers(self, paper_list, date):
        """여러 신문사를 병렬로 크롤링"""
        import pandas as pd
        
        all_articles = []
        
        # 결과 테이블을 위한 데이터
        results_data = []
        table_placeholder = st.empty()
        
        # 병렬 처리
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_paper = {
                executor.submit(self.crawl_single_paper_silent, paper_name, oid, date): (paper_name, oid)
                for paper_name, oid in paper_list
            }
            
            for future in concurrent.futures.as_completed(future_to_paper):
                paper_name, oid = future_to_paper[future]
                try:
                    articles = future.result(timeout=30)
                    for article in articles:
                        article['newspaper'] = paper_name
                    all_articles.extend(articles)
                    
                    results_data.append({
                        "신문사": paper_name,
                        "상태": "✅ 완료",
                        "수집 기사": f"{len(articles)}개"
                    })
                    
                except Exception as e:
                    results_data.append({
                        "신문사": paper_name,
                        "상태": "❌ 실패",
                        "수집 기사": "0개"
                    })
                
                # 테이블 업데이트
                if results_data:
                    df = pd.DataFrame(results_data)
                    with table_placeholder:
                        st.markdown("**📊 수집 현황**")
                        st.dataframe(df, use_container_width=True, hide_index=True)
        
        return all_articles

    def crawl_single_paper(self, paper_name, oid, date):
        """단일 신문사 크롤링 (병렬 처리용)"""
        articles = []
        
        try:
            base_url = f"https://news.naver.com/main/list.naver?mode=LPOD&mid=sec&oid={oid}&listType=paper&date={date}"
            
            # 첫 페이지만 빠르게 테스트
            response = self.session.get(base_url, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'lxml')
            
            # 신문 게재 기사 영역 확인
            main_content = soup.find('div', class_='list_body newsflash_body')
            if not main_content:
                return articles
            
            # 최대 10페이지까지 수집
            for page_num in range(1, self.max_pages_per_newspaper + 1):
                try:
                    if page_num > 1:
                        page_url = f"{base_url}&page={page_num}"
                        response = self.session.get(page_url, timeout=10)
                        response.raise_for_status()
                        soup = BeautifulSoup(response.content, 'lxml')
                        main_content = soup.find('div', class_='list_body newsflash_body')
                        if not main_content:
                            break
                    
                    page_articles = self.extract_articles_fast(main_content)
                    if not page_articles:
                        break
                    
                    articles.extend(page_articles)
                    
                    # 디버깅 정보 (신문사명이 있을 때만)
                    if paper_name:
                        st.info(f"{paper_name} 페이지 {page_num}: {len(page_articles)}개 기사 수집")
                    
                    # 짧은 지연
                    if page_num < self.max_pages_per_newspaper:
                        time.sleep(0.3)
                        
                except Exception as e:
                    if paper_name:
                        st.warning(f"{paper_name} 페이지 {page_num} 수집 중 오류: {str(e)}")
                    break
            
            # 최종 수집 결과
            if paper_name:
                st.success(f"{paper_name}: 총 {len(articles)}개 기사 수집 완료")
            
        except Exception as e:
            if paper_name:
                st.warning(f"{paper_name} 수집 중 오류: {str(e)}")
        
        return articles

    def crawl_single_paper_silent(self, paper_name, oid, date):
        """단일 신문사 크롤링 (Streamlit 호출 없는 버전)"""
        articles = []
        
        try:
            base_url = f"https://news.naver.com/main/list.naver?mode=LPOD&mid=sec&oid={oid}&listType=paper&date={date}"
            
            response = self.session.get(base_url, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'lxml')
            main_content = soup.find('div', class_='list_body newsflash_body')
            if not main_content:
                return articles
            
            for page_num in range(1, self.max_pages_per_newspaper + 1):
                try:
                    if page_num > 1:
                        page_url = f"{base_url}&page={page_num}"
                        response = self.session.get(page_url, timeout=10)
                        response.raise_for_status()
                        soup = BeautifulSoup(response.content, 'lxml')
                        main_content = soup.find('div', class_='list_body newsflash_body')
                        if not main_content:
                            break
                    
                    page_articles = self.extract_articles_fast(main_content)
                    if not page_articles:
                        break
                    
                    articles.extend(page_articles)
                    
                    if page_num < self.max_pages_per_newspaper:
                        time.sleep(0.3)
                        
                except Exception as e:
                    break
            
        except Exception as e:
            pass
        
        return articles

    def extract_articles_fast(self, main_content):
        """빠른 기사 추출 - 모든 구조 통합 처리"""
        articles = []
        
        try:
            # 모든 기사 링크를 한 번에 찾기
            article_links = main_content.find_all('a', href=lambda x: x and 'mnews/article' in x)
            
            for link in article_links:
                try:
                    href = link.get('href')
                    title = link.get_text().strip()
                    
                    if not href or not title or len(title) < 3:
                        continue
                    
                    # 절대 URL로 변환
                    if href.startswith('/'):
                        href = f"https://news.naver.com{href}"
                    
                    # 면 정보 추출 - 여러 위치에서 찾기
                    page_info = self.extract_page_info_comprehensive(link)
                    
                    # 중복 체크
                    if not any(article['url'] == href for article in articles):
                        articles.append({
                            'title': title,
                            'url': href,
                            'page': page_info,
                            'collected_at': datetime.now().isoformat()
                        })
                        
                except Exception:
                    continue
            
        except Exception as e:
            pass
        
        return articles

    def extract_page_info_comprehensive(self, link_element):
        """링크 주변에서 면 정보를 종합적으로 추출"""
        try:
            # 1. 같은 dt 안에서 찾기 (일반 기사)
            dt_parent = link_element.find_parent('dt')
            if dt_parent:
                newspaper_info = dt_parent.find('span', class_='newspaper_info')
                if newspaper_info:
                    info_text = newspaper_info.get_text()
                    page_match = re.search(r'([A-Z]?\d+면)', info_text)
                    if page_match:
                        return page_match.group(1)
            
            # 2. dl > dd 구조에서 찾기 (톱기사)
            dl_parent = link_element.find_parent('dl')
            if dl_parent:
                dd = dl_parent.find('dd')
                if dd:
                    newspaper_info = dd.find('span', class_='newspaper_info')
                    if newspaper_info:
                        info_text = newspaper_info.get_text()
                        page_match = re.search(r'([A-Z]?\d+면)', info_text)
                        if page_match:
                            return page_match.group(1)
            
            # 3. 상위 요소들에서 찾기 (기타 구조)
            current = link_element.parent
            for _ in range(3):  # 최대 3단계 부모까지
                if current:
                    newspaper_info = current.find('span', class_='newspaper_info')
                    if newspaper_info:
                        info_text = newspaper_info.get_text()
                        page_match = re.search(r'([A-Z]?\d+면)', info_text)
                        if page_match:
                            return page_match.group(1)
                    current = current.parent
                else:
                    break
            
            return ""
        except:
            return ""

    def close(self):
        """세션 종료"""
        try:
            self.session.close()
        except:
            pass

    def get_newspaper_categories(self):
        """신문사 카테고리 정보 반환"""
        return {
            "경제신문": {
                "매일경제": "009",
                "머니투데이": "008", 
                "서울경제": "011",
                "이데일리": "018",
                "파이낸셜뉴스": "014",
                "한국경제": "015"
            },
            "종합일간지": {
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
            },
            "석간신문": {
                "문화일보": "021",
                "헤럴드경제": "016", 
                "아시아경제": "277"
            }
        }
