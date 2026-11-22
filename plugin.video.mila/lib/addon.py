# -*- coding: utf-8 -*-
# Core addon class and router
import sys
import re
import xbmc
import xbmcaddon
import xbmcgui
import xbmcplugin
from urllib.parse import parse_qsl

from lib.utils import log
from lib.tmdb import TMDB
from lib.websharder import WebSharder
from lib.gui import GUI
from lib.streaming import StreamSelector
from lib.history import HistoryManager


class MILA:
    def __init__(self):
        self.addon = xbmcaddon.Addon()
        self.addon_id = self.addon.getAddonInfo('id')
        self.handle = int(sys.argv[1])
        self.url = sys.argv[0]

        self.tmdb = TMDB(self.addon)
        self.websharder = WebSharder()
        self.gui = GUI(self)
        self.stream_selector = StreamSelector(self.addon, self.websharder)
        self.history = HistoryManager()

    def get_url(self, **kwargs):
        from urllib.parse import urlencode
        return self.url + '?' + urlencode(kwargs)

    def router(self, paramstring):
        params = dict(parse_qsl(paramstring))
        action = params.get('action', 'main_menu')
        log(f"Routing: {action}")

        if action == 'main_menu':
            self.main_menu()
        elif action == 'discover_menu':
            self.discover_menu()
        elif action == 'discover_trending':
            self.show_discover_list('trending_week', self.gui._get_string('trending_week'))
        elif action == 'discover_trending_day':
            self.show_discover_list('trending_day', self.gui._get_string('trending_day'))
        elif action == 'discover_now_playing':
            self.show_discover_list('now_playing', self.gui._get_string('now_playing'))
        elif action == 'discover_upcoming':
            self.show_discover_list('upcoming', self.gui._get_string('upcoming'))
        elif action == 'genres_menu':
            self.genres_menu()
        elif action == 'genre_action':
            self.show_discover_list('action_movies', self.gui._get_string('action'))
        elif action == 'genre_adventure':
            self.show_discover_list('adventure_movies', self.gui._get_string('adventure'))
        elif action == 'genre_action_adventure':
            self.show_discover_list('action_adventure', self.gui._get_string('action_adventure'))
        elif action == 'genre_comedy':
            self.show_discover_list('comedy_movies', self.gui._get_string('comedy'))
        elif action == 'genre_drama':
            self.show_discover_list('drama_movies', self.gui._get_string('drama'))
        elif action == 'genre_comedy_drama':
            self.show_discover_list('comedy_drama', self.gui._get_string('comedy_drama'))
        elif action == 'genre_thriller':
            self.show_discover_list('thriller_movies', self.gui._get_string('thriller'))
        elif action == 'genre_horror':
            self.show_discover_list('horror_movies', self.gui._get_string('horror'))
        elif action == 'genre_thriller_horror':
            self.show_discover_list('thriller_horror', self.gui._get_string('thriller_horror'))
        elif action == 'genre_scifi':
            self.show_discover_list('sci_fi_movies', self.gui._get_string('sci_fi'))
        elif action == 'genre_fantasy':
            self.show_discover_list('fantasy_movies', self.gui._get_string('fantasy'))
        elif action == 'genre_scifi_fantasy':
            self.show_discover_list('sci_fi_fantasy', self.gui._get_string('sci_fi_fantasy'))
        elif action == 'genre_romance':
            self.show_discover_list('romance_movies', self.gui._get_string('romance'))
        elif action == 'genre_family':
            self.show_discover_list('family_movies', self.gui._get_string('family'))
        elif action == 'genre_animation':
            self.show_discover_list('animation_movies', self.gui._get_string('animation'))
        elif action == 'genre_family_animation':
            self.show_discover_list('family_animation', self.gui._get_string('family_animation'))
        elif action == 'genre_documentary':
            self.show_discover_list('documentary_movies', self.gui._get_string('documentary'))
        elif action == 'genre_war':
            self.show_discover_list('war_movies', self.gui._get_string('war'))
        elif action == 'genre_history':
            self.show_discover_list('history_movies', self.gui._get_string('history'))
        elif action == 'genre_war_history':
            self.show_discover_list('war_history', self.gui._get_string('war_history'))
        elif action == 'genre_crime':
            self.show_discover_list('crime_movies', self.gui._get_string('crime'))
        elif action == 'genre_mystery':
            self.show_discover_list('mystery_movies', self.gui._get_string('mystery'))
        elif action == 'yugoslav_menu':
            self.yugoslav_menu()
        elif action == 'yugoslav_movies_all':
            self.show_discover_list('ex_yu_movies_all', self.gui._get_string('yugoslav_movies_all'))
        elif action == 'yugoslav_tv_all':
            self.show_discover_list('ex_yu_tv_all', self.gui._get_string('yugoslav_tv_all'))
        elif action == 'yugoslav_classics':
            self.show_discover_list('yugoslav_classics', self.gui._get_string('yugoslav_classics'))
        elif action == 'yugoslav_tv_classics':
            self.show_discover_list('yugoslav_tv_classics', self.gui._get_string('yugoslav_tv_classics'))
        elif action == 'yugoslav_westerns':
            self.show_discover_list('yugoslav_westerns', self.gui._get_string('yugoslav_westerns'))
        elif action == 'serbian_movies':
            self.show_discover_list('serbian_movies', self.gui._get_string('serbian_movies'))
        elif action == 'serbian_tv':
            self.show_discover_list('serbian_tv', self.gui._get_string('serbian_tv'))
        elif action == 'croatian_movies':
            self.show_discover_list('croatian_movies', self.gui._get_string('croatian_movies'))
        elif action == 'croatian_tv':
            self.show_discover_list('croatian_tv', self.gui._get_string('croatian_tv'))
        elif action == 'bosnian_movies':
            self.show_discover_list('bosnian_movies', self.gui._get_string('bosnian_movies'))
        elif action == 'bosnian_tv':
            self.show_discover_list('bosnian_tv', self.gui._get_string('bosnian_tv'))
        elif action == 'montenegrin_movies':
            self.show_discover_list('montenegrin_movies', self.gui._get_string('montenegrin_movies'))
        elif action == 'montenegrin_tv':
            self.show_discover_list('montenegrin_tv', self.gui._get_string('montenegrin_tv'))
        elif action == 'regional_recent_movies':
            self.show_discover_list('regional_recent_movies', self.gui._get_string('regional_recent_movies'))
        elif action == 'regional_recent_tv':
            self.show_discover_list('regional_recent_tv', self.gui._get_string('regional_recent_tv'))
        elif action == 'partisan_films':
            self.show_discover_list('partisan_films', self.gui._get_string('partisan_films'))
        elif action == 'pula_film_festival':
            self.show_discover_list('pula_film_festival', self.gui._get_string('pula_film_festival'))
        elif action == 'sarajevo_film_festival':
            self.show_discover_list('sarajevo_film_festival', self.gui._get_string('sarajevo_film_festival'))
        elif action == 'czech_menu':
            self.czech_menu()
        elif action == 'czech_movies':
            self.show_discover_list('czech_movies', self.gui._get_string('czech_movies'))
        elif action == 'czech_recent':
            self.show_discover_list('czech_recent', self.gui._get_string('czech_recent'))
        elif action == 'czechoslovak_classics':
            self.show_discover_list('czechoslovak_classics', self.gui._get_string('czechoslovak_classics'))
        elif action == 'slovak_movies':
            self.show_discover_list('slovak_movies', self.gui._get_string('slovak_movies'))
        elif action == 'czech_tv':
            self.show_discover_list('czech_tv', self.gui._get_string('czech_movies') + ' TV')
        elif action == 'slovak_tv':
            self.show_discover_list('slovak_tv', self.gui._get_string('slovak_movies') + ' TV')
        elif action == 'studios_menu':
            self.studios_menu()
        elif action == 'studio_marvel':
            self.show_discover_list('marvel_movies', self.gui._get_string('marvel'))
        elif action == 'studio_dc':
            self.show_discover_list('dc_movies', self.gui._get_string('dc'))
        elif action == 'studio_disney':
            self.show_discover_list('disney_movies', self.gui._get_string('disney'))
        elif action == 'studio_netflix':
            self.show_discover_list('netflix_movies', self.gui._get_string('netflix'))
        elif action == 'studio_hbo':
            self.show_discover_list('hbo_movies', self.gui._get_string('hbo'))
        elif action == 'studio_amazon':
            self.show_discover_list('amazon_movies', self.gui._get_string('amazon'))
        elif action == 'studio_apple':
            self.show_discover_list('apple_movies', self.gui._get_string('apple'))
        elif action == 'studio_paramount':
            self.show_discover_list('paramount_movies', self.gui._get_string('paramount'))
        elif action == 'studio_universal':
            self.show_discover_list('universal_movies', self.gui._get_string('universal'))
        elif action == 'studio_warner':
            self.show_discover_list('warner_movies', self.gui._get_string('warner'))
        elif action == 'studio_sony':
            self.show_discover_list('sony_movies', self.gui._get_string('sony'))
        elif action == 'decades_menu':
            self.decades_menu()
        elif action == 'decade_80s':
            self.show_discover_list('_80s_movies', self.gui._get_string('decade_80s'))
        elif action == 'decade_90s':
            self.show_discover_list('_90s_movies', self.gui._get_string('decade_90s'))
        elif action == 'decade_00s':
            self.show_discover_list('_00s_movies', self.gui._get_string('decade_00s'))
        elif action == 'decade_2010s':
            self.show_discover_list('_2010s_movies', self.gui._get_string('decade_2010s'))
        elif action == 'decade_2020s':
            self.show_discover_list('_2020s_movies', self.gui._get_string('decade_2020s'))
        elif action == 'smart_mixes_menu':
            self.smart_mixes_menu()
        elif action == 'smart_cult_classics':
            self.show_discover_list('cult_classics', self.gui._get_string('cult_classics'))
        elif action == 'smart_feel_good':
            self.show_discover_list('feel_good_movies', self.gui._get_string('feel_good'))
        elif action == 'smart_date_night':
            self.show_discover_list('date_night_movies', self.gui._get_string('date_night'))
        elif action == 'smart_weekend_binge':
            self.show_discover_list('weekend_binge', self.gui._get_string('weekend_binge'))
        elif action == 'recent_menu':
            self.recent_menu()
        elif action == 'recent_month':
            self.show_discover_list('this_month', self.gui._get_string('this_month'))
        elif action == 'recent_3months':
            self.show_discover_list('last_3_months', self.gui._get_string('last_3_months'))
        elif action == 'recent_year':
            self.show_discover_list('this_year', self.gui._get_string('this_year'))
        elif action == 'search_history':
            self.show_search_history()
        elif action == 'watch_history':
            self.show_watch_history()
        elif action == 'clear_search_history':
            self.history.clear_search_history()
            xbmc.executebuiltin('Container.Refresh')
        elif action == 'clear_watch_history':
            self.history.clear_watch_history()
            xbmc.executebuiltin('Container.Refresh')
        elif action == 'remove_watch_item':
            index = params.get('index')
            if index:
                self.history.remove_from_watch_history(int(index))
        elif action == 'remove_watch_items':
            indices_str = params.get('indices', '')
            if indices_str:
                try:
                    indices = sorted([int(i) for i in indices_str.split(',') if i.strip()], reverse=True)
                    for idx in indices:
                        self.history.remove_from_watch_history(idx)
                    xbmc.executebuiltin('Container.Refresh')
                except Exception as e:
                    log(f"Error removing watch items: {e}")
        elif action == 'remove_search_item':
            query = params.get('query')
            if query:
                self.history.remove_search_item(query)
                xbmc.executebuiltin('Container.Refresh')
        elif action == 'search_from_history':
            query = params.get('query')
            if query:
                self.show_search_results(query)
        elif action == 'search':
            self.search_menu()
        elif action == 'search_results':
            query = params.get('query', '')
            self.show_search_results(query)
        elif action == 'manual_webshare_search':
            self.manual_webshare_search()
        elif action == 'play_manual_webshare':
            ident = params.get('ident', '')
            filename = params.get('filename', '')
            self.play_manual_webshare(ident, filename)
        elif action == 'dynamic_menu':
            self.dynamic_menu()
        elif action == 'dynamic_hidden_gems':
            self.show_dynamic_list('discover_hidden_gems', 'Hidden Gems')
        elif action == 'dynamic_surprise_me':
            self.show_dynamic_list('discover_surprise_me', 'Surprise Me')
        elif action == 'dynamic_browse_all':
            self.show_dynamic_browse_all()
        elif action == 'dynamic_list':
            _m = params.get('method', '')
            _n = params.get('name', 'Results')
            _p = int(params.get('page', '1'))
            self.show_dynamic_list(_m, _n, page=_p)
        elif action == 'dynamic_browse_all_page':
            _p2 = int(params.get('page', '1'))
            self.show_dynamic_browse_all(page=_p2)
        elif action == 'manual_webshare_search_prefill':
            _q = params.get('query', '')
            self.manual_webshare_search(prefill_query=_q)
        elif action == 'tv_popular':
            self.show_tv_popular()
        elif action == 'tv_top_rated':
            self.show_tv_top_rated()
        elif action == 'tv_show':
            tmdb_id = params.get('tmdb_id')
            self.show_tv_show_seasons(tmdb_id)
        elif action == 'tv_season':
            tmdb_id = params.get('tmdb_id')
            season = params.get('season')
            self.show_tv_season_episodes(tmdb_id, season)
        elif action == 'movie_popular':
            self.show_movie_popular()
        elif action == 'movie_top_rated':
            self.show_movie_top_rated()
        elif action == 'play_movie':
            tmdb_id = params.get('tmdb_id')
            title = params.get('title')
            year = params.get('year')
            stream_id = params.get('stream_id')
            movie_details = self.tmdb.get_movie_details(tmdb_id) if tmdb_id else None
            self.stream_selector.play_movie(
                tmdb_id=tmdb_id, title=title, year=year, stream_id=stream_id,
                handle=self.handle, movie_details=movie_details
            )
        elif action == 'play_episode':
            tmdb_id = params.get('tmdb_id')
            show_title = params.get('show_title')
            season = params.get('season')
            episode = params.get('episode')
            episode_title = params.get('episode_title', '')
            stream_id = params.get('stream_id')
            episode_details = self.tmdb.get_episode_details(tmdb_id, season, episode) if tmdb_id else None
            show_details = self.tmdb.get_tv_details(tmdb_id) if tmdb_id else None
            self.stream_selector.play_episode(
                tmdb_id=tmdb_id, show_title=show_title, season=season, episode=episode,
                episode_title=episode_title, stream_id=stream_id, handle=self.handle,
                episode_details=episode_details, show_details=show_details
            )
        elif action == 'select_stream_manual':
            tmdb_id = params.get('tmdb_id')
            content_type = params.get('content_type')
            title = params.get('title')
            year = params.get('year', '')
            season = params.get('season', '')
            episode = params.get('episode', '')
            handle = params.get('handle')
            clean_handle = None
            if handle:
                clean_handle = re.sub(r'[^\d-]', '', handle)
            self.stream_selector.manual_select(
                tmdb_id=tmdb_id, content_type=content_type, title=title,
                year=year, season=season, episode=episode, handle=clean_handle
            )
        elif action == 'clear_subtitles':
            from lib.opensubtitles import OpenSubtitles
            os = OpenSubtitles()
            os.clear_cache()
            xbmc.executebuiltin('Container.Refresh')
        else:
            self.main_menu()

    def main_menu(self):
        xbmcplugin.setPluginCategory(self.handle, 'MILA')
        xbmcplugin.setContent(self.handle, 'files')

        self.gui.add_item(
            label=f'[B][COLOR yellow]{self.gui._get_string("search")}[/COLOR][/B]',
            url=self.get_url(action='search'),
            is_folder=True
        )

        if self.addon.getSetting('enable_manual_webshare_search') == 'true':
            self.gui.add_item(
                label='[COLOR orange][B]Manual WebShare Search[/B][/COLOR]',
                url=self.get_url(action='manual_webshare_search'),
                is_folder=True
            )

        self.gui.add_item(label=self.gui._get_string('search_history'), url=self.get_url(action='search_history'), is_folder=True)
        self.gui.add_item(label=self.gui._get_string('watch_history'), url=self.get_url(action='watch_history'), is_folder=True)
        self.gui.add_item(label='[B][COLOR gold]Dynamic Picks[/COLOR][/B]', url=self.get_url(action='dynamic_menu'), is_folder=True)
        self.gui.add_item(label=f'[B]{self.gui._get_string("popular_movies")}[/B]', url=self.get_url(action='movie_popular'), is_folder=True)
        self.gui.add_item(label=f'[B]{self.gui._get_string("top_rated_movies")}[/B]', url=self.get_url(action='movie_top_rated'), is_folder=True)
        self.gui.add_item(label=f'[B]{self.gui._get_string("popular_tv")}[/B]', url=self.get_url(action='tv_popular'), is_folder=True)
        self.gui.add_item(label=f'[B]{self.gui._get_string("top_rated_tv")}[/B]', url=self.get_url(action='tv_top_rated'), is_folder=True)
        self.gui.add_item(label=self.gui._get_string('trending_now'), url=self.get_url(action='discover_menu'), is_folder=True)
        self.gui.add_item(label=self.gui._get_string('genres'), url=self.get_url(action='genres_menu'), is_folder=True)
        self.gui.add_item(label=self.gui._get_string('yugoslav_region'), url=self.get_url(action='yugoslav_menu'), is_folder=True)
        self.gui.add_item(label=self.gui._get_string('czech_slovak'), url=self.get_url(action='czech_menu'), is_folder=True)
        self.gui.add_item(label=self.gui._get_string('studios'), url=self.get_url(action='studios_menu'), is_folder=True)
        self.gui.add_item(label=self.gui._get_string('decades'), url=self.get_url(action='decades_menu'), is_folder=True)
        self.gui.add_item(label=self.gui._get_string('smart_mixes'), url=self.get_url(action='smart_mixes_menu'), is_folder=True)
        self.gui.add_item(label=self.gui._get_string('recent_releases'), url=self.get_url(action='recent_menu'), is_folder=True)

        xbmcplugin.endOfDirectory(self.handle)

    def show_movie_popular(self):
        xbmcplugin.setPluginCategory(self.handle, self.gui._get_string('popular_movies'))
        xbmcplugin.setContent(self.handle, 'movies')
        try:
            items = self.tmdb.get_popular_movies()
        except Exception as e:
            log(f"Error: {e}")
            items = []
        if not items:
            self.gui.add_item(label='[COLOR grey]No movies found[/COLOR]', url='', is_folder=False)
        else:
            for item in items:
                self.gui.add_movie_item(item)
        xbmcplugin.endOfDirectory(self.handle)

    def show_movie_top_rated(self):
        xbmcplugin.setPluginCategory(self.handle, self.gui._get_string('top_rated_movies'))
        xbmcplugin.setContent(self.handle, 'movies')
        try:
            items = self.tmdb.get_top_rated_movies()
        except Exception as e:
            log(f"Error: {e}")
            items = []
        if not items:
            self.gui.add_item(label='[COLOR grey]No movies found[/COLOR]', url='', is_folder=False)
        else:
            for item in items:
                self.gui.add_movie_item(item)
        xbmcplugin.endOfDirectory(self.handle)

    def show_tv_popular(self):
        xbmcplugin.setPluginCategory(self.handle, self.gui._get_string('popular_tv'))
        xbmcplugin.setContent(self.handle, 'tvshows')
        try:
            items = self.tmdb.get_popular_tv()
        except Exception as e:
            log(f"Error: {e}")
            items = []
        if not items:
            self.gui.add_item(label='[COLOR grey]No TV shows found[/COLOR]', url='', is_folder=False)
        else:
            for item in items:
                self.gui.add_tvshow_item(item)
        xbmcplugin.endOfDirectory(self.handle)

    def show_tv_top_rated(self):
        xbmcplugin.setPluginCategory(self.handle, self.gui._get_string('top_rated_tv'))
        xbmcplugin.setContent(self.handle, 'tvshows')
        try:
            items = self.tmdb.get_top_rated_tv()
        except Exception as e:
            log(f"Error: {e}")
            items = []
        if not items:
            self.gui.add_item(label='[COLOR grey]No TV shows found[/COLOR]', url='', is_folder=False)
        else:
            for item in items:
                self.gui.add_tvshow_item(item)
        xbmcplugin.endOfDirectory(self.handle)

    def show_discover_list(self, discover_method, list_name):
        xbmcplugin.setPluginCategory(self.handle, list_name)
        is_tv = any(k in discover_method for k in ['_tv', 'tv_all', 'tv_classics', 'serbian_tv', 'croatian_tv', 'bosnian_tv', 'montenegrin_tv', 'regional_recent_tv'])
        xbmcplugin.setContent(self.handle, 'tvshows' if is_tv else 'movies')
        try:
            items = getattr(self.tmdb, discover_method)()
        except Exception as e:
            log(f"Error in {discover_method}: {e}")
            items = []
        if not items:
            self.gui.add_item(label='[COLOR grey]No items found[/COLOR]', url='', is_folder=False)
        else:
            for item in items:
                if is_tv:
                    self.gui.add_tvshow_item(item)
                else:
                    self.gui.add_movie_item(item)
        xbmcplugin.endOfDirectory(self.handle)

    def discover_menu(self):
        xbmcplugin.setPluginCategory(self.handle, self.gui._get_string('trending_now'))
        xbmcplugin.setContent(self.handle, 'files')
        self.gui.add_item(label=self.gui._get_string('trending_week'), url=self.get_url(action='discover_trending'), is_folder=True)
        self.gui.add_item(label=self.gui._get_string('trending_day'), url=self.get_url(action='discover_trending_day'), is_folder=True)
        self.gui.add_item(label=self.gui._get_string('now_playing'), url=self.get_url(action='discover_now_playing'), is_folder=True)
        self.gui.add_item(label=self.gui._get_string('upcoming'), url=self.get_url(action='discover_upcoming'), is_folder=True)
        xbmcplugin.endOfDirectory(self.handle)

    def genres_menu(self):
        xbmcplugin.setPluginCategory(self.handle, self.gui._get_string('genres'))
        xbmcplugin.setContent(self.handle, 'files')
        for label_key, action_key in [
            ('action', 'action'), ('adventure', 'adventure'), ('action_adventure', 'action_adventure'),
            ('comedy', 'comedy'), ('drama', 'drama'), ('comedy_drama', 'comedy_drama'),
            ('thriller', 'thriller'), ('horror', 'horror'), ('thriller_horror', 'thriller_horror'),
            ('sci_fi', 'scifi'), ('fantasy', 'fantasy'), ('sci_fi_fantasy', 'scifi_fantasy'),
            ('romance', 'romance'), ('family', 'family'), ('animation', 'animation'),
            ('family_animation', 'family_animation'), ('documentary', 'documentary'),
            ('war', 'war'), ('history', 'history'), ('war_history', 'war_history'),
            ('crime', 'crime'), ('mystery', 'mystery'),
        ]:
            self.gui.add_item(label=self.gui._get_string(label_key), url=self.get_url(action=f'genre_{action_key}'), is_folder=True)
        xbmcplugin.endOfDirectory(self.handle)

    def yugoslav_menu(self):
        xbmcplugin.setPluginCategory(self.handle, self.gui._get_string('yugoslav_region'))
        xbmcplugin.setContent(self.handle, 'files')
        for label_key, action_key in [
            ('yugoslav_movies_all', 'yugoslav_movies_all'), ('yugoslav_tv_all', 'yugoslav_tv_all'),
            ('serbian_movies', 'serbian_movies'), ('serbian_tv', 'serbian_tv'),
            ('croatian_movies', 'croatian_movies'), ('croatian_tv', 'croatian_tv'),
            ('bosnian_movies', 'bosnian_movies'), ('bosnian_tv', 'bosnian_tv'),
            ('montenegrin_movies', 'montenegrin_movies'), ('montenegrin_tv', 'montenegrin_tv'),
            ('yugoslav_classics', 'yugoslav_classics'), ('yugoslav_tv_classics', 'yugoslav_tv_classics'),
            ('yugoslav_westerns', 'yugoslav_westerns'), ('partisan_films', 'partisan_films'),
            ('regional_recent_movies', 'regional_recent_movies'), ('regional_recent_tv', 'regional_recent_tv'),
            ('pula_film_festival', 'pula_film_festival'), ('sarajevo_film_festival', 'sarajevo_film_festival'),
        ]:
            self.gui.add_item(label=self.gui._get_string(label_key), url=self.get_url(action=action_key), is_folder=True)
        xbmcplugin.endOfDirectory(self.handle)

    def czech_menu(self):
        xbmcplugin.setPluginCategory(self.handle, self.gui._get_string('czech_slovak'))
        xbmcplugin.setContent(self.handle, 'files')
        self.gui.add_item(label=self.gui._get_string('czech_movies'), url=self.get_url(action='czech_movies'), is_folder=True)
        self.gui.add_item(label=self.gui._get_string('czech_movies') + ' TV', url=self.get_url(action='czech_tv'), is_folder=True)
        self.gui.add_item(label=self.gui._get_string('czech_recent'), url=self.get_url(action='czech_recent'), is_folder=True)
        self.gui.add_item(label=self.gui._get_string('czechoslovak_classics'), url=self.get_url(action='czechoslovak_classics'), is_folder=True)
        self.gui.add_item(label=self.gui._get_string('slovak_movies'), url=self.get_url(action='slovak_movies'), is_folder=True)
        self.gui.add_item(label=self.gui._get_string('slovak_movies') + ' TV', url=self.get_url(action='slovak_tv'), is_folder=True)
        xbmcplugin.endOfDirectory(self.handle)

    def studios_menu(self):
        xbmcplugin.setPluginCategory(self.handle, self.gui._get_string('studios'))
        xbmcplugin.setContent(self.handle, 'files')
        for label_key, action_key in [
            ('marvel', 'studio_marvel'), ('dc', 'studio_dc'), ('disney', 'studio_disney'),
            ('netflix', 'studio_netflix'), ('hbo', 'studio_hbo'), ('amazon', 'studio_amazon'),
            ('apple', 'studio_apple'), ('paramount', 'studio_paramount'), ('universal', 'studio_universal'),
            ('warner', 'studio_warner'), ('sony', 'studio_sony'),
        ]:
            self.gui.add_item(label=self.gui._get_string(label_key), url=self.get_url(action=action_key), is_folder=True)
        xbmcplugin.endOfDirectory(self.handle)

    def decades_menu(self):
        xbmcplugin.setPluginCategory(self.handle, self.gui._get_string('decades'))
        xbmcplugin.setContent(self.handle, 'files')
        for label_key, action_key in [
            ('decade_80s', 'decade_80s'), ('decade_90s', 'decade_90s'),
            ('decade_00s', 'decade_00s'), ('decade_2010s', 'decade_2010s'), ('decade_2020s', 'decade_2020s'),
        ]:
            self.gui.add_item(label=self.gui._get_string(label_key), url=self.get_url(action=action_key), is_folder=True)
        xbmcplugin.endOfDirectory(self.handle)

    def smart_mixes_menu(self):
        xbmcplugin.setPluginCategory(self.handle, self.gui._get_string('smart_mixes'))
        xbmcplugin.setContent(self.handle, 'files')
        self.gui.add_item(label=self.gui._get_string('cult_classics'), url=self.get_url(action='smart_cult_classics'), is_folder=True)
        self.gui.add_item(label=self.gui._get_string('feel_good'), url=self.get_url(action='smart_feel_good'), is_folder=True)
        self.gui.add_item(label=self.gui._get_string('date_night'), url=self.get_url(action='smart_date_night'), is_folder=True)
        self.gui.add_item(label=self.gui._get_string('weekend_binge'), url=self.get_url(action='smart_weekend_binge'), is_folder=True)
        xbmcplugin.endOfDirectory(self.handle)

    def recent_menu(self):
        xbmcplugin.setPluginCategory(self.handle, self.gui._get_string('recent_releases'))
        xbmcplugin.setContent(self.handle, 'files')
        self.gui.add_item(label=self.gui._get_string('this_month'), url=self.get_url(action='recent_month'), is_folder=True)
        self.gui.add_item(label=self.gui._get_string('last_3_months'), url=self.get_url(action='recent_3months'), is_folder=True)
        self.gui.add_item(label=self.gui._get_string('this_year'), url=self.get_url(action='recent_year'), is_folder=True)
        xbmcplugin.endOfDirectory(self.handle)

    def show_tv_show_seasons(self, tmdb_id):
        show = self.tmdb.get_tv_details(tmdb_id)
        if not show:
            return
        xbmcplugin.setPluginCategory(self.handle, show.get('name', 'TV Show'))
        xbmcplugin.setContent(self.handle, 'seasons')
        for season in show.get('seasons', []):
            if season.get('season_number', 0) == 0:
                continue
            self.gui.add_season_item(show, season)
        xbmcplugin.endOfDirectory(self.handle)

    def show_tv_season_episodes(self, tmdb_id, season_num):
        show = self.tmdb.get_tv_details(tmdb_id)
        if not show:
            return
        season = self.tmdb.get_tv_season(tmdb_id, season_num)
        if not season:
            return
        show_title = show.get('name', '')
        xbmcplugin.setPluginCategory(self.handle, f'{show_title} - {self.gui._get_string("season")} {season_num}')
        xbmcplugin.setContent(self.handle, 'episodes')
        for episode in season.get('episodes', []):
            self.gui.add_episode_item(show, season, episode)
        xbmcplugin.endOfDirectory(self.handle)

    def show_search_history(self):
        xbmcplugin.setPluginCategory(self.handle, self.gui._get_string('search_history'))
        xbmcplugin.setContent(self.handle, 'files')
        history = self.history.get_search_history()
        if not history:
            self.gui.add_item(label=f'[COLOR grey]{self.gui._get_string("no_search_history")}[/COLOR]', url='', is_folder=False)
        else:
            for item in history:
                query = item.get('query', '')
                context_menu = [
                    (self.gui._get_string('remove_from_history'), f'RunPlugin({self.get_url(action="remove_search_item", query=query)})'),
                    (self.gui._get_string('clear_all'), f'RunPlugin({self.get_url(action="clear_search_history")})'),
                ]
                self.gui.add_item(
                    label=f'[COLOR white]{query}[/COLOR]',
                    url=self.get_url(action='search_results', query=query),
                    is_folder=True,
                    context_menu=context_menu
                )
            self.gui.add_item(label=f'[COLOR red]{self.gui._get_string("clear_all")}[/COLOR]', url=self.get_url(action='clear_search_history'), is_folder=False)
        xbmcplugin.endOfDirectory(self.handle)

    def show_watch_history(self):
        xbmcplugin.setPluginCategory(self.handle, self.gui._get_string('watch_history'))
        xbmcplugin.setContent(self.handle, 'videos')
        history = self.history.get_watch_history()
        if not history:
            self.gui.add_item(label=f'[COLOR grey]{self.gui._get_string("no_watch_history")}[/COLOR]', url='', is_folder=False)
            xbmcplugin.endOfDirectory(self.handle)
            return
        group_episodes = self.addon.getSetting('group_episodes_in_history') == 'true'
        if group_episodes:
            grouped = []
            show_groups = {}
            for index, item in enumerate(history):
                if item.get('type') == 'movie':
                    grouped.append({'kind': 'movie', 'item': item, 'index': index})
                else:
                    key = str(item.get('tmdb_id', '') or item.get('show_title', ''))
                    if key not in show_groups:
                        g = {
                            'kind': 'show',
                            'tmdb_id': item.get('tmdb_id'),
                            'show_title': item.get('show_title', 'Unknown'),
                            'poster': item.get('poster', ''),
                            'last': item,
                            'indices': [index]
                        }
                        show_groups[key] = g
                        grouped.append(g)
                    else:
                        show_groups[key]['indices'].append(index)
            for entry in grouped:
                if entry['kind'] == 'movie':
                    item = entry['item']
                    title = item.get('title', 'Unknown')
                    year = item.get('year', '')
                    tmdb_id = item.get('tmdb_id')
                    label = f'[COLOR gold]{title}[/COLOR]'
                    if year:
                        label += f' [COLOR grey]({year})[/COLOR]'
                    url = self.get_url(action='play_movie', tmdb_id=tmdb_id, title=title, year=year)
                    art = {'icon': 'DefaultMovies.png'}
                    if item.get('poster'):
                        art['thumb'] = f"https://image.tmdb.org/t/p/w185{item['poster']}"
                    cm = []
                    if tmdb_id:
                        cm.append((
                            self.gui._get_string('select_stream'),
                            f"RunPlugin({self.get_url(action='select_stream_manual', content_type='movie', tmdb_id=tmdb_id, title=title, year=year, handle=self.handle)})"
                        ))
                    else:
                        cm.append((
                            "Re-search on WebShare",
                            f"RunPlugin({self.get_url(action='manual_webshare_search_prefill', query=title)})"
                        ))
                    cm.append((
                        self.gui._get_string('remove_from_history'),
                        f'RunPlugin({self.get_url(action="remove_watch_item", index=entry["index"])})'
                    ))
                    self.gui.add_item(label=label, url=url, is_folder=False, art=art, context_menu=cm)
                else:
                    show_title = entry['show_title']
                    tmdb_id = entry['tmdb_id']
                    last = entry['last']
                    season = last.get('season', 0)
                    episode = last.get('episode', 0)
                    label = f'[COLOR cyan]{show_title}[/COLOR]'
                    if season and episode:
                        label += f' [COLOR grey]- Last: S{int(season):02d}E{int(episode):02d}[/COLOR]'
                    url = self.get_url(action='tv_show', tmdb_id=tmdb_id)
                    art = {'icon': 'DefaultTVShows.png'}
                    if entry.get('poster'):
                        art['thumb'] = f"https://image.tmdb.org/t/p/w185{entry['poster']}"
                    idx_list = ",".join(str(i) for i in entry['indices'])
                    cm = []
                    if tmdb_id and season and episode:
                        cm.append((
                            self.gui._get_string('select_stream'),
                            f"RunPlugin({self.get_url(action='select_stream_manual', content_type='episode', tmdb_id=tmdb_id, title=show_title, season=season, episode=episode, handle=self.handle)})"
                        ))
                    cm.append((
                        self.gui._get_string('remove_from_history'),
                        f'RunPlugin({self.get_url(action="remove_watch_items", indices=idx_list)})'
                    ))
                    self.gui.add_item(label=label, url=url, is_folder=True, art=art, context_menu=cm)
        else:
            for index, item in enumerate(history):
                item_type = item.get('type', '')
                if item_type == 'movie':
                    title = item.get('title', 'Unknown')
                    year = item.get('year', '')
                    tmdb_id = item.get('tmdb_id')
                    label = f'[COLOR gold]{title}[/COLOR]'
                    if year:
                        label += f' [COLOR grey]({year})[/COLOR]'
                    url = self.get_url(action='play_movie', tmdb_id=tmdb_id, title=title, year=year)
                    art = {'icon': 'DefaultMovies.png'}
                    if item.get('poster'):
                        art['thumb'] = f"https://image.tmdb.org/t/p/w185{item['poster']}"
                else:
                    show_title = item.get('show_title', 'Unknown')
                    season = item.get('season', 0)
                    episode = item.get('episode', 0)
                    episode_title = item.get('title', '')
                    tmdb_id = item.get('tmdb_id')
                    label = f'[COLOR cyan]{show_title}[/COLOR] [COLOR grey]- S{int(season):02d}E{int(episode):02d}[/COLOR]'
                    if episode_title and episode_title != f'S{season}E{episode}':
                        label += f' [COLOR white]- {episode_title}[/COLOR]'
                    url = self.get_url(
                        action='play_episode', tmdb_id=tmdb_id, show_title=show_title,
                        season=season, episode=episode, episode_title=episode_title
                    )
                    art = {'icon': 'DefaultTVShows.png'}
                    if item.get('poster'):
                        art['thumb'] = f"https://image.tmdb.org/t/p/w185{item['poster']}"
                cm = []
                if tmdb_id:
                    if item_type == 'movie':
                        cm.append((
                            self.gui._get_string('select_stream'),
                            f"RunPlugin({self.get_url(action='select_stream_manual', content_type='movie', tmdb_id=tmdb_id, title=title, year=year, handle=self.handle)})"
                        ))
                    else:
                        cm.append((
                            self.gui._get_string('select_stream'),
                            f"RunPlugin({self.get_url(action='select_stream_manual', content_type='episode', tmdb_id=tmdb_id, title=show_title, season=season, episode=episode, handle=self.handle)})"
                        ))
                else:
                    cm.append((
                        "Re-search on WebShare",
                        f"RunPlugin({self.get_url(action='manual_webshare_search_prefill', query=title)})"
                    ))
                cm.append((
                    self.gui._get_string('remove_from_history'),
                    f'RunPlugin({self.get_url(action="remove_watch_item", index=index)})'
                ))
                self.gui.add_item(label=label, url=url, is_folder=False, art=art, context_menu=cm)
        self.gui.add_item(label=f'[COLOR red]{self.gui._get_string("clear_all")}[/COLOR]', url=self.get_url(action='clear_watch_history'), is_folder=False)
        xbmcplugin.endOfDirectory(self.handle)

    def search_menu(self):
        keyboard = xbmc.Keyboard('', self.gui._get_string('search'))
        keyboard.doModal()
        if keyboard.isConfirmed():
            query = keyboard.getText()
            if query:
                self.history.add_search(query)
                self.show_search_results(query)

    def show_search_results(self, query):
        xbmcplugin.setPluginCategory(self.handle, f'{self.gui._get_string("search")}: {query}')
        xbmcplugin.setContent(self.handle, 'files')
        movies = self.tmdb.search_movie(query)
        tv_shows = self.tmdb.search_tv(query)
        total = len(movies) + len(tv_shows)
        self.gui.add_item(
            label=f'[COLOR yellow]{self.gui._get_string("search_results").format(total)}[/COLOR]',
            url='',
            is_folder=False
        )
        for movie in movies:
            self.gui.add_movie_item(movie, is_search_result=True)
        for show in tv_shows:
            self.gui.add_tvshow_item(show, is_search_result=True)
        xbmcplugin.endOfDirectory(self.handle)

    def manual_webshare_search(self, prefill_query=''):
        from lib.utils import popinfo, poperror

        if self.addon.getSetting('enable_manual_webshare_search') != 'true':
            popinfo("Manual WebShare search is disabled in settings")
            xbmcplugin.endOfDirectory(self.handle, succeeded=False)
            return

        if prefill_query:
            query = prefill_query
        else:
            keyboard = xbmc.Keyboard('', 'Search WebShare')
            keyboard.doModal()
            if not keyboard.isConfirmed():
                xbmcplugin.endOfDirectory(self.handle, succeeded=False)
                return
            query = keyboard.getText().strip()
            if not query:
                xbmcplugin.endOfDirectory(self.handle, succeeded=False)
                return

        if not self.websharder.token:
            if not self.websharder.login():
                poperror("WebShare login failed!")
                xbmcplugin.endOfDirectory(self.handle, succeeded=False)
                return

        progress = xbmcgui.DialogProgress()
        progress.create("WebShare Search", "Searching for:\n" + query)
        results = self.websharder.search_webshare(query, max_results=100)
        progress.close()

        if not results:
            popinfo("No results for: " + query)
            xbmcplugin.endOfDirectory(self.handle, succeeded=False)
            return

        xbmcplugin.setPluginCategory(self.handle, "WebShare: " + query)
        xbmcplugin.setContent(self.handle, 'files')

        count = 0
        for r in results:
            ident = r.get('ident')
            fn = r.get('name') or r.get('filename') or ''
            if not ident or not fn:
                continue
            count += 1
            li = xbmcgui.ListItem(label=fn)
            li.setProperty('IsPlayable', 'true')
            li.setInfo('video', {'title': fn, 'mediatype': 'video'})
            url = self.get_url(action='play_manual_webshare', ident=ident, filename=fn)
            xbmcplugin.addDirectoryItem(self.handle, url, li, False)

        if count == 0:
            popinfo("No playable files in results")

        xbmcplugin.endOfDirectory(self.handle)

    def play_manual_webshare(self, ident, filename):
        from lib.utils import poperror
        try:
            log("Manual WebShare play: " + ident + " (" + filename + ")")
            self.stream_selector.handle = self.handle
            success = self.stream_selector._play_stream(
                ident, filename, tmdb_id=None, silent_fail=False
            )
            if success:
                self.history.add_watched({
                    'type': 'movie',
                    'tmdb_id': None,
                    'title': filename,
                    'year': '',
                    'poster': ''
                })
        except Exception as e:
            import traceback
            log("play_manual_webshare EXCEPTION: " + str(e))
            log(traceback.format_exc())
            poperror("Playback error: " + str(e)[:150])

    # ===== DYNAMIC SUGGESTIONS (v2 - under Watch History, fewer folders, more results) =====

    def dynamic_menu(self):
        xbmcplugin.setPluginCategory(self.handle, 'Dynamic Picks')
        xbmcplugin.setContent(self.handle, 'movies')

        self.gui.add_item(
            label='[COLOR orange][B]Surprise Me[/B][/COLOR]',
            url=self.get_url(action='dynamic_surprise_me'),
            is_folder=True
        )
        self.gui.add_item(
            label='[COLOR gold][B]Hidden Gems[/B][/COLOR]',
            url=self.get_url(action='dynamic_hidden_gems'),
            is_folder=True
        )
        self.gui.add_item(
            label='[COLOR cyan][B]Browse All Picks[/B][/COLOR]',
            url=self.get_url(action='dynamic_browse_all'),
            is_folder=True
        )

        xbmcplugin.endOfDirectory(self.handle)

    def _fetch_pages(self, method_name, pages=3, **kwargs):
        """Call a discover_* method across multiple pages and merge results."""
        items = []
        seen = set()
        method = getattr(self.tmdb, method_name)
        for p in range(1, pages + 1):
            try:
                if kwargs:
                    page_items = method(**kwargs, page=p) if self._method_accepts_page(method) else method(**kwargs)
                else:
                    page_items = method(page=p) if self._method_accepts_page(method) else method()
            except TypeError:
                page_items = method(**kwargs) if kwargs else method()
            for it in page_items or []:
                mid = it.get('id')
                if mid and mid not in seen:
                    seen.add(mid)
                    items.append(it)
            if len(page_items or []) < 15:
                break
        return items

    def _method_accepts_page(self, method):
        """True if the underlying method has a 'page' kwarg."""
        import inspect
        try:
            sig = inspect.signature(method)
            return 'page' in sig.parameters
        except Exception:
            return False

    def _fetch_dynamic_pages(self, method_name, pages=3):
        """Direct call with page= — works because _dynamic_call accepts page."""
        items = []
        seen = set()
        method = getattr(self.tmdb, method_name)
        for p in range(1, pages + 1):
            try:
                page_items = method(page=p)
            except TypeError:
                page_items = method()
                # Non-paginated methods return the same page — break after first
                for it in page_items or []:
                    mid = it.get('id')
                    if mid and mid not in seen:
                        seen.add(mid)
                        items.append(it)
                break
            for it in page_items or []:
                mid = it.get('id')
                if mid and mid not in seen:
                    seen.add(mid)
                    items.append(it)
            if len(page_items or []) < 15:
                break
        return items

    def show_dynamic_list(self, method_name, list_name, page=1, total_pages=None):
        xbmcplugin.setPluginCategory(self.handle, list_name)
        xbmcplugin.setContent(self.handle, 'movies')
        try:
            method = getattr(self.tmdb, method_name)
            items = method(page=page)
        except Exception as e:
            log(f"[dynamic] Error in {method_name} page {page}: {e}")
            items = []

        if not items:
            self.gui.add_item(
                label='[COLOR grey]No results on this page — end of list[/COLOR]',
                url='',
                is_folder=False
            )
        else:
            for it in items:
                self.gui.add_movie_item(it)

        # "Next Page" footer — shown if this page returned a full 20
        if items and len(items) >= 15:
            next_page = page + 1
            self.gui.add_item(
                label=f'[COLOR cyan][B]▶ Next Page  ({next_page * 20 - 19} - {next_page * 20})[/B][/COLOR]',
                url=self.get_url(action='dynamic_list', method=method_name, name=list_name, page=next_page),
                is_folder=True
            )

        xbmcplugin.endOfDirectory(self.handle)

    def show_dynamic_browse_all(self, page=1):
        """Merged curated list — one 'logical page' = one page from each source (max 100 items)."""
        xbmcplugin.setPluginCategory(self.handle, 'Browse All Picks')
        xbmcplugin.setContent(self.handle, 'movies')

        sources = [
            'discover_hidden_gems',
            'discover_fresh_acclaimed',
            'discover_underrated',
            'discover_critically_acclaimed',
            'discover_mind_benders',
        ]

        merged = []
        seen = set()
        for src in sources:
            try:
                method = getattr(self.tmdb, src)
                try:
                    items = method(page=page)
                except TypeError:
                    items = method()
                for it in items or []:
                    mid = it.get('id')
                    if mid and mid not in seen:
                        seen.add(mid)
                        merged.append(it)
            except Exception as e:
                log(f"[browse_all] {src} page {page} failed: {e}")

        merged.sort(key=lambda x: float(x.get('vote_average') or 0), reverse=True)
        log(f"[browse_all] page {page} -> {len(merged)} items")

        if not merged:
            self.gui.add_item(label='[COLOR grey]No more results — end of list[/COLOR]', url='', is_folder=False)
        else:
            for it in merged:
                self.gui.add_movie_item(it)

        # Next Page footer
        if merged and len(merged) >= 15:
            next_page = page + 1
            self.gui.add_item(
                label=f'[COLOR cyan][B]▶ Next Page  (page {next_page})[/B][/COLOR]',
                url=self.get_url(action='dynamic_browse_all_page', page=next_page),
                is_folder=True
            )

        xbmcplugin.endOfDirectory(self.handle)

    def dynamic_decade_pick(self):
        """Kept for backward-compat router case; now just redirects to browse all."""
        self.show_dynamic_browse_all()


def run():
    addon = MILA()
    if len(sys.argv) > 2:
        addon.router(sys.argv[2][1:])
    else:
        addon.router('')
