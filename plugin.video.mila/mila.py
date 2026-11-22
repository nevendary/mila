#!/usr/bin/env python3
"""
MILA - Media Index Library Addon
Author: nevendary + cache-sk + Ultra Simple
License: AGPL v.3
"""

import sys
import xbmc
import xbmcgui
import xbmcplugin
import xbmcaddon
import xbmcvfs
import requests
from xml.etree import ElementTree as ET
import hashlib
from md5crypt import md5crypt
import traceback
import json
import re
import uuid
import time
import os
from urllib.parse import quote_plus

# Add manifest finder import
try:
    from manifest_finder import initialize_manifest, auto_find_manifest_on_startup
except ImportError:
    pass

try:
    from urllib import urlencode
    from urlparse import parse_qsl
except ImportError:
    from urllib.parse import urlencode, parse_qsl

# Global variables
_url = sys.argv[0]
_handle = int(sys.argv[1])
_addon = xbmcaddon.Addon()
_addon_id = _addon.getAddonInfo('id')

# TMDB Configuration
TMDB_API_KEY = _addon.getSetting('tmdb_api_key') or "9567cc1179d493c3b22f0682dbdf2e42"
TMDB_URL = "https://api.themoviedb.org/3"
TMDB_IMAGE_URL = "https://image.tmdb.org/t/p/"
TMDB_LANGUAGE = _addon.getSetting('tmdb_language') or 'en-US'

# WebShare configuration
WEBSHARE_BASE_URL = "https://webshare.cz/api/"
# Main manifest file ID (will be auto-found)
MANIFEST_FILE_ID = ""

# Cache settings
CACHE_DIR = xbmcvfs.translatePath(os.path.join(_addon.getAddonInfo('profile'), 'cache'))
EXTRACTED_DIR = os.path.join(CACHE_DIR, 'extracted_metadata')
CACHE_DURATION = 86400  # 24 hours in seconds
TMDB_CACHE_DURATION = 604800  # 7 days for TMDB metadata

# WebShare session
_session = requests.Session()
_session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Referer': 'https://webshare.cz/'
})

# TMDB session with API key
_tmdb_session = requests.Session()
_tmdb_session.headers.update({
    'Authorization': f'Bearer {TMDB_API_KEY}',
    'Accept': 'application/json'
})

def log(msg):
    xbmc.log(f"[{_addon_id}] " + str(msg), xbmc.LOGINFO)

def popinfo(message):
    xbmcgui.Dialog().notification(_addon.getAddonInfo('name'), message, xbmcgui.NOTIFICATION_INFO, 3000)

def get_url(**kwargs):
    return _url + '?' + urlencode(kwargs)

def ensure_cache_dir():
    """Ensure cache directory exists"""
    if not os.path.exists(CACHE_DIR):
        os.makedirs(CACHE_DIR)
    if not os.path.exists(EXTRACTED_DIR):
        os.makedirs(EXTRACTED_DIR)

def get_cache_path(filename):
    """Get cache file path"""
    ensure_cache_dir()
    return os.path.join(CACHE_DIR, filename)

def load_cache(filename):
    """Load data from cache"""
    cache_file = get_cache_path(filename)
    if os.path.exists(cache_file):
        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)
            # Check if cache is still valid
            if filename.startswith('tmdb_'):
                cache_time = TMDB_CACHE_DURATION
            else:
                cache_time = CACHE_DURATION
            if time.time() - cache_data.get('timestamp', 0) < cache_time:
                log(f"Using cache: {filename}")
                return cache_data.get('data')
        except Exception as e:
            log(f"Cache read error: {str(e)}")
    return None

def save_cache(filename, data):
    """Save data to cache"""
    try:
        cache_file = get_cache_path(filename)
        with open(cache_file, 'w', encoding='utf-8') as f:
            json.dump({
                'timestamp': time.time(),
                'data': data
            }, f)
        log(f"Cache saved: {filename}")
    except Exception as e:
        log(f"Cache write error: {str(e)}")

def clear_cache():
    """Clear all cache files"""
    try:
        if os.path.exists(CACHE_DIR):
            for f in os.listdir(CACHE_DIR):
                file_path = os.path.join(CACHE_DIR, f)
                try:
                    if os.path.isfile(file_path):
                        os.remove(file_path)
                    elif os.path.isdir(file_path) and f != 'extracted_metadata':
                        import shutil
                        shutil.rmtree(file_path)
                except Exception as e:
                    log(f"Error removing {file_path}: {str(e)}")
            log("Cache cleared")
            popinfo("Cache cleared")
    except Exception as e:
        log(f"Cache clear error: {str(e)}")

def clear_extracted_metadata():
    """Clear extracted metadata directory"""
    try:
        if os.path.exists(EXTRACTED_DIR):
            import shutil
            shutil.rmtree(EXTRACTED_DIR)
            os.makedirs(EXTRACTED_DIR)
            log("Extracted metadata cleared")
            popinfo("Extracted metadata cleared")
    except Exception as e:
        log(f"Error clearing extracted metadata: {str(e)}")

# TMDB API FUNCTIONS
def fetch_tmdb_movie_details(tmdb_id):
    """Fetch movie details from TMDB"""
    if not tmdb_id or tmdb_id == 'None':
        return None

    cache_key = f"tmdb_movie_{tmdb_id}.json"
    cached = load_cache(cache_key)
    if cached:
        return cached

    try:
        url = f"{TMDB_URL}/movie/{tmdb_id}"
        params = {
            'api_key': TMDB_API_KEY,
            'language': TMDB_LANGUAGE,
            'append_to_response': 'credits,release_dates,videos,images'
        }

        response = _tmdb_session.get(url, params=params, timeout=10)
        if response.status_code == 200:
            data = response.json()
            save_cache(cache_key, data)
            return data
        elif response.status_code == 429:
            log("TMDB rate limit hit")
            return None
        else:
            log(f"TMDB movie fetch error: {response.status_code}")
    except Exception as e:
        log(f"TMDB movie fetch error: {str(e)}")

    return None

def fetch_tmdb_tv_details(tmdb_id):
    """Fetch TV show details from TMDB"""
    if not tmdb_id or tmdb_id == 'None':
        return None

    cache_key = f"tmdb_tv_{tmdb_id}.json"
    cached = load_cache(cache_key)
    if cached:
        return cached

    try:
        url = f"{TMDB_URL}/tv/{tmdb_id}"
        params = {
            'api_key': TMDB_API_KEY,
            'language': TMDB_LANGUAGE,
            'append_to_response': 'credits,content_ratings,images,external_ids'
        }

        response = _tmdb_session.get(url, params=params, timeout=10)
        if response.status_code == 200:
            data = response.json()
            save_cache(cache_key, data)
            return data
        elif response.status_code == 429:
            log("TMDB rate limit hit")
            return None
        else:
            log(f"TMDB TV fetch error: {response.status_code}")
    except Exception as e:
        log(f"TMDB TV fetch error: {str(e)}")

    return None

def fetch_tmdb_tv_season(tmdb_id, season_number):
    """Fetch TV season details from TMDB"""
    if not tmdb_id or not season_number:
        return None

    cache_key = f"tmdb_tv_{tmdb_id}_season_{season_number}.json"
    cached = load_cache(cache_key)
    if cached:
        return cached

    try:
        url = f"{TMDB_URL}/tv/{tmdb_id}/season/{season_number}"
        params = {
            'api_key': TMDB_API_KEY,
            'language': TMDB_LANGUAGE,
            'append_to_response': 'credits,images'
        }

        response = _tmdb_session.get(url, params=params, timeout=10)
        if response.status_code == 200:
            data = response.json()
            save_cache(cache_key, data)
            return data
    except Exception as e:
        log(f"TMDB season fetch error: {str(e)}")

    return None

