# -*- coding: utf-8 -*-
# Stream selection, ranking, and playback with AUTOMATIC FALLBACK AND WATCH HISTORY
import xbmc
import xbmcgui
import xbmcplugin
import sys
import os
import re
import time
from lib.utils import log, popinfo, poperror
from lib.opensubtitles import OpenSubtitles
from lib.tmdb import TMDB
from lib.history import HistoryManager

class StreamSelector:
    def __init__(self, addon, websharder):
        self.addon = addon
        self.websharder = websharder
        self.opensubtitles = OpenSubtitles()
        self.tmdb = TMDB(addon)
        self.history = HistoryManager()

    def _get_handle(self, url_handle=None):
        if url_handle is not None:
            try:
                return int(url_handle)
            except:
                pass
        try:
            return int(sys.argv[1]) if len(sys.argv) > 1 else -1
        except:
            return -1

    def _get_audio_language_code(self, language_name):
        """Convert language name to ISO 639-1 code"""
        lang_map = {
            'English': 'eng',
            'Czech': 'cze',
            'Croatian': 'hrv',
            'Slovak': 'slo',
            'Serbian': 'srp'
        }
        return lang_map.get(language_name, 'eng')

    # ==================== MAIN PUBLIC METHODS ====================

    def play_movie(self, tmdb_id, title, year, stream_id=None, handle=None, movie_details=None):
        """Search and play movie with AUTOMATIC FALLBACK"""
        self.handle = self._get_handle(handle)
        log(f"🎬 play_movie: {title} ({year}) stream_id: {stream_id} handle: {self.handle}")

        # If specific stream requested, try it first
        if stream_id:
            log(f"🎯 Trying specific stream: {stream_id}")
            success = self._play_stream(stream_id, f"{title} ({year})", tmdb_id,
                                       year=year, movie_details=movie_details)
            if success:
                self.history.add_watched({
                    'type': 'movie',
                    'tmdb_id': tmdb_id,
                    'title': title,
                    'year': year,
                    'poster': movie_details.get('poster_path') if movie_details else None
                })
                return
            else:
                autoplay = self.addon.getSetting('autoplay') == 'true'
                if not autoplay:
                    poperror("Selected stream failed to play")
                    return
                log("➡️ Selected stream failed, searching for alternatives...")

        # DON'T SHOW LOGIN DIALOGS FOR POPULAR/TOP RATED LISTS!
        if not self.websharder.token:
            log("⚠️ WebShare not logged in - this should only happen when playing content")
            if not self.websharder.login():
                poperror("WebShare login failed!\nPlease check your credentials in add-on settings.")
                return

        # ===== FIX: GET ALL POSSIBLE TITLES FOR MAXIMUM SEARCH =====
        # Get localized titles from TMDB
        localized = self.tmdb.get_movie_localized_titles(tmdb_id)
        
        # Get original title from movie_details
        original_title = movie_details.get('original_title', title) if movie_details else title
        
        # Get Czech title from TMDB or fallback to provided title
        czech_title = localized.get('czech')
        if not czech_title:
            czech_title = title
        
        # Get Croatian and Serbian titles if available
        croatian_title = localized.get('croatian')
        serbian_title = localized.get('serbian')
        
        # Set ALL titles for maximum search coverage
        self.websharder.set_localized_titles(
            english_title=original_title,      # Original title (may be English, Czech, etc)
            czech_title=czech_title,           # Czech title from TMDB or menu
            croatian_title=croatian_title,     # Croatian title if available
            serbian_title=serbian_title,       # Serbian title if available
            tmdb_id=tmdb_id
        )

        log(f"🔍 SEARCH MAXIMIZER - Original/English: '{original_title}'")
        log(f"🔍 SEARCH MAXIMIZER - Czech: '{czech_title}'")
        if croatian_title:
            log(f"🔍 SEARCH MAXIMIZER - Croatian: '{croatian_title}'")
        if serbian_title:
            log(f"🔍 SEARCH MAXIMIZER - Serbian: '{serbian_title}'")

        # Search for streams
        progress = xbmcgui.DialogProgress()
        progress.create("WebShare Search", f"Searching for:\n{title} ({year})")
        files = self.websharder.search_movie(title, year, tmdb_id)
        progress.close()

        if not files:
            popinfo(f"No files found for: {title} ({year})")
            return

        # Rank streams by quality and language
        ranked = self.rank_streams(files)
        log(f"🔍 Found {len(ranked)} streams, ranked by quality/language")

        # Try each stream in order until one works
        autoplay = self.addon.getSetting('autoplay') == 'true'

        for i, rank_data in enumerate(ranked):
            stream = rank_data['stream']
            stream_id = stream.get('ident')
            quality = stream.get('quality', 'SD')

            log(f"🔄 Trying stream {i+1}/{len(ranked)}: {quality} (Score: {rank_data['score']})")

            silent_fail = (i < len(ranked) - 1) and autoplay
            success = self._play_stream(stream_id, f"{title} ({year})", tmdb_id,
                                       year=year, movie_details=movie_details,
                                       silent_fail=silent_fail)

            if success:
                log(f"✅ Successfully playing stream {i+1}")
                self.history.add_watched({
                    'type': 'movie',
                    'tmdb_id': tmdb_id,
                    'title': title,
                    'year': year,
                    'poster': movie_details.get('poster_path') if movie_details else None
                })
                return True

            if i < len(ranked) - 1:
                log(f"➡️ Stream failed, trying next in 0.5s...")
                xbmc.sleep(500)

        poperror(f"All {len(ranked)} streams failed for: {title} ({year})")
        return False

    def play_episode(self, tmdb_id, show_title, season, episode, episode_title="", stream_id=None,
                    handle=None, episode_details=None, show_details=None):
        """Search and play TV episode with AUTOMATIC FALLBACK"""
        self.handle = self._get_handle(handle)
        log(f"📺 play_episode: {show_title} S{season}E{episode} stream_id: {stream_id}")

        display_title = f"{show_title} S{season}E{episode}"
        if episode_title:
            display_title = f"{show_title} - S{season}E{episode} - {episode_title}"

        if stream_id:
            log(f"🎯 Trying specific stream: {stream_id}")
            success = self._play_stream(stream_id, display_title, tmdb_id,
                                       season=season, episode=episode,
                                       episode_details=episode_details,
                                       show_details=show_details)
            if success:
                self.history.add_watched({
                    'type': 'episode',
                    'tmdb_id': tmdb_id,
                    'show_title': show_title,
                    'title': episode_title or f"S{season}E{episode}",
                    'season': int(season),
                    'episode': int(episode),
                    'poster': episode_details.get('still_path') if episode_details else None
                })
                return
            else:
                autoplay = self.addon.getSetting('autoplay') == 'true'
                if not autoplay:
                    poperror("Selected stream failed to play")
                    return
                log("➡️ Selected stream failed, searching for alternatives...")

        if not self.websharder.token:
            log("⚠️ WebShare not logged in")
            if not self.websharder.login():
                poperror("WebShare login failed!\nPlease check your credentials in add-on settings.")
                return

        # ===== FIX: GET ALL POSSIBLE TITLES FOR MAXIMUM SEARCH =====
        # Get localized titles from TMDB
        localized = self.tmdb.get_tv_localized_titles(tmdb_id)
        
        # Get original title from show_details
        original_title = show_details.get('original_name', show_title) if show_details else show_title
        
        # Get Czech title from TMDB or fallback to provided title
        czech_title = localized.get('czech')
        if not czech_title:
            czech_title = show_title
        
        # Get Croatian and Serbian titles if available
        croatian_title = localized.get('croatian')
        serbian_title = localized.get('serbian')
        
        # Set ALL titles for maximum search coverage
        self.websharder.set_localized_titles(
            english_title=original_title,      # Original title
            czech_title=czech_title,           # Czech title from TMDB or menu
            croatian_title=croatian_title,     # Croatian title if available
            serbian_title=serbian_title,       # Serbian title if available
            tmdb_id=tmdb_id
        )

        log(f"🔍 SEARCH MAXIMIZER - Original/English: '{original_title}'")
        log(f"🔍 SEARCH MAXIMIZER - Czech: '{czech_title}'")
        if croatian_title:
            log(f"🔍 SEARCH MAXIMIZER - Croatian: '{croatian_title}'")
        if serbian_title:
            log(f"🔍 SEARCH MAXIMIZER - Serbian: '{serbian_title}'")

        # Search for streams
        progress = xbmcgui.DialogProgress()
        progress.create("WebShare Search", f"Searching for:\n{show_title}\nS{season}E{episode}")
        files = self.websharder.search_episode(show_title, season, episode, tmdb_id)
        progress.close()

        if not files:
            popinfo(f"No files found for: {display_title}")
            return

        # Rank streams by quality and language
        ranked = self.rank_streams(files)
        log(f"🔍 Found {len(ranked)} streams, ranked by quality/language")

        # Try each stream in order until one works
        autoplay = self.addon.getSetting('autoplay') == 'true'

        for i, rank_data in enumerate(ranked):
            stream = rank_data['stream']
            stream_id = stream.get('ident')
            quality = stream.get('quality', 'SD')

            log(f"🔄 Trying stream {i+1}/{len(ranked)}: {quality} (Score: {rank_data['score']})")

            silent_fail = (i < len(ranked) - 1) and autoplay
            success = self._play_stream(stream_id, display_title, tmdb_id,
                                       season=season, episode=episode,
                                       episode_details=episode_details,
                                       show_details=show_details,
                                       silent_fail=silent_fail)

            if success:
                log(f"✅ Successfully playing stream {i+1}")
                self.history.add_watched({
                    'type': 'episode',
                    'tmdb_id': tmdb_id,
                    'show_title': show_title,
                    'title': episode_title or f"S{season}E{episode}",
                    'season': int(season),
                    'episode': int(episode),
                    'poster': episode_details.get('still_path') if episode_details else None
                })
                return True

            if i < len(ranked) - 1:
                log(f"➡️ Stream failed, trying next in 0.5s...")
                xbmc.sleep(500)

        poperror(f"All {len(ranked)} streams failed for: {display_title}")
        return False

    def manual_select(self, tmdb_id, content_type, title, year, season, episode, handle=None):
        """Manual stream selection from context menu"""
        log(f"📌 manual_select: {content_type} - {title}")

        if not self.websharder.token:
            if not self.websharder.login():
                poperror("WebShare login failed!\nPlease check your credentials in add-on settings.")
                return

        if content_type == 'movie':
            # Get movie details for original title
            movie_details = self.tmdb.get_movie_details(tmdb_id)
            localized = self.tmdb.get_movie_localized_titles(tmdb_id)
            original_title = movie_details.get('original_title', title) if movie_details else title
            czech_title = localized.get('czech', title)
            croatian_title = localized.get('croatian')
            serbian_title = localized.get('serbian')
            
            self.websharder.set_localized_titles(
                english_title=original_title,
                czech_title=czech_title,
                croatian_title=croatian_title,
                serbian_title=serbian_title,
                tmdb_id=tmdb_id
            )

            progress = xbmcgui.DialogProgress()
            progress.create("WebShare Search", f"Searching for:\n{title} ({year})")
            files = self.websharder.search_movie(title, year, tmdb_id)
            progress.close()
            display_title = f"{title} ({year})"
        else:
            # Get show details for original title
            show_details = self.tmdb.get_tv_details(tmdb_id)
            localized = self.tmdb.get_tv_localized_titles(tmdb_id)
            original_title = show_details.get('original_name', title) if show_details else title
            czech_title = localized.get('czech', title)
            croatian_title = localized.get('croatian')
            serbian_title = localized.get('serbian')
            
            self.websharder.set_localized_titles(
                english_title=original_title,
                czech_title=czech_title,
                croatian_title=croatian_title,
                serbian_title=serbian_title,
                tmdb_id=tmdb_id
            )

            progress = xbmcgui.DialogProgress()
            progress.create("WebShare Search", f"Searching for:\n{title}\nS{season}E{episode}")
            files = self.websharder.search_episode(title, season, episode, tmdb_id)
            progress.close()
            display_title = f"{title} S{season}E{episode}"

        if not files:
            popinfo(f"No files found for: {display_title}")
            return

        # Rank streams for better display
        ranked = self.rank_streams(files)

        items = []
        for i, rank_data in enumerate(ranked[:50]):
            stream = rank_data['stream']
            quality = stream.get('quality', 'SD')

            size_mb = 0
            try:
                size_mb = int(stream.get('size', 0)) / (1024 * 1024)
            except:
                pass
            size_str = ""
            if size_mb > 1024:
                size_str = f"{size_mb/1024:.1f} GB"
            elif size_mb > 0:
                size_str = f"{size_mb:.0f} MB"

            languages = self.detect_audio_languages(stream.get('filename', ''))
            lang_str = "/".join(languages[:2]) if languages else "Unknown"
            score = rank_data['score']

            label = f"{i+1}. [B]{quality}[/B]"
            if lang_str != 'Unknown':
                label += f" ({lang_str})"
            if size_str:
                label += f" - {size_str}"
            label += f" [COLOR grey][{score}][/COLOR]"

            items.append((label, stream['ident']))

        dialog = xbmcgui.Dialog()
        selected = dialog.select(f"Select stream - {display_title}", [item[0] for item in items])

        if selected < 0:
            return

        stream_id = items[selected][1]
        log(f"User selected stream: {stream_id}")

        from urllib.parse import urlencode
        import sys

        plugin_url = sys.argv[0]

        if content_type == 'movie':
            params = {
                'action': 'play_movie',
                'tmdb_id': tmdb_id,
                'title': title,
                'year': year,
                'stream_id': stream_id
            }
        else:
            params = {
                'action': 'play_episode',
                'tmdb_id': tmdb_id,
                'show_title': title,
                'season': season,
                'episode': episode,
                'stream_id': stream_id
            }

        url = plugin_url + '?' + urlencode(params)
        log(f"🎯 Playing with URL: {url}")
        xbmc.executebuiltin(f'PlayMedia({url})')

    # ==================== CORE PLAYBACK ENGINE ====================

    def _play_stream(self, ident, title, tmdb_id=None, season=None, episode=None, year=None,
                    movie_details=None, episode_details=None, show_details=None,
                    silent_fail=False):
        """CORE PLAYBACK ENGINE - Actually plays a stream"""
        log(f"🔧 _play_stream: {ident} - {title}")

        try:
            link = self.websharder.get_stream_link(ident)
            if not link:
                log(f"❌ Failed to get stream link for: {ident}")
                if not silent_fail:
                    poperror("Failed to get stream link")
                return False

            token = self.websharder.token
            play_url = f"{link}|Cookie=wst={token}"

            li = xbmcgui.ListItem(path=play_url)
            li.setLabel(title)
            li.setProperty('IsPlayable', 'true')
            li.setMimeType('video/mp4')
            li.setContentLookup(False)

            info = {'title': title, 'mediatype': 'video'}
            art = {}

            if movie_details:
                info['title'] = movie_details.get('title', title)
                info['originaltitle'] = movie_details.get('original_title', '')
                if movie_details.get('release_date'):
                    info['year'] = movie_details['release_date'][:4]
                info['plot'] = movie_details.get('overview', '')
                info['rating'] = float(movie_details.get('vote_average', 0))
                info['genre'] = ', '.join([g.get('name', '') for g in movie_details.get('genres', [])])
                info['duration'] = movie_details.get('runtime', 0)
                info['mediatype'] = 'movie'

                if movie_details.get('poster_path'):
                    poster = f"https://image.tmdb.org/t/p/w500{movie_details['poster_path']}"
                    fanart = f"https://image.tmdb.org/t/p/original{movie_details.get('backdrop_path', movie_details['poster_path'])}"
                    art = {'poster': poster, 'thumb': poster, 'fanart': fanart}

            elif episode_details and show_details:
                info['title'] = episode_details.get('name', title)
                info['tvshowtitle'] = show_details.get('name', '')
                info['season'] = int(season) if season else 0
                info['episode'] = int(episode) if episode else 0
                info['plot'] = episode_details.get('overview', '')
                info['rating'] = float(episode_details.get('vote_average', 0))
                info['aired'] = episode_details.get('air_date', '')
                info['mediatype'] = 'episode'

                if episode_details.get('still_path'):
                    thumb = f"https://image.tmdb.org/t/p/w500{episode_details['still_path']}"
                    art['thumb'] = thumb
                if show_details.get('poster_path'):
                    poster = f"https://image.tmdb.org/t/p/w500{show_details['poster_path']}"
                    art['poster'] = poster
                if show_details.get('backdrop_path'):
                    fanart = f"https://image.tmdb.org/t/p/original{show_details['backdrop_path']}"
                    art['fanart'] = fanart

            li.setInfo('video', info)
            li.setArt(art)

            # ===== FORCE PREFERRED AUDIO LANGUAGE =====
            preferred_lang = self.addon.getSetting('preferred_language') or 'Any'
            if preferred_lang != 'Any':
                lang_map = {
                    'English': 'eng',
                    'Czech': 'cze',
                    'Croatian': 'hrv',
                    'Slovak': 'slo',
                    'Serbian': 'srp'
                }
                lang_code = lang_map.get(preferred_lang, 'eng')
                
                # Set ALL possible properties to force audio language
                li.setProperty('audio_language_preference', lang_code)
                li.setProperty('prefer_audio_language', 'true')
                li.setProperty('inputstream.adaptive.play_audio_language', lang_code)
                li.setProperty('ForceAudioLanguage', lang_code)
                
                log(f"🔊 FORCING audio language: {preferred_lang} ({lang_code})")
            else:
                log(f"🔊 No audio language preference set")

            # Subtitles
            subtitles_enabled = self.addon.getSetting('subtitles_enabled') == 'true'
            if subtitles_enabled and tmdb_id:
                subtitle_file = self.opensubtitles.search_subtitles(
                    tmdb_id=tmdb_id, title=title, season=season, episode=episode, year=year
                )
                if subtitle_file and os.path.exists(subtitle_file):
                    li.setSubtitles([subtitle_file])
                    log(f"📝 Added subtitles: {subtitle_file}")

            log(f"🚀 setResolvedUrl with handle: {self.handle}")
            xbmcplugin.setResolvedUrl(self.handle, True, li)

            # Wait for playback to start
            xbmc.sleep(2000)
            
            player = xbmc.Player()
            if player.isPlaying():
                # Try to switch to preferred audio language
                if preferred_lang != 'Any':
                    try:
                        lang_code = lang_map.get(preferred_lang, 'eng')
                        audio_streams = player.getAvailableAudioStreams()
                        log(f"🔊 Available audio streams: {audio_streams}")
                        
                        for i, stream in enumerate(audio_streams):
                            if stream and lang_code.lower() in stream.lower():
                                log(f"🔊 Found {preferred_lang} audio at index {i}, selecting...")
                                player.setAudioStream(i)
                                break
                        else:
                            # Try index 1 if we can't find by language
                            if len(audio_streams) > 1:
                                log(f"🔊 {preferred_lang} not found by name, trying stream 1")
                                player.setAudioStream(1)
                    except Exception as e:
                        log(f"⚠️ Could not switch audio track: {str(e)}")

                log(f"✅ SUCCESS: Playback started successfully")
                return True
            else:
                log(f"❌ FAILURE: Playback did not start")
                return False

        except Exception as e:
            log(f"❌ EXCEPTION in _play_stream: {str(e)}")
            if not silent_fail:
                poperror(f"Stream error: {str(e)[:50]}")
            return False

    # ==================== STREAM RANKING & LANGUAGE DETECTION ====================

    def detect_audio_languages(self, filename):
        """Detect audio languages from filename"""
        if not filename:
            return []
        filename_lower = filename.lower()
        languages = []
        lang_patterns = [
            (r'cz\.|czech|česky|cesky|\[cz\]|\(cz\)|\scz\s|\.cz\.|cz\s+audio|cz\s+dabing|cz\s+', 'Czech', 100),
            (r'sk\.|slovak|slovensky|\[sk\]|\(sk\)|\ssk\s|\.sk\.', 'Slovak', 90),
            (r'en\.|english|\[en\]|\(en\)|\sen\s|\.en\.', 'English', 80),
            (r'hr\.|croatian|\[hr\]|\(hr\)|\shr\s|\.hr\.', 'Croatian', 70),
            (r'sr\.|serbian|\[sr\]|\(sr\)|\ssr\s|\.sr\.', 'Serbian', 70),
        ]
        if 'multi' in filename_lower or 'vícejazyčný' in filename_lower:
            languages.append(('Multi', 50))
        for pattern, lang, priority in lang_patterns:
            if re.search(pattern, filename_lower):
                languages.append((lang, priority))
        unique_langs = {}
        for lang, priority in languages:
            if lang not in unique_langs or priority > unique_langs[lang]:
                unique_langs[lang] = priority
        sorted_langs = sorted(unique_langs.items(), key=lambda x: x[1], reverse=True)
        return [lang for lang, _ in sorted_langs]

    def rank_streams(self, streams):
        """Rank streams by quality and language preferences"""
        if not streams:
            return []

        preferred_lang = self.addon.getSetting('preferred_language') or 'Any'
        max_quality = self.addon.getSetting('max_quality') or '4K'
        autoplay_resolution = self.addon.getSetting('autoplay_resolution') or '1080p'
        prefer_hdr = self.addon.getSetting('prefer_hdr') == 'true'

        quality_scores = {'4K HDR': 100, '4K': 90, '1080p': 70, '720p': 50, 'SD': 30}
        max_quality_score = {'4K': 100, '1080p': 70, '720p': 50, '480p': 30}.get(max_quality, 100)
        target_quality_score = {'4K': 90, '1080p': 70, '720p': 50, '480p': 30}.get(autoplay_resolution, 70)

        ranked_streams = []
        for i, stream in enumerate(streams):
            score = 0
            quality = stream.get('quality', 'SD')
            quality_score = quality_scores.get(quality, 30)
            filename = stream.get('filename', '')
            languages = self.detect_audio_languages(filename)
            stream['languages'] = languages

            # Quality scoring
            if quality_score <= max_quality_score:
                diff = abs(quality_score - target_quality_score)
                if diff == 0:
                    score += 100
                elif diff == 20:
                    score += 80
                elif diff == 40:
                    score += 60
                else:
                    score += 40 - diff
            else:
                score -= 50

            # ===== LANGUAGE SCORING - STRONGLY PREFER USER SELECTION =====
            if preferred_lang != 'Any':
                # DIRECT MATCH - HUGE BOOST
                if preferred_lang in languages:
                    score += 500  # Massive boost for exact match
                    if languages and languages[0] == preferred_lang:
                        score += 200  # Extra if it's the primary track
                    log(f"🎯 Found {preferred_lang} stream: +700 score")
                else:
                    # No match - small bonus for any audio
                    if languages:
                        score += 20
            else:
                # "Any" language - prefer Czech/Slovak for this addon's user base
                if 'Czech' in languages:
                    score += 100
                elif 'Slovak' in languages:
                    score += 80
                elif languages:
                    score += 40
                else:
                    score += 10

            # HDR preference
            if stream.get('hdr', False):
                if prefer_hdr:
                    score += 50
                else:
                    score -= 20

            # Size-based scoring
            try:
                size_mb = int(stream.get('size', 0)) / (1024 * 1024)
                if size_mb > 0:
                    size_score = min(30, size_mb / 100)
                    score += size_score
            except:
                pass

            # Multi-language bonus
            if len(languages) > 1:
                score += 15
            if 'Multi' in languages:
                score += 25

            ranked_streams.append({
                'stream': stream,
                'score': score,
                'quality_score': quality_score,
                'languages': languages,
                'index': i
            })

        ranked_streams.sort(key=lambda x: x['score'], reverse=True)
        
        log(f"🎯 Preferred language setting: {preferred_lang}")
        for i, rs in enumerate(ranked_streams[:5]):
            log(f"   #{i+1}: Score={rs['score']}, Quality={rs['stream'].get('quality')}, "
                f"Languages={rs['languages']}")
        
        return ranked_streams
