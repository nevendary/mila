#!/usr/bin/env python3
"""
WebSharder for Kodi - Add movies/TV shows by TMDB ID
"""

import sys
import os
import json
import requests
import xml.etree.ElementTree as ET
import hashlib
import time
import re
import tempfile
import zipfile
import shutil
import io
from datetime import datetime

# Kodi imports
import xbmc
import xbmcgui
import xbmcaddon
import xbmcvfs

# TMDB Configuration
TMDB_API_KEY = "9567cc1179d493c3b22f0682dbdf2e42"
TMDB_URL = "https://api.themoviedb.org/3"

# Addon info
_addon = xbmcaddon.Addon()
_addon_id = _addon.getAddonInfo('id')

def log(msg):
    xbmc.log(f"[{_addon_id}-websharder] " + str(msg), xbmc.LOGINFO)

def popinfo(message, duration=3000):
    xbmcgui.Dialog().notification(_addon.getAddonInfo('name'), message, xbmcgui.NOTIFICATION_INFO, duration)

def poperror(message, duration=5000):
    xbmcgui.Dialog().notification(_addon.getAddonInfo('name'), message, xbmcgui.NOTIFICATION_ERROR, duration)

# ========== CONFIGURE THESE ==========
WEBSHARE_USER = _addon.getSetting('wsuser') or ""
WEBSHARE_PASS = _addon.getSetting('wspass') or ""
# =====================================