def fetch_tmdb_tv_episode(tmdb_id, season_number, episode_number):
    """Fetch TV episode details from TMDB"""
    if not tmdb_id or not season_number or not episode_number:
        return None

    cache_key = f"tmdb_tv_{tmdb_id}_season_{season_number}_episode_{episode_number}.json"
    cached = load_cache(cache_key)
    if cached:
        return cached

    try:
        url = f"{TMDB_URL}/tv/{tmdb_id}/season/{season_number}/episode/{episode_number}"
        params = {
            'api_key': TMDB_API_KEY,
            'language': TMDB_LANGUAGE,
            'append_to_response': 'credits,images'
        }

        response = _tmdb_session.get(url, params=params, timeout=10)
        if response.status_code == 200:
            data = response.json()
            save_cache(cache_key, data)
            return data
    except Exception as e:
        log(f"TMDB episode fetch error: {str(e)}")

    return None

def get_tmdb_image_url(path, size='original'):
    """Get TMDB image URL"""
    if not path:
        return ''
    return f"{TMDB_IMAGE_URL}{size}{path}"

def get_content_rating(tmdb_data, content_type='movie'):
    """Get content rating (MPAA, TV rating)"""
    if content_type == 'movie':
        release_dates = tmdb_data.get('release_dates', {}).get('results', [])
        for country in release_dates:
            if country['iso_3166_1'] == 'US':
                for release in country.get('release_dates', []):
                    if release.get('certification'):
                        return release['certification']
    else:  # TV
        content_ratings = tmdb_data.get('content_ratings', {}).get('results', [])
        for rating in content_ratings:
            if rating['iso_3166_1'] == 'US':
                return rating['rating']

    return ''

def format_cast(credits):
    """Format cast list for Kodi"""
    cast = []
    for person in credits.get('cast', [])[:15]:  # Limit to 15 main cast members
        cast.append({
            'name': person.get('name'),
            'role': person.get('character'),
            'thumbnail': get_tmdb_image_url(person.get('profile_path'), 'w185')
        })
    return cast

def get_movie_listitem_info(movie_data, tmdb_data=None):
    """Create Kodi list item info for movie"""
    info = {
        'title': movie_data.get('title', ''),
        'year': int(movie_data.get('year', 0)) if movie_data.get('year') else 0,
        'mediatype': 'movie'
    }

    if tmdb_data:
        # Add TMDB metadata
        info['plot'] = tmdb_data.get('overview', '')
        info['tagline'] = tmdb_data.get('tagline', '')
        info['rating'] = float(tmdb_data.get('vote_average', 0))
        info['votes'] = str(tmdb_data.get('vote_count', 0))

        # Genres
        genres = [g['name'] for g in tmdb_data.get('genres', [])]
        if genres:
            info['genre'] = ' / '.join(genres)

        # Runtime
        if tmdb_data.get('runtime'):
            info['duration'] = tmdb_data['runtime'] * 60  # Convert to seconds

        # Release date
        if tmdb_data.get('release_date'):
            from datetime import datetime
            try:
                release_date = datetime.strptime(tmdb_data['release_date'], '%Y-%m-%d')
                info['premiered'] = tmdb_data['release_date']
                info['year'] = release_date.year
            except:
                pass

        # Director
        credits = tmdb_data.get('credits', {})
        if credits:
            directors = [c['name'] for c in credits.get('crew', [])
                        if c.get('job') == 'Director']
            if directors:
                info['director'] = ' / '.join(directors)

        # MPAA rating
        rating = get_content_rating(tmdb_data, 'movie')
        if rating:
            info['mpaa'] = rating

        # Studio
        companies = tmdb_data.get('production_companies', [])
        if companies:
            info['studio'] = companies[0].get('name', '')

    return info

def get_tvshow_listitem_info(show_data, tmdb_data=None):
    """Create Kodi list item info for TV show"""
    info = {
        'title': show_data.get('title', ''),
        'year': int(show_data.get('year', 0)) if show_data.get('year') else 0,
        'mediatype': 'tvshow'
    }

    if tmdb_data:
        info['plot'] = tmdb_data.get('overview', '')
        info['rating'] = float(tmdb_data.get('vote_average', 0))
        info['votes'] = str(tmdb_data.get('vote_count', 0))

        # Genres
        genres = [g['name'] for g in tmdb_data.get('genres', [])]
        if genres:
            info['genre'] = ' / '.join(genres)

        # First air date
        if tmdb_data.get('first_air_date'):
            info['premiered'] = tmdb_data['first_air_date']
            try:
                from datetime import datetime
                air_date = datetime.strptime(tmdb_data['first_air_date'], '%Y-%m-%d')
                info['year'] = air_date.year
            except:
                pass

        # Status
        info['status'] = tmdb_data.get('status', '')

        # TV rating
        rating = get_content_rating(tmdb_data, 'tv')
        if rating:
            info['mpaa'] = rating

        # Network
        networks = tmdb_data.get('networks', [])
        if networks:
            info['studio'] = networks[0].get('name', '')

    return info

def get_season_listitem_info(season_number, tmdb_data=None):
    """Create Kodi list item info for season"""
    info = {
        'title': f"Season {season_number}",
        'mediatype': 'season',
        'season': int(season_number)
    }

    if tmdb_data:
        info['plot'] = tmdb_data.get('overview', '')

        # Air date
        if tmdb_data.get('air_date'):
            info['premiered'] = tmdb_data['air_date']

    return info

def get_episode_listitem_info(season_number, episode_number, tmdb_data=None):
    """Create Kodi list item info for episode"""
    info = {
        'title': f"Episode {episode_number}",
        'season': int(season_number),
        'episode': int(episode_number),
        'mediatype': 'episode'
    }

    if tmdb_data:
        info['title'] = tmdb_data.get('name', f"Episode {episode_number}")
        info['plot'] = tmdb_data.get('overview', '')
        info['rating'] = float(tmdb_data.get('vote_average', 0))

        # Air date
        if tmdb_data.get('air_date'):
            info['aired'] = tmdb_data['air_date']
            info['date'] = tmdb_data['air_date']

        # Runtime
        if tmdb_data.get('runtime'):
            info['duration'] = tmdb_data['runtime'] * 60

        # Director
        credits = tmdb_data.get('credits', {})
        if credits:
            directors = [c['name'] for c in credits.get('crew', [])
                        if c.get('job') == 'Director']
            if directors:
                info['director'] = ' / '.join(directors)

            # Writers
            writers = [c['name'] for c in credits.get('crew', [])
                      if c.get('job') == 'Writer']
            if writers:
                info['writer'] = ' / '.join(writers)

    return info

def set_artwork(list_item, tmdb_data, content_type='movie', season_data=None):
    """Set artwork for list item"""
    art = {}

    if tmdb_data:
        # Poster
        if content_type in ['movie', 'tvshow']:
            poster_path = tmdb_data.get('poster_path')
            if poster_path:
                art['poster'] = get_tmdb_image_url(poster_path, 'w500')
                art['thumb'] = get_tmdb_image_url(poster_path, 'w342')

        # Fanart/background
        backdrop_path = tmdb_data.get('backdrop_path')
        if backdrop_path:
            art['fanart'] = get_tmdb_image_url(backdrop_path, 'original')
            art['banner'] = get_tmdb_image_url(backdrop_path, 'w780')

        # Season poster for seasons
        if content_type == 'season' and tmdb_data.get('poster_path'):
            art['poster'] = get_tmdb_image_url(tmdb_data['poster_path'], 'w500')
            art['thumb'] = get_tmdb_image_url(tmdb_data['poster_path'], 'w342')

        # Episode still for episodes
        if content_type == 'episode' and tmdb_data.get('still_path'):
            art['thumb'] = get_tmdb_image_url(tmdb_data['still_path'], 'w500')
            # Use episode still as poster too for better display
            art['poster'] = get_tmdb_image_url(tmdb_data['still_path'], 'w500')

    # For episodes without stills, use season poster if available
    if content_type == 'episode' and season_data and not art.get('poster'):
        if season_data.get('poster_path'):
            art['poster'] = get_tmdb_image_url(season_data['poster_path'], 'w500')
            art['thumb'] = get_tmdb_image_url(season_data['poster_path'], 'w342')

    # Set default if no artwork
    if not art.get('poster'):
        if content_type == 'movie':
            art['poster'] = 'DefaultMovies.png'
        elif content_type == 'tvshow':
            art['poster'] = 'DefaultTVShows.png'
        elif content_type == 'season':
            art['poster'] = 'DefaultFolder.png'
        elif content_type == 'episode':
            art['poster'] = 'DefaultVideo.png'

    if not art.get('thumb'):
        art['thumb'] = art.get('poster', '')

    if not art.get('fanart'):
        art['fanart'] = 'special://home/addons/plugin.video.example/fanart.jpg'

    list_item.setArt(art)

