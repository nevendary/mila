# -*- coding: utf-8 -*-
# Kodi list item builders with proper PO file loading
import xbmc
import xbmcgui
import xbmcplugin
import xbmcaddon
from lib.utils import log

class GUI:
    def __init__(self, addon_instance):
        self.addon = addon_instance
        self.handle = addon_instance.handle
        self.tmdb = addon_instance.tmdb
        self.addon_obj = xbmcaddon.Addon()

    def _get_string(self, key, *args):
        """Get translated string from PO files - NO WEBSHARE ERRORS"""

        string_ids = {
            # Search & History (30000-30099)
            'search': 30000,
            'search_history': 30001,
            'watch_history': 30002,
            'clear_all': 30003,
            'remove_from_history': 30004,
            'no_search_history': 30005,
            'no_watch_history': 30006,

            # Movies & TV (30100-30199)
            'popular_movies': 30100,
            'top_rated_movies': 30101,
            'popular_tv': 30102,
            'top_rated_tv': 30103,
            'season': 30104,
            'episode': 30105,
            'episodes': 30106,

            # Search Results (30200-30299)
            'search_results': 30200,

            # Main Menu Categories (32000-32006)
            'trending_now': 32000,
            'genres': 32001,
            'czech_slovak': 32002,
            'studios': 32003,
            'decades': 32004,
            'smart_mixes': 32005,
            'recent_releases': 32006,

            # Trending & Now (32007-32010)
            'trending_week': 32007,
            'trending_day': 32008,
            'now_playing': 32009,
            'upcoming': 32010,

            # Genres (32011-32032)
            'action': 32011,
            'adventure': 32012,
            'action_adventure': 32013,
            'comedy': 32014,
            'drama': 32015,
            'comedy_drama': 32016,
            'thriller': 32017,
            'horror': 32018,
            'thriller_horror': 32019,
            'sci_fi': 32020,
            'fantasy': 32021,
            'sci_fi_fantasy': 32022,
            'romance': 32023,
            'family': 32024,
            'animation': 32025,
            'family_animation': 32026,
            'documentary': 32027,
            'war': 32028,
            'history': 32029,
            'war_history': 32030,
            'crime': 32031,
            'mystery': 32032,

            # Czech & Slovak (32033-32036)
            'czech_movies': 32033,
            'czech_recent': 32034,
            'czechoslovak_classics': 32035,
            'slovak_movies': 32036,

            # Studios (32037-32047)
            'marvel': 32037,
            'dc': 32038,
            'disney': 32039,
            'netflix': 32040,
            'hbo': 32041,
            'amazon': 32042,
            'apple': 32043,
            'paramount': 32044,
            'universal': 32045,
            'warner': 32046,
            'sony': 32047,

            # Decades (32048-32052)
            'decade_80s': 32048,
            'decade_90s': 32049,
            'decade_00s': 32050,
            'decade_2010s': 32051,
            'decade_2020s': 32052,

            # Smart Mixes (32053-32056)
            'cult_classics': 32053,
            'feel_good': 32054,
            'date_night': 32055,
            'weekend_binge': 32056,

            # Recent Releases (32057-32059)
            'this_month': 32057,
            'last_3_months': 32058,
            'this_year': 32059,

            # Additional strings (32060-32062)
            'select_stream': 32060,
            'no_files_found': 32061,
            'searching': 32062,

            # ===== YUGOSLAV / EX-YU REGION (32100-32118) =====
            'yugoslav_region': 32100,
            'yugoslav_movies_all': 32101,
            'yugoslav_tv_all': 32102,
            'serbian_movies': 32103,
            'serbian_tv': 32104,
            'croatian_movies': 32105,
            'croatian_tv': 32106,
            'bosnian_movies': 32107,
            'bosnian_tv': 32108,
            'montenegrin_movies': 32109,
            'montenegrin_tv': 32110,
            'yugoslav_classics': 32111,
            'yugoslav_tv_classics': 32112,
            'yugoslav_westerns': 32113,
            'partisan_films': 32114,
            'regional_recent_movies': 32115,
            'regional_recent_tv': 32116,
            'pula_film_festival': 32117,
            'sarajevo_film_festival': 32118,
            'dyn_hidden_gems': 33000,
            'dyn_fresh_acclaimed': 33001,
            'dyn_surprise_me': 33002,
            'dyn_quick_watch': 33003,
            'dyn_underrated': 33004,
            'dyn_critically_acclaimed': 33005,
            'dyn_feel_good_short': 33006,
            'dyn_mind_benders': 33007,
            'dyn_foreign_gems': 33008,
            'dyn_random_page': 33009,

        }

        string_id = string_ids.get(key)
        if string_id:
            try:
                translated = self.addon_obj.getLocalizedString(string_id)
                if translated and translated != "":
                    if args:
                        try:
                            return translated % args
                        except:
                            return translated
                    return translated
            except:
                pass

        # HARDCODED ENGLISH FALLBACK - WITH YUGOSLAV STRINGS
        fallback = {
            'search': 'Search',
            'search_history': 'Search History',
            'watch_history': 'Watch History',
            'clear_all': 'Clear all',
            'remove_from_history': 'Remove from history',
            'no_search_history': 'No search history',
            'no_watch_history': 'No watch history',
            'popular_movies': 'Popular Movies',
            'top_rated_movies': 'Top Rated Movies',
            'popular_tv': 'Popular TV Shows',
            'top_rated_tv': 'Top Rated TV Shows',
            'season': 'Season',
            'episode': 'Episode',
            'episodes': 'episodes',
            'search_results': 'Found {} results',
            'trending_now': 'Trending Now',
            'genres': 'Genres',
            'czech_slovak': 'Czech & Slovak',
            'studios': 'Studios',
            'decades': 'Decades',
            'smart_mixes': 'Smart Mixes',
            'recent_releases': 'Recent Releases',
            'trending_week': 'Trending This Week',
            'trending_day': 'Trending Today',
            'now_playing': 'Now Playing',
            'upcoming': 'Upcoming',
            'action': 'Action',
            'adventure': 'Adventure',
            'action_adventure': 'Action & Adventure',
            'comedy': 'Comedy',
            'drama': 'Drama',
            'comedy_drama': 'Comedy & Drama',
            'thriller': 'Thriller',
            'horror': 'Horror',
            'thriller_horror': 'Thriller & Horror',
            'sci_fi': 'Sci-Fi',
            'fantasy': 'Fantasy',
            'sci_fi_fantasy': 'Sci-Fi & Fantasy',
            'romance': 'Romance',
            'family': 'Family',
            'animation': 'Animation',
            'family_animation': 'Family & Animation',
            'documentary': 'Documentary',
            'war': 'War',
            'history': 'History',
            'war_history': 'War & History',
            'crime': 'Crime',
            'mystery': 'Mystery',
            'czech_movies': 'Czech Movies',
            'czech_recent': 'Recent Czech Movies',
            'czechoslovak_classics': 'Czechoslovak Classics',
            'slovak_movies': 'Slovak Movies',
            'marvel': 'Marvel',
            'dc': 'DC Comics',
            'disney': 'Disney',
            'netflix': 'Netflix',
            'hbo': 'HBO Max',
            'amazon': 'Amazon Prime',
            'apple': 'Apple TV+',
            'paramount': 'Paramount',
            'universal': 'Universal',
            'warner': 'Warner Bros',
            'sony': 'Sony Pictures',
            'decade_80s': '1980s',
            'decade_90s': '1990s',
            'decade_00s': '2000s',
            'decade_2010s': '2010s',
            'decade_2020s': '2020s',
            'cult_classics': 'Cult Classics',
            'feel_good': 'Feel Good',
            'date_night': 'Date Night',
            'weekend_binge': 'Weekend Binge',
            'this_month': 'This Month',
            'last_3_months': 'Last 3 Months',
            'this_year': 'This Year',
            'select_stream': 'Select Stream',
            'no_files_found': 'No files found',
            'searching': 'Searching...',
            
            # ===== YUGOSLAV / EX-YU REGION FALLBACK =====
            'yugoslav_region': 'Yugoslav & Ex-YU',
            'yugoslav_movies_all': 'All Yugoslav Movies',
            'yugoslav_tv_all': 'All Yugoslav TV Shows',
            'serbian_movies': 'Serbian Movies',
            'serbian_tv': 'Serbian TV Shows',
            'croatian_movies': 'Croatian Movies',
            'croatian_tv': 'Croatian TV Shows',
            'bosnian_movies': 'Bosnian Movies',
            'bosnian_tv': 'Bosnian TV Shows',
            'montenegrin_movies': 'Montenegrin Movies',
            'montenegrin_tv': 'Montenegrin TV Shows',
            'yugoslav_classics': 'Yugoslav Classics (pre-1992)',
            'yugoslav_tv_classics': 'Yugoslav TV Classics',
            'yugoslav_westerns': 'Yugoslav Westerns',
            'partisan_films': 'Partisan Films',
            'regional_recent_movies': 'Recent Regional Movies',
            'regional_recent_tv': 'Recent Regional TV',
            'pula_film_festival': 'Pula Film Festival',
            'sarajevo_film_festival': 'Sarajevo Film Festival',
            'dyn_hidden_gems': 'Hidden Gems',
            'dyn_fresh_acclaimed': 'Fresh & Acclaimed',
            'dyn_surprise_me': 'Surprise Me',
            'dyn_quick_watch': 'Quick Watch (under 90 min)',
            'dyn_underrated': 'Underrated',
            'dyn_critically_acclaimed': 'Critically Acclaimed',
            'dyn_feel_good_short': 'Feel Good (under 2h)',
            'dyn_mind_benders': 'Mind Benders',
            'dyn_foreign_gems': 'Foreign Language Gems',
            'dyn_random_page': 'Random Discovery',

        }

        result = fallback.get(key, key)
        if args:
            try:
                return result.format(*args)
            except:
                return result
        return result

    def add_item(self, label, url, is_folder=True, art=None, info=None, cast=None, context_menu=None):
        """Generic method to add a directory item"""
        li = xbmcgui.ListItem(label=label)

        if art:
            li.setArt(art)

        if info:
            li.setInfo('video', info)

        if cast:
            li.setCast(cast)

        if context_menu:
            li.addContextMenuItems(context_menu)

        if not is_folder:
            li.setProperty('IsPlayable', 'true')

        xbmcplugin.addDirectoryItem(self.handle, url, li, is_folder)
        return li

    def add_movie_item(self, movie, is_search_result=False):
        """Add a movie item to the directory"""
        tmdb_id = movie.get('id')
        title = movie.get('title', 'Unknown')
        year = movie.get('release_date', '')[:4] if movie.get('release_date') else ''

        details = self.tmdb.get_movie_details(tmdb_id) if tmdb_id else None

        label = f"[B]{title}[/B]"
        if year:
            label += f" ({year})"
        if details and details.get('vote_average'):
            rating = details['vote_average']
            label += f" [COLOR yellow]{rating:.1f}★[/COLOR]"

        art = {}
        if details:
            if details.get('poster_path'):
                art['poster'] = self.tmdb.get_poster(details['poster_path'], 'w500')
                art['thumb'] = self.tmdb.get_poster(details['poster_path'], 'w342')
            if details.get('backdrop_path'):
                art['fanart'] = self.tmdb.get_backdrop(details['backdrop_path'])

        if not art.get('poster'):
            art['poster'] = 'DefaultMovies.png'
            art['thumb'] = 'DefaultMovies.png'

        info = {'title': title, 'mediatype': 'movie'}
        if year:
            info['year'] = int(year) if year.isdigit() else 0
            info['premiered'] = movie.get('release_date', '')
        if details:
            info['plot'] = details.get('overview', '')
            info['rating'] = float(details.get('vote_average', 0))
            info['votes'] = str(details.get('vote_count', 0))

            genres = [g['name'] for g in details.get('genres', [])]
            if genres:
                info['genre'] = ' / '.join(genres)

            if details.get('credits'):
                directors = [c['name'] for c in details['credits'].get('crew', [])
                           if c.get('job') == 'Director']
                if directors:
                    info['director'] = ' / '.join(directors)

        cast = []
        if details and details.get('credits'):
            for person in details['credits'].get('cast', [])[:10]:
                cast.append({
                    'name': person.get('name', ''),
                    'role': person.get('character', ''),
                    'thumbnail': self.tmdb.get_image_url(person.get('profile_path'), 'w185')
                                if person.get('profile_path') else ''
                })

        context_menu = []
        url_select = self.addon.get_url(
            action='select_stream_manual',
            content_type='movie',
            tmdb_id=tmdb_id,
            title=title,
            year=year,
            handle=self.handle
        )

        context_menu.append((
            self._get_string('select_stream'),
            f"RunPlugin({url_select})"
        ))

        url_play = self.addon.get_url(
            action='play_movie',
            tmdb_id=tmdb_id,
            title=title,
            year=year
        )

        self.add_item(label, url_play, is_folder=False, art=art, info=info, cast=cast, context_menu=context_menu)

    def add_tvshow_item(self, show, is_search_result=False):
        """Add a TV show item to the directory"""
        tmdb_id = show.get('id')
        title = show.get('name', 'Unknown')
        year = show.get('first_air_date', '')[:4] if show.get('first_air_date') else ''

        details = self.tmdb.get_tv_details(tmdb_id) if tmdb_id else None

        label = f"[B]{title}[/B]"
        if year:
            label += f" ({year})"
        if details and details.get('vote_average'):
            rating = details['vote_average']
            label += f" [COLOR yellow]{rating:.1f}★[/COLOR]"

        art = {}
        if details:
            if details.get('poster_path'):
                art['poster'] = self.tmdb.get_poster(details['poster_path'], 'w500')
                art['thumb'] = self.tmdb.get_poster(details['poster_path'], 'w342')
            if details.get('backdrop_path'):
                art['fanart'] = self.tmdb.get_backdrop(details['backdrop_path'])

        if not art.get('poster'):
            art['poster'] = 'DefaultTVShows.png'
            art['thumb'] = 'DefaultTVShows.png'

        info = {'title': title, 'mediatype': 'tvshow'}
        if year:
            info['year'] = int(year) if year.isdigit() else 0
            info['premiered'] = show.get('first_air_date', '')
        if details:
            info['plot'] = details.get('overview', '')
            info['rating'] = float(details.get('vote_average', 0))
            info['votes'] = str(details.get('vote_count', 0))

            genres = [g['name'] for g in details.get('genres', [])]
            if genres:
                info['genre'] = ' / '.join(genres)

            info['status'] = details.get('status', '')

        cast = []
        if details and details.get('credits'):
            for person in details['credits'].get('cast', [])[:10]:
                cast.append({
                    'name': person.get('name', ''),
                    'role': person.get('character', ''),
                    'thumbnail': self.tmdb.get_image_url(person.get('profile_path'), 'w185')
                                if person.get('profile_path') else ''
                })

        url = self.addon.get_url(action='tv_show', tmdb_id=tmdb_id)
        self.add_item(label, url, is_folder=True, art=art, info=info, cast=cast)

    def add_season_item(self, show, season):
        """Add a season item to the directory"""
        tmdb_id = show.get('id')
        season_num = season.get('season_number', 0)
        episode_count = season.get('episode_count', 0)

        label = f"{self._get_string('season')} {season_num}"
        if episode_count > 0:
            label += f" ({episode_count} {self._get_string('episodes')})"

        art = {}
        if season.get('poster_path'):
            art['poster'] = self.tmdb.get_poster(season['poster_path'], 'w500')
            art['thumb'] = self.tmdb.get_poster(season['poster_path'], 'w342')
        elif show.get('poster_path'):
            art['poster'] = self.tmdb.get_poster(show['poster_path'], 'w500')
            art['thumb'] = self.tmdb.get_poster(show['poster_path'], 'w342')

        if not art.get('poster'):
            art['poster'] = 'DefaultFolder.png'
            art['thumb'] = 'DefaultFolder.png'

        info = {
            'title': f"{self._get_string('season')} {season_num}",
            'mediatype': 'season',
            'season': season_num
        }
        if season.get('air_date'):
            info['premiered'] = season['air_date']
        if season.get('overview'):
            info['plot'] = season['overview']

        url = self.addon.get_url(action='tv_season', tmdb_id=tmdb_id, season=season_num)
        self.add_item(label, url, is_folder=True, art=art, info=info)

    def add_episode_item(self, show, season, episode):
        """Add an episode item to the directory"""
        tmdb_id = show.get('id')
        season_num = season.get('season_number', 0)
        episode_num = episode.get('episode_number', 0)
        episode_name = episode.get('name', f"{self._get_string('episode')} {episode_num}")

        label = f"{episode_num}. {episode_name}"
        if episode.get('vote_average'):
            rating = episode['vote_average']
            label += f" [COLOR yellow]{rating:.1f}★[/COLOR]"

        art = {}
        if episode.get('still_path'):
            art['thumb'] = self.tmdb.get_still(episode['still_path'], 'w500')
            art['poster'] = self.tmdb.get_still(episode['still_path'], 'w500')
        elif season.get('poster_path'):
            art['poster'] = self.tmdb.get_poster(season['poster_path'], 'w500')
            art['thumb'] = self.tmdb.get_poster(season['poster_path'], 'w342')
        elif show.get('poster_path'):
            art['poster'] = self.tmdb.get_poster(show['poster_path'], 'w500')
            art['thumb'] = self.tmdb.get_poster(show['poster_path'], 'w342')

        if not art.get('thumb'):
            art['thumb'] = 'DefaultVideo.png'
            art['poster'] = 'DefaultVideo.png'

        info = {
            'title': episode_name,
            'mediatype': 'episode',
            'season': season_num,
            'episode': episode_num,
            'tvshowtitle': show.get('name', 'Unknown')
        }
        if episode.get('overview'):
            info['plot'] = episode['overview']
        if episode.get('vote_average'):
            info['rating'] = float(episode['vote_average'])
        if episode.get('air_date'):
            info['aired'] = episode['air_date']
        if episode.get('runtime'):
            info['duration'] = episode['runtime'] * 60

        context_menu = []
        url_select = self.addon.get_url(
            action='select_stream_manual',
            content_type='episode',
            tmdb_id=tmdb_id,
            title=show.get('name', 'Unknown'),
            season=season_num,
            episode=episode_num,
            handle=self.handle
        )

        context_menu.append((
            self._get_string('select_stream'),
            f"RunPlugin({url_select})"
        ))

        url_play = self.addon.get_url(
            action='play_episode',
            tmdb_id=tmdb_id,
            show_title=show.get('name', 'Unknown'),
            season=season_num,
            episode=episode_num,
            episode_title=episode_name
        )

        self.add_item(label, url_play, is_folder=False, art=art, info=info, context_menu=context_menu)
