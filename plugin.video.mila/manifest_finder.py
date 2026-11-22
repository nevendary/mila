#!/usr/bin/env python3
"""
MILA Manifest Finder - FIXED to ALWAYS CHECK FOR UPDATES
"""
import sys
import xbmc
import xbmcgui
import xbmcaddon
import xbmcvfs
import requests
import json
import time
import os
import re
import zipfile
import io
from xml.etree import ElementTree as ET
import hashlib
from md5crypt import md5crypt
import traceback

try:
    from urllib import urlencode
    from urlparse import parse_qsl
except ImportError:
    from urllib.parse import urlencode, parse_qsl

# Addon info
_addon = xbmcaddon.Addon()
_addon_id = _addon.getAddonInfo('id')
_addon_name = _addon.getAddonInfo('name')

# WebShare configuration
WEBSHARE_BASE_URL = "https://webshare.cz/api/"
WEBSHARE_USER = _addon.getSetting('wsuser')
WEBSHARE_PASS = _addon.getSetting('wspass')

# Cache directory
CACHE_DIR = xbmcvfs.translatePath(os.path.join(_addon.getAddonInfo('profile'), 'cache'))
ZIP_CACHE_DIR = os.path.join(CACHE_DIR, 'zip_cache')
METADATA_DIR = os.path.join(CACHE_DIR, 'extracted_metadata')

# Session
_session = requests.Session()
_session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Referer': 'https://webshare.cz/',
    'Origin': 'https://webshare.cz',
    'Accept': 'text/xml; charset=UTF-8',
    'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8'
})

def log(msg, level=xbmc.LOGINFO):
    """Log message to Kodi log"""
    xbmc.log(f"[{_addon_id}-Manifest] {msg}", level)

def popinfo(message, heading=_addon_name):
    """Show notification"""
    xbmcgui.Dialog().notification(heading, message, xbmcgui.NOTIFICATION_INFO, 3000)