# WebShare login/playback functions
def login():
    username = _addon.getSetting('wsuser')
    password = _addon.getSetting('wspass')
    if not username or not password:
        popinfo("Set username/password")
        return None

    try:
        response = _session.post(f"{WEBSHARE_BASE_URL}salt/",
                               data={'username_or_email': username},
                               timeout=10)
        xml = ET.fromstring(response.content)
        if xml.find('status').text != 'OK':
            log("Salt request failed")
            return None

        salt = xml.find('salt').text
        encrypted_pass = hashlib.sha1(md5crypt(password.encode('utf-8'),
                                             salt.encode('utf-8')).encode('utf-8')).hexdigest()
        pass_digest = hashlib.md5(username.encode('utf-8') + b':Webshare:' +
                                encrypted_pass.encode('utf-8')).hexdigest()

        response = _session.post(f"{WEBSHARE_BASE_URL}login/", data={
            'username_or_email': username,
            'password': encrypted_pass,
            'digest': pass_digest,
            'keep_logged_in': 1
        }, timeout=10)
        xml = ET.fromstring(response.content)
        if xml.find('status').text == 'OK':
            token = xml.find('token').text
            log(f"Login successful, token: {token[:10]}...")
            return token
    except Exception as e:
        log(f"Login error: {str(e)}")

    return None

def get_stream_link(ident, token):
    duuid = _addon.getSetting('duuid') or str(uuid.uuid4())
    _addon.setSetting('duuid', duuid)

    try:
        response = _session.post(f"{WEBSHARE_BASE_URL}file_link/", data={
            'ident': ident,
            'wst': token,
            'download_type': 'video_stream',
            'device_uuid': duuid
        }, timeout=10)
        xml = ET.fromstring(response.content)
        if xml.find('status').text == 'OK':
            return xml.find('link').text
    except Exception as e:
        log(f"Stream link error: {str(e)}")

    return None

def play_video(ident, title):
    token = login()
    if not token:
        popinfo("Login failed")
        return

    link = get_stream_link(ident, token)
    if not link:
        popinfo("No stream link")
        return

    play_url = link + "|Cookie=wst=" + token

    li = xbmcgui.ListItem(label=title, path=play_url)
    li.setProperty('IsPlayable', 'true')
    li.setMimeType('video/mp4')
    li.setContentLookup(False)

    xbmcplugin.setResolvedUrl(_handle, True, li)

# Metadata extraction
def get_metadata_from_api(stream):
    """Get metadata from stream"""
    filename = stream.get('filename', '')
    quality = stream.get('quality', 'Unknown')

    info = {
        'quality': quality,
        'resolution': quality,
        'audio_channels': '',
        'audio_codec': '',
        'languages': [],
        'source': '',
        'hdr': False,
        'size_mb': int(stream.get('size', 0)) / (1024 * 1024) if stream.get('size', '0').isdigit() else 0
    }

    # Extract audio channels
    channel_patterns = [
        (r'(7\.1|7-1)', '7.1'),
        (r'(5\.1|5-1)', '5.1'),
        (r'(2\.0|2-0|stereo)', '2.0'),
    ]

    for pattern, channel in channel_patterns:
        if re.search(pattern, filename, re.IGNORECASE):
            info['audio_channels'] = channel
            break

    # Extract audio codec
    codec_patterns = [
        (r'(DTS-HD MA|DTSHDMA)', 'DTS-HD MA'),
        (r'(TrueHD|ATMOS)', 'TrueHD/ATMOS'),
        (r'(DTS-HD|DTSHD)', 'DTS-HD'),
        (r'(DTS)', 'DTS'),
        (r'(AC3|DD)', 'AC3'),
        (r'(AAC)', 'AAC'),
        (r'(MP3)', 'MP3')
    ]

    for pattern, codec in codec_patterns:
        if re.search(pattern, filename, re.IGNORECASE):
            info['audio_codec'] = codec
            break

    # Extract languages
    lang_patterns = [
        (r'(CZ\.|CZSK|CZ-SK|Czech|cesky|česky)', 'Czech'),
        (r'(SK\.|Slovak|slovensky)', 'Slovak'),
        (r'(ENG\.|English|EN\.)', 'English'),
        (r'(DE\.|German|GER\.|německy)', 'German'),
        (r'(PL\.|Polish|polsky)', 'Polish'),
        (r'(HU\.|Hungarian|maďarsky)', 'Hungarian'),
        (r'(FR\.|French|francouzsky)', 'French'),
        (r'(ES\.|Spanish|španělsky)', 'Spanish'),
        (r'(multi|MULTI|vícejazyčný)', 'Multi'),
        (r'(dabing|dabingem|DAB)', 'Dubbed')
    ]

    for pattern, lang in lang_patterns:
        if re.search(pattern, filename, re.IGNORECASE):
            if lang not in info['languages']:
                info['languages'].append(lang)

    # Extract HDR
    if re.search(r'(HDR|hdr)', filename):
        info['hdr'] = True
        info['quality'] += ' HDR'

    # Extract source
    source_patterns = [
        (r'(BluRay|BLURAY|BDrip|BD-rip)', 'BluRay'),
        (r'(WEB-DL|WEB\.DL|WEBRip|WEBRIP)', 'WEB'),
        (r'(HDTV|HDTVRip|TVrip)', 'HDTV'),
        (r'(DVDrip|DVD|DVD-Rip)', 'DVD'),
        (r'(CAM|TS|TELESYNC|TC)', 'CAM')
    ]

    for pattern, source in source_patterns:
        if re.search(pattern, filename, re.IGNORECASE):
            info['source'] = source
            break

    return info

# Ranking and selection functions
def rank_streams(streams):
    """Rank streams based on user preferences"""
    preferred_lang = _addon.getSetting('preferred_language') or 'Any'
    max_quality = _addon.getSetting('max_quality') or '4K'
    prefer_hdr = _addon.getSetting('prefer_hdr') == 'true'
    min_audio_channels = _addon.getSetting('min_audio_channels') or '2.0'
    preferred_resolution = _addon.getSetting('preferred_resolution') or '1080p'

    quality_values = {
        'Unknown': 1,
        '480p': 2,
        '720p': 3,
        '1080p': 4,
        '4K': 5,
        '4K HDR': 6
    }

    max_quality_value = quality_values.get(max_quality, 5)
    target_quality_value = quality_values.get(preferred_resolution, 4)

    ranked_streams = []
    for i, stream in enumerate(streams):
        score = 0
        info = get_metadata_from_api(stream)

        # Quality scoring
        quality_value = quality_values.get(info['quality'].split()[0] if ' ' in info['quality'] else info['quality'], 1)

        if quality_value <= max_quality_value:
            diff = abs(quality_value - target_quality_value)
            if diff == 0:
                score += 100
            elif diff == 1:
                score += 80
            elif diff == 2:
                score += 60
            else:
                score += 40 - (diff * 5)
        else:
            score -= 30

        # Language scoring
        if preferred_lang != 'Any':
            if preferred_lang in info['languages']:
                score += 150
            elif info['languages']:
                if 'Czech' in info['languages'] or 'Slovak' in info['languages']:
                    score += 50
                else:
                    score += 20
        else:
            if info['languages']:
                score += 30

        # HDR scoring
        if info['hdr'] and prefer_hdr:
            score += 25
        elif info['hdr'] and not prefer_hdr:
            score -= 10

        # Audio scoring
        if info['audio_channels']:
            if info['audio_channels'] in ['7.1', '5.1']:
                score += 30
            elif info['audio_channels'] == min_audio_channels:
                score += 15
            elif info['audio_codec'] in ['DTS-HD MA', 'TrueHD/ATMOS']:
                score += 20

        # Source scoring
        if info['source'] == 'BluRay':
            score += 20
        elif info['source'] == 'WEB':
            score += 15
        elif info['source'] == 'HDTV':
            score += 10

        # File size scoring
        if info['size_mb'] > 100:
            size_score = min(20, info['size_mb'] / 50)
            score += size_score

        ranked_streams.append({
            'stream': stream,
            'score': score,
            'info': info,
            'size_mb': info['size_mb'],
            'index': i
        })

    ranked_streams.sort(key=lambda x: x['score'], reverse=True)
    return ranked_streams

