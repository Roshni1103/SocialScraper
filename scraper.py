from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, WebDriverException
import os
import platform
import time
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
import logging
import sys
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('scraper.log'),
        logging.StreamHandler(sys.stdout)
    ]
)

class BaseScraper(ABC):
    def __init__(self):
        self.driver = None
        self.max_retries = 3
        self.retry_delay = 2
        
        for attempt in range(self.max_retries):
            try:
                options = self._configure_chrome_options()
                service = self._configure_chrome_service()
                self.driver = webdriver.Chrome(service=service, options=options)
                self.driver.set_page_load_timeout(30)
                self.wait = WebDriverWait(self.driver, 20)
                logging.info("Chrome driver initialized successfully")
                break
            except Exception as e:
                logging.error(f"Attempt {attempt + 1} failed: {str(e)}")
                if attempt == self.max_retries - 1:
                    raise Exception(f"Failed to initialize Chrome driver after {self.max_retries} attempts: {str(e)}")
                time.sleep(self.retry_delay)

    def _configure_chrome_options(self):
        options = webdriver.ChromeOptions()
        options.add_argument('--headless=new')
        options.add_argument('--disable-gpu')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-extensions')
        options.add_argument('--disable-software-rasterizer')
        options.add_argument('--ignore-certificate-errors')
        options.add_argument('--disable-notifications')
        options.add_argument('--disable-popup-blocking')
        options.add_argument('--start-maximized')
        options.add_experimental_option('excludeSwitches', ['enable-logging'])
        options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.6834.111 Safari/537.36')
        return options

    def _configure_chrome_service(self):
        try:
            # Try multiple ChromeDriver paths
            possible_paths = [
                "chromedriver.exe",
                Path.cwd() / "chromedriver.exe",
                Path.home() / "chromedriver.exe",
                Path(os.environ.get('CHROMEDRIVER_PATH', '')) / "chromedriver.exe"
            ]
            
            for driver_path in possible_paths:
                if Path(driver_path).exists():
                    logging.info(f"Found ChromeDriver at: {driver_path}")
                    return Service(str(driver_path))
            
            logging.warning("No ChromeDriver found in common locations, using default Service")
            return Service("chromedriver.exe")
        except Exception as e:
            logging.error(f"Error configuring Chrome service: {str(e)}")
            return Service("chromedriver.exe")

    def __del__(self):
        if hasattr(self, 'driver') and self.driver:
            try:
                self.driver.quit()
            except:
                pass

    def _format_url(self, url: str) -> str:
        """Format URL to ensure it's valid."""
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
        return url.rstrip('/')

    def _safe_get(self, url: str, max_retries: int = 3) -> bool:
        """Safely navigate to a URL with retries."""
        for attempt in range(max_retries):
            try:
                self.driver.get(url)
                return True
            except Exception as e:
                logging.error(f"Attempt {attempt + 1} to load {url} failed: {str(e)}")
                if attempt == max_retries - 1:
                    return False
                time.sleep(self.retry_delay)
        return False

    def _safe_find_element(self, by: By, value: str, timeout: int = 20) -> Optional[Any]:
        """Safely find an element with explicit wait."""
        try:
            return self.wait.until(EC.presence_of_element_located((by, value)))
        except Exception as e:
            logging.error(f"Failed to find element {value}: {str(e)}")
            return None

    @abstractmethod
    def scrape_profile(self, url: str) -> Dict[str, Any]:
        pass

    @abstractmethod
    def scrape_post(self, url: str) -> Dict[str, Any]:
        pass

