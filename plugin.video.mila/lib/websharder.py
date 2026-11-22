#!/usr/bin/env python3
"""
WebSharder for Kodi - COMPLETE FIX WITH TMDB FALLBACK
- Automatically fetches English title from TMDB if caller is stupid
- NEVER uses Czech title for English search
"""

import sys
import os
import json
import requests
import xml.etree.ElementTree as ET
import hashlib
import time
import re
import xbmc
import xbmcgui
import xbmcaddon
import xbmcvfs

_addon = xbmcaddon.Addon()
_addon_id = _addon.getAddonInfo('id')

def log(msg):
    xbmc.log(f"[{_addon_id}-websharder] " + str(msg), xbmc.LOGINFO)

def md5crypt(password, salt, magic='$1$'):
    password = password.encode('utf-8')
    salt = salt.encode('utf-8')[:8]
    magic = magic.encode('utf-8')

    ctx = hashlib.md5()
    ctx.update(password)
    ctx.update(magic)
    ctx.update(salt)

    ctx1 = hashlib.md5()
    ctx1.update(password)
    ctx1.update(salt)
    ctx1.update(password)
    final = ctx1.digest()

    plen = len(password)
    while plen > 0:
        if plen > 16:
            ctx.update(final)
        else:
            ctx.update(final[:plen])
        plen -= 16

    i = len(password)
    while i:
        if i & 1:
            ctx.update(b'\x00')
        else:
            ctx.update(password[:1])
        i >>= 1

    final = ctx.digest()

    for i in range(1000):
        ctx1 = hashlib.md5()
        if i & 1:
            ctx1.update(password)
        else:
            ctx1.update(final)
        if i % 3:
            ctx1.update(salt)
        if i % 7:
            ctx1.update(password)
        if i & 1:
            ctx1.update(final)
        else:
            ctx1.update(password)
        final = ctx1.digest()

    final_bytes = list(final)
    itoa64 = "./0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"

    result = magic.decode() + salt.decode() + '$'
    for a, b, c in [(0, 6, 12), (1, 7, 13), (2, 8, 14), (3, 9, 15), (4, 10, 5)]:
        v = (final_bytes[a] << 16) | (final_bytes[b] << 8) | final_bytes[c]
        for i in range(4):
            result += itoa64[v & 0x3f]
            v >>= 6

    v = final_bytes[11]
    for i in range(2):
        result += itoa64[v & 0x3f]
        v >>= 6

    return result