class WebShareManifestFinder:
    def __init__(self):
        self.token = None
        self.zip_manifest_id = None
        self.zip_manifest_data = None
        self.latest_info = None

    def ensure_directories(self):
        """Ensure cache directories exist"""
        for directory in [CACHE_DIR, ZIP_CACHE_DIR, METADATA_DIR]:
            if not os.path.exists(directory):
                os.makedirs(directory)

    def login(self):
        """Login to WebShare"""
        if not WEBSHARE_USER or not WEBSHARE_PASS:
            log("No WebShare credentials configured")
            return None

        try:
            log("Logging in to WebShare...")

            # Get salt
            response = _session.post(
                f"{WEBSHARE_BASE_URL}salt/",
                data={'username_or_email': WEBSHARE_USER},
                timeout=10
            )

            if response.status_code != 200:
                log(f"Salt request failed: {response.status_code}")
                return None

            # Extract salt
            content = response.text
            if '<salt>' in content and '</salt>' in content:
                start = content.find('<salt>') + 6
                end = content.find('</salt>', start)
                salt = content[start:end]
            else:
                log("Could not extract salt from response")
                return None

            # Calculate hashes
            encrypted_pass = hashlib.sha1(md5crypt(WEBSHARE_PASS.encode('utf-8'),
                                                 salt.encode('utf-8')).encode('utf-8')).hexdigest()
            pass_digest = hashlib.md5(WEBSHARE_USER.encode('utf-8') + b':Webshare:' +
                                    encrypted_pass.encode('utf-8')).hexdigest()

            # Login
            response = _session.post(
                f"{WEBSHARE_BASE_URL}login/",
                data={
                    'username_or_email': WEBSHARE_USER,
                    'password': encrypted_pass,
                    'digest': pass_digest,
                    'keep_logged_in': 1
                },
                timeout=10
            )

            if response.status_code != 200:
                log(f"Login request failed: {response.status_code}")
                return None

            # Extract token
            content = response.text
            if '<token>' in content and '</token>' in content:
                start = content.find('<token>') + 7
                end = content.find('</token>', start)
                self.token = content[start:end]
                log(f"Login successful (Token: {self.token[:10]}...)")
                return self.token

            log("Login status not OK")
            return None

        except Exception as e:
            log(f"Login error: {str(e)}")
            traceback.print_exc()
            return None

    def list_files_api(self, search_term="", limit=20, offset=0):
        """Use /api/files/ endpoint to list/search files - FIXED parsing"""
        if not self.token:
            return []

        try:
            # Parameters from your test-filecheck.py
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

            log(f"Listing files with search='{search_term}', limit={limit}, offset={offset}")

            response = _session.post(
                f"{WEBSHARE_BASE_URL}files/",
                data=data,
                timeout=15
            )

            if response.status_code != 200:
                log(f"Files API failed: {response.status_code}")
                return []

            # Parse XML response
            try:
                xml = ET.fromstring(response.text)

                # Check status
                status_elem = xml.find('status')
                if status_elem is None or status_elem.text != 'OK':
                    log(f"API status not OK: {status_elem.text if status_elem else 'No status'}")
                    return []

                # Parse files directly from root
                files = []
                for file_elem in xml.findall('file'):
                    file_data = self._parse_file_element(file_elem)
                    if file_data:
                        files.append(file_data)

                log(f"Found {len(files)} files via files API")
                return files

            except Exception as e:
                log(f"XML parse error: {e}")
                return self._extract_files_from_text(response.text)

        except Exception as e:
            log(f"Files API error: {str(e)}")
            traceback.print_exc()
            return []

    def _parse_file_element(self, file_elem):
        """Parse a <file> XML element"""
        try:
            file_data = {}
            for child in file_elem:
                file_data[child.tag] = child.text

            # Required fields
            if 'ident' in file_data and 'name' in file_data:
                return {
                    'ident': file_data['ident'],
                    'name': file_data['name'],
                    'size': file_data.get('size', '0'),
                    'created': file_data.get('created', ''),
                    'type': file_data.get('type', '')
                }

        except Exception as e:
            log(f"Error parsing file element: {e}")

        return None

    def _extract_files_from_text(self, text):
        """Extract files from plain text response"""
        files = []

        # Look for file patterns
        file_pattern = r'<file>(.*?)</file>'
        file_matches = re.findall(file_pattern, text, re.DOTALL)

        for file_match in file_matches:
            name_match = re.search(r'<name>(.*?)</name>', file_match)
            ident_match = re.search(r'<ident>(.*?)</ident>', file_match)

            if name_match and ident_match:
                files.append({
                    'name': name_match.group(1),
                    'ident': ident_match.group(1)
                })

        return files

    def find_latest_info(self, force_check=False):
        """Find LATEST.json file - CHANGED TO ALWAYS CHECK"""
        log("Finding LATEST.json on WebShare...")

        # Get all files (sorted by created date, newest first)
        all_files = self.list_files_api(limit=50)
        
        if not all_files:
            log("No files found at all")
            return None, None

        log(f"Found {len(all_files)} total files on WebShare")

        # Show first few files for debugging
        for i, file in enumerate(all_files[:5]):
            log(f"  {i+1}. {file['name']} ({file['ident']})")

        # Look for LATEST.json first
        for file in all_files:
            name = file.get('name', '').lower()
            
            if name == 'latest.json':
                log(f"Found LATEST.json on WebShare: {file['ident']}")
                
                # Check if this is different from cached version
                if force_check:
                    return self.check_if_newer(file['ident'])
                else:
                    return self.download_and_parse_file(file['ident'])

        # If no LATEST.json, look for any JSON with manifest/index in name
        log("No LATEST.json found, looking for manifest/index JSON files...")
        
        manifest_files = []
        for file in all_files:
            name = file.get('name', '').lower()
            if name.endswith('.json'):
                # Check for keywords
                keywords = ['manifest', 'index', 'library', 'catalog', 'mila']
                if any(keyword in name for keyword in keywords):
                    manifest_files.append(file)
        
        if manifest_files:
            log(f"Found {len(manifest_files)} manifest-like JSON files")
            # Sort by name to prefer LATEST or manifest
            manifest_files.sort(key=lambda x: x['name'].lower())
            file = manifest_files[0]
            log(f"Using: {file['name']} ({file['ident']})")
            
            if force_check:
                return self.check_if_newer(file['ident'])
            else:
                return self.download_and_parse_file(file['ident'])

        # Last resort: any JSON file
        log("Looking for ANY JSON file...")
        for file in all_files:
            name = file.get('name', '').lower()
            if name.endswith('.json'):
                log(f"Found JSON file: {name}")
                
                if force_check:
                    return self.check_if_newer(file['ident'])
                else:
                    return self.download_and_parse_file(file['ident'])

        log("Could not find any JSON file on WebShare")
        return None, None

    def check_if_newer(self, file_ident):
        """Check if file is newer than cached version"""
        # Download the file to check its content
        result = self.download_and_parse_file(file_ident)
        if not result[0]:
            return None, None
        
        data, file_id = result
        
        # Check if we have a cached version
        cache_file = os.path.join(CACHE_DIR, 'latest_info.json')
        if os.path.exists(cache_file):
            try:
                with open(cache_file, 'r', encoding='utf-8') as f:
                    cache_data = json.load(f)
                
                cached_manifest_id = cache_data.get('manifest_id')
                cached_data = cache_data.get('data', {})
                
                # If it's a ZIP format, compare file IDs
                if isinstance(data, dict) and isinstance(cached_data, dict):
                    # New ZIP format
                    if 'file_id' in data and 'file_id' in cached_data:
                        if data['file_id'] == cached_data['file_id']:
                            log(f"Same file ID as cache: {data['file_id']}")
                            return None, None  # Same file, no update
                        else:
                            log(f"NEW file ID found! {data['file_id']} vs cached {cached_data['file_id']}")
                            return data, file_id
                    
                    # Old format - check if content looks different
                    elif 'files' in data or 'files' in cached_data:
                        # Simple check: compare keys or structure
                        if data.keys() != cached_data.keys():
                            log(f"Different structure found!")
                            return data, file_id
                
            except Exception as e:
                log(f"Cache comparison error: {e}")
        
        # No cache or can't compare, return the new data
        return data, file_id

    def download_and_parse_file(self, file_ident):
        """Download a file and parse it as JSON"""
        content = self.download_file(file_ident)
        if not content:
            return None, None

        try:
            # Try to decode as JSON
            if isinstance(content, bytes):
                content = content.decode('utf-8')

            data = json.loads(content)
            log(f"Successfully parsed JSON file")

            # Check if it's a LATEST info file
            if 'filename' in data and 'file_id' in data:
                log(f"Valid LATEST.json format")
                return data, file_ident

            # Check if it's old manifest format
            elif 'files' in data:
                log("Found old manifest format")
                return data, file_ident

            # Check if it's an index file
            elif 'movies' in data or 'tv_shows' in data:
                log("Found index file")
                return data, file_ident

            # Unknown JSON structure but we'll accept it
            else:
                log("Found JSON file with unknown structure")
                return data, file_ident

        except Exception as e:
            log(f"Error parsing file {file_ident}: {str(e)}")
            return None, None

    def download_file(self, file_ident):
        """Download a file by ID"""
        if not self.token:
            return None

        try:
            # Get download link
            response = _session.post(
                f"{WEBSHARE_BASE_URL}file_link/",
                data={
                    'ident': file_ident,
                    'wst': self.token,
                    'download_type': 'direct'
                },
                timeout=15
            )

            if response.status_code != 200:
                log(f"Failed to get download link: {response.status_code}")
                return None

            # Extract download URL
            content = response.text
            if '<link>' in content and '</link>' in content:
                start = content.find('<link>') + 6
                end = content.find('</link>', start)
                download_url = content[start:end]
            else:
                log("Could not extract download URL")
                return None

            # Download the file
            log(f"Downloading from: {download_url[:80]}...")
            response = _session.get(download_url, timeout=60)
            if response.status_code != 200:
                log(f"File download failed: {response.status_code}")
                return None

            log(f"Downloaded {len(response.content)} bytes")
            return response.content

        except Exception as e:
            log(f"Download error: {str(e)}")
            return None

    def find_and_load_manifest(self, force_check=False):
        """Main function to find and load manifest - UPDATED TO CHECK FOR NEW VERSIONS"""
        self.ensure_directories()

        # Login first
        if not self.login():
            log("Login failed")
            return False

        # Find LATEST.json or any manifest - ALWAYS CHECK WEBSHARE
        latest_data, latest_id = self.find_latest_info(force_check=force_check)
        if not latest_data:
            # If force check found nothing new, use cache
            if force_check:
                log("No newer version found, using cache")
                cache_file = os.path.join(CACHE_DIR, 'latest_info.json')
                if os.path.exists(cache_file):
                    try:
                        with open(cache_file, 'r', encoding='utf-8') as f:
                            cache_data = json.load(f)
                        self.latest_info = cache_data.get('data')
                        self.zip_manifest_id = cache_data.get('manifest_id')
                        log("Using cached manifest (no newer version found)")
                        return True
                    except Exception as e:
                        log(f"Cache read error: {e}")
                return False
            else:
                log("Could not find any manifest file")
                return False

        # Save latest info
        self.latest_info = latest_data
        self.zip_manifest_id = latest_id

        log(f"Found manifest: {latest_id}")

        # Check format and handle accordingly
        if isinstance(latest_data, dict):
            if 'filename' in latest_data and 'file_id' in latest_data:
                # New ZIP format
                zip_filename = latest_data['filename']
                zip_file_id = latest_data['file_id']

                log(f"New ZIP format: {zip_filename}")

                # Download and extract ZIP if file ID is different from cache
                if force_check:
                    log("Force check mode - downloading new ZIP")
                    
                success = self.download_and_extract_zip(zip_file_id, zip_filename)
                if success:
                    log("ZIP downloaded and extracted successfully")
                    # Save to cache
                    self.save_manifest_cache()
                    return True
                else:
                    log("Failed to download/extract ZIP")
                    return False
            else:
                # Old format (manifest or index)
                log("Using old format (direct JSON)")
                # Save to cache
                self.save_manifest_cache()
                return True

        log("Unknown manifest format")
        return False

    def download_and_extract_zip(self, zip_file_id, zip_filename):
        """Download ZIP file and extract metadata"""
        log(f"Downloading ZIP file: {zip_filename}")

        # Download ZIP file
        zip_content = self.download_file(zip_file_id)
        if not zip_content:
            log("Failed to download ZIP file")
            return False

        # Extract ZIP
        try:
            # Clear old metadata
            if os.path.exists(METADATA_DIR):
                for f in os.listdir(METADATA_DIR):
                    file_path = os.path.join(METADATA_DIR, f)
                    try:
                        if os.path.isfile(file_path):
                            os.remove(file_path)
                        elif os.path.isdir(file_path):
                            import shutil
                            shutil.rmtree(file_path)
                    except:
                        pass

            # Extract ZIP
            with zipfile.ZipFile(io.BytesIO(zip_content), 'r') as zip_ref:
                zip_ref.extractall(METADATA_DIR)

            log(f"ZIP extracted to: {METADATA_DIR}")

            # Save version info
            version_file = os.path.join(METADATA_DIR, "version.txt")
            with open(version_file, 'w') as f:
                f.write(zip_file_id)
                f.write(f"\n{zip_filename}")
                f.write(f"\n{time.strftime('%Y-%m-%d %H:%M:%S')}")

            return True

        except Exception as e:
            log(f"Error extracting ZIP: {str(e)}")
            traceback.print_exc()
            return False

    def get_manifest_data(self):
        """Get manifest data"""
        if self.latest_info:
            return self.latest_info

        # Try to load from extracted metadata
        for root, dirs, files in os.walk(METADATA_DIR):
            for file in files:
                if file == 'index.json':
                    index_file = os.path.join(root, file)
                    try:
                        with open(index_file, 'r', encoding='utf-8') as f:
                            return json.load(f)
                    except Exception as e:
                        log(f"Error loading {index_file}: {str(e)}")

        return None

    def save_manifest_cache(self):
        """Save manifest info to cache"""
        if not self.latest_info:
            return False

        try:
            cache_file = os.path.join(CACHE_DIR, 'latest_info.json')
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump({
                    'timestamp': time.time(),
                    'data': self.latest_info,
                    'manifest_id': self.zip_manifest_id
                }, f)

            log(f"Saved to cache: {cache_file}")
            return True

        except Exception as e:
            log(f"Error saving cache: {str(e)}")
            return False

