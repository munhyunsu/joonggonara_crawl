#!/usr/bin/env python
# -*- coding: utf-8 -*-





##### ##### ===== 포함 파일 =====
# 개인적인 아이디, 비밀번호 파일.
from personal.pconfig import LOGIN_ID, LOGIN_PW
# scrapy item 파일.
from ppomppu.items import PpomppuItem
# 로그인을 위한 FormRequest.
# 로그인 이후 크롤링을 위한 Request.
from scrapy.http import FormRequest, Request
# 게시판 페이지에서 각 게시글 url을 얻어온 후 url을 Spider에 넣어주기 위한 urljoin.
from urlparse import urljoin
# scrapy를 사용하기 위한 scrapy.
import scrapy
# response에서 ArticleNumber를 얻어내기위한 re.
import re
# file의 존재유무 체크를 위한 os.path
import os.path
# 랜덤 sleep을 위한 time, random
import time
import random
# Database를 위한 sqlite3
import sqlite3
# 휴대폰 번호 상호 수집을 위한 urllib
import urllib
##### ##### ===== 포함 파일 끝 =====





##### ##### ===== 전역 변수 지역 =====
RAWL_TARGET = 0
CRAWL_COUNT = 0
MAX_PAGE = 0
DOWNLOAD_DELAY = 1
conn = None
cur = None
##### ##### ===== 전역 변수 지역 끝 =====





##### ##### ===== 프로젝트별 변수 =====
# 주요 변수
SPIDER_NAME = 'kt'
START_URL = 'http://www.ppomppu.co.kr/index.php'
BOARD_PAGE_URL_HEAD = 'http://www.ppomppu.co.kr/zboard/zboard.php?id=market_phone&page='
BOARD_PAGE_URL_TAIL = '&category=3&divpage=196' #SKT-2, KT-3, LGT-5
ARTICLE_URL = 'http://www.ppomppu.co.kr/zboard/view.php?id=market_phone&no='

DATABASE_NAME = 'ppomppu.sqlite'
LIST_DB = 'list_kt'
DOWNLOADED_DB = 'downloaded_kt'
DOWNLOADED_PHONE_DB = 'downloaded_phone_kt'

# 임시 변수
TARGET_FILE = 'target_kt.txt'
MAX_FILE = 'max_kt.txt'
LOGIN_FILE = 'output/login_kt.html'
ARTICLE_AHREF = '//a[contains(@href, "view.php?id=market_phone") and not(contains(@href, "&&"))]/@href'
SAVE_LOCATION = 'output/kt/'
SAVE_LOCATION_PHONE = 'output_phone/kt/'
##### ##### ===== 프로젝트별 변수 끝 =====





