# -*- coding: utf-8 -*-
# TMDB API wrapper - WITH ALL DISCOVER METHODS AND BASIC LISTS FIXED
import requests
import time
import hashlib
import json
import xbmc
from datetime import datetime, timedelta
from lib.utils import log, cache_get, cache_set

class TMDB:
    def __init__(self, addon):
        self.api_key = addon.getSetting('tmdb_api_key') or "9567cc1179d493c3b22f0682dbdf2e42"
        self.addon = addon
        self.base_url = "https://api.themoviedb.org/3"
        self.image_url = "https://image.tmdb.org/t/p/"

        # Get language from settings
        self.language = addon.getSetting('tmdb_language')
        if not self.language or self.language == '':
            self.language = 'en-US'

        log(f"🎯 TMDB using language: {self.language}")

        self.session = requests.Session()
        self.session.headers.update({
            'Accept': 'application/json',
            'Content-Type': 'application/json'
        })

    def _get(self, endpoint, params=None, language_override=None):
        """Make TMDB API request with caching and PROPER LANGUAGE HANDLING"""
        if params is None:
            params = {}

        lang = language_override if language_override else self.language
        params['language'] = lang
        params['api_key'] = self.api_key
        params['include_image_language'] = f"{lang.split('-')[0]},en,null"

        param_str = json.dumps(params, sort_keys=True)
        cache_key = f"tmdb_{endpoint}_{hashlib.md5(param_str.encode()).hexdigest()}"

        cached = cache_get(cache_key, ttl=86400)
        if cached:
            log(f"📦 Cache hit: {endpoint} ({lang})")
            return cached

        try:
            url = f"{self.base_url}/{endpoint}"
            log(f"🌐 TMDB request: {url} | language={lang}")

            response = self.session.get(url, params=params, timeout=10)

            if response.status_code == 200:
                data = response.json()
                cache_set(cache_key, data)
                return data
            elif response.status_code == 429:
                log(f"⏳ TMDB rate limit hit, waiting...")
                time.sleep(2)
                return self._get(endpoint, params, language_override)
            else:
                log(f"❌ TMDB error {response.status_code}: {endpoint}")

        except Exception as e:
            log(f"❌ TMDB exception: {str(e)}")

        return None

    # ===== MOVIE DETAILS =====

    def get_movie_details(self, tmdb_id):
        """Get movie details with credits - IN USER'S LANGUAGE"""
        return self._get(f"movie/{tmdb_id}", {
            'append_to_response': 'credits,release_dates,videos,translations,keywords'
        })

    def search_movie(self, query):
        """Search for movies - RESULTS IN USER'S LANGUAGE"""
        log(f"🔍 Searching movies: {query} in {self.language}")
        data = self._get("search/movie", {
            'query': query,
            'include_adult': False
        })
        if data and 'results' in data:
            log(f"📊 Found {len(data['results'])} movie results")
            return data['results']
        return []

    # ===== TV DETAILS =====

    def get_tv_details(self, tmdb_id):
        """Get TV show details - IN USER'S LANGUAGE"""
        return self._get(f"tv/{tmdb_id}", {
            'append_to_response': 'credits,content_ratings,translations,keywords'
        })

    def get_tv_season(self, tmdb_id, season_num):
        """Get TV season details - IN USER'S LANGUAGE"""
        return self._get(f"tv/{tmdb_id}/season/{season_num}")

    def get_episode_details(self, tmdb_id, season_num, episode_num):
        """Get TV episode details - IN USER'S LANGUAGE"""
        return self._get(f"tv/{tmdb_id}/season/{season_num}/episode/{episode_num}")

    def search_tv(self, query):
        """Search for TV shows - RESULTS IN USER'S LANGUAGE"""
        log(f"🔍 Searching TV: {query} in {self.language}")
        data = self._get("search/tv", {
            'query': query,
            'include_adult': False
        })
        if data and 'results' in data:
            log(f"📊 Found {len(data['results'])} TV results")
            return data['results']
        return []

    # ===== BASIC LISTS - THESE WERE MISSING! =====

    def get_popular_movies(self):
        """Get popular movies"""
        data = self._get("movie/popular")
        return data.get('results', []) if data else []

    def get_top_rated_movies(self):
        """Get top rated movies"""
        data = self._get("movie/top_rated")
        return data.get('results', []) if data else []

    def get_popular_tv(self):
        """Get popular TV shows - THIS WAS MISSING!"""
        data = self._get("tv/popular")
        return data.get('results', []) if data else []

    def get_top_rated_tv(self):
        """Get top rated TV shows - THIS WAS MISSING!"""
        data = self._get("tv/top_rated")
        return data.get('results', []) if data else []

    def get_now_playing(self):
        """Now playing in theaters"""
        data = self._get("movie/now_playing")
        return data.get('results', []) if data else []

    def get_upcoming(self):
        """Upcoming movies"""
        data = self._get("movie/upcoming")
        return data.get('results', []) if data else []

    def get_list(self, list_type):
        """Get TMDB list by type - BACKWARD COMPATIBILITY"""
        if list_type == 'popular_movies':
            return self.get_popular_movies()
        elif list_type == 'top_rated_movies':
            return self.get_top_rated_movies()
        elif list_type == 'popular_tv':
            return self.get_popular_tv()
        elif list_type == 'top_rated_tv':
            return self.get_top_rated_tv()
        return []

    # ===== DISCOVER - ALL METHODS YOUR ADDON.PY CALLS =====

    def trending_week(self):
        """Trending this week"""
        data = self._get("trending/movie/week")
        return data.get('results', []) if data else []

    def trending_day(self):
        """Trending today"""
        data = self._get("trending/movie/day")
        return data.get('results', []) if data else []

    def now_playing(self):
        """Now playing"""
        data = self._get("movie/now_playing")
        return data.get('results', []) if data else []

    def upcoming(self):
        """Upcoming movies"""
        data = self._get("movie/upcoming")
        return data.get('results', []) if data else []

    # ===== GENRES =====
    def action_movies(self):
        data = self._get("discover/movie", {'with_genres': '28', 'sort_by': 'popularity.desc', 'vote_count.gte': 100})
        return data.get('results', []) if data else []

    def adventure_movies(self):
        data = self._get("discover/movie", {'with_genres': '12', 'sort_by': 'popularity.desc', 'vote_count.gte': 100})
        return data.get('results', []) if data else []

    def action_adventure(self):
        data = self._get("discover/movie", {'with_genres': '28,12', 'sort_by': 'popularity.desc', 'vote_count.gte': 100})
        return data.get('results', []) if data else []

    def comedy_movies(self):
        data = self._get("discover/movie", {'with_genres': '35', 'sort_by': 'popularity.desc', 'vote_count.gte': 100})
        return data.get('results', []) if data else []

    def drama_movies(self):
        data = self._get("discover/movie", {'with_genres': '18', 'sort_by': 'popularity.desc', 'vote_count.gte': 100})
        return data.get('results', []) if data else []

    def comedy_drama(self):
        data = self._get("discover/movie", {'with_genres': '35,18', 'sort_by': 'popularity.desc', 'vote_count.gte': 100})
        return data.get('results', []) if data else []

    def thriller_movies(self):
        data = self._get("discover/movie", {'with_genres': '53', 'sort_by': 'popularity.desc', 'vote_count.gte': 100})
        return data.get('results', []) if data else []

    def horror_movies(self):
        data = self._get("discover/movie", {'with_genres': '27', 'sort_by': 'popularity.desc', 'vote_count.gte': 100})
        return data.get('results', []) if data else []

    def thriller_horror(self):
        data = self._get("discover/movie", {'with_genres': '53,27', 'sort_by': 'popularity.desc', 'vote_count.gte': 100})
        return data.get('results', []) if data else []

    def sci_fi_movies(self):
        data = self._get("discover/movie", {'with_genres': '878', 'sort_by': 'popularity.desc', 'vote_count.gte': 100})
        return data.get('results', []) if data else []

    def fantasy_movies(self):
        data = self._get("discover/movie", {'with_genres': '14', 'sort_by': 'popularity.desc', 'vote_count.gte': 100})
        return data.get('results', []) if data else []

    def sci_fi_fantasy(self):
        data = self._get("discover/movie", {'with_genres': '878,14', 'sort_by': 'popularity.desc', 'vote_count.gte': 100})
        return data.get('results', []) if data else []

    def romance_movies(self):
        data = self._get("discover/movie", {'with_genres': '10749', 'sort_by': 'popularity.desc', 'vote_count.gte': 100})
        return data.get('results', []) if data else []

    def family_movies(self):
        data = self._get("discover/movie", {'with_genres': '10751', 'sort_by': 'popularity.desc', 'vote_count.gte': 100})
        return data.get('results', []) if data else []

    def animation_movies(self):
        data = self._get("discover/movie", {'with_genres': '16', 'sort_by': 'popularity.desc', 'vote_count.gte': 100})
        return data.get('results', []) if data else []

    def family_animation(self):
        data = self._get("discover/movie", {'with_genres': '10751,16', 'sort_by': 'popularity.desc', 'vote_count.gte': 100})
        return data.get('results', []) if data else []

    def documentary_movies(self):
        data = self._get("discover/movie", {'with_genres': '99', 'sort_by': 'popularity.desc', 'vote_count.gte': 50})
        return data.get('results', []) if data else []

    def war_movies(self):
        data = self._get("discover/movie", {'with_genres': '10752', 'sort_by': 'popularity.desc', 'vote_count.gte': 100})
        return data.get('results', []) if data else []

    def history_movies(self):
        data = self._get("discover/movie", {'with_genres': '36', 'sort_by': 'popularity.desc', 'vote_count.gte': 100})
        return data.get('results', []) if data else []

    def war_history(self):
        data = self._get("discover/movie", {'with_genres': '10752,36', 'sort_by': 'popularity.desc', 'vote_count.gte': 100})
        return data.get('results', []) if data else []

    def crime_movies(self):
        data = self._get("discover/movie", {'with_genres': '80', 'sort_by': 'popularity.desc', 'vote_count.gte': 100})
        return data.get('results', []) if data else []

    def mystery_movies(self):
        data = self._get("discover/movie", {'with_genres': '9648', 'sort_by': 'popularity.desc', 'vote_count.gte': 100})
        return data.get('results', []) if data else []

    # ===== YUGOSLAV / EX-YU REGION =====
    # Serbian, Croatian, Bosnian, Montenegrin - ADDED ABOVE CZECH SECTION
    
    def serbian_movies(self):
        """Serbian movies"""
        data = self._get("discover/movie", {
            'with_original_language': 'sr',
            'sort_by': 'popularity.desc',
            'vote_count.gte': 5
        })
        return data.get('results', []) if data else []
    
    def serbian_tv(self):
        """Serbian TV shows"""
        data = self._get("discover/tv", {
            'with_original_language': 'sr',
            'sort_by': 'popularity.desc',
            'vote_count.gte': 5
        })
        return data.get('results', []) if data else []
    
    def croatian_movies(self):
        """Croatian movies"""
        data = self._get("discover/movie", {
            'with_original_language': 'hr',
            'sort_by': 'popularity.desc',
            'vote_count.gte': 5
        })
        return data.get('results', []) if data else []
    
    def croatian_tv(self):
        """Croatian TV shows"""
        data = self._get("discover/tv", {
            'with_original_language': 'hr',
            'sort_by': 'popularity.desc',
            'vote_count.gte': 5
        })
        return data.get('results', []) if data else []
    
    def bosnian_movies(self):
        """Bosnian movies"""
        data = self._get("discover/movie", {
            'with_original_language': 'bs',
            'sort_by': 'popularity.desc',
            'vote_count.gte': 5
        })
        return data.get('results', []) if data else []
    
    def bosnian_tv(self):
        """Bosnian TV shows"""
        data = self._get("discover/tv", {
            'with_original_language': 'bs',
            'sort_by': 'popularity.desc',
            'vote_count.gte': 5
        })
        return data.get('results', []) if data else []
    
    def montenegrin_movies(self):
        """Montenegrin movies (using Serbian as base)"""
        data = self._get("discover/movie", {
            'with_original_language': 'sr',
            'with_keywords': 'montenegro|cn-me',  # Placeholder - adjust if needed
            'sort_by': 'popularity.desc',
            'vote_count.gte': 5
        })
        return data.get('results', []) if data else []
    
    def montenegrin_tv(self):
        """Montenegrin TV shows (using Serbian as base)"""
        data = self._get("discover/tv", {
            'with_original_language': 'sr',
            'with_keywords': 'montenegro|cn-me',
            'sort_by': 'popularity.desc',
            'vote_count.gte': 5
        })
        return data.get('results', []) if data else []
    
    # ===== COMBINED REGIONAL LISTS =====
    
    def ex_yu_movies_all(self):
        """All movies from ex-Yugoslavia (Sr, Hr, Bs)"""
        data = self._get("discover/movie", {
            'with_original_language': 'sr|hr|bs',
            'sort_by': 'popularity.desc',
            'vote_count.gte': 5
        })
        return data.get('results', []) if data else []
    
    def ex_yu_tv_all(self):
        """All TV from ex-Yugoslavia (Sr, Hr, Bs)"""
        data = self._get("discover/tv", {
            'with_original_language': 'sr|hr|bs',
            'sort_by': 'popularity.desc',
            'vote_count.gte': 5
        })
        return data.get('results', []) if data else []
    
    def yugoslav_classics(self):
        """Classic Yugoslav films (pre-1992)"""
        data = self._get("discover/movie", {
            'with_original_language': 'sh|sr|hr|bs',  # sh = Serbo-Croatian
            'primary_release_date.lte': '1991-12-31',
            'sort_by': 'vote_average.desc',
            'vote_count.gte': 10
        })
        return data.get('results', []) if data else []
    
    def yugoslav_tv_classics(self):
        """Classic Yugoslav TV shows (pre-1992)"""
        data = self._get("discover/tv", {
            'with_original_language': 'sh|sr|hr|bs',
            'first_air_date.lte': '1991-12-31',
            'sort_by': 'vote_average.desc',
            'vote_count.gte': 5
        })
        return data.get('results', []) if data else []
    
    def yugoslav_westerns(self):
        """Partisan films / Yugoslav Westerns"""
        data = self._get("discover/movie", {
            'with_original_language': 'sh|sr|hr|bs',
            'with_keywords': 'partisan|western|war',
            'sort_by': 'popularity.desc',
            'vote_count.gte': 10
        })
        return data.get('results', []) if data else []
    
    def regional_recent_movies(self):
        """Recent films from region (last 5 years)"""
        current_year = datetime.now().year
        data = self._get("discover/movie", {
            'with_original_language': 'sr|hr|bs',
            'primary_release_date.gte': f"{current_year-5}-01-01",
            'sort_by': 'release_date.desc',
            'vote_count.gte': 5
        })
        return data.get('results', []) if data else []
    
    def regional_recent_tv(self):
        """Recent TV from region (last 5 years)"""
        current_year = datetime.now().year
        data = self._get("discover/tv", {
            'with_original_language': 'sr|hr|bs',
            'first_air_date.gte': f"{current_year-5}-01-01",
            'sort_by': 'first_air_date.desc',
            'vote_count.gte': 5
        })
        return data.get('results', []) if data else []
    
    def regional_popular_movies(self):
        """Currently popular in region"""
        data = self._get("discover/movie", {
            'with_original_language': 'sr|hr|bs',
            'sort_by': 'popularity.desc',
            'vote_count.gte': 5
        })
        return data.get('results', []) if data else []
    
    def regional_popular_tv(self):
        """Currently popular TV in region"""
        data = self._get("discover/tv", {
            'with_original_language': 'sr|hr|bs',
            'sort_by': 'popularity.desc',
            'vote_count.gte': 5
        })
        return data.get('results', []) if data else []
    
    # ===== SPECIFIC REGIONAL COLLECTIONS =====
    
    def partisan_films(self):
        """Partisan film classics"""
        data = self._get("discover/movie", {
            'with_original_language': 'sh|sr|hr|bs',
            'with_keywords': 'partisan|156871',  # partisan keyword ID
            'sort_by': 'vote_average.desc',
            'vote_count.gte': 10
        })
        return data.get('results', []) if data else []
    
    def pula_film_festival(self):
        """Films from Pula Film Festival"""
        data = self._get("discover/movie", {
            'with_original_language': 'hr|sr|bs',
            'sort_by': 'vote_average.desc',
            'vote_count.gte': 5
        })
        return data.get('results', []) if data else []
    
    def sarajevo_film_festival(self):
        """Films from Sarajevo Film Festival"""
        data = self._get("discover/movie", {
            'with_original_language': 'bs|hr|sr',
            'sort_by': 'vote_average.desc',
            'vote_count.gte': 5
        })
        return data.get('results', []) if data else []

    # ===== CZECH & REGIONAL =====
    def czech_movies(self):
        """Czech movies"""
        data = self._get("discover/movie", {
            'with_original_language': 'cs',
            'sort_by': 'popularity.desc',
            'vote_count.gte': 10
        })
        return data.get('results', []) if data else []

    def czech_tv(self):
        """Czech TV shows"""
        data = self._get("discover/tv", {
            'with_original_language': 'cs',
            'sort_by': 'popularity.desc',
            'vote_count.gte': 5
        })
        return data.get('results', []) if data else []

    def czech_recent(self):
        """Recent Czech movies"""
        current_year = datetime.now().year
        data = self._get("discover/movie", {
            'with_original_language': 'cs',
            'primary_release_date.gte': f"{current_year-5}-01-01",
            'sort_by': 'release_date.desc',
            'vote_count.gte': 5
        })
        return data.get('results', []) if data else []

    def czechoslovak_classics(self):
        """Czechoslovak classics"""
        data = self._get("discover/movie", {
            'with_original_language': 'cs',
            'primary_release_date.lte': '1992-12-31',
            'sort_by': 'vote_average.desc',
            'vote_count.gte': 20
        })
        return data.get('results', []) if data else []

    def slovak_movies(self):
        """Slovak movies"""
        data = self._get("discover/movie", {
            'with_original_language': 'sk',
            'sort_by': 'popularity.desc'
        })
        return data.get('results', []) if data else []

    def slovak_tv(self):
        """Slovak TV shows"""
        data = self._get("discover/tv", {
            'with_original_language': 'sk',
            'sort_by': 'popularity.desc'
        })
        return data.get('results', []) if data else []

    # ===== STUDIOS =====
    def marvel_movies(self):
        data = self._get("discover/movie", {'with_companies': '420', 'sort_by': 'release_date.desc'})
        return data.get('results', []) if data else []

    def dc_movies(self):
        data = self._get("discover/movie", {'with_companies': '429,174', 'sort_by': 'release_date.desc'})
        return data.get('results', []) if data else []

    def disney_movies(self):
        data = self._get("discover/movie", {'with_companies': '2', 'sort_by': 'release_date.desc'})
        return data.get('results', []) if data else []

    def netflix_movies(self):
        data = self._get("discover/movie", {'with_companies': '213850', 'sort_by': 'release_date.desc'})
        return data.get('results', []) if data else []

    def hbo_movies(self):
        data = self._get("discover/movie", {'with_companies': '174,3186,19507', 'sort_by': 'release_date.desc'})
        return data.get('results', []) if data else []

    def amazon_movies(self):
        data = self._get("discover/movie", {'with_companies': '102395,102396', 'sort_by': 'release_date.desc'})
        return data.get('results', []) if data else []

    def apple_movies(self):
        data = self._get("discover/movie", {'with_companies': '175525', 'sort_by': 'release_date.desc'})
        return data.get('results', []) if data else []

    def paramount_movies(self):
        data = self._get("discover/movie", {'with_companies': '4', 'sort_by': 'release_date.desc'})
        return data.get('results', []) if data else []

    def universal_movies(self):
        data = self._get("discover/movie", {'with_companies': '33', 'sort_by': 'release_date.desc'})
        return data.get('results', []) if data else []

    def warner_movies(self):
        data = self._get("discover/movie", {'with_companies': '174', 'sort_by': 'release_date.desc'})
        return data.get('results', []) if data else []

    def sony_movies(self):
        data = self._get("discover/movie", {'with_companies': '34', 'sort_by': 'release_date.desc'})
        return data.get('results', []) if data else []

    # ===== DECADES =====
    def _80s_movies(self):
        data = self._get("discover/movie", {
            'primary_release_date.gte': '1980-01-01',
            'primary_release_date.lte': '1989-12-31',
            'sort_by': 'popularity.desc',
            'vote_count.gte': 100
        })
        return data.get('results', []) if data else []

    def _90s_movies(self):
        data = self._get("discover/movie", {
            'primary_release_date.gte': '1990-01-01',
            'primary_release_date.lte': '1999-12-31',
            'sort_by': 'popularity.desc',
            'vote_count.gte': 100
        })
        return data.get('results', []) if data else []

    def _00s_movies(self):
        data = self._get("discover/movie", {
            'primary_release_date.gte': '2000-01-01',
            'primary_release_date.lte': '2009-12-31',
            'sort_by': 'popularity.desc',
            'vote_count.gte': 100
        })
        return data.get('results', []) if data else []

    def _2010s_movies(self):
        data = self._get("discover/movie", {
            'primary_release_date.gte': '2010-01-01',
            'primary_release_date.lte': '2019-12-31',
            'sort_by': 'popularity.desc',
            'vote_count.gte': 100
        })
        return data.get('results', []) if data else []

    def _2020s_movies(self):
        data = self._get("discover/movie", {
            'primary_release_date.gte': '2020-01-01',
            'sort_by': 'popularity.desc',
            'vote_count.gte': 50
        })
        return data.get('results', []) if data else []

    # ===== SMART MIXES =====
    def cult_classics(self):
        data = self._get("discover/movie", {
            'with_keywords': '972',
            'sort_by': 'popularity.desc',
            'vote_count.gte': 50
        })
        return data.get('results', []) if data else []

    def feel_good_movies(self):
        data = self._get("discover/movie", {
            'with_genres': '35,10751,18',
            'without_genres': '53,27,80',
            'vote_average.gte': 6.5,
            'sort_by': 'popularity.desc',
            'vote_count.gte': 100
        })
        return data.get('results', []) if data else []

    def date_night_movies(self):
        data = self._get("discover/movie", {
            'with_genres': '10749,35,18',
            'vote_average.gte': 6.0,
            'sort_by': 'popularity.desc',
            'vote_count.gte': 100
        })
        return data.get('results', []) if data else []

    def weekend_binge(self):
        data = self._get("discover/movie", {
            'with_genres': '28,12,878,53',
            'vote_average.gte': 6.5,
            'sort_by': 'popularity.desc',
            'vote_count.gte': 100
        })
        return data.get('results', []) if data else []

    # ===== RECENT =====
    def this_month(self):
        thirty_days_ago = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
        data = self._get("discover/movie", {
            'primary_release_date.gte': thirty_days_ago,
            'sort_by': 'popularity.desc',
            'vote_count.gte': 10
        })
        return data.get('results', []) if data else []

    def last_3_months(self):
        ninety_days_ago = (datetime.now() - timedelta(days=90)).strftime('%Y-%m-%d')
        data = self._get("discover/movie", {
            'primary_release_date.gte': ninety_days_ago,
            'sort_by': 'popularity.desc',
            'vote_count.gte': 20
        })
        return data.get('results', []) if data else []

    def this_year(self):
        current_year = datetime.now().year
        data = self._get("discover/movie", {
            'primary_release_date.gte': f"{current_year}-01-01",
            'sort_by': 'popularity.desc',
            'vote_count.gte': 20
        })
        return data.get('results', []) if data else []

    # ===== IMAGE HELPERS =====
    def get_image_url(self, path, size='original'):
        if not path:
            return ''
        return f"{self.image_url}{size}{path}"

    def get_poster(self, path, size='w500'):
        return self.get_image_url(path, size)

    def get_backdrop(self, path, size='original'):
        return self.get_image_url(path, size)

    def get_still(self, path, size='w500'):
        return self.get_image_url(path, size)

    # ===== LOCALIZED TITLES =====
    def get_movie_localized_titles(self, tmdb_id):
        """Get movie titles in Czech, Croatian, Serbian"""
        titles = {
            'english': None,
            'czech': None,
            'croatian': None,
            'serbian': None,
            'original': None
        }

        try:
            en_data = self._get(f"movie/{tmdb_id}", {'language': 'en-US'})
            if en_data:
                titles['english'] = en_data.get('title')
                titles['original'] = en_data.get('original_title')

            cz_data = self._get(f"movie/{tmdb_id}", {'language': 'cs-CZ'})
            if cz_data and cz_data.get('title'):
                cz_title = cz_data.get('title')
                if cz_title != titles['english']:
                    titles['czech'] = cz_title

            hr_data = self._get(f"movie/{tmdb_id}", {'language': 'hr-HR'})
            if hr_data and hr_data.get('title'):
                hr_title = hr_data.get('title')
                if hr_title != titles['english']:
                    titles['croatian'] = hr_title

            sr_data = self._get(f"movie/{tmdb_id}", {'language': 'sr-RS'})
            if sr_data and sr_data.get('title'):
                sr_title = sr_data.get('title')
                if sr_title != titles['english']:
                    titles['serbian'] = sr_title

            if not titles['czech']:
                titles['czech'] = titles['english']
            if not titles['croatian']:
                titles['croatian'] = titles['english']
            if not titles['serbian']:
                titles['serbian'] = titles['english']

        except Exception as e:
            log(f"Error getting localized titles: {str(e)}")
            titles['czech'] = titles.get('english', '')
            titles['croatian'] = titles.get('english', '')
            titles['serbian'] = titles.get('english', '')

        return titles

    def get_tv_localized_titles(self, tmdb_id):
        """Get TV show titles in Czech, Croatian, Serbian"""
        titles = {
            'english': None,
            'czech': None,
            'croatian': None,
            'serbian': None,
            'original': None
        }

        try:
            en_data = self._get(f"tv/{tmdb_id}", {'language': 'en-US'})
            if en_data:
                titles['english'] = en_data.get('name')
                titles['original'] = en_data.get('original_name')

            cz_data = self._get(f"tv/{tmdb_id}", {'language': 'cs-CZ'})
            if cz_data and cz_data.get('name'):
                cz_title = cz_data.get('name')
                if cz_title != titles['english']:
                    titles['czech'] = cz_title

            hr_data = self._get(f"tv/{tmdb_id}", {'language': 'hr-HR'})
            if hr_data and hr_data.get('name'):
                hr_title = hr_data.get('name')
                if hr_title != titles['english']:
                    titles['croatian'] = hr_title

            sr_data = self._get(f"tv/{tmdb_id}", {'language': 'sr-RS'})
            if sr_data and sr_data.get('name'):
                sr_title = sr_data.get('name')
                if sr_title != titles['english']:
                    titles['serbian'] = sr_title

            if not titles['czech']:
                titles['czech'] = titles['english']
            if not titles['croatian']:
                titles['croatian'] = titles['english']
            if not titles['serbian']:
                titles['serbian'] = titles['english']

        except Exception as e:
            log(f"Error getting localized titles: {str(e)}")
            titles['czech'] = titles.get('english', '')
            titles['croatian'] = titles.get('english', '')
            titles['serbian'] = titles.get('english', '')

        return titles

    def get_title_in_current_language(self, tmdb_id, media_type='movie'):
        """Get title in user's current language setting"""
        try:
            if media_type == 'movie':
                data = self._get(f"movie/{tmdb_id}")
                if data:
                    return data.get('title')
            else:
                data = self._get(f"tv/{tmdb_id}")
                if data:
                    return data.get('name')
        except Exception as e:
            log(f"Error getting title in current language: {str(e)}")
        return None

    # ===== DYNAMIC SUGGESTIONS (added by dynamic suggestions feature) =====
    def _dynamic_call(self, params, page=1, region='US'):
        params = dict(params)
        params['page'] = page
        params['region'] = region
        data = self._get('discover/movie', params)
        return data.get('results', []) if data else []

    def _decade_bounds(self):
        """Return (start_year, end_year) for a random decade 1970s-2020s."""
        import random
        decades = [(1970,1979),(1980,1989),(1990,1999),(2000,2009),(2010,2019),(2020,2029)]
        return random.choice(decades)

    def _random_genre(self):
        import random
        # 28=Action,12=Adventure,16=Animation,35=Comedy,80=Crime,99=Documentary,
        # 18=Drama,10751=Family,14=Fantasy,36=History,27=Horror,10749=Romance,
        # 878=Sci-Fi,53=Thriller,10752=War,9648=Mystery
        return random.choice(['28','12','16','35','80','99','18','10751','14','36','27','10749','878','53','10752','9648'])

    def discover_hidden_gems(self, page=1):
        """High rating, low-ish vote count, random decade. Different every visit."""
        start, end = self._decade_bounds()
        return self._dynamic_call({
            'sort_by': 'vote_average.desc',
            'vote_average.gte': 7.5,
            'vote_count.gte': 500,
            'vote_count.lte': 5000,
            'primary_release_date.gte': f'{start}-01-01',
            'primary_release_date.lte': f'{end}-12-31'
        })

    def discover_fresh_acclaimed(self, page=1):
        """Last 12 months, rating >= 6.5."""
        from datetime import datetime, timedelta
        cutoff = (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d')
        return self._dynamic_call({
            'primary_release_date.gte': cutoff,
            'sort_by': 'vote_average.desc',
            'vote_average.gte': 6.5,
            'vote_count.gte': 100
        })

    def discover_surprise_me(self, page=1):
        """Random genre x random sort order. Always different."""
        import random
        sort_by = random.choice(['popularity.desc', 'vote_average.desc', 'revenue.desc'])
        return self._dynamic_call({
            'with_genres': self._random_genre(),
            'sort_by': sort_by,
            'vote_count.gte': 200,
            'vote_average.gte': 6.0
        })

    def discover_quick_watch(self, page=1):
        """Under 90 minutes, watchable rating."""
        return self._dynamic_call({
            'with_runtime.lte': 90,
            'sort_by': 'popularity.desc',
            'vote_average.gte': 6.0,
            'vote_count.gte': 100
        })

    def discover_decade(self, start, end):
        """Top-rated from a specific decade."""
        return self._dynamic_call({
            'primary_release_date.gte': f'{start}-01-01',
            'primary_release_date.lte': f'{end}-12-31',
            'sort_by': 'vote_average.desc',
            'vote_count.gte': 1000
        })

    def discover_underrated(self, page=1):
        """Rating 6.0-7.5 — good but underseen."""
        return self._dynamic_call({
            'sort_by': 'vote_average.desc',
            'vote_average.gte': 6.0,
            'vote_average.lte': 7.5,
            'vote_count.gte': 200,
            'vote_count.lte': 3000
        })

    def discover_critically_acclaimed(self, page=1):
        """Rating >= 8.0."""
        return self._dynamic_call({
            'sort_by': 'vote_average.desc',
            'vote_average.gte': 8.0,
            'vote_count.gte': 2000
        })

    def discover_feel_good_short(self, page=1):
        """Comedy/Family/Romance, under 2h, positive rating."""
        return self._dynamic_call({
            'with_genres': '35,10751,10749',
            'without_genres': '53,27,80',
            'with_runtime.lte': 120,
            'vote_average.gte': 6.5,
            'sort_by': 'popularity.desc',
            'vote_count.gte': 200
        })

    def discover_mind_benders(self, page=1):
        """Mystery/Thriller/Sci-Fi, high rating."""
        return self._dynamic_call({
            'with_genres': '9648,53,878',
            'vote_average.gte': 7.0,
            'sort_by': 'vote_average.desc',
            'vote_count.gte': 300
        })

    def discover_foreign_gems(self, page=1):
        """Non-English, rating >= 7.5."""
        return self._dynamic_call({
            'without_original_language': 'en',
            'vote_average.gte': 7.5,
            'vote_count.gte': 500,
            'sort_by': 'vote_average.desc'
        })

    def discover_random_page(self):
        """Popular movies, random page 1-20 — different set each visit."""
        import random
        page = random.randint(1, 20)
        return self._dynamic_call({
            'sort_by': 'popularity.desc',
            'vote_count.gte': 500
        }, page=page)
