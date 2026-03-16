import os
import json
import time
import asyncio
from datetime import datetime, timedelta
import nodriver as uc
from nodriver import cdp  # Chrome DevTools Protocol for cookies
import requests
import ctypes  # For Windows API - window minimization

# Configuration
CONFIG_FILE = "config.json"
LAST_OPENING_FILE = "last_opening.json"

class CasehugBotNodriver:
    def __init__(self, config_file=CONFIG_FILE):
        """Initialize bot with configuration from file"""
        with open(config_file, 'r', encoding='utf-8') as f:
            self.config = json.load(f)
        
        self.telegram_token = self.config.get('telegram_bot_token', '')
        self.telegram_chat_id = self.config.get('telegram_chat_id', '')
        self.accounts = self.config.get('accounts', [])
        self.captcha_api_key = self.config.get('2captcha_api_key', '')
        self.steam_login_debug_enabled = self.config.get('steam_login_debug_enabled', True)
        self.steam_debug_log_file = self.config.get(
            'steam_debug_log_file',
            os.path.join('logs', 'steam_login_debug.log')
        )
        self.steam_debug_log_retention_days = int(self.config.get('steam_debug_log_retention_days', 2))
        self.steam_login_max_retries = int(self.config.get('steam_login_max_retries', 1))
        
        # FlareSolverr URL: Environment variable has priority (for Docker)
        self.flaresolverr_url = os.environ.get('FLARESOLVERR_URL', 
                            self.config.get('flaresolverr_url', 'http://localhost:8191/v1'))
        
        # FlareSolverr sessions for each account (keeps cookies in Docker)
        self.flare_sessions = {}  # {account_name: session_id}
        
        # Docker detection
        is_docker = os.environ.get('DISPLAY') == ':99' or os.environ.get('CHROME_BIN') is not None
        
        # In Docker: FlareSolverr PRIMARY (headless Nodriver doesn't bypass Cloudflare)
        # On Windows: Nodriver PRIMARY (11.22s, faster)
        if is_docker:
            print(f"   🐳 Docker detected - using FlareSolverr as PRIMARY bypass")
            self.use_flaresolverr = True
            self.flaresolverr_primary = True  # Use FlareSolverr first, not as fallback
            print(f"   🛡️  FlareSolverr URL: {self.flaresolverr_url}")
        else:
            print(f"   💻 Windows detected - using Nodriver PRIMARY (11.22s avg)")
            self.flaresolverr_primary = False
            # Check if FlareSolverr available as fallback
            try:
                flaresolverr_check = requests.get(self.flaresolverr_url.replace('/v1', ''), timeout=3)
                if flaresolverr_check.status_code == 200:
                    print(f"   🛡️  FlareSolverr available as fallback (16.57s)")
                    self.use_flaresolverr = True
                else:
                    self.use_flaresolverr = False
            except:
                self.use_flaresolverr = False

    def log_steam_debug(self, account_name, event, details=None):
        """Write Steam auto-login diagnostics to logs/steam_login_debug.log."""
        try:
            if not self.steam_login_debug_enabled:
                return

            os.makedirs('logs', exist_ok=True)
            self.prune_steam_debug_log(retention_days=self.steam_debug_log_retention_days)
            payload = {
                "timestamp": datetime.now().isoformat(),
                "account": account_name,
                "event": event,
                "details": details or {}
            }
            with open(self.steam_debug_log_file, 'a', encoding='utf-8') as f:
                f.write(json.dumps(payload, ensure_ascii=False) + "\n")
        except Exception:
            # Never block bot flow if debug logging fails
            pass

    def prune_steam_debug_log(self, retention_days=2):
        """Keep only steam debug log entries newer than retention_days."""
        try:
            if not os.path.exists(self.steam_debug_log_file):
                return

            cutoff = datetime.now() - timedelta(days=retention_days)
            kept_lines = []

            with open(self.steam_debug_log_file, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue

                    try:
                        entry = json.loads(line)
                        ts = entry.get("timestamp")
                        if not ts:
                            continue

                        entry_dt = datetime.fromisoformat(ts)
                        if entry_dt >= cutoff:
                            kept_lines.append(line)
                    except Exception:
                        # Skip malformed lines
                        continue

            with open(self.steam_debug_log_file, 'w', encoding='utf-8') as f:
                if kept_lines:
                    f.write("\n".join(kept_lines) + "\n")
        except Exception:
            # Never block bot flow if retention cleanup fails
            pass
    
    async def setup_browser(self):
        """Nodriver doesn't require explicit setup - each account will create its own browser"""
        print("   🚀 Nodriver ready - each account will launch browser automatically")
        return True
    
    def load_last_opening(self):
        """Load tracking of last openings"""
        if not os.path.exists(LAST_OPENING_FILE):
            # Create new file with all accounts
            default_data = {}
            for account in self.accounts:
                account_name = account.get('name', '')
                if account_name:
                    default_data[account_name] = {
                        "last_opening": None,
                        "last_check": None
                    }
            
            with open(LAST_OPENING_FILE, 'w', encoding='utf-8') as f:
                json.dump(default_data, f, indent=2, ensure_ascii=False)
            
            return default_data
        
        try:
            with open(LAST_OPENING_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {}
    
    def save_account_timestamp(self, account_name, had_success=True):
        """Save timestamp for an account after processing"""
        last_opening = self.load_last_opening()
        
        if account_name not in last_opening:
            last_opening[account_name] = {}
        
        timestamp = datetime.now().isoformat()
        
        # If cases were opened successfully, save as last_opening
        # Otherwise, only update last_check (for tracking)
        if had_success:
            last_opening[account_name]['last_opening'] = timestamp
            print(f"   ✅ Timestamp saved for {account_name}: {timestamp}")
        
        last_opening[account_name]['last_check'] = timestamp
        
        with open(LAST_OPENING_FILE, 'w', encoding='utf-8') as f:
            json.dump(last_opening, f, indent=2, ensure_ascii=False)
    
    async def create_flaresolverr_session(self, account_name):
        """Create FlareSolverr session for an account (keeps cookies between requests)"""
        try:
            session_id = f"session_{account_name.replace(' ', '_')}"
            
            payload = {
                "cmd": "sessions.create",
                "session": session_id
            }
            
            response = requests.post(self.flaresolverr_url, json=payload, timeout=10)
            
            if response.status_code == 200:
                result = response.json()
                if result.get('status') == 'ok':
                    self.flare_sessions[account_name] = session_id
                    print(f"   ✅ FlareSolverr session created: {session_id}")
                    return session_id
            
            print(f"   ⚠️  Could not create FlareSolverr session for {account_name}")
            return None
        except Exception as e:
            print(f"   ⚠️  Error creating FlareSolverr session: {e}")
            return None
    
    async def destroy_flaresolverr_session(self, account_name):
        """Delete FlareSolverr session after processing account"""
        if account_name not in self.flare_sessions:
            return
        
        try:
            session_id = self.flare_sessions[account_name]
            payload = {
                "cmd": "sessions.destroy",
                "session": session_id
            }
            
            requests.post(self.flaresolverr_url, json=payload, timeout=5)
            del self.flare_sessions[account_name]
            print(f"   🗑️  FlareSolverr session closed: {session_id}")
        except:
            pass
    
    async def create_page_with_stealth(self, account_name):
        """Create Nodriver browser with persistent profile - bypass Cloudflare automatically"""
        # Create persistent folder for this account
        profile_dir = f'profiles/{account_name.replace(" ", "_")}'
        os.makedirs(profile_dir, exist_ok=True)
        
        print(f"   📁 Persistent profile: {profile_dir}")
        print(f"   🚀 Launching Nodriver (bypass Cloudflare automatically)...")
        
        # Detect if running in Docker
        is_docker = os.environ.get('DISPLAY') == ':99' or os.environ.get('CHROME_BIN') is not None
        headless_mode = True  # Always headless mode (no GUI)
        
        if is_docker:
            print(f"   🐳 Docker detected - running in headless mode")
        else:
            print(f"   💻 Headless mode enabled - no GUI window")
        
        # Launch Nodriver browser with persistent profile
        # Nodriver solves Cloudflare automatically through DevTools Protocol
        browser = await uc.start(
            user_data_dir=os.path.abspath(profile_dir),
            headless=headless_mode,
            browser_args=[
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-dev-shm-usage',
                '--disable-infobars',
                '--mute-audio',  # Disable sound
            ]
        )
        
        # First tab opened automatically
        page = browser.main_tab
        
        # Minimize Chrome window (only on Windows, not in Docker)
        if not is_docker:
            await asyncio.sleep(1)  # Wait for window to appear
            try:
                user32 = ctypes.windll.user32
                
                # Find and minimize all ferestrele Chrome
                def enum_callback(hwnd, _):
                    if user32.IsWindowVisible(hwnd):
                        length = user32.GetWindowTextLengthW(hwnd)
                        if length > 0:
                            buffer = ctypes.create_unicode_buffer(length + 1)
                            user32.GetWindowTextW(hwnd, buffer, length + 1)
                            title = buffer.value
                            
                            # Minimize if e Chrome
                            if 'Chrome' in title or 'casehug.com' in title.lower():
                                user32.ShowWindow(hwnd, 6)  # SW_MINIMIZE = 6
                    return True
                
                EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
                user32.EnumWindows(EnumWindowsProc(enum_callback), 0)
                print(f"   🪟 Chrome window minimized to taskbar")
            except Exception as e:
                print(f"   ⚠️ Nu s-a putut minimiza: {e}")
        
        print(f"   ✅ Browser Nodriver ready for {account_name}")
        print(f"   🛡️  Cloudflare will be bypassed automatically (avg 11.22s)")
        
        # Wait stabilizarea conexiunii browser/WebSocket
        await asyncio.sleep(2)
        
        return page, browser
    
    async def solve_cloudflare_with_flaresolverr(self, url: str, account_name=None):
        """Solve Cloudflare using FlareSolverr (FREE, 99% success rate)"""
        try:
            print(f"   🛡️  Sending request to FlareSolverr...")
            print(f"      URL: {url}")
            
            # Send request to FlareSolverr
            payload = {
                "cmd": "request.get",
                "url": url,
                "maxTimeout": 60000  # 60 seconds timeout
            }
            
            # Use session if exists (keeps cookies)
            if account_name and account_name in self.flare_sessions:
                payload["session"] = self.flare_sessions[account_name]
                print(f"      📎 Using session: {self.flare_sessions[account_name]}")
            
            response = requests.post(
                self.flaresolverr_url,
                json=payload,
                timeout=65  # Slightly more than maxTimeout
            )
            
            if response.status_code != 200:
                print(f"   ❌ FlareSolverr HTTP error {response.status_code}")
                return None
            
            result = response.json()
            
            if result.get('status') != 'ok':
                print(f"   ❌ FlareSolverr error: {result.get('message', 'Unknown error')}")
                return None
            
            solution = result.get('solution', {})
            cookies = solution.get('cookies', [])
            user_agent = solution.get('userAgent', '')
            response_body = solution.get('response', '')  # HTML of the page
            
            if not cookies:
                print(f"   ⚠️  FlareSolverr did not return cookies")
                return None
            
            print(f"   ✅ FlareSolverr SUCCESS! Received {len(cookies)} cookies")
            print(f"   🍪 Cookies: {', '.join([c['name'] for c in cookies[:5]])}...")
            
            return {
                'cookies': cookies,
                'user_agent': user_agent,
                'html': response_body  # HTML of page without Cloudflare
            }
            
        except requests.exceptions.Timeout:
            print(f"   ❌ FlareSolverr timeout (>60s) - site is too slow or FlareSolverr is blocked")
            return None
        except Exception as e:
            print(f"   ❌ FlareSolverr error: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    async def solve_turnstile_with_2captcha(self, page, sitekey: str, url: str):
        """Solve Cloudflare Turnstile using 2Captcha API (FALLBACK)"""
        try:
            print(f"   🔐 Sending challenge to 2Captcha (FALLBACK)...")
            print(f"      Sitekey: {sitekey[:20]}...")
            print(f"      URL: {url}")
            
            # Send challenge to 2Captcha
            result = self.captcha_solver.turnstile(
                sitekey=sitekey,
                url=url
            )
            
            token = result.get('code')
            if not token:
                print(f"   ❌ 2Captcha did not return token")
                return None
            
            print(f"   ✅ Token received from 2Captcha: {token[:50]}...")
            return token
            
        except Exception as e:
            print(f"   ❌ 2Captcha error: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    async def check_cloudflare(self, page):
        """Check if Cloudflare was successfully passed (cookies already injected in Docker)"""
        try:
            # In Docker: Cookies already injected in open_free_case(), only check
            # Pe Windows: Nodriver solves automat
            is_docker = os.environ.get('DISPLAY') == ':99'
            
            if is_docker and hasattr(self, 'flaresolverr_primary') and self.flaresolverr_primary:
                print(f"   🐳 Checking if Cloudflare was bypassed with FlareSolverr cookies...")
                await asyncio.sleep(2)  # Wait briefly for the page to fully load
                
                content = await page.get_content()
                has_cloudflare = 'cloudflare' in content.lower() or 'checking your browser' in content.lower()
                
                if has_cloudflare:
                    print("   ❌ Cloudflare is STILL present after FlareSolverr cookie injection")
                    return False
                else:
                    print("   ✅ Cloudflare bypassed with FlareSolverr cookies!")
                    return True
            
            # On Windows: Nodriver solves automatically - wait longer
            first_wait = 15 if is_docker else 10
            second_wait = 15 if is_docker else 10
            
            print(f"   🛡️  Waiting for automatic Cloudflare resolution (Nodriver - {first_wait}s)...")
            await asyncio.sleep(first_wait)
            
            # Check if Cloudflare still exists
            content = await page.get_content()
            content_lower = content.lower()
            
            has_cloudflare = any(indicator in content_lower for indicator in [
                'cloudflare', 'checking your browser', 'just a moment', 
                'turnstile', 'performing security verification'
            ])
            
            if has_cloudflare:
                print(f"   ⚠️  Cloudflare still present - waiting {second_wait}s more...")
                await asyncio.sleep(second_wait)
                
                content = await page.get_content()
                has_cloudflare = 'cloudflare' in content.lower()
                
                if has_cloudflare:
                    print("   ⚠️  Cloudflare NOT bypassed automatically - manual check")
                    return False
            
            print("   ✅ Cloudflare bypassed successfully!")
            return True
            
        except Exception as e:
            print(f"   ⚠️  Error checking Cloudflare: {e}")
            import traceback
            traceback.print_exc()
            return True  # Continue anyway
    
    async def check_steam_login(self, page, account_name, retry_attempt=0):
        """Check whether the user is logged in with Steam (checks balance in header)"""
        try:
            try:
                self.log_steam_debug(account_name, "check_start", {
                    "retry_attempt": retry_attempt,
                    "current_url": page.url
                })
            except Exception:
                pass

            content = await page.get_content()
            
            # Check if exists balance in header (indicator sigur that e logat)
            has_balance = 'data-testid="header-account-balance"' in content
            
            if has_balance:
                # Extract balance ONLY from header-account-balance section
                import re
                # Search header-account-balance section and extract balance from there
                header_match = re.search(r'data-testid="header-account-balance"[^>]*>.*?<span\s+data-testid="format-price"[^>]*>(\$[\d.]+)</span>', content, re.DOTALL)
                if header_match:
                    balance = header_match.group(1)
                    print(f"   ✅ {account_name} is logged in with Steam (Balance: {balance})")
                    self.log_steam_debug(account_name, "already_logged_in", {
                        "balance": balance,
                        "retry_attempt": retry_attempt
                    })
                else:
                    print(f"   ✅ {account_name} is logged in with Steam")
                    self.log_steam_debug(account_name, "already_logged_in", {
                        "balance": None,
                        "retry_attempt": retry_attempt
                    })
                return True
            else:
                # Nu exists balance → is not logged in, try auto-login
                print(f"\n⚠️  {account_name} NU is logged in with Steam!")
                print(f"   🔄 Attempting Steam auto-login...")
                
                try:
                    # STEP 1: Search and click on button "steam login"
                    login_button = None
                    
                    # Search button that contains label text "steam login"
                    buttons = await page.select_all('button')
                    for btn in buttons:
                        try:
                            btn_html = await btn.get_html()
                            
                            # Check if HTML contains exact label with "steam login"
                            if 'ri-steam-fill' in btn_html and 'steam login' in btn_html.lower():
                                login_button = btn
                                print(f"   ✓ Found 'steam login' button")
                                break
                        except:
                            continue
                    
                    if not login_button:
                        print(f"   ❌ Could not find 'steam login' button")
                        self.log_steam_debug(account_name, "login_button_missing", {
                            "retry_attempt": retry_attempt,
                            "current_url": page.url
                        })
                        return False
                    
                    # Click the button de login
                    await login_button.scroll_into_view()
                    await asyncio.sleep(1)
                    await login_button.click()
                    print(f"   ✓ Click on 'steam login'")
                    
                    # Wait to appear modal with checkbox-uri
                    await asyncio.sleep(3)
                    
                    # STEP 2: Tick checkbox-urile
                    print(f"   🔄 Bifez checkbox-urile...")
                    
                    # Checkbox 1: Terms and Privacy Policy
                    try:
                        checkbox1 = await page.query_selector('input[data-testid="terms-and-age-verification-terms-privacy"]')
                        if checkbox1:
                            await checkbox1.click()
                            print(f"   ✓ Bifat: Terms and Privacy Policy")
                            await asyncio.sleep(0.5)
                        else:
                            print(f"   ⚠️  Could not find checkbox Terms")
                    except Exception as e:
                        print(f"   ⚠️  Checkbox1 error: {e}")
                    
                    # Checkbox 2: 18 years or older
                    try:
                        checkbox2 = await page.query_selector('input[data-testid="terms-and-age-verification-is-adult"]')
                        if checkbox2:
                            await checkbox2.click()
                            print(f"   ✓ Bifat: 18 years or older")
                            await asyncio.sleep(0.5)
                        else:
                            print(f"   ⚠️  Could not find checkbox Age")
                    except Exception as e:
                        print(f"   ⚠️  Checkbox2 error: {e}")
                    
                    # STEP 3: Click the button "log with steam"
                    try:
                        submit_button = await page.query_selector('button[data-testid="sign-in-button"]')
                        if submit_button:
                            await asyncio.sleep(1)
                            await submit_button.click()
                            print(f"   ✓ Click on 'log with steam'")
                        else:
                            print(f"   ❌ Could not find button 'log with steam'")
                            return False
                    except Exception as e:
                        print(f"   ❌ Submit click error: {e}")
                        return False
                    
                    # STEP 4: Switch at tab Steam and click on "Sign In"
                    print(f"   ⏳ Waiting for Steam popup to open (5s)...")
                    await asyncio.sleep(5)
                    
                    try:
                        # Find all tab-urile deschise
                        all_tabs = page.browser.tabs
                        print(f"   📑 Found {len(all_tabs)} tab-uri deschise")
                        
                        steam_tab = None
                        has_about_tab = False
                        tab_urls = []
                        # Search tab with Steam
                        for tab in all_tabs:
                            try:
                                tab_url = tab.url.lower()
                                tab_urls.append(tab.url)
                                if tab_url.startswith('about:'):
                                    has_about_tab = True
                                if 'steam' in tab_url:
                                    steam_tab = tab
                                    print(f"   ✓ Found Steam tab: {tab.url[:50]}...")
                                    break
                            except:
                                continue

                        self.log_steam_debug(account_name, "tabs_scan", {
                            "retry_attempt": retry_attempt,
                            "tabs_count": len(all_tabs),
                            "has_about_tab": has_about_tab,
                            "found_steam_tab": steam_tab is not None,
                            "tab_urls": tab_urls[:10]
                        })
                        
                        if steam_tab:
                            # Switch at tab Steam
                            await steam_tab.activate()
                            await asyncio.sleep(2)
                            
                            # Search button "Sign In"
                            signin_button = await steam_tab.query_selector('input#imageLogin')
                            
                            if signin_button:
                                await signin_button.click()
                                print(f"   ✓ Clicked 'Sign In' in Steam popup")
                                await asyncio.sleep(5)
                            else:
                                print(f"   ⏳ Could not find Sign In button, waiting for automatic authentication...")
                                await asyncio.sleep(10)
                        else:
                            if has_about_tab:
                                print(f"   ⚠️  Popup Steam a opened tab temporar (about:*). Waiting and re-checking...")
                                await asyncio.sleep(6)
                                # Re-scan tabs after short wait
                                all_tabs_retry = page.browser.tabs
                                for tab in all_tabs_retry:
                                    try:
                                        if 'steam' in tab.url.lower():
                                            steam_tab = tab
                                            print(f"   ✓ Found Steam tab at re-check: {tab.url[:50]}...")
                                            break
                                    except:
                                        continue
                                if steam_tab:
                                    await steam_tab.activate()
                                    await asyncio.sleep(2)
                                    signin_button = await steam_tab.query_selector('input#imageLogin')
                                    if signin_button:
                                        await signin_button.click()
                                        print(f"   ✓ Clicked 'Sign In' in Steam popup (retry)")
                                        self.log_steam_debug(account_name, "steam_signin_clicked_retry", {
                                            "retry_attempt": retry_attempt,
                                            "steam_url": steam_tab.url
                                        })
                                        await asyncio.sleep(5)
                                    else:
                                        print(f"   ⏳ Could not find Sign In button after re-check")
                                        self.log_steam_debug(account_name, "steam_signin_button_missing_retry", {
                                            "retry_attempt": retry_attempt,
                                            "steam_url": steam_tab.url
                                        })
                                        await asyncio.sleep(10)
                                else:
                                    print(f"   ⏳ Still cannot find Steam tab, continuing login check...")
                                    self.log_steam_debug(account_name, "steam_tab_missing_after_about", {
                                        "retry_attempt": retry_attempt,
                                        "current_url": page.url
                                    })
                                    await asyncio.sleep(10)
                            else:
                                print(f"   ⏳ Could not find Steam tab, waiting for automatic authentication...")
                                self.log_steam_debug(account_name, "steam_tab_missing", {
                                    "retry_attempt": retry_attempt,
                                    "current_url": page.url
                                })
                                await asyncio.sleep(15)
                    except Exception as e:
                        print(f"   ⚠️  Steam tab switch error: {e}")
                        self.log_steam_debug(account_name, "steam_tab_switch_error", {
                            "retry_attempt": retry_attempt,
                            "error": str(e)
                        })
                        await asyncio.sleep(15)
                    
                    # Wait redirect back at CaseHug
                    print(f"   ⏳ Waiting for redirect back to CaseHug (15s)...")
                    await asyncio.sleep(15)
                    
                    # Check if suntem on casehug.com
                    current_url = page.url
                    if 'casehug.com' not in current_url:
                        print(f"   🔄 Navigating back to /free-cases...")
                        await page.get('https://casehug.com/free-cases')
                        await asyncio.sleep(3)
                    
                except Exception as e:
                    print(f"   ❌ Auto-login error: {e}")
                    self.log_steam_debug(account_name, "auto_login_exception", {
                        "retry_attempt": retry_attempt,
                        "error": str(e),
                        "current_url": (page.url if page else "")
                    })
                    import traceback
                    traceback.print_exc()
                    return False
                
                # Check again after login
                await asyncio.sleep(2)
                content = await page.get_content()
                has_balance_after = 'data-testid="header-account-balance"' in content
                
                if not has_balance_after:
                    if retry_attempt < self.steam_login_max_retries:
                        try:
                            current_url = (page.url or '').lower()
                        except:
                            current_url = ''

                        if current_url.startswith('about:') or 'steam' in current_url:
                            print(f"   ⚠️  Detectat tab/page temporary ({current_url}). Retry auto-login o single time...")
                        else:
                            print(f"   ⚠️  Auto-login was not successful. Retry o single time...")

                        self.log_steam_debug(account_name, "login_failed_retrying", {
                            "retry_attempt": retry_attempt,
                            "current_url": current_url
                        })

                        try:
                            await page.get('https://casehug.com/free-cases')
                            await asyncio.sleep(3)
                        except:
                            pass

                        return await self.check_steam_login(page, account_name, retry_attempt + 1)

                    print(f"   ❌ Auto-login failed after retry. The account will be skipped.")
                    self.log_steam_debug(account_name, "login_failed_after_retry", {
                        "retry_attempt": retry_attempt,
                        "current_url": (page.url if page else "")
                    })
                    return False
                else:
                    # Extract balance
                    import re
                    header_match = re.search(r'data-testid="header-account-balance"[^>]*>.*?<span\s+data-testid="format-price"[^>]*>(\$[\d.]+)</span>', content, re.DOTALL)
                    if header_match:
                        balance = header_match.group(1)
                        print(f"   ✅ Auto-login successful for {account_name}! (Balance: {balance})")
                        self.log_steam_debug(account_name, "auto_login_success", {
                            "retry_attempt": retry_attempt,
                            "balance": balance,
                            "current_url": page.url
                        })
                    else:
                        print(f"   ✅ Auto-login successful for {account_name}!")
                        self.log_steam_debug(account_name, "auto_login_success", {
                            "retry_attempt": retry_attempt,
                            "balance": None,
                            "current_url": page.url
                        })
                    return True
                
        except Exception as e:
            print(f"   ⚠️  Login verification error: {e}")
            self.log_steam_debug(account_name, "check_exception", {
                "retry_attempt": retry_attempt,
                "error": str(e),
                "current_url": (page.url if page else "")
            })
            return True  # Continue oricum
    
    async def check_available_cases(self, page, account_name):
        """Check which cases are available on https://casehug.com/free-cases"""
        try:
            print(f"\n🔍 Checking available cases for {account_name}...")
            
            # Navigate to the free-cases page
            free_cases_url = "https://casehug.com/free-cases"
            print(f"   🌐 Accesez: {free_cases_url}")
            
            await page.get(free_cases_url)
            await asyncio.sleep(3)
            
            # Check if suntem on site corect
            current_url = page.url
            if "casehug.com/free-cases" in current_url:
                print(f"   ✅ Site loaded correctly: {current_url}")
            else:
                print(f"   ⚠️  WARNING: Wrong page. Expected 'casehug.com/free-cases', landed on: {current_url}")
                # Try again
                await page.get(free_cases_url)
                await asyncio.sleep(3)
                current_url = page.url
                if "casehug.com/free-cases" in current_url:
                    print(f"   ✅ Second attempt succeeded: {current_url}")
                else:
                    print(f"   ❌ Could not reach free-cases, stopping check")
                    return []
            
            # Check Cloudflare
            cloudflare_ok = await self.check_cloudflare(page)
            
            # Wait for the page to fully load
            await asyncio.sleep(2)
            
            # Check whether the user is logged in with Steam
            is_logged_in = await self.check_steam_login(page, account_name)
            
            # Wait after check login
            await asyncio.sleep(2)
            
            # Extract page HTML
            content = await page.get_content()
            
            available_cases = []
            
            # Define cases by level order (for smart checking)
            # Format: (case_name, required_level)
            level_cases_order = [
                ("wood", 0),
                ("iron", 12),
                ("bronze", 24),
                ("silver", 32),
                ("gold", 41),
                ("platinum", 54),
                ("emerald", 64),
                ("diamond", 72),
                ("master", 87),
                ("challenger", 100),
                ("legend", 111),
                ("mythic", 119),
                ("immortal", 120)
            ]
            
            # Check fiecare case specific after link its
            case_urls = {
                "discord": 'href="/free-cases/discord"',
                "steam": 'href="/free-cases/steam"',
                "wood": 'href="/free-cases/wood"',
                "iron": 'href="/free-cases/iron"',
                "bronze": 'href="/free-cases/bronze"',
                "silver": 'href="/free-cases/silver"',
                "gold": 'href="/free-cases/gold"',
                "platinum": 'href="/free-cases/platinum"',
                "emerald": 'href="/free-cases/emerald"',
                "diamond": 'href="/free-cases/diamond"',
                "master": 'href="/free-cases/master"',
                "challenger": 'href="/free-cases/challenger"',
                "legend": 'href="/free-cases/legend"',
                "mythic": 'href="/free-cases/mythic"',
                "immortal": 'href="/free-cases/immortal"'
            }
            
            # Check fiecare case
            # 1. Always check Discord and Steam (they do not depend on level)
            # 2. Check level-based cases in order, STOP at first one locked by level
            
            # Check Discord and Steam (always available, not level-dependent)
            for case_type in ["discord", "steam"]:
                if case_type not in case_urls:
                    continue
                    
                case_url_marker = case_urls[case_type]
                case_pos = content.find(case_url_marker)
                
                if case_pos == -1:
                    print(f"   ⚠️  {case_type.upper()} - was not found on page")
                    continue
                
                # Extract section (500 before, 2000 after for full context)
                section_start = max(0, case_pos - 500)
                section_end = min(len(content), case_pos + 2000)
                case_section = content[section_start:section_end]
                
                # Check if e on cooldown
                has_timer = False
                if 'data-testid="badge"' in case_section and 'ri-timer-line' in case_section:
                    import re
                    time_pattern = re.search(r'(\d{1,2}):(\d{2}):(\d{2})', case_section)
                    if time_pattern:
                        time_str = time_pattern.group(0)
                        print(f"   ⏰ {case_type.upper()} - on cooldown (remaining {time_str})")
                        has_timer = True
                
                if has_timer:
                    continue  # Skip this case
                
                # Check if it is locked due to incomplete tasks
                has_lock_icon = 'and-ch-lock' in case_section
                has_disabled_button = ('disabled=""' in case_section or '<button disabled' in case_section)
                is_case_locked = 'CASE LOCKED' in case_section or 'Case Locked' in case_section
                
                if has_lock_icon or (has_disabled_button and is_case_locked):
                    print(f"   🔒 {case_type.upper()} - locked (task incomplete)")
                    continue
                
                if has_disabled_button and not has_timer:
                    print(f"   ⚠️  {case_type.upper()} - button disabled")
                    continue
                
                # Check if are button Open activ
                has_open_button = False
                if '>Open<' in case_section:
                    open_positions = []
                    search_pos = 0
                    while True:
                        pos = case_section.find('>Open<', search_pos)
                        if pos == -1:
                            break
                        open_positions.append(pos)
                        search_pos = pos + 1
                    
                    for open_pos in open_positions:
                        button_context = case_section[max(0, open_pos - 400):open_pos]
                        if '<button' in button_context:
                            last_button_start = button_context.rfind('<button')
                            button_tag = button_context[last_button_start:]
                            if 'disabled' not in button_tag:
                                has_open_button = True
                                break
                
                if has_open_button:
                    available_cases.append(case_type)
                    print(f"   ✅ {case_type.upper()} - available")
                else:
                    print(f"   ⏳ {case_type.upper()} - unclear status")
            
            # Check level cases in ordine (wood → iron → bronze → etc.)
            # STOP at first case that does not appear on page (locked by level)
            print(f"\\n   📊 Check level-based cases...")
            for case_type, required_level in level_cases_order:
                if case_type not in case_urls:
                    continue
                    
                case_url_marker = case_urls[case_type]
                
                # Check if case apare in page
                case_pos = content.find(case_url_marker)
                
                if case_pos == -1:
                    # Case does NOT appear on page -> LOCKED due to level requirement
                    # All next cases are also locked
                    print(f"   🔒 {case_type.upper()} (level {required_level}) - locked due to level requirement")
                    print(f"   🛑 STOP: All next cases are locked")
                    break  # STOP - do not check next cases
                
                # Case-ul apare in page → check statusul
                # IMPORTANT: Extract section ONLY AFTER case URL 
                # (nu before, ca to nu prindem date de at case anterior)
                section_start = case_pos  # Start exact de at URL
                section_end = min(len(content), case_pos + 2000)  # 2000 after URL
                case_section = content[section_start:section_end]
                
                # 1. Check indicatori de status
                has_lock_icon = 'and-ch-lock' in case_section
                has_disabled_button = ('disabled=""' in case_section or '<button disabled' in case_section)
                has_timer = False
                if 'data-testid="badge"' in case_section and 'ri-timer-line' in case_section:
                    import re
                    time_pattern = re.search(r'(\d{1,2}):(\d{2}):(\d{2})', case_section)
                    if time_pattern:
                        has_timer = True
                        time_str = time_pattern.group(0)
                
                # 2. DECISION LOGIC for level-based cases:
                # - LOCK (with or without timer) -> INSUFFICIENT LEVEL -> BREAK
                # - Doar TIMER (without lock) → PE COOLDOWN → CONTINUE
                
                # If LOCK is present (regardless of timer) -> INSUFFICIENT LEVEL
                if has_lock_icon:
                    print(f"   🔒 {case_type.upper()} (level {required_level}) - level insufficient")
                    print(f"   🛑 STOP: All next cases require a higher level")
                    break  # STOP checking
                
                # If are only TIMER (without lock) → PE COOLDOWN
                if has_timer and not has_lock_icon:
                    print(f"   ⏰ {case_type.upper()} (level {required_level}) - on cooldown ({time_str})")
                    continue  # Continue checking - next ones may be available
                
                # If button is disabled but without lock and timer -> unclear
                if has_disabled_button and not has_lock_icon and not has_timer:
                    print(f"   ⚠️  {case_type.upper()} (level {required_level}) - button disabled (unclear)")
                    continue
                
                # 3. Check if are button OPEN activ
                has_open_button = False
                if '>Open<' in case_section:
                    open_positions = []
                    search_pos = 0
                    while True:
                        pos = case_section.find('>Open<', search_pos)
                        if pos == -1:
                            break
                        open_positions.append(pos)
                        search_pos = pos + 1
                    
                    for open_pos in open_positions:
                        button_context = case_section[max(0, open_pos - 400):open_pos]
                        if '<button' in button_context:
                            last_button_start = button_context.rfind('<button')
                            button_tag = button_context[last_button_start:]
                            if 'disabled' not in button_tag:
                                has_open_button = True
                                break
                
                if has_open_button:
                    available_cases.append(case_type)
                    print(f"   ✅ {case_type.upper()} (level {required_level}) - available")
                else:
                    print(f"   ⏳ {case_type.upper()} (level {required_level}) - unclear status")
            
            if not available_cases:
                print(f"   ⚠️  No case available for {account_name}")
            
            return available_cases
            
        except Exception as e:
            print(f"   ❌ Error while checking available cases: {e}")
            import traceback
            traceback.print_exc()
            # Fallback: return all cases from config
            return ["discord", "steam", "wood"]
    
    async def open_free_case(self, page, account_name, case_type):
        """Open a specific free case"""
        case_urls = {
            "discord": "https://casehug.com/free-cases/discord",
            "steam": "https://casehug.com/free-cases/steam",
            "wood": "https://casehug.com/free-cases/wood",
            "iron": "https://casehug.com/free-cases/iron",
            "bronze": "https://casehug.com/free-cases/bronze",
            "silver": "https://casehug.com/free-cases/silver",
            "gold": "https://casehug.com/free-cases/gold",
            "platinum": "https://casehug.com/free-cases/platinum",
            "emerald": "https://casehug.com/free-cases/emerald",
            "diamond": "https://casehug.com/free-cases/diamond",
            "master": "https://casehug.com/free-cases/master",
            "challenger": "https://casehug.com/free-cases/challenger",
            "legend": "https://casehug.com/free-cases/legend",
            "mythic": "https://casehug.com/free-cases/mythic",
            "immortal": "https://casehug.com/free-cases/immortal"
        }
        
        if case_type.lower() not in case_urls:
            print(f"   ⚠️ Unknown case type '{case_type}'")
            return None
        
        case_url = case_urls[case_type.lower()]
        print(f"\n📦 Opening {case_type} for {account_name}...")
        print(f"   🌐 Navigating directly to: {case_url}")
        
        try:
            # In Docker: Get cookies de at FlareSolverr BEFORE de navigare
            if hasattr(self, 'flaresolverr_primary') and self.flaresolverr_primary and self.use_flaresolverr:
                print(f"   🐳 Docker: Using FlareSolverr for Cloudflare bypass...")
                flare_result = await self.solve_cloudflare_with_flaresolverr(case_url, account_name=account_name)
                
                if flare_result and flare_result.get('cookies'):
                    print(f"   🍪 Injecting {len(flare_result['cookies'])} cookies BEFORE navigation...")
                    
                    # Set cookies in browser BEFORE de navigare
                    for cookie in flare_result['cookies']:
                        try:
                            # Build cookie in format CDP
                            cookie_params = {
                                'name': cookie['name'],
                                'value': cookie['value'],
                                'domain': cookie.get('domain', '.casehug.com'),
                                'path': cookie.get('path', '/'),
                                'secure': cookie.get('secure', False),
                                'http_only': cookie.get('httpOnly', False)
                            }
                            
                            # Add sameSite if exists
                            if 'sameSite' in cookie:
                                cookie_params['same_site'] = cookie['sameSite']
                            
                            await page.send(cdp.network.set_cookie(**cookie_params))
                        except Exception as cookie_err:
                            # Ignore erori for cookies individuale (unele pot fi invalide)
                            pass
                    
                    print(f"   ✅ Cookies injectate - navighez at page...")
                    await asyncio.sleep(1)
                else:
                    print("   ⚠️  FlareSolverr could not solve - continuing without cookies")
            
            # Direct navigation with Nodriver (now with cookies already set in Docker)
            await page.get(case_url)
            await asyncio.sleep(3)
            
            # Check Cloudflare (Nodriver solves automatically)
            cloudflare_ok = await self.check_cloudflare(page)
            
            # Scroll
            await page.evaluate("window.scrollTo(0, 400)")
            await asyncio.sleep(1)
            
            # Search button OPEN/CLAIM
            print(f"   🔍 Searching for 'Open for Free' button...")
            
            button = None
            
            # Method 1: Search directly after data-testid (most reliable)
            try:
                button = await page.query_selector('button[data-testid="open-button"]')
                if button:
                    print(f"   ✓ Found button with data-testid='open-button'")
            except:
                pass
            
            # Metoda 2: Fallback - search all butoanele
            if not button:
                button_texts = ["Open for Free", "Open", "Claim", "Free", "Get"]
                buttons = await page.select_all("button")
                
                for btn in buttons:
                    try:
                        # Skip buttons disabled (locked)
                        is_disabled = await btn.get_attribute('disabled')
                        if is_disabled is not None:
                            btn_text = await btn.text
                            print(f"   🔒 Ignored button (disabled): {btn_text}")
                            continue
                        
                        # Check textul
                        btn_text = await btn.text
                        if btn_text:
                            for text in button_texts:
                                if text.lower() in btn_text.lower():
                                    button = btn
                                    print(f"   ✓ Found button with text: {btn_text}")
                                    break
                        
                        if button:
                            break
                    except:
                        continue
            
            if not button:
                print(f"   ❌ Could not find OPEN button (case locked or on cooldown)")
                return {
                    "case": case_type,
                    "skin": "Button missing",
                    "price": "N/A"
                }
            
            # Check if button is disabled (final check)
            try:
                is_disabled = await button.get_attribute('disabled')
                if is_disabled is not None:
                    print(f"   🔒 Button is LOCKED (disabled)")
                    return {
                        "case": case_type,
                        "skin": "Locked",
                        "price": "N/A"
                    }
            except:
                pass
            
            # Click on button
            await button.scroll_into_view()
            await asyncio.sleep(0.5)
            await button.click()
            print(f"   ✓ Click the button OPEN")
            
            # Wait rezultatul
            await asyncio.sleep(5)
            
            # Check if an error message exists (insufficient playtime)
            content = await page.get_content()
            if 'Insufficient CS:GO/CS2 playtime' in content or 'Insufficient CS' in content:
                print(f"   ❌ ERROR: Insufficient CS:GO/CS2 playtime for this account!")
                print(f"   ⚠️  This account cannot open free cases (more played hours required)")
                return {
                    "case": case_type,
                    "skin": "Insufficient playtime",
                    "price": "N/A"
                }
            
            # Search skinul and price
            print(f"   🔍 Searching for result...")
            
            skin_name = "Unknown"
            price = "N/A"
            
            # Search skin prin selectors comuni
            skin_selectors = [
                '.item-name', '.skin-name', '.reward-name',
                '.item-title', '.skin-title', '.reward-title'
            ]
            
            for selector in skin_selectors:
                try:
                    elements = await page.select_all(selector)
                    for elem in elements:
                        try:
                            text = await elem.text
                            if text and len(text) > 3 and ('-' in text or '|' in text or '(' in text):
                                skin_name = text.strip()
                                print(f"   ✓ Skin: {skin_name}")
                                break
                        except:
                            continue
                    if skin_name != "Unknown":
                        break
                except:
                    continue
            
            # Search price
            price_selectors = [
                '.price', '.value', '.amount', '.cost'
            ]
            
            for selector in price_selectors:
                try:
                    elements = await page.select_all(selector)
                    for elem in elements:
                        try:
                            text = await elem.text
                            if text and ('$' in text or '€' in text or any(c.isdigit() for c in text)):
                                price = text.strip()
                                print(f"   ✓ Price: {price}")
                                break
                        except:
                            continue
                    if price != "N/A":
                        break
                except:
                    continue
            
            print(f"✅ {case_type}: {skin_name} - {price}")
            
            return {
                "case": case_type,
                "skin": skin_name,
                "price": price
            }
            
        except Exception as e:
            print(f"   ❌ Error: {e}")
            import traceback
            traceback.print_exc()
            return {
                "case": case_type,
                "skin": "Error",
                "price": "N/A"
            }
    
    async def process_account(self, account):
        """Process one account - launch separate browser flow per case"""
        account_name = account['name']
        
        print(f"\n{'='*50}")
        print(f"🎮 Processing account: {account_name}")
        print(f"{'='*50}")
        
        # In Docker: Create FlareSolverr session for this account  
        if hasattr(self, 'flaresolverr_primary') and self.flaresolverr_primary:
            await self.create_flaresolverr_session(account_name)
        
        browser = None
        try:
            # Launch browser only once for this account
            print(f"   🔍 Launching browser...")
            page, browser = await self.create_page_with_stealth(account_name)
            
            # Check which cases are available (dynamic)
            available_cases = await self.check_available_cases(page, account_name)
            
            if not available_cases:
                print(f"⚠️  No case available for {account_name} today")
                print(f"   ℹ️  Still checking profile page for new skins...")
            else:
                # Process fiecare case WITHOUT to close browser
                results = []
                for idx, case_type in enumerate(available_cases, 1):
                    print(f"\n   📦 Processing case {idx}/{len(available_cases)}: {case_type.upper()}")
                    
                    try:
                        # Find and click the button directly on the /free-cases page
                        result = await self.open_free_case_on_page(page, account_name, case_type)
                        # Do not save result here anymore - extract from profile
                        
                        # Return to /free-cases for next case
                        if idx < len(available_cases):
                            print(f"   ↩️  Returning to /free-cases for next case...")
                            await page.get("https://casehug.com/free-cases")
                            await asyncio.sleep(3)
                            
                    except Exception as e:
                        print(f"   ❌ Processing error {case_type}: {e}")
                    
                    # Pause between cases
                    if idx < len(available_cases):
                        await asyncio.sleep(2)
            
            # After all cases are opened, extract new skins from profile
            print(f"\n   🔍 Extracting results from profile page...")
            results = await self.extract_new_skins_from_profile(page, account_name)
            
            return {
                "account": account_name,
                "results": results,
                "balance": "N/A"
            }
            
        except Exception as e:
            print(f"❌ Processing error {account_name}: {e}")
            import traceback
            traceback.print_exc()
            return None
        finally:
            # Close browser at final with force
            if browser:
                try:
                    await browser.stop()
                    print(f"   ✅ Browser closed for {account_name}")
                    await asyncio.sleep(2)  # Wait for full close
                except Exception as e:
                    print(f"   ⚠️  Error while closing browser: {e}")
                
                # Force closing proceselor Chrome remaining
                try:
                    import subprocess
                    import platform
                    if platform.system() == 'Windows':
                        # Close Chrome processes with force on Windows
                        subprocess.run(['taskkill', '/F', '/IM', 'chrome.exe'], 
                                     stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
                        subprocess.run(['taskkill', '/F', '/IM', 'chromedriver.exe'], 
                                     stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
                        print(f"   🧹 Chrome processes cleaned for {account_name}")
                except:
                    pass
            
            # Close FlareSolverr session in Docker
            if hasattr(self, 'flaresolverr_primary') and self.flaresolverr_primary:
                await self.destroy_flaresolverr_session(account_name)
    
    async def extract_new_skins_from_profile(self, page, account_name):
        """Extract new skins from profile page (https://casehug.com/user-account)"""
        print(f"\n   📊 Extracting new skins from profile page...")
        
        try:
            # Navigate to the profile page
            await page.get("https://casehug.com/user-account")
            print(f"   🌐 Navigated to https://casehug.com/user-account")
            
            # Wait loading paginii
            await asyncio.sleep(4)
            
            # Get HTML paginii
            content = await page.get_content()
            
            # Search all skins with label "New"
            import re
            
            # Pattern: find all divs with data-testid="your-drop-card-label" that contain "New"
            # Then extract data from the same container
            new_skins = []
            
            # Split HTML in sections for fiecare card de skin
            # Find all occurrences de "your-drop-card-label"
            pattern = r'<div data-testid="your-drop-card-label"[^>]*>([^<]+)</div>'
            labels = re.finditer(pattern, content)
            
            for label_match in labels:
                label_text = label_match.group(1).strip()
                
                # Check if label is "New"
                if label_text.lower() == "new":
                    # Find beginning container-ului (climb until at div-ul parent mare)
                    # Search backward until finding the parent div with all data
                    start_pos = label_match.start()
                    
                    # Search back until find div-ul principal (class="sc-965b1227-6")
                    search_back = content[max(0, start_pos - 5000):start_pos]
                    container_match = re.search(r'<div class="sc-965b1227-6[^"]*">', search_back)
                    
                    if container_match:
                        container_start = start_pos - len(search_back) + container_match.start()
                        # Extract section (next 3000 characters)
                        section = content[container_start:start_pos + 3000]
                        
                        # Extract data from this section
                        name_match = re.search(r'<div data-testid="your-drop-name"[^>]*>([^<]+)</div>', section)
                        category_match = re.search(r'<div data-testid="your-drop-category"[^>]*>([^<]+)</div>', section)
                        price_match = re.search(r'<span data-testid="your-drop-price"[^>]*>([^<]+)</span>', section)
                        case_type_match = re.search(r'<div data-testid="your-drops-hover-date"[^>]*>([^<]+)</div>', section)
                        
                        if name_match and category_match and price_match:
                            weapon_name = name_match.group(1).strip()
                            skin_category = category_match.group(1).strip()
                            price = price_match.group(1).strip()
                            case_type = case_type_match.group(1).strip().lower() if case_type_match else "unknown"
                            
                            # Extract color (rarity) from gradient SVG
                            color_match = re.search(r'stop-color="([^"]+)"', section)
                            rarity_color = color_match.group(1).upper() if color_match else "#FFFFFF"
                            
                            # Map color to rarity and emoji
                            rarity_map = {
                                "#B0C3D9": ("⚪", "Consumer Grade"),  # Consumer - alb
                                "#A3A7BB": ("⚪", "Consumer Grade"),  # Consumer variations
                                "#5E98D9": ("🔵", "Industrial Grade"),  # Industrial - albastru opened
                                "#4B69FF": ("🔵", "Mil-Spec Grade"),  # Mil-Spec - albastru
                                "#8847FF": ("🟣", "Restricted"),  # Restricted - mov
                                "#D32CE6": ("🟣", "Restricted"),  # Restricted variations
                                "#EB4B4B": ("🔴", "Classified"),  # Classified - red
                                "#E4AE39": ("🟡", "Classified"),  # Classified variations
                                "#F93AA6": ("🩷", "Classified"),  # Classified - roz
                                "#FFD700": ("🟡", "Covert/Contraband"),  # Covert - auriu
                            }
                            
                            # Find closest color match
                            rarity_emoji = "⚪"
                            for color_code, (emoji, grade_name) in rarity_map.items():
                                if rarity_color.startswith(color_code[:4]):  # Match primele 4 caractere
                                    rarity_emoji = emoji
                                    break
                            
                            # We no longer use fallback by price.
                            # Price is not a reliable indicator for rarity.
                            
                            skin_full_name = f"{weapon_name} | {skin_category}"
                            
                            new_skins.append({
                                "case": case_type,
                                "skin": skin_full_name,
                                "price": price,
                                "rarity": rarity_emoji
                            })
                            
                            print(f"   🆕 Found skin new: {rarity_emoji} {case_type.upper()} - {skin_full_name} - {price}")
            
            if not new_skins:
                print(f"   ℹ️  No new skins found on profile page")
            else:
                print(f"   ✅ Total {len(new_skins)} new skins extracted")
            
            return new_skins
            
        except Exception as e:
            print(f"   ❌ Error while extracting from profile: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    async def open_free_case_on_page(self, page, account_name, case_type):
        """Open case directly on /free-cases page without extra navigation"""
        print(f"📦 Opening {case_type} directly on /free-cases...")
        
        try:
            # Wait until the page is ready
            await asyncio.sleep(2)
            
            # Find link to case (for a identifica section)
            case_link = f'/free-cases/{case_type}'
            
            # Search button "Open" in HTML folosind selector
            # Strategia: find anchor-ul with href=/free-cases/{case_type}, 
            # then search "Open" button in parent div
            
            content = await page.get_content()
            
            # Check if case is available (not on cooldown, not locked)
            case_pos = content.find(f'href="{case_link}"')
            if case_pos == -1:
                print(f"   ❌ Could not find link for {case_type}")
                return None
            
            # Extract section (2000 characters after link)
            section = content[case_pos:case_pos + 2000]
            
            # Check again if are timer or e locked
            if 'ri-timer-line' in section:
                print(f"   ⏰ {case_type.upper()} is on cooldown")
                return None
            
            if 'and-ch-lock' in section or 'disabled=""' in section:
                print(f"   🔒 {case_type.upper()} is locked")
                return None
            
            # Search button "Open" folosind click on link caseui
            # Simpler: click anchor that points to /free-cases/{case_type}
            try:
                # Find anchor-ul with href="/free-cases/{case_type}"
                links = await page.select_all(f'a[href="{case_link}"]')
                
                if not links:
                    print(f"   ❌ Could not find link {case_link}")
                    return None
                
                # Click the first link (which opens the case page)
                link = links[0]
                await link.scroll_into_view()
                await asyncio.sleep(0.5)
                await link.click()
                print(f"   ✓ Click on case {case_type.upper()}")
                
                # Wait for the case page to load
                await asyncio.sleep(3)
                
                # Acum suntem on /free-cases/{case_type}
                # Search button "Open for Free" on this page
                button = None
                
                # Strategia 1: data-testid="open-button"
                try:
                    button = await page.query_selector('button[data-testid="open-button"]')
                    if button:
                        is_disabled = await button.get_attribute('disabled')
                        if is_disabled is not None:
                            print(f"   ⚠️  Button disabled")
                            return None
                        print(f"   🔓 Button found: open-button")
                except:
                    pass
                
                # Strategia 2: search button with text "Open"
                if not button:
                    buttons = await page.select_all('button')
                    for btn in buttons:
                        try:
                            text = await btn.text
                            if text and 'open' in text.lower():
                                is_disabled = await btn.get_attribute('disabled')
                                if is_disabled is None:
                                    button = btn
                                    print(f"   🔓 Button found with text: {text}")
                                    break
                        except:
                            continue
                
                if not button:
                    print(f"   ❌ Could not find button OPEN for {case_type}")
                    return None
                
                # Click the button Open
                await button.scroll_into_view()
                await asyncio.sleep(0.5)
                await button.click()
                print(f"   ✓ Click the button OPEN")
                
                # Wait for the opening animation
                print(f"   ⏳ Waiting animation (15s)...")
                await asyncio.sleep(15)
                
                # Check only if an error appeared (insufficient playtime)
                content = await page.get_content()
                
                # Check erori (playtime insufficient)
                import re
                content_without_scripts = re.sub(r'<script[^>]*>.*?</script>', '', content, flags=re.DOTALL | re.IGNORECASE)
                
                error_patterns = [
                    r'<div[^>]*class="[^"]*notification[^"]*"[^>]*>.*?Insufficient.*?CS.*?playtime.*?</div>',
                    r'<div[^>]*class="[^"]*error[^"]*"[^>]*>.*?Insufficient.*?CS.*?playtime.*?</div>',
                    r'<p[^>]*class="[^"]*error[^"]*"[^>]*>.*?Insufficient.*?CS.*?playtime.*?</p>'
                ]
                
                has_error = False
                for pattern in error_patterns:
                    if re.search(pattern, content_without_scripts, re.IGNORECASE | re.DOTALL):
                        has_error = True
                        break
                
                if has_error:
                    print(f"   ❌ ERROR: Insufficient CS:GO/CS2 playtime!")
                    return False
                
                print(f"   ✅ Case {case_type.upper()} opened successfully")
                return True
                
            except Exception as e:
                print(f"   ❌ Click error: {e}")
                return False
            
        except Exception as e:
            print(f"   ❌ Error: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def send_telegram_message(self, message):
        """Send message to Telegram"""
        if not self.telegram_token or not self.telegram_chat_id:
            print("Telegram is not configured.")
            return
        
        url = f"https://api.telegram.org/bot{self.telegram_token}/sendMessage"
        data = {
            "chat_id": self.telegram_chat_id,
            "text": message,
            "parse_mode": "HTML"
        }
        
        try:
            response = requests.post(url, data=data)
            if response.status_code == 200:
                print("✅ Message trimis on Telegram")
            else:
                print(f"❌ Telegram error: {response.text}")
        except Exception as e:
            print(f"❌ Telegram error: {e}")
    
    def format_telegram_report(self, all_results):
        """Format report for Telegram"""
        now = datetime.now().strftime("%d.%m.%Y %H:%M:%S")
        
        message = f"🎰 <b>Casehug Daily Report</b>\n"
        message += f"📅 {now}\n"
        message += f"{'─'*30}\n\n"
        
        for account_data in all_results:
            if account_data is None:
                continue
            
            message += f"<b>{account_data['account']}</b>\n"
            
            if account_data['results']:
                for result in account_data['results']:
                    case_name = result['case'].upper()
                    skin = result['skin']
                    price = result['price']
                    rarity = result.get('rarity', '⚪')  # Default at alb if nu exists
                    message += f"{rarity} {case_name}: {skin} - {price}\n"
            else:
                message += "❌ No new skin\n"
            
            message += f"\n"
        
        message += f"{'─'*30}\n"
        
        return message
    
    async def run(self):
        """Run botul"""
        print("🚀 Starting CasehugBot (Nodriver)...")
        print(f"📊 Number of accounts: {len(self.accounts)}")
        print("🛡️  Bypass Cloudflare: AUTOMAT (Nodriver - 11.22s avg)\n")
        
        try:
            # Setup browser (minimal for Nodriver)
            await self.setup_browser()
            
            # Process all accounts
            all_results = []
            for account in self.accounts:
                print(f"\n🧪 Processing: {account['name']}\n")
                result = await self.process_account(account)
                all_results.append(result)
                
                # Save timestamp if processed successfully
                if result and result.get('results'):
                    # Opened at least one case successfully
                    self.save_account_timestamp(account['name'], had_success=True)
                elif result:
                    # A fost procesat dar without cases (cooldown, locked, etc)
                    self.save_account_timestamp(account['name'], had_success=False)
                
                # Pause between accounts
                if account != self.accounts[-1]:  # Nu wait after ultimul account
                    print("\n⏳ 10s pause before next account (browser cleanup)...")
                    await asyncio.sleep(10)
            
            # Send Telegram report
            if any(r is not None for r in all_results):
                report = self.format_telegram_report(all_results)
                self.send_telegram_message(report)
            
            print("\n✅ All accounts processed!")
            
        except Exception as e:
            print(f"❌ Error: {e}")
            import traceback
            traceback.print_exc()

async def main():
    bot = CasehugBotNodriver()
    await bot.run()

if __name__ == "__main__":
    asyncio.run(main())