def initialize_manifest(force_check=False):
    """Initialize manifest - UPDATED TO CHECK FOR UPDATES"""
    log("Initializing manifest..." + (" (force check)" if force_check else ""))

    # Find manifest - ALWAYS check WebShare
    finder = WebShareManifestFinder()
    success = finder.find_and_load_manifest(force_check=force_check)

    if success:
        manifest_data = finder.get_manifest_data()
        if manifest_data:
            log("Manifest initialized successfully")
            return manifest_data, finder.zip_manifest_id

    log("Manifest initialization failed")
    return None, None

def auto_find_manifest_on_startup():
    """Auto-find on startup - ALWAYS CHECK FOR UPDATES"""
    log("Auto-finding manifest on startup...")

    try:
        auto_find = _addon.getSetting('auto_find_manifest')
        if auto_find != 'true':
            log("Auto-find disabled in settings")
            return None, None
    except:
        pass

    # Always check WebShare for newer versions
    return initialize_manifest(force_check=True)

def check_for_updates():
    """Check for updates and return True if new version found"""
    log("Checking for updates on WebShare...")
    
    finder = WebShareManifestFinder()
    if not finder.login():
        log("Login failed for update check")
        return False
    
    # Get cached version first
    cache_file = os.path.join(CACHE_DIR, 'latest_info.json')
    cached_id = None
    if os.path.exists(cache_file):
        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)
            cached_id = cache_data.get('manifest_id')
            log(f"Cached manifest ID: {cached_id}")
        except:
            pass
    
    # Find latest on WebShare
    latest_data, latest_id = finder.find_latest_info(force_check=True)
    
    if latest_data and latest_id:
        if cached_id and latest_id == cached_id:
            log("No update available (same ID)")
            return False
        else:
            log(f"UPDATE AVAILABLE! New ID: {latest_id}")
            popinfo(f"New version found: {latest_id[:8]}...")
            return True
    else:
        log("Could not find any manifest for update check")
        return False

