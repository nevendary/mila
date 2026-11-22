# -*- coding: utf-8 -*-
# Module: default
# Author: nevendary + cache-sk + Ultra Simple
# License: AGPL v.3

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

try:
    from urllib import urlencode
    from urlparse import parse_qsl
except ImportError:
    from urllib.parse import urlencode, parse_qsl

# Global variables
_url = sys.argv[0]
_handle = int(sys.argv[1])
_addon = xbmcaddon.Addon()

# GitHub Pages URL for data
GITHUB_DATA_URL = "https://raw.githubusercontent.com/nevendary/mila/main/data/kodi_tmdb_cz.json"
# Local cache file path
CACHE_FILE = xbmcvfs.translatePath(os.path.join(_addon.getAddonInfo('profile'), 'data_cache.json'))
CACHE_DURATION = 3600  # 1 hour in seconds

# Webshare session
_session = requests.Session()
_session.headers.update({
    'User-Agent': 'Mozilla/5.0',
    'Referer': 'https://webshare.cz/'
})

def log(msg):
    xbmc.log("[MILA] " + str(msg), xbmc.LOGINFO)

def get_url(**kwargs):
    return _url + '?' + urlencode(kwargs)

def popinfo(message):
    xbmcgui.Dialog().notification(_addon.getAddonInfo('name'), message, xbmcgui.NOTIFICATION_INFO, 3000)

def generate_id(title, year=""):
    """Generate consistent ID from title and year (same as API)"""
    text = f"{title.lower()}{year}".strip()
    return hashlib.md5(text.encode('utf-8')).hexdigest()[:8]

def load_data():
    """Load data from cache or fetch from GitHub"""
    # Check cache first
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)
            # Check if cache is still valid
            if time.time() - cache_data.get('timestamp', 0) < CACHE_DURATION:
                log("Using cached data")
                return cache_data.get('data')
        except Exception as e:
            log(f"Cache read error: {str(e)}")

    # Fetch fresh data from GitHub
    try:
        log(f"Fetching data from GitHub: {GITHUB_DATA_URL}")
        response = requests.get(GITHUB_DATA_URL, timeout=30)
        if response.status_code == 200:
            data = response.json()

            # Save to cache
            try:
                cache_dir = os.path.dirname(CACHE_FILE)
                if not os.path.exists(cache_dir):
                    os.makedirs(cache_dir)
                with open(CACHE_FILE, 'w', encoding='utf-8') as f:
                    json.dump({
                        'timestamp': time.time(),
                        'data': data
                    }, f)
                log("Data cached successfully")
            except Exception as e:
                log(f"Cache write error: {str(e)}")

            return data
        else:
            log(f"GitHub request failed: {response.status_code}")
    except Exception as e:
        log(f"Error fetching from GitHub: {str(e)}")
        popinfo("Error loading data")

    return None

def refresh_data():
    """Force refresh data from GitHub"""
    if os.path.exists(CACHE_FILE):
        os.remove(CACHE_FILE)
    return load_data()

# Webshare login/playback functions (unchanged)
def login():
    username = _addon.getSetting('wsuser')
    password = _addon.getSetting('wspass')
    if not username or not password:
        popinfo("Set username/password")
        return None

    try:
        response = _session.post('https://webshare.cz/api/salt/', data={'username_or_email': username}, timeout=10)
        xml = ET.fromstring(response.content)
        if xml.find('status').text != 'OK':
            return None

        salt = xml.find('salt').text
        encrypted_pass = hashlib.sha1(md5crypt(password.encode('utf-8'), salt.encode('utf-8')).encode('utf-8')).hexdigest()
        pass_digest = hashlib.md5(username.encode('utf-8') + b':Webshare:' + encrypted_pass.encode('utf-8')).hexdigest()

        response = _session.post('https://webshare.cz/api/login/', data={
            'username_or_email': username,
            'password': encrypted_pass,
            'digest': pass_digest,
            'keep_logged_in': 1
        }, timeout=10)
        xml = ET.fromstring(response.content)
        if xml.find('status').text == 'OK':
            return xml.find('token').text
    except Exception as e:
        log(f"Login error: {str(e)}")

    return None