def get_autoplay_stream(streams):
    """Select the best stream based on preferences"""
    if not streams:
        return None

    ranked = rank_streams(streams)

    if ranked and ranked[0]['score'] >= 50:
        return ranked[0]['stream']

    preferred_lang = _addon.getSetting('preferred_language') or 'Any'
    if preferred_lang != 'Any':
        for ranked_stream in ranked:
            info = ranked_stream['info']
            if preferred_lang in info['languages']:
                return ranked_stream['stream']

    return streams[0] if streams else None

def format_stream_label(stream, info, index, size_mb):
    """Create a detailed label for stream selection"""
    label_parts = []

    # Index
    label_parts.append(f"{index+1}.")

    # Quality
    if info['quality'] != 'Unknown':
        quality_display = info['quality']
        if info['hdr'] and 'HDR' not in quality_display:
            quality_display += ' HDR'
        label_parts.append(f"[B]{quality_display}[/B]")

    # Source
    if info['source']:
        label_parts.append(f"[{info['source']}]")

    # Languages
    if info['languages']:
        langs = '/'.join(info['languages'][:2])
        if len(info['languages']) > 2:
            langs += '+'
        label_parts.append(f"({langs})")

    # Audio
    audio_parts = []
    if info['audio_channels']:
        audio_parts.append(info['audio_channels'])
    if info['audio_codec']:
        audio_parts.append(info['audio_codec'])
    if audio_parts:
        label_parts.append(f"[I]{' '.join(audio_parts)}[/I]")

    # Size
    if size_mb > 0:
        if size_mb > 1024:
            label_parts.append(f"({size_mb/1024:.1f} GB)")
        else:
            label_parts.append(f"({size_mb:.0f} MB)")

    full_label = " ".join(label_parts)

    # Color coding
    if '4K' in info['quality']:
        full_label = f"[COLOR gold]{full_label}[/COLOR]"
    elif '1080p' in info['quality']:
        full_label = f"[COLOR lime]{full_label}[/COLOR]"
    elif '720p' in info['quality']:
        full_label = f"[COLOR cyan]{full_label}[/COLOR]"

    return full_label

def select_stream_popup(streams, title, auto_play=True):
    """Show stream selection popup - with option to bypass auto-play"""
    if not streams:
        popinfo("No streams available")
        return None

    ranked_streams = rank_streams(streams)
    autoplay_enabled = _addon.getSetting('autoplay') == 'true'
    skip_popup = _addon.getSetting('skip_popup') == 'true'

    # If only one stream, just play it
    if len(streams) == 1:
        play_video(streams[0]['ident'], title)
        return streams[0]['ident']

    # Auto-select if enabled and skip popup is on AND auto_play is True
    if autoplay_enabled and skip_popup and auto_play:
        best_stream = get_autoplay_stream(streams)
        if best_stream:
            play_video(best_stream['ident'], title)
            return best_stream['ident']

    # Show stream selection dialog
    items = []
    for ranked in ranked_streams:
        stream = ranked['stream']
        info = ranked['info']
        size_mb = ranked['size_mb']
        index = ranked['index']

        label = format_stream_label(stream, info, index, size_mb)

        if ranked['score'] == ranked_streams[0]['score']:
            label = f"[B][COLOR yellow]★ {label}[/COLOR][/B]"

        items.append((label, stream['ident']))

    dialog = xbmcgui.Dialog()
    selected = dialog.select(f"Select stream - {title}", [item[0] for item in items])

    if selected >= 0:
        stream_id = items[selected][1]
        play_video(stream_id, title)
        return stream_id

    return None

def manual_stream_selection(streams, title):
    """Force manual stream selection (bypasses auto-play)"""
    return select_stream_popup(streams, title, auto_play=False)

def show_context_menu_select_stream(params):
    """Show context menu for manual stream selection"""
    tmdb_id = params.get('tmdb_id')
    content_type = params.get('content_type', 'movie')
    
    if content_type == 'movie':
        movie_title = params.get('movie_title', 'Movie')
        movie_year = params.get('movie_year', '')
        
        data = load_all_data()
        if not data or 'movies' not in data:
            popinfo("No movies data")
            return
        
        # Find movie
        movie = None
        for m in data['movies']:
            if m.get('tmdb_id') == tmdb_id:
                movie = m
                break
        
        if not movie or 'streams' not in movie:
            popinfo("Movie not found")
            return
        
        streams = []
        for stream in movie['streams']:
            streams.append({
                'ident': stream['ident'],
                'filename': stream['filename'],
                'size': stream.get('size', '0'),
                'quality': stream.get('quality', 'Unknown')
            })
        
        if not streams:
            popinfo("No streams available")
            return
        
        title = f"{movie_title} ({movie_year})" if movie_year else movie_title
        manual_stream_selection(streams, title)
    
    elif content_type == 'episode':
        season = params.get('season')
        episode = params.get('episode')
        show_title = params.get('show_title', 'Episode')
        
        data = load_all_data()
        if not data or 'tv_shows' not in data:
            popinfo("No data available")
            return
        
        # Find show and episode streams
        show = None
        for s in data['tv_shows']:
            if s.get('tmdb_id') == tmdb_id:
                show = s
                break
        
        if not show or 'seasons' not in show or season not in show['seasons']:
            popinfo("Show or season not found")
            return
        
        season_data = show['seasons'][season]
        if episode not in season_data:
            popinfo(f"Episode {episode} not found")
            return
        
        episode_files = season_data[episode]
        streams = []
        
        for file in episode_files:
            streams.append({
                'ident': file['ident'],
                'filename': file['filename'],
                'size': file.get('size', '0'),
                'quality': file.get('quality', 'Unknown')
            })
        
        if not streams:
            popinfo("No streams available")
            return
        
        # Fetch episode name for better title
        ep_name = ""
        tmdb_data = fetch_tmdb_tv_episode(tmdb_id, season, episode)
        if tmdb_data and tmdb_data.get('name'):
            ep_name = f": {tmdb_data['name']}"
        
        title = f"{show_title} S{season}E{episode}{ep_name}"
        manual_stream_selection(streams, title)

# SEARCH FUNCTIONS
def search_content():
    """Show search interface"""
    keyboard = xbmc.Keyboard('', _addon.getLocalizedString(30001))  # "Search"
    keyboard.doModal()

    if keyboard.isConfirmed():
        search_term = keyboard.getText()
        if search_term:
            show_search_results(search_term)

def show_search_results(search_term):
    """Show search results across movies and TV shows"""
    data = load_all_data()
    if not data:
        popinfo("No data available")
        return

    xbmcplugin.setPluginCategory(_handle, f"Search: {search_term}")
    xbmcplugin.setContent(_handle, 'files')

    search_term_lower = search_term.lower()
    movies = data.get('movies', [])
    tv_shows = data.get('tv_shows', [])

    found_items = []

    # Search in movies
    for movie in movies:
        title_lower = movie.get('title', '').lower()
        if search_term_lower in title_lower:
            found_items.append({
                'type': 'movie',
                'data': movie,
                'relevance': title_lower.find(search_term_lower)
            })

    # Search in TV shows
    for show in tv_shows:
        title_lower = show.get('title', '').lower()
        if search_term_lower in title_lower:
            found_items.append({
                'type': 'tvshow',
                'data': show,
                'relevance': title_lower.find(search_term_lower)
            })

    # Sort by relevance
    found_items.sort(key=lambda x: x['relevance'])

    if not found_items:
        li = xbmcgui.ListItem(label="[COLOR red]No results found[/COLOR]")
        li.setArt({'icon': 'DefaultFolder.png'})
        xbmcplugin.addDirectoryItem(_handle, '', li, False)
    else:
        # Add header
        li = xbmcgui.ListItem(label=f"[COLOR yellow]Found {len(found_items)} results[/COLOR]")
        li.setArt({'icon': 'DefaultFolder.png'})
        xbmcplugin.addDirectoryItem(_handle, '', li, False)

        # Add results
        for item in found_items:
            if item['type'] == 'movie':
                add_movie_search_result(item['data'])
            else:
                add_tvshow_search_result(item['data'])

    xbmcplugin.endOfDirectory(_handle)