##### ##### ===== 클래스 선언 지역 =====
##### ----- -----
##### 뽐뿌 스파이더 클래스
##### ----- -----
## ----- -----
class Spider(scrapy.Spider):
	name = SPIDER_NAME
	global CRAWL_TARGET
	global CRAWL_COUNT
	global MAX_PAGE
	global conn
	global cur

	# 딜레이 설정
	download_delay = DOWNLOAD_DELAY

	# 로그인을 하고 시작해야함
	# 따라서 로그인 페이지에서 시작
	start_urls = [
		START_URL
	]

	# 파일로부터 수집할 개수를 읽어옴
	# 이렇게 하는 것이 소스코드 수정 없이 수집양을 조절할 수 있음
	target_file = open(TARGET_FILE, 'r')
	CRAWL_TARGET = int(target_file.readline())
	target_file.close()

	max_file = open(MAX_FILE, 'r')
	MAX_PAGE = int(max_file.readline())
	max_file.close()



	# 로그인을 하는 함수
	def parse(self, response):
		# 로그인을 수정하기 위한 부분
		# 각 폼에 맞게 id와 pw를 입력
		# 이후의 쿠키는 scrapy가 알아서 관리해줌
		return scrapy.FormRequest.from_response(
			response,
			formname='zb_login',
			formdata={'user_id': LOGIN_ID, 'password': LOGIN_PW},
			clickdata={'nr': 0},
			callback=self.after_login
		)

	# 로그인이후 게시판 List에서 각 게시글 URL을 얻기위한 함수
	def after_login(self, response):
		# 글로벌 변수를 불러옴
		global CRAWL_TARGET
		global CRAWL_COUNT
		global MAX_PAGE
		global conn
		global cur

		# 로그인 디버깅 용
		with open(LOGIN_FILE, 'wb') as f:
			f.write(response.body)
		f.close()

		# Create Database Connector
		conn = sqlite3.connect(DATABASE_NAME)
		# Create Database Cursor
		cur = conn.cursor()

		# Create Table
		cur.executescript('''
			CREATE TABLE IF NOT EXISTS ''' + LIST_DB + ''' (
			article_num INTEGER PRIMARY KEY NOT NULL UNIQUE);
			''' +
			'''
			CREATE TABLE IF NOT EXISTS ''' + DOWNLOADED_DB + ''' (
			article_num INTEGER PRIMARY KEY NOT NULL UNIQUE);
			''' + 
			'''
			CREATE TABLE IF NOT EXISTS ''' + DOWNLOADED_PHONE_DB + ''' (
			article_num INTEGER PRIMARY KEY NOT NULL UNIQUE);
			'''
		)
		conn.commit()

		# 이전 수집때 목표로 저장해둔 리스트 수 불러오기
		cur.execute('''
			SELECT COUNT(*) FROM ''' + LIST_DB 
		)
		CRAWL_COUNT = CRAWL_COUNT + int(cur.fetchone()[0])

		# 로그인 성공 후 게시판에서 각 게시글의 URL을 따옴
		return Request(url=BOARD_PAGE_URL_HEAD + str(1) + BOARD_PAGE_URL_TAIL, callback=self.parse_list)



	# 수집한 게시판 정보에서 공지사항을 제외한 게시글 URL을 파싱
	def parse_list(self, response):
		# 글로벌 변수를 불러옴
		global CRAWL_TARGET
		global CRAWL_COUNT
		global MAX_PAGE
		global conn
		global cur

		# 사용자가 작성한 게시글 파악
		for ahref in response.xpath(ARTICLE_AHREF).extract():
			# 수집 목표량을 채웠을 경우 탈출
			if CRAWL_COUNT >= CRAWL_TARGET:
				break
			
			# 게시글 번호 파싱
			article_num = re.split(r'[?=&]', ahref)[10]
			# 이미 받은 게시글일 경우 패스
			cur.execute('SELECT * FROM ' + DOWNLOADED_DB + ' WHERE article_num = ' + str(article_num)
			)
			if cur.fetchone() is not None:
				print 'tartget skip: ' + str(article_num)
				continue
				
			# 다운로드 대상에 입력
			cur.execute('INSERT OR IGNORE INTO ' + LIST_DB + ' (article_num) VALUES ('	+ str(article_num) + ')'
			)
			conn.commit()
			CRAWL_COUNT = CRAWL_COUNT + 1

		# 목표 개수 만큼 리스트를 채웠는지 체크
		page_num = int(re.split(r'[?&=]', response.url)[4])
		if ((CRAWL_COUNT >= CRAWL_TARGET) or (page_num >= MAX_PAGE)):
			return self.crawl_article()
		else:
			# 목표 개수 미달인 경우 다음 페이지 불러오기
			next_url = BOARD_PAGE_URL_HEAD + str(page_num+1) + BOARD_PAGE_URL_TAIL
			return Request(url=next_url, callback=self.parse_list)

		

	# 게시글 수집
	def crawl_article(self):
		# 글로벌 변수를 불러옴
		global CRAWL_TARGET
		global CRAWL_COUNT
		global MAX_PAGE
		global conn
		global cur

		# 다운로드 대상 리스트 불러오기
		# 참고: yield로 Request를 전송하기 때문에 cur가 동시에 사용될 가능성이 있다
		# 	따라서 fetchall()로 데이터를 모두 가져와야 한다
		cur.execute('SELECT * FROM ' + LIST_DB)
		target_list = cur.fetchall()

		# Request 보내기
		for data in target_list:
			# request_url 조립
			article_num = data[0]
			request_url = ARTICLE_URL + str(article_num)

			# Request를 날리기 전 다운로드 대상 리스트에서 제거
			cur.execute('DELETE FROM ' + LIST_DB + ' WHERE article_num = ' + str(article_num)
			)
			conn.commit()

			# 랜덤 sleep
			time.sleep(random.randint(0, 1))
			
			# 요청 전송
			yield Request(request_url, callback = self.parse_article)


			
	# 각 게시글의 원본을 저장
	def parse_article(self, response):
		# 글로벌 변수를 불러옴.
		global CRAWL_TARGET
		global CRAWL_COUNT
		global MAX_PAGE
		global conn
		global cur

		# 수집한 게시글 다운로드 완료 리스트에 저장
		article_num = re.split(r'[?=&]', response.url)[4]
		cur.execute('INSERT OR IGNORE INTO ' + DOWNLOADED_DB + ' (article_num) VALUES (' + str(article_num) + ')'
		)
		conn.commit()

		# 수집한 게시글을 파일로 저장
		with open(SAVE_LOCATION + article_num + '.html', 'wb') as f:
			f.write(response.body)
		f.close()

		# 전화번호가 있을 경우 수집
		try:
			p1 = urllib.quote(re.split(r'[\'=]', response.xpath('//div[@id="market_phone_number"]')[0].extract())[4])
			p2 = urllib.quote(re.split(r'[\'=]', response.xpath('//div[@id="market_phone_number"]')[0].extract())[8])
			phone_url = 'http://www.ppomppu.co.kr/zboard/a_v_phone2.php?p1=' + p1 + '&p2=' + p2
			yield Request(url=phone_url, callback=lambda response, typeid=5: self.parse_phone(response, article_num))
		except:
			pass
		


	# 전화번호 수집.
	def parse_phone(self, response, article_num):
		# 글로벌 변수를 불러옴.
		global CRAWL_TARGET
		global CRAWL_COUNT
		global MAX_PAGE
		global conn
		global cur

		# 수집한 전화번호 게시글 전화번호 리스트에 저장
		cur.execute('INSERT OR IGNORE INTO ' + DOWNLOADED_PHONE_DB + ' (article_num) VALUES (' + str(article_num) + ')'
		)
		conn.commit()

		# 수집한 전화번호 게시글 파일로 저장
		with open(SAVE_LOCATION_PHONE + article_num + '.html', 'wb') as f:
			f.write(response.body)
		f.close()
##### ##### ===== 클래스 선언 지역 끝 =====