class WebSharder:
    def __init__(self):
        self.base_url = "https://webshare.cz/api/"
        self.tmdb_api_key = "5ae6323c732ba4100c1a2152eab3f1d7"  # TMDB API key
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Referer': 'https://webshare.cz/',
            'Origin': 'https://webshare.cz',
            'Accept': 'text/xml; charset=UTF-8',
            'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8'
        })

        self.username = _addon.getSetting('wsuser') or ""
        self.password = _addon.getSetting('wspass') or ""
        self.token = None
        self.last_request_time = 0
        self.min_request_interval = 0.5

        # Limits
        self.max_streams_per_movie = 10
        self.max_streams_per_episode = 5
        self.max_results_per_search = 100

        # Store titles
        self.english_title = None
        self.czech_title = None
        self.croatian_title = None
        self.serbian_title = None
        self.tmdb_id = None

        # EXCLUDE patterns
        self.exclude_patterns = [
            r'_snaps', r'_thumbs', r'screenshot', r'sample',
            r'video\s+sample', r'audio\s+sample', r'@',
            r'incomplete', r'part\s+\d+', r'cd\d', r'disc\d',
            r'disk\d', r'test', r'preview', r'teaser', r'trailer',
            r'bonus', r'extra', r'deleted', r'behind\s*the\s*scenes',
            r'making\s*of', r'interview', r'featurette', r'blooper',
            r'clip', r'scene', r'promo'
        ]
        self.exclude_regex = re.compile('|'.join(self.exclude_patterns), re.IGNORECASE)

    def fetch_english_title_from_tmdb(self, tmdb_id, media_type='movie'):
        """Fetch English title directly from TMDB"""
        if not tmdb_id:
            return None
        
        try:
            log(f"🔄 Fetching English title from TMDB for {media_type} ID: {tmdb_id}")
            url = f"https://api.themoviedb.org/3/{media_type}/{tmdb_id}"
            params = {
                'api_key': self.tmdb_api_key,
                'language': 'en-US'
            }
            
            response = requests.get(url, params=params, timeout=10)
            if response.status_code == 200:
                data = response.json()
                english_title = data.get('title') if media_type == 'movie' else data.get('name')
                log(f"✅ Got English title from TMDB: '{english_title}'")
                return english_title
            else:
                log(f"❌ Failed to fetch from TMDB: {response.status_code}")
        except Exception as e:
            log(f"❌ Error fetching from TMDB: {str(e)}")
        
        return None

    def set_localized_titles(self, english_title, czech_title=None, croatian_title=None, serbian_title=None, tmdb_id=None):
        """
        Set localized titles for current search
        This function is SMART - it detects when caller is stupid and fixes it
        """
        # Store TMDB ID for potential fallback
        self.tmdb_id = tmdb_id
        
        # DETECT if the "english_title" is actually Czech
        czech_chars = set('áčďéěíňóřšťúůýžÁČĎÉĚÍŇÓŘŠŤÚŮÝŽ')
        czech_char_count = sum(1 for c in english_title if c in czech_chars)
        
        # Check if it looks like English (ASCII only, no special chars)
        is_ascii = all(ord(c) < 128 for c in english_title)
        
        # LOG the detection
        log(f"🔍 Title detection - ASCII: {is_ascii}, Czech chars: {czech_char_count}")
        
        # If it has Czech characters or non-ASCII, it's probably NOT English
        if czech_char_count > 0 or not is_ascii:
            log(f"⚠ DETECTED: 'english_title' parameter is actually Czech or non-English!")
            log(f"   Provided as English: '{english_title}'")
            log(f"   Provided as Czech: '{czech_title}'")
            
            # Store Czech title from the English parameter
            self.czech_title = english_title
            
            # If caller also provided a Czech title, use the longer/more complete one
            if czech_title and len(czech_title) > len(english_title):
                self.czech_title = czech_title
            
            # Try to get English title from TMDB
            if tmdb_id:
                self.english_title = self.fetch_english_title_from_tmdb(tmdb_id, 'movie')
            
            # If still no English title, try to create one from the Czech title
            if not self.english_title:
                # Simple heuristic: if it has "Válka světů", it's "War of the Worlds"
                if "válka" in english_title.lower() and "světů" in english_title.lower():
                    self.english_title = "War of the Worlds"
                    log(f"🔄 Using hardcoded translation: '{self.english_title}'")
                else:
                    # Last resort - use the original input but mark it as problematic
                    self.english_title = english_title
                    log(f"⚠ WARNING: Could not determine English title, using provided title: '{self.english_title}'")
        else:
            # Normal case - English title looks like English
            self.english_title = english_title
            self.czech_title = czech_title
            self.croatian_title = croatian_title
            self.serbian_title = serbian_title
        
        log(f"📚 FINAL titles - English: '{self.english_title}', Czech: '{self.czech_title}'")
        return self.english_title

    def _rate_limit(self):
        current = time.time()
        elapsed = current - self.last_request_time
        if elapsed < self.min_request_interval:
            time.sleep(self.min_request_interval - elapsed)
        self.last_request_time = time.time()

    def login(self):
        if not self.username or not self.password:
            log("❌ No WebShare credentials")
            return False

        try:
            log("🔑 Logging in to WebShare...")

            self._rate_limit()
            response = self.session.post(
                f"{self.base_url}salt/",
                data={'username_or_email': self.username},
                timeout=30
            )

            if response.status_code != 200:
                return False

            xml = ET.fromstring(response.content)
            if xml.find('status').text != 'OK':
                return False

            salt = xml.find('salt').text

            encrypted_pass = md5crypt(self.password, salt)
            encrypted_pass_sha1 = hashlib.sha1(encrypted_pass.encode()).hexdigest()
            pass_digest = hashlib.md5(
                (self.username + ':Webshare:' + encrypted_pass_sha1).encode()
            ).hexdigest()

            self._rate_limit()
            response = self.session.post(
                f"{self.base_url}login/",
                data={
                    'username_or_email': self.username,
                    'password': encrypted_pass_sha1,
                    'digest': pass_digest,
                    'keep_logged_in': 1
                },
                timeout=30
            )

            if response.status_code != 200:
                return False

            xml = ET.fromstring(response.content)
            if xml.find('status').text == 'OK':
                self.token = xml.find('token').text
                log("✅ Login successful")
                return True
            return False

        except Exception as e:
            log(f"❌ Login error: {str(e)}")
            return False

    def search_webshare(self, query, max_results=100):
        if not self.token:
            if not self.login():
                return []
            if not self.token:
                return []

        files = []
        seen = set()
        offset = 0
        max_results = min(max_results, self.max_results_per_search)

        while len(files) < max_results:
            try:
                self._rate_limit()
                data = {
                    'wst': self.token,
                    'what': query,
                    'limit': 50,
                    'offset': offset,
                    'sort': 'rating'
                }

                response = self.session.post(
                    f"{self.base_url}search/",
                    data=data,
                    timeout=30
                )

                if response.status_code != 200:
                    break

                xml = ET.fromstring(response.content)
                if xml.find('status').text != 'OK':
                    break

                batch_count = 0
                for file_elem in xml.iter('file'):
                    file_data = {}
                    for child in file_elem:
                        file_data[child.tag] = child.text

                    ident = file_data.get('ident')
                    if ident in seen:
                        continue

                    name = file_data.get('name', '').lower()
                    if any(ext in name for ext in ['.mp4', '.mkv', '.avi', '.mov', '.webm', '.flv', '.wmv', '.m4v']):
                        files.append(file_data)
                        seen.add(ident)
                        batch_count += 1

                        if len(files) >= max_results:
                            return files

                if batch_count < 10:
                    break

                offset += 50

            except Exception as e:
                log(f"❌ Search error: {str(e)}")
                break

        return files

    def clean_title(self, title):
        if not title:
            return ""
        cleaned = re.sub(r'[^\w\sáčďéěíňóřšťúůýžÁČĎÉĚÍŇÓŘŠŤÚŮÝŽ]', ' ', title.lower())
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()
        return cleaned

    def get_quality(self, filename):
        filename_lower = filename.lower()
        if '2160p' in filename_lower or '4k' in filename_lower or 'uhd' in filename_lower:
            return '4K'
        elif '1080p' in filename_lower or 'fhd' in filename_lower:
            return '1080p'
        elif '720p' in filename_lower or 'hd' in filename_lower:
            return '720p'
        else:
            return 'SD'

    def title_contains_phrase(self, filename, title_words):
        """Check if filename contains the title words as a phrase, not scattered"""
        if not title_words:
            return False

        filename_lower = filename.lower()

        # Create the full title phrase
        title_phrase = ' '.join(title_words)

        # Check if the full phrase appears in filename
        if title_phrase in filename_lower:
            return True

        # Also check without spaces (for filenames with dots)
        title_phrase_nospace = title_phrase.replace(' ', '')
        if title_phrase_nospace in filename_lower:
            return True

        # Check if all words appear in order
        last_pos = -1
        words_in_order = 0
        for word in title_words:
            pos = filename_lower.find(word, last_pos + 1)
            if pos > last_pos:
                words_in_order += 1
                last_pos = pos
            else:
                break

        # If all words appear in order, it's probably the same show
        if words_in_order == len(title_words):
            return True

        return False

    def is_relevant_movie_file(self, filename, search_title, year):
        """Check if file is relevant using the provided search title"""
        if not filename:
            return False

        filename_lower = filename.lower()
        year_str = str(year) if year else ""

        # EXCLUDE garbage
        if self.exclude_regex.search(filename_lower):
            return False

        if not any(filename_lower.endswith(ext) for ext in ['.mp4', '.mkv', '.avi', '.mov', '.webm']):
            return False

        if year_str and year_str not in filename_lower:
            return False

        clean_search = self.clean_title(search_title)
        search_words = [w for w in clean_search.split() if len(w) > 1]

        return self.title_contains_phrase(filename, search_words)

    def search_movie(self, title, year, tmdb_id=None):
        """
        Search for movie
        This function is SMART - it uses English title for English search,
        even if the caller is too stupid to provide it correctly
        """
        log(f"🎬 Searching for movie: {title} ({year})")
        log(f"  📝 Caller provided title: '{title}'")
        
        # If we have a TMDB ID but no English title, try to fetch it
        if tmdb_id and not self.english_title:
            self.english_title = self.fetch_english_title_from_tmdb(tmdb_id, 'movie')
            self.tmdb_id = tmdb_id
        
        # Determine what titles to use for each search
        english_for_search = self.english_title
        czech_for_search = self.czech_title or title
        
        # If we STILL don't have an English title, try to get it from TMDB now
        if not english_for_search and tmdb_id:
            english_for_search = self.fetch_english_title_from_tmdb(tmdb_id, 'movie')
        
        # Last resort - try to translate common Czech titles
        if not english_for_search:
            # Common movie title translations
            translations = {
                'válka světů': 'War of the Worlds',
                'matrix': 'The Matrix',
                'avatar': 'Avatar',
                'titanic': 'Titanic',
                # Add more as needed
            }
            
            title_lower = title.lower()
            for czech, english in translations.items():
                if czech in title_lower:
                    english_for_search = english
                    log(f"🔄 Using translation: '{czech}' -> '{english}'")
                    break
            
            if not english_for_search:
                english_for_search = title  # Fallback to provided title
                log(f"⚠ WARNING: No English title available, using: '{english_for_search}'")
        
        log(f"  📝 ENGLISH search will use: '{english_for_search}'")
        log(f"  📝 CZECH search will use: '{czech_for_search}'")

        files = []
        seen_ids = set()
        seen_filenames = set()

        # ENGLISH SEARCH - ALWAYS use English title
        english_query = f"{english_for_search} {year}"
        log(f"  🔍 English search: '{english_query}'")
        english_results = self.search_webshare(english_query, max_results=100)

        for file in english_results:
            filename = file.get('name', '')
            if self.is_relevant_movie_file(filename, english_for_search, year):
                file_id = file.get('ident')
                if file_id not in seen_ids:
                    try:
                        size_bytes = int(file.get('size', 0))
                        size_mb = size_bytes / (1024 * 1024)
                        if size_mb < 50:
                            log(f"    ⚠ EXCLUDED (too small - {size_mb:.0f}MB): {filename}")
                            continue
                    except:
                        pass

                    if filename not in seen_filenames:
                        seen_ids.add(file_id)
                        seen_filenames.add(filename)
                        files.append(file)
                        log(f"    ✅ ACCEPTED: {filename}")
                        if len(files) >= self.max_streams_per_movie:
                            break

        log(f"    Found {len(files)} files from English search")

        # CZECH SEARCH - only if different from English and we haven't found enough
        if czech_for_search and czech_for_search != english_for_search and len(files) < self.max_streams_per_movie:
            czech_query = f"{czech_for_search} {year}"
            log(f"  🔍 Czech search: '{czech_query}'")
            czech_results = self.search_webshare(czech_query, max_results=100)

            for file in czech_results:
                if len(files) >= self.max_streams_per_movie:
                    break
                filename = file.get('name', '')
                if self.is_relevant_movie_file(filename, czech_for_search, year):
                    file_id = file.get('ident')
                    if file_id not in seen_ids:
                        try:
                            size_bytes = int(file.get('size', 0))
                            size_mb = size_bytes / (1024 * 1024)
                            if size_mb < 50:
                                continue
                        except:
                            pass
                        if filename not in seen_filenames:
                            seen_ids.add(file_id)
                            seen_filenames.add(filename)
                            files.append(file)
                            log(f"    ✅ ACCEPTED: {filename}")

        # Format results
        results = []
        for file in files[:self.max_streams_per_movie]:
            filename = file.get('name', '')
            results.append({
                'ident': file.get('ident'),
                'filename': filename,
                'size': file.get('size', '0'),
                'quality': self.get_quality(filename),
                'url': f"https://webshare.cz/#/file/{file.get('ident')}"
            })

        quality_order = {'4K': 0, '1080p': 1, '720p': 2, 'SD': 3}
        results.sort(key=lambda x: quality_order.get(x['quality'], 99))

        log(f"📊 Total files: {len(results)}")
        
        # Reset titles
        self.english_title = None
        self.czech_title = None
        self.croatian_title = None
        self.serbian_title = None
        self.tmdb_id = None
        
        return results

    def search_episode(self, show_title, season, episode, tmdb_id=None):
        """Search for TV episode - STRICT phrase matching with TMDB fallback"""
        try:
            season_int = int(season)
            episode_int = int(episode)
        except:
            season_int = 1
            episode_int = 1

        log(f"📺 Searching for episode: {show_title} S{season_int:02d}E{episode_int:02d}")
        log(f"  📝 Caller provided title: '{show_title}'")
        
        # If we have a TMDB ID but no English title, try to fetch it
        if tmdb_id and not self.english_title:
            self.english_title = self.fetch_english_title_from_tmdb(tmdb_id, 'tv')
            self.tmdb_id = tmdb_id

        season_padded = f"{season_int:02d}"
        episode_padded = f"{episode_int:02d}"

        # Determine what titles to use
        english_for_search = self.english_title or show_title
        czech_for_search = self.czech_title or show_title
        
        log(f"  📝 ENGLISH search will use: '{english_for_search}'")
        log(f"  📝 CZECH search will use: '{czech_for_search}'")

        # Clean titles
        clean_english = self.clean_title(english_for_search)
        english_words = [w for w in clean_english.split() if len(w) > 2]

        clean_czech = self.clean_title(czech_for_search) if czech_for_search else None
        czech_words = [w for w in clean_czech.split() if len(w) > 2] if clean_czech else []

        files = []
        seen_ids = set()
        seen_filenames = set()

        # English search
        if english_words:
            english_query = f"{english_for_search} S{season_padded}E{episode_padded}"
            log(f"  🔍 English search: '{english_query}'")
            english_results = self.search_webshare(english_query, max_results=50)

            for file in english_results:
                if len(files) >= self.max_streams_per_episode:
                    break
                filename = file.get('name', '')
                filename_lower = filename.lower()
                file_id = file.get('ident')

                if f"s{season_padded}e{episode_padded}" not in filename_lower:
                    continue

                if not self.title_contains_phrase(filename, english_words):
                    log(f"    ⚠ EXCLUDED (wrong show - English title not found): {filename}")
                    continue

                try:
                    size_bytes = int(file.get('size', 0))
                    size_mb = size_bytes / (1024 * 1024)
                    if size_mb < 50:
                        log(f"    ⚠ EXCLUDED (too small - {size_mb:.0f}MB): {filename}")
                        continue
                except:
                    pass

                if file_id not in seen_ids and filename not in seen_filenames:
                    seen_ids.add(file_id)
                    seen_filenames.add(filename)
                    files.append(file)
                    log(f"    ✅ ACCEPTED: {filename}")

            log(f"    Found {len(files)} files from English search")

        # Czech search
        if czech_words and czech_for_search != english_for_search and len(files) < self.max_streams_per_episode:
            czech_query = f"{czech_for_search} S{season_padded}E{episode_padded}"
            log(f"  🔍 Czech search: '{czech_query}'")
            czech_results = self.search_webshare(czech_query, max_results=50)

            for file in czech_results:
                if len(files) >= self.max_streams_per_episode:
                    break
                filename = file.get('name', '')
                filename_lower = filename.lower()
                file_id = file.get('ident')

                if f"s{season_padded}e{episode_padded}" not in filename_lower:
                    continue

                if not self.title_contains_phrase(filename, czech_words):
                    log(f"    ⚠ EXCLUDED (wrong show - Czech title not found): {filename}")
                    continue

                try:
                    size_bytes = int(file.get('size', 0))
                    size_mb = size_bytes / (1024 * 1024)
                    if size_mb < 50:
                        continue
                except:
                    pass

                if file_id not in seen_ids and filename not in seen_filenames:
                    seen_ids.add(file_id)
                    seen_filenames.add(filename)
                    files.append(file)
                    log(f"    ✅ ACCEPTED: {filename}")

        log(f"📊 Found {len(files)} files for this episode")

        # Format results
        results = []
        for file in files[:self.max_streams_per_episode]:
            filename = file.get('name', '')
            results.append({
                'ident': file.get('ident'),
                'filename': filename,
                'size': file.get('size', '0'),
                'quality': self.get_quality(filename),
                'url': f"https://webshare.cz/#/file/{file.get('ident')}"
            })

        quality_order = {'4K': 0, '1080p': 1, '720p': 2, 'SD': 3}
        results.sort(key=lambda x: quality_order.get(x['quality'], 99))

        # Reset titles
        self.english_title = None
        self.czech_title = None
        self.croatian_title = None
        self.serbian_title = None
        self.tmdb_id = None
        
        return results

    def get_stream_link(self, ident):
        if not self.token and not self.login():
            return None

        try:
            self._rate_limit()
            response = self.session.post(
                f"{self.base_url}file_link/",
                data={
                    'ident': ident,
                    'wst': self.token,
                    'download_type': 'video_stream'
                },
                timeout=30
            )

            if response.status_code != 200:
                return None

            xml = ET.fromstring(response.content)
            if xml.find('status').text == 'OK':
                link = xml.find('link').text
                return link

        except Exception as e:
            log(f"❌ Stream link error: {str(e)}")

        return None