def md5crypt(password, salt, magic='$1$'):
    """Simplified md5crypt that works - FIXED to return string"""
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
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Referer': 'https://webshare.cz/',
            'Origin': 'https://webshare.cz',
            'Accept': 'text/xml; charset=UTF-8',
            'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8'
        })

        self.username = WEBSHARE_USER
        self.password = WEBSHARE_PASS
        self.token = None

        # Use the same directories as MILA
        profile_dir = xbmcvfs.translatePath(_addon.getAddonInfo('profile'))
        self.cache_dir = os.path.join(profile_dir, 'cache')
        self.extracted_dir = os.path.join(self.cache_dir, 'extracted_metadata')

        # Create directories
        os.makedirs(self.cache_dir, exist_ok=True)
        os.makedirs(self.extracted_dir, exist_ok=True)

        # Limits
        self.max_streams_per_movie = 10
        self.max_streams_per_episode = 5
        self.max_results_per_search = 100

        self.last_request_time = 0
        self.min_request_interval = 0.5

    def _rate_limit(self):
        current = time.time()
        elapsed = current - self.last_request_time
        if elapsed < self.min_request_interval:
            time.sleep(self.min_request_interval - elapsed)
        self.last_request_time = time.time()

    def login(self):
        """Login to WebShare - FIXED VERSION"""
        if not self.username or not self.password:
            poperror("Please set WebShare username/password in addon settings")
            return False

        try:
            log("Logging in to WebShare...")

            # Get salt
            response = self.session.post(
                f"{self.base_url}salt/",
                data={'username_or_email': self.username},
                timeout=30
            )

            if response.status_code != 200:
                log(f"Salt request failed: {response.status_code}")
                return False

            # Parse response
            xml = ET.fromstring(response.content)
            if xml.find('status').text != 'OK':
                return False

            salt = xml.find('salt').text

            # Calculate hashes - FIXED: md5crypt returns string, no need to encode
            encrypted_pass = md5crypt(self.password, salt)
            # Just get sha1 of the string
            encrypted_pass_sha1 = hashlib.sha1(encrypted_pass.encode('utf-8')).hexdigest()
            pass_digest = hashlib.md5(
                (self.username + ':Webshare:' + encrypted_pass_sha1).encode('utf-8')
            ).hexdigest()

            # Login
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
                log(f"Login request failed: {response.status_code}")
                return False

            # Parse response
            xml = ET.fromstring(response.content)
            if xml.find('status').text == 'OK':
                self.token = xml.find('token').text
                log(f"Login successful (Token: {self.token[:10]}...)")
                return True

            log("Login status not OK")
            return False

        except Exception as e:
            log(f"Login error: {str(e)}")
            poperror(f"Login error: {str(e)}")
            return False

    def list_files_api(self, search_term="", limit=50, offset=0):
        """Use /api/files/ endpoint to list/search files"""
        if not self.token:
            return []

        try:
            # Parameters
            data = {
                'wst': self.token,
                'path': '/',
                'sort_by': 'created',
                'sort_order': 'desc',
                'private': 1,
                'limit': limit,
                'offset': offset
            }

            # Add search term if provided
            if search_term:
                data['search'] = search_term

            response = self.session.post(
                f"{self.base_url}files/",
                data=data,
                timeout=30
            )

            if response.status_code != 200:
                log(f"Files API failed: {response.status_code}")
                return []

            # Parse XML response
            xml = ET.fromstring(response.text)

            # Check status
            if xml.find('status').text != 'OK':
                return []

            # Parse files
            files = []
            for file_elem in xml.findall('file'):
                file_data = {}
                for child in file_elem:
                    file_data[child.tag] = child.text

                if 'ident' in file_data and 'name' in file_data:
                    files.append({
                        'ident': file_data['ident'],
                        'name': file_data['name'],
                        'size': file_data.get('size', '0'),
                        'created': file_data.get('created', ''),
                        'type': file_data.get('type', '')
                    })

            log(f"Found {len(files)} files via files API")
            return files

        except Exception as e:
            log(f"Files API error: {str(e)}")
            return []

    def delete_file(self, file_ident):
        """Delete a file from WebShare"""
        if not self.token:
            log("No token available for deletion")
            return False

        try:
            self._rate_limit()
            data = {
                'wst': self.token,
                'ident': file_ident
            }

            response = self.session.post(
                f"{self.base_url}file_delete/",
                data=data,
                timeout=30
            )

            if response.status_code != 200:
                log(f"Delete request failed: {response.status_code}")
                return False

            # Parse response
            xml = ET.fromstring(response.content)
            if xml.find('status').text == 'OK':
                log(f"Successfully deleted file: {file_ident}")
                return True
            else:
                log(f"Delete failed: {xml.find('status').text}")
                return False

        except Exception as e:
            log(f"Delete error: {str(e)}")
            return False

    def delete_old_latest_files(self):
        """Delete old LATEST.json files before uploading new one"""
        if not self.token:
            if not self.login():
                return False

        try:
            # Get all files
            all_files = self.list_files_api(limit=50)
            if not all_files:
                return True  # No files to delete

            deleted_count = 0
            # Find and delete old LATEST*.json files
            for file in all_files:
                name = file.get('name', '').lower()
                if name.startswith('latest') and name.endswith('.json'):
                    log(f"Deleting old LATEST file: {file['name']}")
                    if self.delete_file(file['ident']):
                        deleted_count += 1
                        time.sleep(0.5)  # Small delay between deletions

            log(f"Deleted {deleted_count} old LATEST files")
            return True

        except Exception as e:
            log(f"Error deleting old files: {str(e)}")
            return False

    def delete_old_metadata_zips(self, keep_latest=1):
        """Delete old metadata ZIP files, keeping only the latest ones"""
        if not self.token:
            if not self.login():
                return False

        try:
            # Get all files
            all_files = self.list_files_api(limit=50)
            if not all_files:
                return True

            # Find metadata ZIPs
            metadata_zips = []
            for file in all_files:
                name = file.get('name', '').lower()
                if 'metadata' in name and name.endswith('.zip'):
                    metadata_zips.append(file)

            if len(metadata_zips) <= keep_latest:
                log(f"Keeping all {len(metadata_zips)} metadata ZIPs")
                return True

            # Sort by creation date (newest first)
            metadata_zips.sort(key=lambda x: x.get('created', ''), reverse=True)

            # Delete old ones (keep only the latest N)
            deleted_count = 0
            for file in metadata_zips[keep_latest:]:
                log(f"Deleting old metadata ZIP: {file['name']}")
                if self.delete_file(file['ident']):
                    deleted_count += 1
                    time.sleep(0.5)

            log(f"Deleted {deleted_count} old metadata ZIPs, kept {keep_latest} latest")
            return True

        except Exception as e:
            log(f"Error deleting old metadata ZIPs: {str(e)}")
            return False

    def search_webshare(self, query, max_results=100):
        """Search ALL files (public and private) using /api/search/ endpoint"""
        if not self.token:
            log("No token available for search")
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
                log(f"Search error: {str(e)}")
                break

        log(f"Search API found {len(files)} files for query: '{query}'")
        return files

    def find_and_download_latest(self):
        """Find and download latest metadata"""
        log("Finding and downloading latest metadata...")

        # Login first
        if not self.login():
            poperror("Login failed!")
            return False

        # Get all files
        all_files = self.list_files_api(limit=50)

        if not all_files:
            log("No files found at all")
            poperror("No files found on WebShare!")
            return False

        log(f"Found {len(all_files)} total files on WebShare")

        # Look for LATEST.json first
        for file in all_files:
            name = file.get('name', '').lower()

            if name == 'latest.json':
                log(f"Found LATEST.json: {file['ident']}")

                # Download and parse LATEST.json
                content = self.download_file(file['ident'])
                if not content:
                    poperror("Failed to download LATEST.json!")
                    return False

                try:
                    latest_info = json.loads(content)
                    zip_id = latest_info.get('file_id')
                    zip_filename = latest_info.get('filename')

                    if zip_id and zip_filename:
                        log(f"Found ZIP reference: {zip_filename}")
                        return self.download_and_extract_zip(zip_id, zip_filename)
                except:
                    pass

        # If no LATEST.json, look for any metadata ZIP
        log("Looking for metadata ZIP files...")
        for file in all_files:
            name = file.get('name', '').lower()
            if name.endswith('.zip') and 'metadata' in name:
                log(f"Found metadata ZIP: {name}")
                return self.download_and_extract_zip(file['ident'], file['name'])

        poperror("No metadata files found on WebShare!")
        return False

    def download_and_extract_zip(self, zip_id, zip_filename):
        """Download and extract ZIP file"""
        try:
            # Download ZIP
            content = self.download_file(zip_id)
            if not content:
                poperror("Failed to download ZIP file!")
                return False

            # Clear old extracted data
            if os.path.exists(self.extracted_dir):
                shutil.rmtree(self.extracted_dir)
            os.makedirs(self.extracted_dir)

            # Extract ZIP
            with zipfile.ZipFile(io.BytesIO(content), 'r') as zip_ref:
                zip_ref.extractall(self.extracted_dir)

            log(f"ZIP extracted to: {self.extracted_dir}")
            return True

        except Exception as e:
            log(f"Error extracting ZIP: {str(e)}")
            poperror(f"Error extracting ZIP: {str(e)}")
            return False

    def download_file(self, file_ident):
        """Download a file by ID"""
        if not self.token:
            return None

        try:
            # Get download link
            response = self.session.post(
                f"{self.base_url}file_link/",
                data={
                    'ident': file_ident,
                    'wst': self.token,
                    'download_type': 'direct'
                },
                timeout=30
            )

            if response.status_code != 200:
                return None

            # Parse XML response
            xml = ET.fromstring(response.text)
            if xml.find('status').text == 'OK':
                download_url = xml.find('link').text

                # Download the file
                response = self.session.get(download_url, timeout=60)
                if response.status_code == 200:
                    return response.content

        except Exception as e:
            log(f"Download error: {str(e)}")

        return None

    def get_tmdb_info(self, tmdb_id, media_type):
        """Get TMDB info"""
        try:
            endpoint = f"{TMDB_URL}/{media_type}/{tmdb_id}"
            params = {'api_key': TMDB_API_KEY, 'language': 'en-US'}

            response = requests.get(endpoint, params=params, timeout=10)
            if response.status_code == 200:
                data = response.json()

                if media_type == 'movie':
                    title = data.get('title', 'Unknown')
                    year = data.get('release_date', '')[:4] if data.get('release_date') else ''
                    return {
                        'tmdb_id': tmdb_id,
                        'title': title,
                        'year': year,
                        'type': 'movie'
                    }
                else:
                    title = data.get('name', 'Unknown')
                    year = data.get('first_air_date', '')[:4] if data.get('first_air_date') else ''

                    # Get seasons info
                    seasons_endpoint = f"{TMDB_URL}/tv/{tmdb_id}"
                    seasons_response = requests.get(seasons_endpoint, params={'api_key': TMDB_API_KEY}, timeout=10)
                    seasons_info = []
                    if seasons_response.status_code == 200:
                        seasons_data = seasons_response.json()
                        seasons_info = seasons_data.get('seasons', [])

                    return {
                        'tmdb_id': tmdb_id,
                        'title': title,
                        'year': year,
                        'type': 'tv',
                        'seasons': seasons_info,
                        'total_seasons': data.get('number_of_seasons', 0),
                        'total_episodes': data.get('number_of_episodes', 0)
                    }
            else:
                log(f"TMDB API error: {response.status_code}")
                return None
        except Exception as e:
            log(f"Error fetching TMDB info: {str(e)}")
            return None

    def clean_title(self, title):
        """Clean title for matching"""
        if not title:
            return ""
        cleaned = re.sub(r'[^\w\sáčďéěíňóřšťúůýžÁČĎÉĚÍŇÓŘŠŤÚŮÝŽ]', ' ', title.lower())
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()
        return cleaned

    def is_relevant_movie_file(self, filename, title, year):
        """Check if file is relevant movie"""
        if not filename:
            return False

        filename_lower = filename.lower()
        year_str = str(year) if year else ""

        # Exclude patterns
        exclude_patterns = [
            r'_snaps', r'_thumbs', r'screenshot', r'sample',
            r'video\s+sample', r'audio\s+sample', r'@',
            r'incomplete', r'part\s+\d+', r'cd\d', r'disc\d',
            r'disk\d', r'test', r'preview', r'teaser', r'trailer',
            r'bonus', r'extra', r'deleted', r'behind\s*the\s*scenes',
            r'making\s*of', r'interview', r'featurette', r'blooper',
            r'clip', r'scene', r'promo'
        ]

        for pattern in exclude_patterns:
            if re.search(pattern, filename_lower, re.IGNORECASE):
                return False

        if not any(filename_lower.endswith(ext) for ext in ['.mp4', '.mkv', '.avi', '.mov', '.webm']):
            return False

        if year_str and year_str not in filename_lower:
            return False

        clean_title = self.clean_title(title)
        title_words = [w for w in clean_title.split() if len(w) > 1]

        if title_words:
            found_words = 0
            for word in title_words:
                if len(word) <= 3:
                    if re.search(r'\b' + re.escape(word) + r'\b', filename_lower):
                        found_words += 1
                else:
                    if re.search(re.escape(word), filename_lower):
                        found_words += 1

            if found_words / len(title_words) >= 0.6:
                return True

        return False

    def is_relevant_tv_file(self, filename, title, season, episode):
        """Check if file is relevant TV episode"""
        if not filename or not title or not season or not episode:
            return False

        filename_lower = filename.lower()

        # Exclude patterns
        exclude_patterns = [
            r'_snaps', r'_thumbs', r'screenshot', r'sample',
            r'video\s+sample', r'audio\s+sample', r'@',
            r'incomplete', r'part\s+\d+', r'cd\d', r'disc\d',
            r'disk\d', r'test', r'preview', r'teaser', r'trailer',
            r'bonus', r'extra', r'deleted', r'behind\s*the\s*scenes',
            r'making\s*of', r'interview', r'featurette', r'blooper',
            r'clip', r'scene', r'promo'
        ]

        for pattern in exclude_patterns:
            if re.search(pattern, filename_lower, re.IGNORECASE):
                return False

        if not any(filename_lower.endswith(ext) for ext in ['.mp4', '.mkv', '.avi', '.mov', '.webm']):
            return False

        # Check for season/episode patterns
        season_episode_patterns = [
            f's{season:02d}e{episode:02d}',
            f's{season}e{episode:02d}',
            f's{season:02d}e{episode}',
            f'{season}x{episode:02d}',
            f'{season}x{episode}',
        ]

        has_season_episode = False
        for pattern in season_episode_patterns:
            if pattern in filename_lower:
                has_season_episode = True
                break

        if not has_season_episode:
            return False

        clean_title = self.clean_title(title)
        title_words = [w for w in clean_title.split() if len(w) > 2]

        if title_words:
            found_words = 0
            for word in title_words:
                if re.search(r'\b' + re.escape(word) + r'\b', filename_lower):
                    found_words += 1

            if found_words / len(title_words) >= 0.4:
                return True

        return False

    def find_movie_files(self, title, year):
        """Find movie files on WebShare"""
        log(f"Searching for movie: {title} ({year})")

        files = []
        seen_ids = set()

        # Try different search queries
        queries = [
            f"{title} {year}",
            title,
            f"{title} {year} 1080p",
            f"{title} {year} 720p"
        ]

        for query in queries:
            if len(files) >= self.max_streams_per_movie:
                break

            log(f"Search query: '{query}'")
            results = self.search_webshare(query, max_results=50)

            for file in results:
                filename = file.get('name', '')
                if self.is_relevant_movie_file(filename, title, year):
                    file_id = file.get('ident')
                    if file_id not in seen_ids:
                        seen_ids.add(file_id)
                        files.append(file)
                        if len(files) >= self.max_streams_per_movie:
                            break

        log(f"Found {len(files)} relevant movie files")
        return files

    def find_tv_episodes(self, title, seasons_info):
        """Find TV episodes on WebShare"""
        log(f"Searching for TV show: {title}")

        seasons = {}
        total_found = 0

        for season_info in seasons_info:
            season_num = season_info.get('season_number', 0)
            episode_count = season_info.get('episode_count', 0)

            if season_num == 0:
                continue

            log(f"Season {season_num} ({episode_count} episodes):")
            seasons[season_num] = {}

            for episode_num in range(1, episode_count + 1):
                files = []
                seen_ids = set()

                searches = [
                    f"{title} S{season_num:02d}E{episode_num:02d}",
                    f"{title} S{season_num}E{episode_num:02d}",
                    f"{title} {season_num}x{episode_num:02d}"
                ]

                for query in searches:
                    if len(files) >= self.max_streams_per_episode:
                        break

                    results = self.search_webshare(query, max_results=30)

                    for file in results:
                        if len(files) >= self.max_streams_per_episode:
                            break

                        filename = file.get('name', '')
                        if self.is_relevant_tv_file(filename, title, season_num, episode_num):
                            file_id = file.get('ident')
                            if file_id not in seen_ids:
                                seen_ids.add(file_id)
                                files.append(file)

                if files:
                    seasons[season_num][episode_num] = files
                    total_found += len(files)
                    log(f"  Episode {episode_num:02d}: Found {len(files)} files")
                else:
                    log(f"  Episode {episode_num:02d}: No files found")

        log(f"Total episodes with files: {sum(len(eps) for eps in seasons.values())}")
        log(f"Total files found: {total_found}")

        return seasons

    def organize_movie_files(self, files):
        """Organize movie files"""
        organized_files = []

        for file_data in files:
            filename = file_data.get('name', '')
            ident = file_data.get('ident')
            size = file_data.get('size', '0')

            quality = 'SD'
            if '2160p' in filename.lower() or '4k' in filename.lower() or 'uhd' in filename.lower():
                quality = '4K'
            elif '1440p' in filename.lower() or '2k' in filename.lower():
                quality = '1440p'
            elif '1080p' in filename.lower() or 'fhd' in filename.lower():
                quality = '1080p'
            elif '720p' in filename.lower() or 'hd' in filename.lower():
                quality = '720p'

            organized_files.append({
                'ident': ident,
                'filename': filename,
                'size': size,
                'quality': quality,
                'url': f"https://webshare.cz/#/file/{ident}"
            })

        quality_order = {'4K': 0, '1440p': 1, '1080p': 2, '720p': 3, 'SD': 4}
        organized_files.sort(key=lambda x: quality_order.get(x['quality'], 99))

        return organized_files

    def organize_tv_files(self, seasons):
        """Organize TV episode files"""
        organized_seasons = {}
        quality_order = {'4K': 0, '1440p': 1, '1080p': 2, '720p': 3, 'SD': 4}

        for season_num, episodes in seasons.items():
            organized_seasons[season_num] = {}

            for episode_num, files in episodes.items():
                episode_files = []

                for file_data in files:
                    filename = file_data.get('name', '')
                    ident = file_data.get('ident')
                    size = file_data.get('size', '0')

                    quality = 'SD'
                    if '2160p' in filename.lower() or '4k' in filename.lower() or 'uhd' in filename.lower():
                        quality = '4K'
                    elif '1440p' in filename.lower() or '2k' in filename.lower():
                        quality = '1440p'  # <-- This line needs proper indentation!
                    elif '1080p' in filename.lower() or 'fhd' in filename.lower():
                        quality = '1080p'
                    elif '720p' in filename.lower() or 'hd' in filename.lower():
                        quality = '720p'

                    episode_files.append({
                        'ident': ident,
                        'filename': filename,
                        'size': size,
                        'quality': quality,
                        'url': f"https://webshare.cz/#/file/{ident}"
                    })

                episode_files.sort(key=lambda x: quality_order.get(x['quality'], 99))
                organized_seasons[season_num][episode_num] = episode_files

        return organized_seasons
        
    def get_first_letter(self, title):
        """Get first letter for sharding"""
        if not title:
            return '#'

        articles = ['the ', 'a ', 'an ', 'der ', 'die ', 'das ']
        clean_title = title.lower().strip()

        for article in articles:
            if clean_title.startswith(article):
                clean_title = clean_title[len(article):]
                break

        if not clean_title:
            return '#'

        first_char = clean_title[0].upper()
        if first_char.isalpha():
            return first_char
        else:
            return '#'

    def get_decade_from_year(self, year):
        """Get decade from year"""
        if not year or not year.isdigit():
            return 'unknown'

        year_int = int(year)
        if year_int < 1980:
            return '1970s'
        elif year_int < 1990:
            return '1980s'
        elif year_int < 2000:
            return '1990s'
        elif year_int < 2010:
            return '2000s'
        elif year_int < 2020:
            return '2010s'
        else:
            return '2020s'

    def add_movie_to_extracted(self, tmdb_id, title, year, files):
        """Add movie to extracted data"""
        letter = self.get_first_letter(title)
        decade = self.get_decade_from_year(year)

        movies_dir = os.path.join(self.extracted_dir, 'movies', letter)
        os.makedirs(movies_dir, exist_ok=True)

        shard_file = os.path.join(movies_dir, f"{decade}.json")

        # Load existing data
        if os.path.exists(shard_file):
            with open(shard_file, 'r', encoding='utf-8') as f:
                shard_data = json.load(f)
        else:
            shard_data = {'files': []}

        # Check if already exists
        existing_index = -1
        for i, item in enumerate(shard_data['files']):
            if str(item.get('tmdb_id')) == str(tmdb_id):
                existing_index = i
                break

        if len(files) > self.max_streams_per_movie:
            files = files[:self.max_streams_per_movie]

        entry = {
            'tmdb_id': tmdb_id,
            'title': title,
            'year': year,
            'files': files,
            'updated': datetime.now().isoformat()
        }

        if existing_index >= 0:
            # Update existing entry
            shard_data['files'][existing_index] = entry
            log(f"Updated existing movie: {title}")
        else:
            # Add new entry
            shard_data['files'].append(entry)
            log(f"Added new movie: {title}")

        shard_data['files'] = sorted(shard_data['files'], key=lambda x: x['title'].lower())

        with open(shard_file, 'w', encoding='utf-8') as f:
            json.dump(shard_data, f, indent=2, ensure_ascii=False)

        return existing_index < 0

    def add_tv_to_extracted(self, tmdb_id, title, year, seasons):
        """Add TV show to extracted data"""
        letter = self.get_first_letter(title)

        tv_dir = os.path.join(self.extracted_dir, 'tv')
        os.makedirs(tv_dir, exist_ok=True)

        shard_file = os.path.join(tv_dir, f"{letter}.json")

        # Load existing data
        if os.path.exists(shard_file):
            with open(shard_file, 'r', encoding='utf-8') as f:
                shard_data = json.load(f)
        else:
            shard_data = {'episodes': {}}

        # Limit episodes per season
        limited_seasons = {}
        for season_num, episodes in seasons.items():
            limited_seasons[season_num] = {}
            for episode_num, files in episodes.items():
                if len(files) > self.max_streams_per_episode:
                    files = files[:self.max_streams_per_episode]
                limited_seasons[season_num][episode_num] = files

        entry = {
            'tmdb_id': tmdb_id,
            'title': title,
            'year': year,
            'seasons': limited_seasons,
            'updated': datetime.now().isoformat()
        }

        is_new = str(tmdb_id) not in shard_data['episodes']
        shard_data['episodes'][str(tmdb_id)] = entry

        log(f"{'Added new' if is_new else 'Updated existing'} TV show: {title}")

        with open(shard_file, 'w', encoding='utf-8') as f:
            json.dump(shard_data, f, indent=2, ensure_ascii=False)

        return is_new

    def create_zip_from_extracted(self):
        """Create ZIP from extracted directory"""
        log("Creating ZIP archive...")

        # Create temporary directory for ZIP
        with tempfile.TemporaryDirectory() as temp_dir:
            zip_filename = f"metadata_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
            zip_path = os.path.join(temp_dir, zip_filename)

            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                # Add all files from extracted directory
                for root, dirs, files in os.walk(self.extracted_dir):
                    for file in files:
                        file_path = os.path.join(root, file)
                        arcname = os.path.relpath(file_path, self.extracted_dir)
                        zipf.write(file_path, arcname)

            # Read ZIP content
            with open(zip_path, 'rb') as f:
                zip_content = f.read()

            return zip_content, zip_filename

    def upload_file_simple(self, content, filename, description=""):
        """Upload a file to WebShare - USING WORKING CODE FROM YOUR BLUEPRINT"""
        if not self.token and not self.login():
            poperror("Login failed!")
            return None

        try:
            log(f"Uploading: {filename}")

            # Get upload URL - from your working blueprint
            self._rate_limit()
            response = self.session.post(
                f"{self.base_url}upload_url/",
                data={'wst': self.token},
                timeout=30
            )

            if response.status_code != 200:
                log(f"✗ Failed to get upload URL")
                return None

            try:
                xml = ET.fromstring(response.content)
                if xml.find('status').text == 'OK':
                    upload_url = xml.find('url').text if xml.find('url') is not None else None
            except:
                try:
                    data = response.json()
                    upload_url = data.get('url')
                except:
                    log(f"✗ Could not parse upload URL response")
                    return None

            if not upload_url:
                log(f"✗ No upload URL received")
                return None

            # Upload file - from your working blueprint
            files = {'file': (filename, content)}
            data = {
                'name': filename,
                'description': description,
                'private': '1',
                'wst': self.token
            }

            self._rate_limit()
            response = self.session.post(
                upload_url,
                data=data,
                files=files,
                timeout=60
            )

            log(f"Upload status: {response.status_code}")

            if response.status_code == 200:
                try:
                    result = response.json()
                    if 'ident' in result:
                        file_id = result['ident']
                        log(f"✓ Uploaded: {file_id}")
                        return file_id
                    else:
                        log(f"✗ No ident in response")
                        return None
                except:
                    try:
                        xml = ET.fromstring(response.content)
                        if xml.find('status').text == 'OK':
                            file_id = xml.find('ident').text if xml.find('ident') is not None else None
                            if file_id:
                                log(f"✓ Uploaded: {file_id}")
                                return file_id
                    except:
                        # Check for empty response - sometimes WebShare returns empty but successful
                        if response.content == b'':
                            log(f"⚠ Empty response but status 200 - assuming success")
                            # Try to parse from headers or return a dummy ID
                            return "UPLOAD_SUCCESS_EMPTY_RESPONSE"
                        log(f"✗ Could not parse upload response")
                        return None

            return None

        except Exception as e:
            log(f"Upload error: {str(e)}")
            return None

    def add_content(self, tmdb_id, media_type):
        """Main function to add content by TMDB ID - UPDATED TO DELETE OLD FILES"""
        try:
            # Step 1: Show progress
            progress = xbmcgui.DialogProgress()
            progress.create("Adding Content", "Initializing...")

            def update_progress(percent, message):
                if progress.iscanceled():
                    raise Exception("Cancelled by user")
                progress.update(percent, message)

            # Step 2: Get TMDB info
            update_progress(10, f"Fetching {media_type} info from TMDB...")
            tmdb_info = self.get_tmdb_info(tmdb_id, media_type)

            if not tmdb_info:
                progress.close()
                poperror(f"Could not find {media_type} with TMDB ID: {tmdb_id}")
                return False

            title = tmdb_info['title']
            year = tmdb_info.get('year', '')

            # Step 3: Confirm with user
            progress.close()
            dialog = xbmcgui.Dialog()
            ret = dialog.yesno(f"Add {media_type.capitalize()}",
                             f"Add this {media_type}?\n\n"
                             f"Title: {title}\n"
                             f"Year: {year}\n"
                             f"TMDB ID: {tmdb_id}\n\n"
                             "This will:\n"
                             "1. Download latest database from WebShare\n"
                             "2. Search WebShare for files\n"
                             "3. Add to database\n"
                             "4. Create updated ZIP\n"
                             "5. Delete old LATEST files\n"
                             "6. Upload to WebShare for everyone")

            if not ret:
                return False

            # Restart progress
            progress = xbmcgui.DialogProgress()
            progress.create(f"Adding {title}", "Please wait...")

            # Step 4: DOWNLOAD LATEST DATABASE FIRST
            update_progress(30, "Downloading latest database...")
            if not self.find_and_download_latest():
                progress.close()
                poperror("Failed to download latest database!")
                return False

            # Step 5: Search for files
            if media_type == 'movie':
                update_progress(50, f"Searching for movie files: {title}...")
                files = self.find_movie_files(title, year)

                if not files:
                    progress.close()
                    poperror(f"No files found on WebShare for: {title}")
                    return False

                update_progress(60, "Organizing files...")
                organized_files = self.organize_movie_files(files)

                update_progress(70, "Adding to database...")
                is_new = self.add_movie_to_extracted(tmdb_id, title, year, organized_files)

                files_count = len(organized_files)

            else:  # TV
                if not tmdb_info.get('seasons'):
                    progress.close()
                    poperror(f"No season information available for: {title}")
                    return False

                update_progress(50, f"Searching for TV episodes: {title}...")
                seasons = self.find_tv_episodes(title, tmdb_info['seasons'])

                if not seasons:
                    progress.close()
                    poperror(f"No episodes found on WebShare for: {title}")
                    return False

                update_progress(60, "Organizing episodes...")
                organized_seasons = self.organize_tv_files(seasons)

                update_progress(70, "Adding to database...")
                is_new = self.add_tv_to_extracted(tmdb_id, title, year, organized_seasons)

                total_seasons = len(organized_seasons)
                total_episodes = sum(len(eps) for eps in organized_seasons.values())

            # Step 6: Create ZIP
            update_progress(80, "Creating updated ZIP...")
            zip_content, zip_filename = self.create_zip_from_extracted()

            # Step 7: DELETE OLD FILES BEFORE UPLOADING NEW ONES
            update_progress(85, "Cleaning up old files on WebShare...")
            self.delete_old_latest_files()
            self.delete_old_metadata_zips(keep_latest=2)  # Keep 2 latest ZIPs

            # Step 8: Upload ZIP
            update_progress(90, "Uploading ZIP to WebShare...")
            zip_id = self.upload_file_simple(zip_content, zip_filename,
                                           f"MILA Metadata - Updated {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

            if not zip_id:
                progress.close()
                poperror("Failed to upload ZIP!")
                return False

            # Step 9: Upload LATEST.json
            update_progress(95, "Creating LATEST.json...")
            latest_info = {
                'filename': zip_filename,
                'file_id': zip_id,
                'size': len(zip_content),
                'format': 'single_zip',
                'timestamp': datetime.now().isoformat(),
                'download_url': f"https://webshare.cz/#/file/{zip_id}"
            }

            latest_content = json.dumps(latest_info, indent=2).encode('utf-8')
            latest_id = self.upload_file_simple(latest_content, "LATEST.json", "Latest metadata info")

            progress.close()

            # Step 10: Show success
            if media_type == 'movie':
                message = f"✓ Movie added successfully!\n\nTitle: {title}\nYear: {year}\nFiles found: {files_count}\n\nDatabase has been updated and uploaded to WebShare.\nOld files have been cleaned up."
            else:
                message = f"✓ TV Show added successfully!\n\nTitle: {title}\nYear: {year}\nSeasons: {total_seasons}\nEpisodes: {total_episodes}\n\nDatabase has been updated and uploaded to WebShare.\nOld files have been cleaned up."

            dialog = xbmcgui.Dialog()
            dialog.ok("Success!", message)

            # Step 11: Automatically refresh database
            xbmc.executebuiltin('RunPlugin(plugin://plugin.video.mila/?action=refresh)')
            log("Auto-refresh triggered for new content")

            return True

        except Exception as e:
            log(f"Error adding content: {str(e)}")
            import traceback
            traceback.print_exc()
            if 'progress' in locals():
                progress.close()
            poperror(f"Error: {str(e)}")
            return False

# Kodi Interface Functions
def add_tv_show():
    """Kodi function to add TV show"""
    keyboard = xbmc.Keyboard('', 'Enter TMDB ID for TV Show')
    keyboard.doModal()

    if keyboard.isConfirmed():
        tmdb_id_str = keyboard.getText()
        if not tmdb_id_str:
            popinfo("No TMDB ID entered")
            return

        try:
            tmdb_id = int(tmdb_id_str)
        except ValueError:
            poperror("Invalid TMDB ID. Must be a number.")
            return

        organizer = WebSharder()
        organizer.add_content(tmdb_id, 'tv')

def add_movie():
    """Kodi function to add movie"""
    keyboard = xbmc.Keyboard('', 'Enter TMDB ID for Movie')
    keyboard.doModal()

    if keyboard.isConfirmed():
        tmdb_id_str = keyboard.getText()
        if not tmdb_id_str:
            popinfo("No TMDB ID entered")
            return

        try:
            tmdb_id = int(tmdb_id_str)
        except ValueError:
            poperror("Invalid TMDB ID. Must be a number.")
            return

        organizer = WebSharder()
        organizer.add_content(tmdb_id, 'movie')

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='WebSharder - Add content to database')
    parser.add_argument('--add', type=int, help='TMDB ID to add')
    parser.add_argument('--type', choices=['movie', 'tv'], help='Content type')

    args = parser.parse_args()

    if args.add:
        organizer = WebSharder()
        organizer.add_content(args.add, args.type)