def add_movie_search_result(movie):
    """Add a movie to search results"""
    tmdb_id = movie.get('tmdb_id', '')

    # Fetch TMDB metadata
    tmdb_data = fetch_tmdb_movie_details(tmdb_id) if tmdb_id else None

    label = f"[B]{movie['title']}[/B]"
    if movie.get('year'):
        label += f" ({movie['year']})"

    if tmdb_data:
        # Add rating to label
        rating = tmdb_data.get('vote_average')
        if rating:
            label += f" [COLOR yellow]{rating:.1f}★[/COLOR]"

    li = xbmcgui.ListItem(label=label)

    # Set info and artwork
    info = get_movie_listitem_info(movie, tmdb_data)
    li.setInfo('video', info)
    set_artwork(li, tmdb_data, 'movie')

    # Set cast if available
    if tmdb_data and tmdb_data.get('credits'):
        cast = format_cast(tmdb_data['credits'])
        if cast:
            li.setCast(cast)

    # Add context menu for manual stream selection
    context_menu = []
    context_menu.append(("Select Stream", 
                       f"RunPlugin({get_url(action='context_select_stream', tmdb_id=tmdb_id, content_type='movie', movie_title=movie['title'], movie_year=movie.get('year', ''))})"))
    li.addContextMenuItems(context_menu)

    li.setProperty('IsPlayable', 'true')

    url = get_url(
        action='play_movie',
        tmdb_id=tmdb_id,
        movie_title=movie['title'],
        movie_year=movie.get('year', '')
    )

    xbmcplugin.addDirectoryItem(_handle, url, li, False)

def add_tvshow_search_result(show):
    """Add a TV show to search results"""
    tmdb_id = show.get('tmdb_id', '')

    # Fetch TMDB metadata
    tmdb_data = fetch_tmdb_tv_details(tmdb_id) if tmdb_id else None

    label = f"[B]{show['title']}[/B]"
    if show.get('year'):
        label += f" ({show['year']})"

    if tmdb_data:
        # Add rating to label
        rating = tmdb_data.get('vote_average')
        if rating:
            label += f" [COLOR yellow]{rating:.1f}★[/COLOR]"

    li = xbmcgui.ListItem(label=label)

    # Set info and artwork
    info = get_tvshow_listitem_info(show, tmdb_data)
    li.setInfo('video', info)
    set_artwork(li, tmdb_data, 'tvshow')

    # Set cast if available
    if tmdb_data and tmdb_data.get('credits'):
        cast = format_cast(tmdb_data['credits'])
        if cast:
            li.setCast(cast)

    url = get_url(action='tv_show', tmdb_id=tmdb_id)
    xbmcplugin.addDirectoryItem(_handle, url, li, True)

# TMDB LIST FUNCTIONS
def load_tmdb_lists():
    """Load TMDB lists from extracted data"""
    lists_data = {
        'popular_tv': [],
        'top_rated_tv': [],
        'popular_movies': [],
        'top_rated_movies': []
    }

    # Check for list directories
    popular_dir = os.path.join(EXTRACTED_DIR, 'popular')
    top_rated_dir = os.path.join(EXTRACTED_DIR, 'top_rated')
    combined_dir = os.path.join(EXTRACTED_DIR, 'combined_lists')

    # Load popular movies
    popular_movies_file = os.path.join(popular_dir, 'movies.json') if os.path.exists(popular_dir) else None
    if popular_movies_file and os.path.exists(popular_movies_file):
        data = load_json_file(popular_movies_file)
        if data and 'entries' in data:
            lists_data['popular_movies'] = data['entries'][:30]  # Limit to 30

    # Load popular TV shows
    popular_tv_file = os.path.join(popular_dir, 'tv.json') if os.path.exists(popular_dir) else None
    if popular_tv_file and os.path.exists(popular_tv_file):
        data = load_json_file(popular_tv_file)
        if data and 'entries' in data:
            lists_data['popular_tv'] = data['entries'][:30]  # Limit to 30

    # Load top rated movies
    top_rated_movies_file = os.path.join(top_rated_dir, 'movies.json') if os.path.exists(top_rated_dir) else None
    if top_rated_movies_file and os.path.exists(top_rated_movies_file):
        data = load_json_file(top_rated_movies_file)
        if data and 'entries' in data:
            lists_data['top_rated_movies'] = data['entries'][:30]  # Limit to 30

    # Load top rated TV shows
    top_rated_tv_file = os.path.join(top_rated_dir, 'tv.json') if os.path.exists(top_rated_dir) else None
    if top_rated_tv_file and os.path.exists(top_rated_tv_file):
        data = load_json_file(top_rated_tv_file)
        if data and 'entries' in data:
            lists_data['top_rated_tv'] = data['entries'][:30]  # Limit to 30

    return lists_data

def show_tmdb_list(list_type, list_name):
    """Show a TMDB list (Popular/Top Rated Movies/TV)"""
    lists_data = load_tmdb_lists()
    
    if list_type not in lists_data or not lists_data[list_type]:
        li = xbmcgui.ListItem(label=f"[COLOR red]No {list_name} found[/COLOR]")
        li.setArt({'icon': 'DefaultFolder.png'})
        xbmcplugin.addDirectoryItem(_handle, '', li, False)
        xbmcplugin.endOfDirectory(_handle)
        return
    
    xbmcplugin.setPluginCategory(_handle, list_name)
    
    if 'movies' in list_type:
        xbmcplugin.setContent(_handle, 'movies')
    else:
        xbmcplugin.setContent(_handle, 'tvshows')
    
    for item in lists_data[list_type]:
        if 'movies' in list_type:
            add_movie_from_list(item)
        else:
            add_tvshow_from_list(item)
    
    xbmcplugin.endOfDirectory(_handle)

def add_movie_from_list(item):
    """Add a movie from TMDB list"""
    tmdb_id = str(item.get('tmdb_id', ''))
    title = item.get('title', '')
    year = item.get('year', '')
    
    # Fetch TMDB metadata
    tmdb_data = fetch_tmdb_movie_details(tmdb_id) if tmdb_id else None
    
    label = f"[B]{title}[/B]"
    if year:
        label += f" ({year})"
    
    if tmdb_data:
        # Add rating to label
        rating = tmdb_data.get('vote_average')
        if rating:
            label += f" [COLOR yellow]{rating:.1f}★[/COLOR]"
    
    li = xbmcgui.ListItem(label=label)
    
    # Set info and artwork
    movie_data = {'tmdb_id': tmdb_id, 'title': title, 'year': year}
    info = get_movie_listitem_info(movie_data, tmdb_data)
    li.setInfo('video', info)
    set_artwork(li, tmdb_data, 'movie')
    
    # Set cast if available
    if tmdb_data and tmdb_data.get('credits'):
        cast = format_cast(tmdb_data['credits'])
        if cast:
            li.setCast(cast)
    
    # Try to find the movie in our main data for streaming
    main_data = load_all_data()
    movie_found = None
    for movie in main_data.get('movies', []):
        if str(movie.get('tmdb_id')) == tmdb_id:
            movie_found = movie
            break
    
    if movie_found and movie_found.get('streams'):
        # Add context menu for manual stream selection
        context_menu = []
        context_menu.append(("Select Stream", 
                           f"RunPlugin({get_url(action='context_select_stream', tmdb_id=tmdb_id, content_type='movie', movie_title=title, movie_year=year)})"))
        li.addContextMenuItems(context_menu)
        
        li.setProperty('IsPlayable', 'true')
        url = get_url(
            action='play_movie',
            tmdb_id=tmdb_id,
            movie_title=title,
            movie_year=year
        )
    else:
        li.setProperty('IsPlayable', 'false')
        url = get_url(action='no_stream_available')
    
    xbmcplugin.addDirectoryItem(_handle, url, li, False)