def get_stream_link(ident, token):
    duuid = _addon.getSetting('duuid') or str(uuid.uuid4())
    _addon.setSetting('duuid', duuid)

    try:
        response = _session.post('https://webshare.cz/api/file_link/', data={
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

def get_metadata_from_api(stream):
    """Get metadata from API response or extract from filename"""
    # Use metadata from data file if available
    if 'metadata' in stream:
        return stream['metadata']

    # Fallback to filename parsing
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
        'size_mb': int(stream.get('size', 0)) / (1024 * 1024)
    }

    # Extract audio channels from filename
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

    # Extract languages from filename
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

# Ranking and selection functions (unchanged except for metadata extraction)
def rank_streams(streams):
    """Rank streams based on user preferences"""
    preferred_lang = _addon.getSetting('preferred_language') or 'English'
    max_quality = _addon.getSetting('max_quality') or '4K'
    prefer_hdr = _addon.getSetting('prefer_hdr') == 'true'
    min_audio_channels = _addon.getSetting('min_audio_channels') or '2.0'
    autoplay_resolution = _addon.getSetting('autoplay_resolution') or '1080p'

    quality_values = {
        'Unknown': 1,
        '480p': 2,
        '720p': 3,
        '1080p': 4,
        '4K': 5,
        '4K HDR': 6
    }

    max_quality_value = quality_values.get(max_quality, 5)
    target_quality_value = quality_values.get(autoplay_resolution, 4)

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

    preferred_lang = _addon.getSetting('preferred_language') or 'English'
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

def select_stream_popup(streams, title):
    """Show enhanced popup dialog for stream selection"""
    if not streams:
        popinfo("No streams available")
        return None

    ranked_streams = rank_streams(streams)
    autoplay_enabled = _addon.getSetting('autoplay') == 'true'
    skip_popup = _addon.getSetting('skip_popup') == 'true'

    if autoplay_enabled and skip_popup and ranked_streams:
        best_stream = ranked_streams[0]['stream']
        play_video(best_stream['ident'], title)
        return best_stream['ident']

    items = []
    for ranked in ranked_streams:
        stream = ranked['stream']
        info = ranked['info']
        size_mb = ranked['size_mb']
        index = ranked['index']

        label = format_stream_label(stream, info, index, size_mb)

        if ranked['score'] == ranked_streams[0]['score']:
            label = f"[B][COLOR yellow]★ {label}[/COLOR][/B]"

        items.append((label, stream['ident'], info))

    if autoplay_enabled and ranked_streams:
        best_info = ranked_streams[0]['info']
        notification_msg = f"Auto-selected: {best_info['quality']}"
        if best_info['languages']:
            notification_msg += f" ({'/'.join(best_info['languages'][:1])})"
        popinfo(notification_msg)

        best_stream = ranked_streams[0]['stream']
        play_video(best_stream['ident'], title)
        return best_stream['ident']

    dialog = xbmcgui.Dialog()
    selected = dialog.select(f"Select stream - {title}", [item[0] for item in items])

    if selected >= 0:
        stream_id = items[selected][1]
        stream_info = items[selected][2]

        info_text = f"[B]Stream Details:[/B]\n"
        info_text += f"Quality: [B]{stream_info['quality']}[/B]\n"

        if stream_info['languages']:
            info_text += f"Languages: [COLOR yellow]{', '.join(stream_info['languages'])}[/COLOR]\n"

        if stream_info['audio_channels'] or stream_info['audio_codec']:
            audio_info = []
            if stream_info['audio_channels']:
                audio_info.append(stream_info['audio_channels'])
            if stream_info['audio_codec']:
                audio_info.append(stream_info['audio_codec'])
            info_text += f"Audio: [COLOR cyan]{' '.join(audio_info)}[/COLOR]\n"

        if stream_info['source']:
            info_text += f"Source: [COLOR lime]{stream_info['source']}[/COLOR]\n"

        if stream_info['hdr']:
            info_text += f"HDR: [COLOR gold]Yes[/COLOR]\n"

        if stream_info['size_mb'] > 0:
            if stream_info['size_mb'] > 1024:
                info_text += f"Size: {stream_info['size_mb']/1024:.1f} GB\n"
            else:
                info_text += f"Size: {stream_info['size_mb']:.0f} MB\n"

        show_info = _addon.getSetting('show_stream_info') == 'true'
        if show_info:
            xbmcgui.Dialog().ok("Stream Information", info_text)

        play_video(stream_id, f"{title}")
        return stream_id

    return None

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
    data = load_data()
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
                'relevance': title_lower.find(search_term_lower)  # Lower index = better match
            })
        # Also search in alternative titles if available
        elif movie.get('original_title'):
            original_lower = movie.get('original_title', '').lower()
            if search_term_lower in original_lower:
                found_items.append({
                    'type': 'movie',
                    'data': movie,
                    'relevance': original_lower.find(search_term_lower) + 10  # Slightly less relevant than main title
                })
        # Search in description if search term is long enough
        elif len(search_term) > 3 and movie.get('description'):
            desc_lower = movie.get('description', '').lower()
            if search_term_lower in desc_lower:
                found_items.append({
                    'type': 'movie',
                    'data': movie,
                    'relevance': desc_lower.find(search_term_lower) + 20
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
        # Also search in original title if available
        elif show.get('original_name'):
            original_lower = show.get('original_name', '').lower()
            if search_term_lower in original_lower:
                found_items.append({
                    'type': 'tvshow',
                    'data': show,
                    'relevance': original_lower.find(search_term_lower) + 10
                })
        # Search in description if search term is long enough
        elif len(search_term) > 3 and show.get('description'):
            desc_lower = show.get('description', '').lower()
            if search_term_lower in desc_lower:
                found_items.append({
                    'type': 'tvshow',
                    'data': show,
                    'relevance': desc_lower.find(search_term_lower) + 20
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
    movie_id = generate_id(movie['title'], movie.get('year', ''))
    
    label = f"[B]{movie['title']}[/B]"
    if movie.get('year'):
        label += f" ({movie['year']})"
    
    # Add movie icon
    label += " [MOVIE]"
    
    li = xbmcgui.ListItem(label=label)
    li.setArt({'icon': 'DefaultMovies.png'})
    
    info = {
        'title': movie['title'],
        'year': int(movie.get('year', 0)) if movie.get('year') else 0,
        'mediatype': 'movie'
    }
    
    if movie.get('description'):
        info['plot'] = movie['description'][:200] + "..." if len(movie['description']) > 200 else movie['description']
    
    if movie.get('rating'):
        info['rating'] = float(movie['rating'])
        # Add rating to label
        label += f" [IMDB: {movie['rating']}]"
    
    if movie.get('genres'):
        genres = [g.get('name', '') for g in movie.get('genres', []) if g.get('name')]
        if genres:
            info['genre'] = ' / '.join(genres)
            # Add genres to label
            label += f" [{', '.join(genres[:2])}]"
    
    li.setLabel(label)
    li.setInfo('video', info)
    li.setProperty('IsPlayable', 'true')
    
    if movie.get('poster'):
        li.setArt({'poster': movie['poster']})
    if movie.get('backdrop'):
        li.setArt({'fanart': movie['backdrop']})
    
    url = get_url(
        action='play_movie',
        movie_id=movie_id,
        movie_title=movie['title'],
        movie_year=movie.get('year', '')
    )
    
    xbmcplugin.addDirectoryItem(_handle, url, li, False)

def add_tvshow_search_result(show):
    """Add a TV show to search results"""
    show_id = generate_id(show['title'], show.get('year', ''))
    
    label = f"[B]{show['title']}[/B]"
    if show.get('year'):
        label += f" ({show['year']})"
    
    # Add TV show icon
    label += " [TV SHOW]"
    
    li = xbmcgui.ListItem(label=label)
    li.setArt({'icon': 'DefaultTVShows.png'})
    
    info = {
        'title': show['title'],
        'year': int(show.get('year', 0)) if show.get('year') else 0,
        'mediatype': 'tvshow'
    }
    
    if show.get('description'):
        info['plot'] = show['description'][:200] + "..." if len(show['description']) > 200 else show['description']
    
    if show.get('rating'):
        info['rating'] = float(show['rating'])
        # Add rating to label
        label += f" [IMDB: {show['rating']}]"
    
    if show.get('genres'):
        genres = [g.get('name', '') for g in show.get('genres', []) if g.get('name')]
        if genres:
            info['genre'] = ' / '.join(genres)
            # Add genres to label
            label += f" [{', '.join(genres[:2])}]"
    
    li.setLabel(label)
    li.setInfo('video', info)
    
    if show.get('poster'):
        li.setArt({'poster': show['poster']})
    if show.get('backdrop'):
        li.setArt({'fanart': show['backdrop']})
    
    url = get_url(action='tv_show', show_id=show_id)
    xbmcplugin.addDirectoryItem(_handle, url, li, True)

# MAIN MENU - MODIFIED TO INCLUDE SEARCH
def main_menu():
    xbmcplugin.setPluginCategory(_handle, "MILA")
    xbmcplugin.setContent(_handle, 'files')

    # Load data to check if available
    data = load_data()
    if not data:
        li = xbmcgui.ListItem(label="[COLOR red]Error: Could not load data[/COLOR]")
        xbmcplugin.addDirectoryItem(_handle, '', li, False)

        # Refresh button
        li = xbmcgui.ListItem(label="Refresh Data")
        li.setArt({'icon': 'DefaultFolder.png'})
        url = get_url(action='refresh')
        xbmcplugin.addDirectoryItem(_handle, url, li, False)

        xbmcplugin.endOfDirectory(_handle)
        return

    # Search
    li = xbmcgui.ListItem(label="[B][COLOR yellow]Search[/COLOR][/B]")
    li.setArt({'icon': 'DefaultSearch.png'})
    url = get_url(action='search')
    xbmcplugin.addDirectoryItem(_handle, url, li, False)

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

    # All Content
    li = xbmcgui.ListItem(label="All Content")
    li.setArt({'icon': 'DefaultFolder.png'})
    li.setInfo('video', {'title': "All Content"})
    url = get_url(action='all_content')
    xbmcplugin.addDirectoryItem(_handle, url, li, True)

    # Refresh Data
    li = xbmcgui.ListItem(label="Refresh Data")
    li.setArt({'icon': 'DefaultSettings.png'})
    url = get_url(action='refresh')
    xbmcplugin.addDirectoryItem(_handle, url, li, False)

    # Settings
    li = xbmcgui.ListItem(label="Settings")
    li.setArt({'icon': 'DefaultSettings.png'})
    xbmcplugin.addDirectoryItem(_handle, 'plugin://plugin.video.mila/?action=settings', li, False)

    xbmcplugin.endOfDirectory(_handle)

# TV SHOWS - MODIFIED FOR SINGLE FILE
def show_tv_shows():
    data = load_data()
    if not data or 'tv_shows' not in data:
        popinfo("No TV shows")
        main_menu()
        return

    xbmcplugin.setPluginCategory(_handle, "TV Shows")
    xbmcplugin.setContent(_handle, 'tvshows')

    for i, show in enumerate(data['tv_shows']):
        show_id = generate_id(show['title'], show.get('year', ''))

        label = show['title']
        if show.get('year'):
            label += f" ({show['year']})"

        info = {
            'title': show['title'],
            'year': int(show.get('year', 0)) if show.get('year') else 0,
            'mediatype': 'tvshow'
        }

        if show.get('description'):
            info['plot'] = show['description']
        elif show.get('description_cz'):
            info['plot'] = show['description_cz']

        if show.get('rating'):
            info['rating'] = float(show['rating'])

        if show.get('vote_count'):
            info['votes'] = str(show['vote_count'])

        if show.get('genres'):
            genres = [g.get('name', '') for g in show.get('genres', []) if g.get('name')]
            if genres:
                info['genre'] = ' / '.join(genres)

        li = xbmcgui.ListItem(label=label)
        li.setArt({'icon': 'DefaultTVShows.png'})

        if show.get('poster'):
            li.setArt({'poster': show['poster']})
        if show.get('backdrop'):
            li.setArt({'fanart': show['backdrop']})

        li.setInfo('video', info)

        url = get_url(action='tv_show', show_id=show_id)
        xbmcplugin.addDirectoryItem(_handle, url, li, True)

    xbmcplugin.endOfDirectory(_handle)

def show_tv_seasons(params):
    show_id = params.get('show_id')

    if not show_id:
        popinfo("No show ID")
        return

    data = load_data()
    if not data or 'tv_shows' not in data:
        popinfo("No TV shows data")
        return

    # Find show by ID
    show = None
    for s in data['tv_shows']:
        if generate_id(s['title'], s.get('year', '')) == show_id:
            show = s
            break

    if not show or 'seasons' not in show:
        popinfo("Show not found")
        return

    title = show['title']
    xbmcplugin.setPluginCategory(_handle, title)
    xbmcplugin.setContent(_handle, 'seasons')

    for season_num in sorted(show['seasons'].keys(), key=lambda x: int(x)):
        label = f"Season {season_num}"

        li = xbmcgui.ListItem(label=label)
        li.setArt({'icon': 'DefaultFolder.png'})

        info = {
            'title': f"Season {season_num}",
            'mediatype': 'season',
            'season': int(season_num)
        }

        # Try to get season details
        if show.get('seasons_info'):
            for season_info in show['seasons_info']:
                if season_info.get('season_number') == int(season_num):
                    if season_info.get('name'):
                        info['title'] = season_info['name']
                    if season_info.get('overview'):
                        info['plot'] = season_info['overview']
                    elif season_info.get('overview_cz'):
                        info['plot'] = season_info['overview_cz']
                    if season_info.get('air_date'):
                        info['year'] = int(season_info['air_date'][:4]) if season_info['air_date'] else 0
                    if season_info.get('poster_path'):
                        li.setArt({'poster': season_info['poster_path']})
                    break

        li.setInfo('video', info)

        url = get_url(action='season', show_id=show_id, season=season_num)
        xbmcplugin.addDirectoryItem(_handle, url, li, True)

    xbmcplugin.endOfDirectory(_handle)

def show_episodes(params):
    show_id = params.get('show_id')
    season = params.get('season')

    if not show_id or not season:
        popinfo("Missing parameters")
        return

    data = load_data()
    if not data or 'tv_shows' not in data:
        popinfo("No TV shows data")
        return

    # Find show
    show = None
    for s in data['tv_shows']:
        if generate_id(s['title'], s.get('year', '')) == show_id:
            show = s
            break

    if not show or 'seasons' not in show or season not in show['seasons']:
        popinfo(f"No episodes for season {season}")
        return

    show_title = show['title']
    xbmcplugin.setPluginCategory(_handle, f"{show_title} - Season {season}")
    xbmcplugin.setContent(_handle, 'episodes')

    season_data = show['seasons'][season]

    # Get season details
    season_details = None
    if show.get('detailed_seasons') and season in show['detailed_seasons']:
        season_details = show['detailed_seasons'][season]

    for ep_num in sorted(season_data.keys(), key=lambda x: int(x)):
        ep_data = season_data[ep_num]

        # Default label
        label = f"Episode {ep_num}"

        # Try to get episode details
        episode_details = None
        if season_details and season_details.get('episodes'):
            for ep in season_details['episodes']:
                if ep.get('episode_number') == int(ep_num):
                    episode_details = ep
                    if ep.get('name'):
                        label = f"Episode {ep_num}: {ep['name']}"
                    break

        li = xbmcgui.ListItem(label=label)
        li.setArt({'icon': 'DefaultVideo.png'})

        info = {
            'title': f"Episode {ep_num}",
            'season': int(season),
            'episode': int(ep_num),
            'mediatype': 'episode'
        }

        if episode_details:
            if episode_details.get('name'):
                info['title'] = episode_details['name']
            if episode_details.get('overview'):
                info['plot'] = episode_details['overview']
            elif episode_details.get('overview_cz'):
                info['plot'] = episode_details['overview_cz']
            if episode_details.get('air_date'):
                info['aired'] = episode_details['air_date']
            if episode_details.get('runtime'):
                info['duration'] = episode_details['runtime'] * 60
            if episode_details.get('vote_average'):
                info['rating'] = episode_details['vote_average']
            if episode_details.get('still_path'):
                li.setArt({'thumb': episode_details['still_path']})

        li.setInfo('video', info)
        li.setProperty('IsPlayable', 'true')

        url = get_url(
            action='play_episode',
            show_id=show_id,
            season=season,
            episode=ep_num,
            show_title=show_title
        )

        xbmcplugin.addDirectoryItem(_handle, url, li, False)

    xbmcplugin.endOfDirectory(_handle)

def handle_episode_play(params):
    """Handle episode playback with enhanced stream selection"""
    show_id = params.get('show_id')
    season = params.get('season')
    episode = params.get('episode')
    show_title = params.get('show_title', 'Episode')

    if not show_id or not season or not episode:
        popinfo("Missing parameters")
        return

    data = load_data()
    if not data or 'tv_shows' not in data:
        popinfo("No data available")
        return

    # Find show and episode streams
    show = None
    for s in data['tv_shows']:
        if generate_id(s['title'], s.get('year', '')) == show_id:
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
        # Use metadata if available in the data file
        metadata = file.get('metadata', {})
        if not metadata:
            # Generate metadata from filename
            metadata = get_metadata_from_api(file)

        streams.append({
            'ident': file['ident'],
            'filename': file['filename'],
            'size': file.get('size', '0'),
            'quality': metadata.get('quality', 'Unknown'),
            'metadata': metadata,
            'type': 'webshare'
        })

    if not streams:
        popinfo("No streams available")
        return

    title = f"{show_title} S{season}E{episode}"
    autoplay_enabled = _addon.getSetting('autoplay') == 'true'

    if len(streams) == 1:
        stream = streams[0]
        play_video(stream['ident'], title)
    elif autoplay_enabled:
        best_stream = get_autoplay_stream(streams)
        if best_stream:
            play_video(best_stream['ident'], title)
        else:
            select_stream_popup(streams, title)
    else:
        select_stream_popup(streams, title)

# MOVIES - MODIFIED FOR SINGLE FILE
def show_movies():
    data = load_data()
    if not data or 'movies' not in data:
        popinfo("No movies")
        main_menu()
        return

    xbmcplugin.setPluginCategory(_handle, "Movies")
    xbmcplugin.setContent(_handle, 'movies')

    for i, movie in enumerate(data['movies']):
        movie_id = generate_id(movie['title'], movie.get('year', ''))

        label = movie['title']
        if movie.get('year'):
            label += f" ({movie['year']})"

        info = {
            'title': movie['title'],
            'year': int(movie.get('year', 0)) if movie.get('year') else 0,
            'mediatype': 'movie'
        }

        if movie.get('description'):
            info['plot'] = movie['description']
        elif movie.get('description_cz'):
            info['plot'] = movie['description_cz']

        if movie.get('rating'):
            info['rating'] = float(movie['rating'])

        if movie.get('vote_count'):
            info['votes'] = str(movie['vote_count'])

        if movie.get('runtime'):
            info['duration'] = movie['runtime'] * 60

        if movie.get('release_date'):
            info['premiered'] = movie['release_date']

        if movie.get('genres'):
            genres = [g.get('name', '') for g in movie.get('genres', []) if g.get('name')]
            if genres:
                info['genre'] = ' / '.join(genres)

        if movie.get('cast'):
            cast = []
            for actor in movie.get('cast', [])[:10]:
                if actor.get('name'):
                    cast.append(actor['name'])
            if cast:
                info['cast'] = cast

        if movie.get('crew'):
            directors = []
            for crew in movie.get('crew', []):
                if crew.get('job') == 'Director' and crew.get('name'):
                    directors.append(crew['name'])
            if directors:
                info['director'] = ' / '.join(directors)

        li = xbmcgui.ListItem(label=label)
        li.setArt({'icon': 'DefaultMovies.png'})

        if movie.get('poster'):
            li.setArt({'poster': movie['poster']})
        if movie.get('backdrop'):
            li.setArt({'fanart': movie['backdrop']})

        li.setInfo('video', info)
        li.setProperty('IsPlayable', 'true')

        url = get_url(
            action='play_movie',
            movie_id=movie_id,
            movie_title=movie['title'],
            movie_year=movie.get('year', '')
        )

        xbmcplugin.addDirectoryItem(_handle, url, li, False)

    xbmcplugin.endOfDirectory(_handle)

def handle_movie_play(params):
    """Handle movie playback with enhanced stream selection"""
    movie_id = params.get('movie_id')
    movie_title = params.get('movie_title', 'Movie')
    movie_year = params.get('movie_year', '')

    if not movie_id:
        popinfo("No movie ID")
        return

    data = load_data()
    if not data or 'movies' not in data:
        popinfo("No movies data")
        return

    # Find movie
    movie = None
    for m in data['movies']:
        if generate_id(m['title'], m.get('year', '')) == movie_id:
            movie = m
            break

    if not movie or 'streams' not in movie:
        popinfo("Movie not found")
        return

    streams = []
    for stream in movie['streams']:
        # Use metadata if available in the data file
        metadata = stream.get('metadata', {})
        if not metadata:
            # Generate metadata from filename
            metadata = get_metadata_from_api(stream)

        streams.append({
            'ident': stream['ident'],
            'filename': stream['name'],
            'size': stream.get('size', '0'),
            'quality': metadata.get('quality', 'Unknown'),
            'metadata': metadata,
            'type': 'webshare'
        })

    if not streams:
        popinfo("No streams available")
        return

    title = f"{movie_title} ({movie_year})" if movie_year else movie_title
    autoplay_enabled = _addon.getSetting('autoplay') == 'true'

    if len(streams) == 1:
        stream = streams[0]
        play_video(stream['ident'], title)
    elif autoplay_enabled:
        best_stream = get_autoplay_stream(streams)
        if best_stream:
            play_video(best_stream['ident'], title)
        else:
            select_stream_popup(streams, title)
    else:
        select_stream_popup(streams, title)

# ALL CONTENT - MODIFIED FOR SINGLE FILE
def show_all_content():
    """Show all content that can be browsed"""
    data = load_data()
    if not data:
        popinfo("No data available")
        main_menu()
        return

    xbmcplugin.setPluginCategory(_handle, "All Content")
    xbmcplugin.setContent(_handle, 'files')

    movies = data.get('movies', [])
    tv_shows = data.get('tv_shows', [])

    # Show Movies section
    if movies:
        li = xbmcgui.ListItem(label="[COLOR yellow]--- MOVIES ---[/COLOR]")
        li.setArt({'icon': 'DefaultFolder.png'})
        xbmcplugin.addDirectoryItem(_handle, '', li, False)

        for movie in movies[:50]:
            movie_id = generate_id(movie['title'], movie.get('year', ''))

            label = movie['title']
            if movie.get('year'):
                label += f" ({movie['year']})"

            li = xbmcgui.ListItem(label=label)
            li.setArt({'icon': 'DefaultMovies.png'})

            info = {
                'title': movie['title'],
                'year': int(movie.get('year', 0)) if movie.get('year') else 0,
                'mediatype': 'movie'
            }

            if movie.get('poster'):
                li.setArt({'poster': movie['poster']})
            if movie.get('backdrop'):
                li.setArt({'fanart': movie['backdrop']})

            li.setInfo('video', info)
            li.setProperty('IsPlayable', 'true')

            url = get_url(
                action='play_movie',
                movie_id=movie_id,
                movie_title=movie['title'],
                movie_year=movie.get('year', '')
            )

            xbmcplugin.addDirectoryItem(_handle, url, li, False)

    # Show TV Shows section
    if tv_shows:
        li = xbmcgui.ListItem(label="[COLOR yellow]--- TV SHOWS ---[/COLOR]")
        li.setArt({'icon': 'DefaultFolder.png'})
        xbmcplugin.addDirectoryItem(_handle, '', li, False)

        for show in tv_shows[:30]:
            show_id = generate_id(show['title'], show.get('year', ''))

            label = show['title']
            if show.get('year'):
                label += f" ({show['year']})"

            li = xbmcgui.ListItem(label=label)
            li.setArt({'icon': 'DefaultTVShows.png'})

            info = {
                'title': show['title'],
                'year': int(show.get('year', 0)) if show.get('year') else 0,
                'mediatype': 'tvshow'
            }

            if show.get('poster'):
                li.setArt({'poster': show['poster']})
            if show.get('backdrop'):
                li.setArt({'fanart': show['backdrop']})

            li.setInfo('video', info)

            url = get_url(action='tv_show', show_id=show_id)
            xbmcplugin.addDirectoryItem(_handle, url, li, True)

    xbmcplugin.endOfDirectory(_handle)

# REFRESH DATA ACTION
def refresh_data_action():
    popinfo("Refreshing data...")
    data = refresh_data()
    if data:
        popinfo("Data refreshed successfully")
    else:
        popinfo("Failed to refresh data")
    main_menu()

# ROUTER
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
        elif action == 'all_content':
            show_all_content()
        elif action == 'refresh':
            refresh_data_action()
        elif action == 'settings':
            _addon.openSettings()
        else:
            main_menu()

    except Exception as e:
        log(f"Router error: {str(e)}")
        traceback.print_exc()
        popinfo("Error occurred")

if __name__ == '__main__':
    router(sys.argv[2][1:] if len(sys.argv) > 2 else '')
