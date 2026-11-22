# -*- coding: utf-8 -*-
# OpenSubtitles.com API v1 - WORKING AUTO-DOWNLOADER
# NEVER deletes existing subtitles, only adds missing ones
import os
import hashlib
import re
import requests
import xbmc
import xbmcaddon
import xbmcvfs
from lib.utils import log

_addon = xbmcaddon.Addon()

class OpenSubtitles:
    def __init__(self):
        self.base_url = "https://api.opensubtitles.com/api/v1"
        self.api_key = "zCGm5bsaqSEbglUDxYjPspRDkZI3Cjef"
        self.token = None
        self.user_agent = "MILA-Kodi-Addon/2.0.0"

        self.session = requests.Session()
        self.session.headers.update({
            'Api-Key': self.api_key,
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'User-Agent': self.user_agent
        })

        # Subtitle cache directory - NEVER DELETES EXISTING FILES
        self.cache_dir = xbmcvfs.translatePath(_addon.getSetting('subtitle_folder') or 'special://temp/mila_subs/')
        if not os.path.exists(self.cache_dir):
            os.makedirs(self.cache_dir)

    def get_kodi_language(self):
        """Get Kodi interface language - returns ISO 639-1 codes (cs, hr, en, sk, etc)"""
        try:
            lang = xbmc.getLanguage(xbmc.ISO_639_1).lower()
            log(f"OpenSubtitles: Kodi language detected: {lang}")
            
            # Map to OpenSubtitles supported languages
            # Full list at https://www.opensubtitles.com/docs/api/html/index.htm
            supported_langs = ['cs', 'hr', 'en', 'sk', 'pl', 'hu', 'de', 'fr', 'es', 'it', 'sr', 'sl']
            
            if lang in supported_langs:
                return lang
            else:
                log(f"OpenSubtitles: Language {lang} not supported, falling back to en")
                return 'en'
        except:
            return 'en'

    def search_subtitles(self, tmdb_id, title, season=None, episode=None, year=None):
        """
        Search and return path to best subtitle file (string) or None
        NEVER deletes existing subtitles - only adds missing ones
        """
        # Check if subtitles are enabled
        enabled = _addon.getSetting('subtitles_enabled') == 'true'
        if not enabled:
            log("OpenSubtitles: Subtitles disabled in settings")
            return None

        # Get language from Kodi
        language = self.get_kodi_language()
        
        # Check if we already have subtitles for this language
        clean_title = self._clean_filename(title)
        
        if season is not None and episode is not None:
            # Episode subtitle pattern
            subtitle_patterns = [
                f"{clean_title}.S{int(season):02d}E{int(episode):02d}.{language}.srt",
                f"{clean_title}.{int(season)}x{int(episode):02d}.{language}.srt",
                f"{clean_title}.S{int(season)}E{int(episode)}.{language}.srt"
            ]
        else:
            # Movie subtitle pattern
            subtitle_patterns = [
                f"{clean_title}.{language}.srt",
                f"{clean_title}.{year}.{language}.srt" if year else None
            ]
            subtitle_patterns = [p for p in subtitle_patterns if p]
        
        # Check if any subtitle already exists in cache
        for pattern in subtitle_patterns:
            cached_file = os.path.join(self.cache_dir, pattern)
            if os.path.exists(cached_file):
                log(f"OpenSubtitles: Using existing subtitle: {pattern}")
                return cached_file

        log(f"OpenSubtitles: No existing subtitle found, searching: {title} [{language}]")

        params = {
            'tmdb_id': tmdb_id,
            'languages': language
        }

        if season and episode:
            params['season_number'] = int(season)
            params['episode_number'] = int(episode)
            log(f"OpenSubtitles: Searching TV: {title} S{season}E{episode} [{language}]")
        else:
            log(f"OpenSubtitles: Searching movie: {title} ({year}) [{language}]")

        try:
            response = self.session.get(
                f"{self.base_url}/subtitles",
                params=params,
                timeout=15
            )

            if response.status_code != 200:
                log(f"OpenSubtitles: API error {response.status_code}")
                return None

            data = response.json()
            subtitles = data.get('data', [])

            # If no subtitles found in desired language, try English as fallback
            if not subtitles and language != 'en':
                log(f"OpenSubtitles: No {language} subs, trying English fallback")
                params['languages'] = 'en'
                response = self.session.get(
                    f"{self.base_url}/subtitles",
                    params=params,
                    timeout=15
                )
                if response.status_code == 200:
                    data = response.json()
                    subtitles = data.get('data', [])
                    if subtitles:
                        language = 'en'  # Update language for filename

            if not subtitles:
                log(f"OpenSubtitles: No subtitles found for: {title}")
                return None

            best_sub = self._get_best_subtitle(subtitles)
            if best_sub:
                return self._download_subtitle(best_sub, title, season, episode, language)

            return None

        except requests.exceptions.Timeout:
            log(f"OpenSubtitles: Search timeout")
            return None
        except requests.exceptions.ConnectionError:
            log(f"OpenSubtitles: Connection error")
            return None
        except Exception as e:
            log(f"OpenSubtitles: Search error - {str(e)}")
            return None

    def _clean_filename(self, title):
        """Clean title for filename - safe for filesystem"""
        clean_title = re.sub(r'[^\w\s-]', '', title)
        clean_title = re.sub(r'[:\-]', ' ', clean_title)
        clean_title = ' '.join(clean_title.split())
        clean_title = clean_title.replace(' ', '.')
        return clean_title

    def _get_best_subtitle(self, subtitles):
        """Select best subtitle based on quality"""
        best_score = 0
        best_sub = None

        for sub_data in subtitles:
            attrs = sub_data.get('attributes', {})
            score = 0

            # Prefer SRT format (universal)
            if attrs.get('format') == 'srt':
                score += 50
            elif attrs.get('format') == 'vtt':
                score += 30  # VTT works too

            # Prefer non-hearing impaired (cleaner)
            if not attrs.get('hearing_impaired', False):
                score += 30

            # Prefer trusted uploaders (more reliable)
            if attrs.get('uploader', {}).get('trusted'):
                score += 20

            # Download count bonus (popular = good)
            download_count = attrs.get('download_count', 0)
            score += min(download_count / 500, 30)

            # FPS match bonus (less conversion needed)
            if attrs.get('fps'):
                score += 10

            # Subtitle rating
            rating = attrs.get('ratings', 0)
            if rating:
                score += rating

            if score > best_score:
                best_score = score
                best_sub = sub_data
                log(f"OpenSubtitles: Candidate score {score} for {attrs.get('files', [{}])[0].get('file_name', 'unknown')}")

        if best_sub:
            log(f"OpenSubtitles: Selected subtitle with score {best_score}")
        
        return best_sub

    def _download_subtitle(self, subtitle_data, title, season=None, episode=None, language='en'):
        """Download subtitle with sensible filename - NEVER overwrites existing"""
        try:
            attrs = subtitle_data.get('attributes', {})
            files = attrs.get('files', [])

            if not files:
                log(f"OpenSubtitles: No files in subtitle data")
                return None

            file_id = files[0].get('file_id')
            if not file_id:
                log(f"OpenSubtitles: No file_id")
                return None

            # Get language code
            lang_code = attrs.get('language', language)
            
            # Create sensible filename
            clean_title = self._clean_filename(title)

            if season is not None and episode is not None:
                filename = f"{clean_title}.S{int(season):02d}E{int(episode):02d}.{lang_code}.srt"
            else:
                filename = f"{clean_title}.{lang_code}.srt"

            cached_file = os.path.join(self.cache_dir, filename)

            # DOUBLE CHECK: If file already exists, use it (NEVER overwrite)
            if os.path.exists(cached_file):
                log(f"OpenSubtitles: File already exists (double-check): {filename}")
                return cached_file

            log(f"OpenSubtitles: Downloading: {filename}")

            # Get download link
            response = self.session.post(
                f"{self.base_url}/download",
                json={'file_id': file_id},
                timeout=30
            )

            if response.status_code != 200:
                log(f"OpenSubtitles: Download API error {response.status_code}")
                return None

            download_url = response.json().get('link')
            if not download_url:
                log(f"OpenSubtitles: No download link in response")
                return None

            # Download subtitle file
            sub_response = requests.get(
                download_url,
                headers={'User-Agent': self.user_agent},
                timeout=30
            )

            if sub_response.status_code == 200:
                # Write to temp file first to avoid partial writes
                temp_file = cached_file + '.tmp'
                with open(temp_file, 'wb') as f:
                    f.write(sub_response.content)
                
                # Move temp file to final destination
                os.rename(temp_file, cached_file)
                
                log(f"OpenSubtitles: Successfully downloaded: {filename}")
                return cached_file
            else:
                log(f"OpenSubtitles: Download failed {sub_response.status_code}")
                return None

        except Exception as e:
            log(f"OpenSubtitles: Download error - {str(e)}")
            return None

    def get_available_languages(self, tmdb_id, season=None, episode=None):
        """Check what subtitle languages are available (useful for UI)"""
        params = {'tmdb_id': tmdb_id}
        if season and episode:
            params['season_number'] = int(season)
            params['episode_number'] = int(episode)

        try:
            response = self.session.get(
                f"{self.base_url}/subtitles",
                params=params,
                timeout=15
            )

            if response.status_code != 200:
                return []

            data = response.json()
            subtitles = data.get('data', [])
            
            languages = set()
            for sub in subtitles:
                attrs = sub.get('attributes', {})
                lang = attrs.get('language')
                if lang:
                    languages.add(lang)
            
            return list(languages)

        except Exception as e:
            log(f"OpenSubtitles: Language check error - {str(e)}")
            return []

    def clear_cache(self):
        """Clear subtitle cache - ONLY if user explicitly requests"""
        try:
            import shutil
            if os.path.exists(self.cache_dir):
                shutil.rmtree(self.cache_dir)
                os.makedirs(self.cache_dir)
                log("OpenSubtitles: Cache cleared by user request")
                return True
        except Exception as e:
            log(f"OpenSubtitles: Clear cache error - {str(e)}")
            return False

    def get_cache_stats(self):
        """Get cache statistics"""
        try:
            if not os.path.exists(self.cache_dir):
                return {'count': 0, 'size': 0}
            
            files = [f for f in os.listdir(self.cache_dir) if f.endswith('.srt')]
            total_size = sum(os.path.getsize(os.path.join(self.cache_dir, f)) for f in files)
            
            return {
                'count': len(files),
                'size': total_size,
                'dir': self.cache_dir
            }
        except:
            return {'count': 0, 'size': 0}