class YouTubeScraper(BaseScraper):
    def scrape_profile(self, url: str) -> Dict[str, Any]:
        url = self._format_url(url)
        if not self._safe_get(url):
            raise Exception("Failed to load YouTube channel")

        result = {
            "platform": "YouTube",
            "type": "channel",
            "channel_name": "Unknown",
            "subscribers": "Not available"
        }

        try:
            # Wait longer for dynamic content
            time.sleep(5)
            
            # Scroll to trigger content loading
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight/2);")
            time.sleep(2)

            # Try to get channel name using multiple methods
            try:
                # Method 1: Direct XPath for channel title
                channel_name = self.driver.find_element(
                    By.XPATH,
                    "//yt-formatted-string[contains(@class, 'ytd-channel-name')]"
                ).text.strip()
                if channel_name:
                    result["channel_name"] = channel_name
            except:
                try:
                    # Method 2: Get the h1 title
                    channel_name = self.driver.find_element(
                        By.CSS_SELECTOR,
                        "ytd-channel-name h1"
                    ).text.strip()
                    if channel_name:
                        result["channel_name"] = channel_name
                except:
                    try:
                        # Method 3: Get from meta tag
                        channel_name = self.driver.find_element(
                            By.XPATH,
                            "//meta[@property='og:title']"
                        ).get_attribute("content")
                        if channel_name:
                            result["channel_name"] = channel_name.replace(" - YouTube", "")
                    except:
                        pass

            # Try to get subscriber count using multiple methods
            try:
                # Method 1: Direct ID
                sub_count = self.driver.find_element(
                    By.ID,
                    "subscriber-count"
                ).text.strip()
                if sub_count:
                    result["subscribers"] = sub_count
            except:
                try:
                    # Method 2: XPath for subscriber count
                    sub_count = self.driver.find_element(
                        By.XPATH,
                        "//yt-formatted-string[@id='subscriber-count']"
                    ).text.strip()
                    if sub_count:
                        result["subscribers"] = sub_count
                except:
                    try:
                        # Method 3: Get from channel metadata
                        sub_count = self.driver.find_element(
                            By.CSS_SELECTOR,
                            "#metadata-container #subscriber-count"
                        ).text.strip()
                        if sub_count:
                            result["subscribers"] = sub_count
                    except:
                        pass

            # If still no data, try JavaScript injection
            if result["channel_name"] == "Unknown":
                try:
                    channel_name = self.driver.execute_script(
                        "return document.querySelector('ytd-channel-name').innerText"
                    )
                    if channel_name:
                        result["channel_name"] = channel_name.split('\n')[0].strip()
                except:
                    pass

            if result["subscribers"] == "Not available":
                try:
                    sub_count = self.driver.execute_script(
                        "return document.querySelector('#subscriber-count').innerText"
                    )
                    if sub_count:
                        result["subscribers"] = sub_count.strip()
                except:
                    pass

            # Log for debugging
            if result["channel_name"] == "Unknown" or result["subscribers"] == "Not available":
                logging.error(f"Failed to find data for URL: {url}")
                logging.error("Current selectors failed. Page title: " + self.driver.title)

            return result

        except Exception as e:
            logging.error(f"Error scraping YouTube profile: {str(e)}")
            return result

    def scrape_post(self, url: str) -> Dict[str, Any]:
        url = self._format_url(url)
        if not self._safe_get(url):
            raise Exception("Failed to load YouTube video")

        result = {
            "platform": "YouTube",
            "type": "video",
            "title": "Unknown",
            "likes": "Not available",
            "views": "Not available"
        }

        try:
            # Wait longer for dynamic content
            time.sleep(5)
            
            # Updated selectors for video title
            title_selectors = [
                "h1.ytd-video-primary-info-renderer yt-formatted-string",
                "#container h1.ytd-video-primary-info-renderer",
                "ytd-watch-metadata h1.ytd-watch-metadata yt-formatted-string",
                "#title h1 yt-formatted-string"
            ]
            
            for selector in title_selectors:
                try:
                    title_elem = self.wait.until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                    )
                    if title_elem and title_elem.text.strip():
                        result["title"] = title_elem.text.strip()
                        break
                except:
                    continue

            # Updated selectors for like count
            like_selectors = [
                "#top-level-buttons-computed ytd-toggle-button-renderer:first-child #text",
                "ytd-menu-renderer ytd-toggle-button-renderer #text",
                "#info ytd-toggle-button-renderer:first-child #text",
                "ytd-watch-metadata ytd-toggle-button-renderer #text"
            ]
            
            for selector in like_selectors:
                try:
                    like_elem = self.wait.until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                    )
                    if like_elem and like_elem.text.strip():
                        result["likes"] = like_elem.text.strip()
                        break
                except:
                    continue

            # Try XPath if CSS selectors fail
            if result["title"] == "Unknown":
                try:
                    title_xpath = "//h1[contains(@class, 'ytd-video-primary-info-renderer')]//yt-formatted-string"
                    title_elem = self.driver.find_element(By.XPATH, title_xpath)
                    if title_elem and title_elem.text.strip():
                        result["title"] = title_elem.text.strip()
                except:
                    pass

            return result
        except Exception as e:
            logging.error(f"Error scraping YouTube video: {str(e)}")
            return result