def add_tvshow_from_list(item):
    """Add a TV show from TMDB list"""
    tmdb_id = str(item.get('tmdb_id', ''))
    title = item.get('title', '')
    year = item.get('year', '')
    
    # Fetch TMDB metadata
    tmdb_data = fetch_tmdb_tv_details(tmdb_id) if tmdb_id else None
    
    label = f"[B]{title}[/B]"
    if year:
        label += f" ({year})"
    
    if tmdb_data:
        # Add rating to label
        rating = tmdb_data.get('vote_average')
        if rating:
            label += f" [COLOR yellow]{rating:.1f}★[/COLOR]"
    
    li = xbmcgui.ListItem(label=label)
    
    # Set info and artwork
    show_data = {'tmdb_id': tmdb_id, 'title': title, 'year': year}
    info = get_tvshow_listitem_info(show_data, tmdb_data)
    li.setInfo('video', info)
    set_artwork(li, tmdb_data, 'tvshow')
    
    # Set cast if available
    if tmdb_data and tmdb_data.get('credits'):
        cast = format_cast(tmdb_data['credits'])
        if cast:
            li.setCast(cast)
    
    # Try to find the show in our main data
    main_data = load_all_data()
    show_found = None
    for show in main_data.get('tv_shows', []):
        if str(show.get('tmdb_id')) == tmdb_id:
            show_found = show
            break
    
    if show_found:
        url = get_url(action='tv_show', tmdb_id=tmdb_id)
    else:
        url = get_url(action='no_content_available')
    
    xbmcplugin.addDirectoryItem(_handle, url, li, True)

# MANIFEST FUNCTIONS - SIMPLIFIED
def get_manifest():
    """Get the main manifest - SIMPLIFIED VERSION"""
    log("Getting manifest - SIMPLIFIED")

    # Just return empty dict for compatibility
    return {'files': {}}

