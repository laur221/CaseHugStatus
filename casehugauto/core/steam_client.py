"""
Steam client for handling authentication and profile extraction
"""
import logging
import json
import requests
from typing import Optional, Dict, Any, Tuple
import qrcode
from io import BytesIO
import base64
import time
import secrets
import string
import urllib.parse

logger = logging.getLogger(__name__)

STEAM_API_BASE = "https://steamcommunity.com"
STEAM_LOGIN_URL = "https://steamcommunity.com/login"
STEAM_MOBILE_API = "https://api.steampowered.com"
CASEHUG_BASE = "https://www.casehug.com"

class SteamClient:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        self.steam_session_id = None
        self.steam_cookies = {}
        self.client_id = None
        self.encryption_key = None

    def generate_qr_code_for_steam_login(self) -> Tuple[str, str]:
        """
        Generate Steam login QR code
        For now, redirects to manual login since Steam Guard QR codes require
        real-time server communication that's difficult to implement.
        
        Returns: (qr_code_path, login_hint)
        """
        from pathlib import Path
        
        try:
            logger.info("Generating Steam login instruction QR...")
            
            # For now, create a simple instruction QR that directs to manual login
            # This is because proper Steam Guard QR requires:
            # 1. Active Steam session
            # 2. Real-time Steam API communication
            # 3. Mobile app pairing protocol
            
            instruction = "https://steamcommunity.com/login"
            login_hint = secrets.token_hex(16)
            
            qr = qrcode.QRCode(
                version=3,
                error_correction=qrcode.constants.ERROR_CORRECT_H,
                box_size=10,
                border=2,
            )
            qr.add_data(instruction)
            qr.make(fit=True)
            
            img = qr.make_image(fill_color="black", back_color="white").convert('RGB')
            
            qr_folder = Path("temp_qr_codes")
            qr_folder.mkdir(exist_ok=True)
            
            qr_path = qr_folder / f"qr_steam_login_{login_hint[:8]}.png"
            img.save(str(qr_path))
            
            logger.info(f"Steam login QR code generated at: {qr_path}")
            logger.info("NOTE: For best results, use Manual Login below with your Steam credentials")
            
            return str(qr_path), login_hint
            
        except Exception as e:
            logger.error(f"Error generating Steam login QR: {e}")
            raise

    def extract_steam_profile(self, cookies: Dict[str, str]) -> Optional[Dict[str, Any]]:
        """
        Extract Steam profile information from cookies
        """
        try:
            # Set session cookies.
            for key, value in cookies.items():
                self.session.cookies.set(key, value)
            
            # Retrieve profile information.
            response = self.session.get(f"{STEAM_API_BASE}/api/IPlayer/GetProfile/v1", 
                                       params={"access_token": cookies.get("sessionid", "")})
            
            if response.status_code == 200:
                profile_data = response.json()
                
                # Parse profile data.
                return {
                    "steam_id": profile_data.get("steamid", ""),
                    "steam_nickname": profile_data.get("personaname", ""),
                    "steam_avatar_url": profile_data.get("avatarfull", ""),
                    "steam_username": profile_data.get("steamid", "")
                }
            
            logger.warning("Failed to extract Steam profile, trying alternative method...")
            
            # Alternative method: parse HTML.
            response = self.session.get(f"{STEAM_API_BASE}/my/profile")
            if response.status_code == 200:
                # Extract Steam ID from profile URL.
                steam_id = self._extract_steam_id_from_html(response.text)
                
                if steam_id:
                    # Fetch public profile details.
                    profile_response = self.session.get(
                        f"{STEAM_API_BASE}/profiles/{steam_id}",
                        params={"xml": 1}
                    )
                    
                    if profile_response.status_code == 200:
                        return self._parse_steam_xml_profile(profile_response.text, steam_id)
            
            return None
            
        except Exception as e:
            logger.error(f"Error extracting Steam profile: {e}")
            return None

    def _extract_steam_id_from_html(self, html: str) -> Optional[str]:
        """Extract Steam ID from HTML"""
        import re
        match = re.search(r'profiles/(\d+)', html)
        if match:
            return match.group(1)
        return None

    def _parse_steam_xml_profile(self, xml: str, steam_id: str) -> Dict[str, Any]:
        """Parse Steam XML profile response"""
        import xml.etree.ElementTree as ET
        try:
            root = ET.fromstring(xml)
            return {
                "steam_id": steam_id,
                "steam_nickname": root.findtext("personaname", "Unknown"),
                "steam_avatar_url": root.findtext("avatarfull", ""),
                "steam_username": root.findtext("steamID", steam_id)
            }
        except Exception as e:
            logger.error(f"Error parsing Steam XML: {e}")
            return None

    def get_steam_cookies_from_browser(self) -> Optional[Dict[str, str]]:
        """
        Extract Steam cookies from browser (Chrome, Firefox, etc.)
        """
        try:
            import sqlite3
            from pathlib import Path
            
            # Search Chrome cookies.
            chrome_cookie_path = Path.home() / "AppData\\Local\\Google\\Chrome\\User Data\\Default\\Cookies"
            
            if chrome_cookie_path.exists():
                return self._extract_cookies_from_chrome(str(chrome_cookie_path))
            
            return None
        except Exception as e:
            logger.error(f"Error getting browser cookies: {e}")
            return None

    def _extract_cookies_from_chrome(self, cookie_path: str) -> Optional[Dict[str, str]]:
        """Extract cookies from Chrome database"""
        try:
            import sqlite3
            import shutil
            
            # Create a copy to avoid DB lock issues.
            temp_path = "/tmp/chrome_cookies.db"
            shutil.copy(cookie_path, temp_path)
            
            conn = sqlite3.connect(temp_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT name, value FROM cookies 
                WHERE host_key LIKE '%steamcommunity%' 
                OR host_key LIKE '%steam%'
            """)
            
            cookies = {}
            for name, value in cursor.fetchall():
                cookies[name] = value
            
            conn.close()
            return cookies if cookies else None
            
        except Exception as e:
            logger.error(f"Error extracting Chrome cookies: {e}")
            return None

    def login_to_casehug_with_steam(self, steam_cookies: Dict[str, str]) -> Dict[str, str]:
        """
        Login to casehug.com using Steam cookies
        """
        try:
            # Set Steam cookies.
            for key, value in steam_cookies.items():
                self.session.cookies.set(key, value)
            
            # Open CaseHug login page.
            response = self.session.get(f"{CASEHUG_BASE}/login")
            
            if response.status_code == 200:
                # Attempt Steam login.
                login_response = self.session.post(
                    f"{CASEHUG_BASE}/api/auth/steam",
                    json={"method": "steam_login"},
                    cookies=steam_cookies
                )
                
                if login_response.status_code == 200:
                    result = login_response.json()
                    if result.get("success"):
                        # Return cookies after successful login.
                        return dict(self.session.cookies)
            
            logger.warning("Failed to login to casehug with Steam")
            return {}
            
        except Exception as e:
            logger.error(f"Error logging in to casehug: {e}")
            return {}

    def save_cookies_to_file(self, cookies: Dict[str, str], filepath: str) -> bool:
        """Save cookies to file for later use"""
        try:
            with open(filepath, 'w') as f:
                json.dump(cookies, f)
            return True
        except Exception as e:
            logger.error(f"Error saving cookies: {e}")
            return False

    def load_cookies_from_file(self, filepath: str) -> Optional[Dict[str, str]]:
        """Load cookies from file"""
        try:
            with open(filepath, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading cookies: {e}")
            return None


steam_client = SteamClient()