class InstagramScraper(BaseScraper):
    def __init__(self):
        super().__init__()
        self._configure_instagram()

    def _configure_instagram(self):
        """Configure additional settings for Instagram."""
        if self.driver:
            # Add additional cookies and localStorage settings
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            self.driver.execute_cdp_cmd('Network.setUserAgentOverride', {
                "userAgent": 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.6834.111 Safari/537.36'
            })

    def scrape_profile(self, url: str) -> Dict[str, Any]:
        url = self._format_url(url)
        result = {
            "platform": "Instagram",
            "type": "profile",
            "followers": "Not available",
            "following": "Not available",
            "posts": "Not available"
        }

        try:
            if not self._safe_get(url):
                return result

            time.sleep(5)  # Wait for Instagram's dynamic content

            # Try multiple selectors for followers
            follower_selectors = [
                "li:nth-child(2) span span",
                "span._ac2a",
                "span.g47SY"
            ]

            for selector in follower_selectors:
                try:
                    followers_elem = self._safe_find_element(By.CSS_SELECTOR, selector)
                    if followers_elem and followers_elem.text.strip():
                        result["followers"] = followers_elem.text.strip()
                        break
                except:
                    continue

            # Try multiple selectors for following
            following_selectors = [
                "li:nth-child(3) span span",
                "span._ac2a:nth-child(2)",
                "span.g47SY:nth-child(2)"
            ]

            for selector in following_selectors:
                try:
                    following_elem = self._safe_find_element(By.CSS_SELECTOR, selector)
                    if following_elem and following_elem.text.strip():
                        result["following"] = following_elem.text.strip()
                        break
                except:
                    continue

            return result

        except Exception as e:
            logging.error(f"Error scraping Instagram profile: {str(e)}")
            return result

    def scrape_post(self, url: str) -> Dict[str, Any]:
        url = self._format_url(url)
        result = {
            "platform": "Instagram",
            "type": "post",
            "likes": "Not available",
            "comments": "Not available"
        }

        try:
            if not self._safe_get(url):
                return result

            time.sleep(5)  # Wait for Instagram's dynamic content

            # Try multiple selectors for likes
            like_selectors = [
                "span.like-count",
                "section._ae5m span",
                "span._aacl"
            ]

            for selector in like_selectors:
                try:
                    likes_elem = self._safe_find_element(By.CSS_SELECTOR, selector)
                    if likes_elem and likes_elem.text.strip():
                        result["likes"] = likes_elem.text.strip()
                        break
                except:
                    continue

            return result

        except Exception as e:
            logging.error(f"Error scraping Instagram post: {str(e)}")
            return result

class TikTokScraper(BaseScraper):
    def scrape_profile(self, url: str) -> Dict[str, Any]:
        self.driver.get(url)
        try:
            followers = self.wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "strong[data-e2e='followers-count']"))
            ).text
            following = self.driver.find_element(By.CSS_SELECTOR, "strong[data-e2e='following-count']").text
            
            return {
                "platform": "TikTok",
                "type": "profile",
                "followers": followers,
                "following": following,
            }
        except TimeoutException:
            raise Exception("Failed to load TikTok profile data")

    def scrape_post(self, url: str) -> Dict[str, Any]:
        self.driver.get(url)
        try:
            likes = self.wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "strong[data-e2e='like-count']"))
            ).text
            
            return {
                "platform": "TikTok",
                "type": "video",
                "likes": likes,
            }
        except TimeoutException:
            raise Exception("Failed to load TikTok video data")

class FacebookScraper(BaseScraper):
    def scrape_profile(self, url: str) -> Dict[str, Any]:
        self.driver.get(url)
        try:
            followers = self.wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "div[data-key='followers']"))
            ).text
            
            return {
                "platform": "Facebook",
                "type": "profile",
                "followers": followers,
            }
        except TimeoutException:
            raise Exception("Failed to load Facebook profile data")

    def scrape_post(self, url: str) -> Dict[str, Any]:
        self.driver.get(url)
        try:
            likes = self.wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "span.like-count"))
            ).text
            
            return {
                "platform": "Facebook",
                "type": "post",
                "likes": likes,
            }
        except TimeoutException:
            raise Exception("Failed to load Facebook post data") 