def test_manifest_finder():
    """Test the manifest finder"""
    popinfo("Testing manifest finder...")

    finder = WebShareManifestFinder()
    success = finder.find_and_load_manifest()

    if success:
        manifest_data = finder.get_manifest_data()

        dialog = xbmcgui.Dialog()
        info = f"✅ Manifest found!\n\n"

        if isinstance(manifest_data, dict):
            if 'filename' in manifest_data:
                info += f"File: {manifest_data['filename']}\n"

            if 'file_id' in manifest_data:
                info += f"File ID: {manifest_data['file_id']}\n"

            if 'format' in manifest_data:
                info += f"Format: {manifest_data['format']}\n"

            if 'total_movies' in manifest_data:
                info += f"Movies: {manifest_data['total_movies']:,}\n"

            if 'total_tv_shows' in manifest_data:
                info += f"TV Shows: {manifest_data['total_tv_shows']:,}\n"

        # Check extracted files
        if os.path.exists(METADATA_DIR):
            files = os.listdir(METADATA_DIR)
            info += f"\n📁 Files in metadata: {len(files)}\n"

            for f in sorted(files)[:5]:
                info += f"  • {f}\n"

            if len(files) > 5:
                info += f"  ... and {len(files) - 5} more\n"

        dialog.ok("Manifest Finder - Success", info)
        return True
    else:
        dialog = xbmcgui.Dialog()
        dialog.ok("Manifest Finder - Failed",
                  "Could not find any manifest files.\n\n"
                  "Make sure LATEST.json exists on WebShare.")
        return False

if __name__ == '__main__':
    test_manifest_finder()