def load_json_file(filepath):
    """Load a JSON file"""
    try:
        if os.path.exists(filepath):
            with open(filepath, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception as e:
        log(f"Error loading {filepath}: {e}")
    return None

def load_all_data():
    """Load all data from extracted ZIP files - FIXED FOR CORRECT STRUCTURE"""
    log("=== LOAD_ALL_DATA START ===")

    all_data = {
        'movies': [],
        'tv_shows': []
    }

    # Check if we have extracted metadata
    if not os.path.exists(EXTRACTED_DIR):
        log(f"ERROR: EXTRACTED_DIR doesn't exist: {EXTRACTED_DIR}")
        return all_data

    log(f"EXTRACTED_DIR exists: {EXTRACTED_DIR}")

    # ===== LOAD MOVIES =====
    movies_dir = os.path.join(EXTRACTED_DIR, 'movies')
    if os.path.exists(movies_dir):
        log(f"Movies directory exists: {movies_dir}")

        # List all letter directories
        for letter in os.listdir(movies_dir):
            letter_path = os.path.join(movies_dir, letter)
            if os.path.isdir(letter_path):
                log(f"  Checking letter: {letter}")

                # Look for JSON files directly in letter directory
                json_files = [f for f in os.listdir(letter_path) if f.endswith('.json')]
                log(f"    Found {len(json_files)} JSON files in {letter}")

                for json_file in json_files:
                    filepath = os.path.join(letter_path, json_file)
                    log(f"    Loading movie JSON: {json_file}")

                    data = load_json_file(filepath)
                    if data:
                        if 'files' in data:
                            for movie_entry in data['files']:
                                movie_data = {
                                    'tmdb_id': str(movie_entry.get('tmdb_id', '')),
                                    'title': movie_entry.get('title', ''),
                                    'year': movie_entry.get('year', ''),
                                    'streams': movie_entry.get('files', [])
                                }
                                all_data['movies'].append(movie_data)
                                log(f"      Added movie: {movie_entry.get('title')}")
                        else:
                            log(f"      ERROR: No 'files' key in {json_file}")
                    else:
                        log(f"      ERROR: Failed to load {json_file}")

                if len(json_files) == 0:
                    log(f"    WARNING: No JSON files found in {letter} directory!")
    else:
        log(f"ERROR: Movies directory doesn't exist: {movies_dir}")

    # ===== LOAD TV SHOWS =====
    tv_dir = os.path.join(EXTRACTED_DIR, 'tv')
    if os.path.exists(tv_dir):
        log(f"TV directory exists: {tv_dir}")

        # List all JSON files in TV directory
        json_files = [f for f in os.listdir(tv_dir) if f.endswith('.json')]
        log(f"Found {len(json_files)} TV JSON files")

        for json_file in json_files:
            filepath = os.path.join(tv_dir, json_file)
            log(f"  Loading TV JSON: {json_file}")

            data = load_json_file(filepath)
            if data:
                if 'episodes' in data:
                    for tmdb_id, show_entry in data['episodes'].items():
                        tv_data = {
                            'tmdb_id': str(tmdb_id),
                            'title': show_entry.get('title', ''),
                            'year': show_entry.get('year', ''),
                            'seasons': show_entry.get('seasons', {})
                        }
                        all_data['tv_shows'].append(tv_data)
                        log(f"    Added TV show: {show_entry.get('title')}")
                else:
                    log(f"    ERROR: No 'episodes' key in {json_file}")
            else:
                log(f"    ERROR: Failed to load {json_file}")
    else:
        log(f"ERROR: TV directory doesn't exist: {tv_dir}")

    log(f"=== LOAD_ALL_DATA END: {len(all_data['movies'])} movies, {len(all_data['tv_shows'])} TV shows ===")

    return all_data

def check_for_updates():
    """Check if there's a newer version on WebShare"""
    log("Checking for updates on WebShare...")

    try:
        from manifest_finder import check_for_updates as manifest_check
        return manifest_check()
    except:
        pass

    return False

# MAIN MENU - UPDATED WITH TMDB LISTS
def main_menu():
    """Main menu - checks for updates on startup"""
    xbmcplugin.setPluginCategory(_handle, "MILA (WebShare)")
    xbmcplugin.setContent(_handle, 'files')

    # Check for updates on startup
    auto_update = _addon.getSetting('auto_update') == 'true'
    if auto_update:
        log("Auto-update enabled, checking for updates...")
        if check_for_updates():
            popinfo("New version available! Use Refresh Data.")

    # Search
    li = xbmcgui.ListItem(label="[B][COLOR yellow]Search[/COLOR][/B]")
    li.setArt({'icon': 'DefaultSearch.png'})
    url = get_url(action='search')
    xbmcplugin.addDirectoryItem(_handle, url, li, True)

    # TMDB Lists
    li = xbmcgui.ListItem(label="[COLOR gold]Popular Movies[/COLOR]")
    li.setArt({'icon': 'DefaultMovies.png'})
    url = get_url(action='tmdb_list', list_type='popular_movies', list_name='Popular Movies')
    xbmcplugin.addDirectoryItem(_handle, url, li, True)

    li = xbmcgui.ListItem(label="[COLOR gold]Top Rated Movies[/COLOR]")
    li.setArt({'icon': 'DefaultMovies.png'})
    url = get_url(action='tmdb_list', list_type='top_rated_movies', list_name='Top Rated Movies')
    xbmcplugin.addDirectoryItem(_handle, url, li, True)

    li = xbmcgui.ListItem(label="[COLOR cyan]Popular TV Shows[/COLOR]")
    li.setArt({'icon': 'DefaultTVShows.png'})
    url = get_url(action='tmdb_list', list_type='popular_tv', list_name='Popular TV Shows')
    xbmcplugin.addDirectoryItem(_handle, url, li, True)

    li = xbmcgui.ListItem(label="[COLOR cyan]Top Rated TV Shows[/COLOR]")
    li.setArt({'icon': 'DefaultTVShows.png'})
    url = get_url(action='tmdb_list', list_type='top_rated_tv', list_name='Top Rated TV Shows')
    xbmcplugin.addDirectoryItem(_handle, url, li, True)

    # TV Shows
    li = xbmcgui.ListItem(label="TV Shows")
    li.setArt({'icon': 'DefaultTVShows.png'})
    li.setInfo('video', {'title': "TV Shows"})
    url = get_url(action='tv_shows')
    xbmcplugin.addDirectoryItem(_handle, url, li, True)

    # Movies
    li = xbmcgui.ListItem(label="Movies")
    li.setArt({'icon': 'DefaultMovies.png'})
    li.setInfo('video', {'title': "Movies"})
    url = get_url(action='movies')
    xbmcplugin.addDirectoryItem(_handle, url, li, True)

    # Add TV Show
    li = xbmcgui.ListItem(label="Add TV Show")
    li.setInfo('video', {'title': "Add TV Show", 'plot': "Go to TMDB, copy the number from the TV show URL, and enter it here"})
    li.setArt({'icon': 'DefaultTVShows.png'})
    url = 'plugin://plugin.video.mila/?action=add_tv_show'
    xbmcplugin.addDirectoryItem(_handle, url, li, False)

    # Add Movie
    li = xbmcgui.ListItem(label="Add Movie")
    li.setInfo('video', {'title': "Add Movie", 'plot': "Go to TMDB, copy the number from the movie URL, and enter it here"})
    li.setArt({'icon': 'DefaultMovies.png'})
    url = 'plugin://plugin.video.mila/?action=add_movie'
    xbmcplugin.addDirectoryItem(_handle, url, li, False)

    # Refresh Data
    li = xbmcgui.ListItem(label="Refresh Data")
    li.setArt({'icon': 'DefaultFolderRefresh.png'})
    url = get_url(action='refresh')
    xbmcplugin.addDirectoryItem(_handle, url, li, False)

    # Clear Cache
    li = xbmcgui.ListItem(label="Clear Cache")
    li.setArt({'icon': 'DefaultSettings.png'})
    url = get_url(action='clear_cache')
    xbmcplugin.addDirectoryItem(_handle, url, li, False)

    # Clear Extracted Metadata
    li = xbmcgui.ListItem(label="Clear Extracted Metadata")
    li.setArt({'icon': 'DefaultSettings.png'})
    url = get_url(action='clear_extracted')
    xbmcplugin.addDirectoryItem(_handle, url, li, False)

    # Settings
    li = xbmcgui.ListItem(label="Settings")
    li.setArt({'icon': 'DefaultSettings.png'})
    xbmcplugin.addDirectoryItem(_handle, 'plugin://plugin.video.mila/?action=settings', li, False)

    xbmcplugin.endOfDirectory(_handle)

# TV SHOWS
def show_tv_shows():
    data = load_all_data()
    if not data or 'tv_shows' not in data or len(data['tv_shows']) == 0:
        log("No TV shows data loaded")
        li = xbmcgui.ListItem(label="[COLOR red]No TV shows found[/COLOR]")
        li.setArt({'icon': 'DefaultFolder.png'})
        xbmcplugin.addDirectoryItem(_handle, '', li, False)
        xbmcplugin.endOfDirectory(_handle)
        return

    xbmcplugin.setPluginCategory(_handle, "TV Shows")
    xbmcplugin.setContent(_handle, 'tvshows')

    # Sort by title
    shows = sorted(data['tv_shows'], key=lambda x: x.get('title', '').lower())

    log(f"Displaying {len(shows)} TV shows")

    for show in shows:
        tmdb_id = show.get('tmdb_id', '')

        # Fetch TMDB metadata
        tmdb_data = fetch_tmdb_tv_details(tmdb_id) if tmdb_id else None

        # Create label WITHOUT stream count in title
        label = f"[B]{show['title']}[/B]"
        if show.get('year'):
            label += f" ({show['year']})"

        # Add rating if available
        if tmdb_data:
            rating = tmdb_data.get('vote_average')
            if rating:
                label += f" [COLOR yellow]{rating:.1f}★[/COLOR]"

        # Create list item with metadata
        li = xbmcgui.ListItem(label=label)

        # Set info
        info = get_tvshow_listitem_info(show, tmdb_data)
        li.setInfo('video', info)

        # Set artwork
        set_artwork(li, tmdb_data, 'tvshow')

        # Set cast if available
        if tmdb_data and tmdb_data.get('credits'):
            cast = format_cast(tmdb_data['credits'])
            if cast:
                li.setCast(cast)

        url = get_url(action='tv_show', tmdb_id=tmdb_id)
        xbmcplugin.addDirectoryItem(_handle, url, li, True)

    xbmcplugin.endOfDirectory(_handle)

def show_tv_seasons(params):
    tmdb_id = params.get('tmdb_id')

    if not tmdb_id:
        popinfo("No TMDB ID")
        return

    data = load_all_data()
    if not data or 'tv_shows' not in data:
        popinfo("No TV shows data")
        return

    # Find show by TMDB ID
    show = None
    for s in data['tv_shows']:
        if s.get('tmdb_id') == tmdb_id:
            show = s
            break

    if not show or 'seasons' not in show:
        popinfo("Show not found or no seasons")
        return

    title = show['title']
    xbmcplugin.setPluginCategory(_handle, title)
    xbmcplugin.setContent(_handle, 'seasons')

    seasons = show.get('seasons', {})
    for season_num in sorted(seasons.keys(), key=lambda x: int(x)):
        episodes = seasons[season_num]
        ep_count = len(episodes)

        # Fetch season metadata
        tmdb_data = fetch_tmdb_tv_season(tmdb_id, season_num)

        label = f"Season {season_num}"
        if ep_count > 0:
            label += f" ({ep_count} episodes)"

        li = xbmcgui.ListItem(label=label)

        # Set info
        info = get_season_listitem_info(season_num, tmdb_data)
        li.setInfo('video', info)

        # Set artwork
        set_artwork(li, tmdb_data, 'season')

        url = get_url(action='season', tmdb_id=tmdb_id, season=season_num)
        xbmcplugin.addDirectoryItem(_handle, url, li, True)

    xbmcplugin.endOfDirectory(_handle)

def show_episodes(params):
    tmdb_id = params.get('tmdb_id')
    season = params.get('season')

    if not tmdb_id or not season:
        popinfo("Missing parameters")
        return

    data = load_all_data()
    if not data or 'tv_shows' not in data:
        popinfo("No TV shows data")
        return

    # Find show
    show = None
    for s in data['tv_shows']:
        if s.get('tmdb_id') == tmdb_id:
            show = s
            break

    if not show or 'seasons' not in show or season not in show['seasons']:
        popinfo(f"No episodes for season {season}")
        return

    show_title = show['title']
    xbmcplugin.setPluginCategory(_handle, f"{show_title} - Season {season}")
    xbmcplugin.setContent(_handle, 'episodes')

    season_data = show['seasons'][season]

    # Get season metadata for fallback artwork
    season_tmdb_data = fetch_tmdb_tv_season(tmdb_id, season)

    for ep_num in sorted(season_data.keys(), key=lambda x: int(x)):
        ep_files = season_data[ep_num]

        # Fetch episode metadata
        tmdb_data = fetch_tmdb_tv_episode(tmdb_id, season, ep_num)

        # Create label WITHOUT stream count
        if tmdb_data and tmdb_data.get('name'):
            label = f"Episode {ep_num}: {tmdb_data['name']}"
        else:
            label = f"Episode {ep_num}"

        # Add rating if available
        if tmdb_data and tmdb_data.get('vote_average'):
            label += f" [COLOR yellow]{tmdb_data['vote_average']:.1f}★[/COLOR]"

        li = xbmcgui.ListItem(label=label)

        # Set info
        info = get_episode_listitem_info(season, ep_num, tmdb_data)
        li.setInfo('video', info)

        # Set artwork - use season poster as fallback for episodes
        set_artwork(li, tmdb_data, 'episode', season_tmdb_data)

        # Set cast if available
        if tmdb_data and tmdb_data.get('credits'):
            cast = format_cast(tmdb_data['credits'])
            if cast:
                li.setCast(cast)

        # Add context menu for manual stream selection
        context_menu = []
        context_menu.append(("Select Stream", 
                           f"RunPlugin({get_url(action='context_select_stream', tmdb_id=tmdb_id, content_type='episode', season=season, episode=ep_num, show_title=show_title)})"))
        li.addContextMenuItems(context_menu)

        li.setProperty('IsPlayable', 'true')

        url = get_url(
            action='play_episode',
            tmdb_id=tmdb_id,
            season=season,
            episode=ep_num,
            show_title=show_title
        )

        xbmcplugin.addDirectoryItem(_handle, url, li, False)

    xbmcplugin.endOfDirectory(_handle)

def handle_episode_play(params):
    """Handle episode playback with manual stream selection option"""
    tmdb_id = params.get('tmdb_id')
    season = params.get('season')
    episode = params.get('episode')
    show_title = params.get('show_title', 'Episode')
    manual_select = params.get('manual_select', 'false') == 'true'

    if not tmdb_id or not season or not episode:
        popinfo("Missing parameters")
        return

    data = load_all_data()
    if not data or 'tv_shows' not in data:
        popinfo("No data available")
        return

    # Find show and episode streams
    show = None
    for s in data['tv_shows']:
        if s.get('tmdb_id') == tmdb_id:
            show = s
            break

    if not show or 'seasons' not in show or season not in show['seasons']:
        popinfo("Show or season not found")
        return

    season_data = show['seasons'][season]
    if episode not in season_data:
        popinfo(f"Episode {episode} not found")
        return

    episode_files = season_data[episode]
    streams = []

    for file in episode_files:
        streams.append({
            'ident': file['ident'],
            'filename': file['filename'],
            'size': file.get('size', '0'),
            'quality': file.get('quality', 'Unknown')
        })

    if not streams:
        popinfo("No streams available")
        return

    # Fetch episode name for better title
    ep_name = ""
    tmdb_data = fetch_tmdb_tv_episode(tmdb_id, season, episode)
    if tmdb_data and tmdb_data.get('name'):
        ep_name = f": {tmdb_data['name']}"

    title = f"{show_title} S{season}E{episode}{ep_name}"

    # Use manual stream selection if requested, otherwise use normal flow
    if manual_select:
        manual_stream_selection(streams, title)
    else:
        select_stream_popup(streams, title)

# MOVIES
def show_movies():
    data = load_all_data()
    if not data or 'movies' not in data or len(data['movies']) == 0:
        log("No movies data loaded")
        li = xbmcgui.ListItem(label="[COLOR red]No movies found[/COLOR]")
        li.setArt({'icon': 'DefaultFolder.png'})
        xbmcplugin.addDirectoryItem(_handle, '', li, False)
        xbmcplugin.endOfDirectory(_handle)
        return

    xbmcplugin.setPluginCategory(_handle, "Movies")
    xbmcplugin.setContent(_handle, 'movies')

    # Sort by title
    movies = sorted(data['movies'], key=lambda x: x.get('title', '').lower())

    log(f"Displaying {len(movies)} movies")

    for movie in movies:
        tmdb_id = movie.get('tmdb_id', '')

        # Fetch TMDB metadata
        tmdb_data = fetch_tmdb_movie_details(tmdb_id) if tmdb_id else None

        # Create label WITHOUT stream count in title
        label = f"[B]{movie['title']}[/B]"
        if movie.get('year'):
            label += f" ({movie['year']})"

        # Add rating if available
        if tmdb_data:
            rating = tmdb_data.get('vote_average')
            if rating:
                label += f" [COLOR yellow]{rating:.1f}★[/COLOR]"

        # Create list item with metadata
        li = xbmcgui.ListItem(label=label)

        # Set info
        info = get_movie_listitem_info(movie, tmdb_data)
        li.setInfo('video', info)

        # Set artwork
        set_artwork(li, tmdb_data, 'movie')

        # Set cast if available
        if tmdb_data and tmdb_data.get('credits'):
            cast = format_cast(tmdb_data['credits'])
            if cast:
                li.setCast(cast)

        # Add context menu for manual stream selection
        context_menu = []
        context_menu.append(("Select Stream", 
                           f"RunPlugin({get_url(action='context_select_stream', tmdb_id=tmdb_id, content_type='movie', movie_title=movie['title'], movie_year=movie.get('year', ''))})"))
        li.addContextMenuItems(context_menu)

        li.setProperty('IsPlayable', 'true')

        url = get_url(
            action='play_movie',
            tmdb_id=tmdb_id,
            movie_title=movie['title'],
            movie_year=movie.get('year', '')
        )

        xbmcplugin.addDirectoryItem(_handle, url, li, False)

    xbmcplugin.endOfDirectory(_handle)

def handle_movie_play(params):
    """Handle movie playback with manual stream selection option"""
    tmdb_id = params.get('tmdb_id')
    movie_title = params.get('movie_title', 'Movie')
    movie_year = params.get('movie_year', '')
    manual_select = params.get('manual_select', 'false') == 'true'

    if not tmdb_id:
        popinfo("No TMDB ID")
        return

    data = load_all_data()
    if not data or 'movies' not in data:
        popinfo("No movies data")
        return

    # Find movie
    movie = None
    for m in data['movies']:
        if m.get('tmdb_id') == tmdb_id:
            movie = m
            break

    if not movie or 'streams' not in movie:
        popinfo("Movie not found")
        return

    streams = []
    for stream in movie['streams']:
        streams.append({
            'ident': stream['ident'],
            'filename': stream['filename'],
            'size': stream.get('size', '0'),
            'quality': stream.get('quality', 'Unknown')
        })

    if not streams:
        popinfo("No streams available")
        return

    title = f"{movie_title} ({movie_year})" if movie_year else movie_title

    # Use manual stream selection if requested, otherwise use normal flow
    if manual_select:
        manual_stream_selection(streams, title)
    else:
        select_stream_popup(streams, title)

# ROUTER - UPDATED WITH NEW ACTIONS
def router(paramstring):
    params = dict(parse_qsl(paramstring))

    try:
        action = params.get('action', '')

        if action == 'search':
            search_content()
        elif action == 'tv_shows':
            show_tv_shows()
        elif action == 'tv_show':
            show_tv_seasons(params)
        elif action == 'season':
            show_episodes(params)
        elif action == 'play_episode':
            handle_episode_play(params)
        elif action == 'movies':
            show_movies()
        elif action == 'play_movie':
            handle_movie_play(params)
        elif action == 'tmdb_list':
            list_type = params.get('list_type', '')
            list_name = params.get('list_name', 'TMDB List')
            show_tmdb_list(list_type, list_name)
        elif action == 'context_select_stream':
            show_context_menu_select_stream(params)
        elif action == 'refresh':
            popinfo("Force refreshing data from WebShare...")
            # Clear everything and force fresh download
            clear_cache()
            clear_extracted_metadata()
            global MANIFEST_FILE_ID
            MANIFEST_FILE_ID = ""
            _addon.setSetting('manifest_id', "")
            # Trigger auto-find which will download fresh ZIP
            try:
                from manifest_finder import auto_find_manifest_on_startup
                auto_find_manifest_on_startup()
            except:
                pass
            main_menu()
        elif action == 'clear_cache':
            clear_cache()
            main_menu()
        elif action == 'clear_extracted':
            clear_extracted_metadata()
            main_menu()
        elif action == 'add_tv_show':
            from websharder import add_tv_show
            add_tv_show()
        elif action == 'add_movie':
            from websharder import add_movie
            add_movie()
        elif action == 'settings':
            _addon.openSettings()
        elif action == 'no_stream_available':
            popinfo("This content is in the TMDB list but no streams were found on WebShare.")
            main_menu()
        elif action == 'no_content_available':
            popinfo("This content is in the TMDB list but is not in the main database.")
            main_menu()
        else:
            main_menu()

    except Exception as e:
        log(f"Router error: {str(e)}")
        traceback.print_exc()
        popinfo("Error occurred")

if __name__ == '__main__':
    router(sys.argv[2][1:] if len(sys.argv) > 2 else '')
