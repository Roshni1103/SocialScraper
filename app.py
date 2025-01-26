import streamlit as st
import pandas as pd
from scraper import YouTubeScraper, InstagramScraper, TikTokScraper, FacebookScraper
import re
from typing import Optional, Dict, Any

st.set_page_config(page_title="Social Scraper", page_icon="🔍", layout="wide")

def validate_social_link(platform: str, link: str) -> tuple[bool, str]:
    """Validate the social media link and determine its type."""
    platform_patterns = {
        "YouTube": {
            "channel": r"youtube\.com/@?[\w-]+/?$",
            "video": r"youtube\.com/watch\?v=[\w-]+",
        },
        "Instagram": {
            "profile": r"instagram\.com/[\w_.]+/?$",
            "post": r"instagram\.com/p/[\w-]+",
        },
        "TikTok": {
            "profile": r"tiktok\.com/@[\w.]+/?$",
            "video": r"tiktok\.com/@[\w.]+/video/\d+",
        },
        "Facebook": {
            "profile": r"facebook\.com/[\w.]+/?$",
            "post": r"facebook\.com/[\w.]+/posts/[\w-]+",
        },
    }
    
    patterns = platform_patterns.get(platform, {})
    for link_type, pattern in patterns.items():
        if re.search(pattern, link):
            return True, link_type
    return False, "invalid"

def main():
    st.title("🔍 Social Scraper")
    st.write("Scrape data from various social media platforms")
    
    # Platform selection
    platform = st.selectbox(
        "Select Platform",
        ["YouTube", "Instagram", "TikTok", "Facebook"]
    )
    
    # Link input
    link = st.text_input("Enter social media link", placeholder=f"Enter {platform} link here...")
    
    if link:
        is_valid, link_type = validate_social_link(platform, link)
        
        if not is_valid:
            st.error("Invalid link format. Please check the URL and try again.")
            return
            
        st.success(f"Valid {platform} {link_type} link detected!")
        
        # Initialize appropriate scraper based on platform
        scrapers = {
            "YouTube": YouTubeScraper,
            "Instagram": InstagramScraper,
            "TikTok": TikTokScraper,
            "Facebook": FacebookScraper
        }
        
        scraper_class = scrapers.get(platform)
        if scraper_class:
            try:
                scraper = scraper_class()
                with st.spinner(f"Scraping data from {platform}..."):
                    if link_type in ["channel", "profile"]:
                        data = scraper.scrape_profile(link)
                    else:  # post, video
                        data = scraper.scrape_post(link)
                
                if data:
                    # Display data in a nice format
                    st.subheader("Scraped Data")
                    df = pd.DataFrame([data])
                    st.dataframe(df)
                    
                    # Export options
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button("Export as CSV"):
                            csv = df.to_csv(index=False)
                            st.download_button(
                                "Download CSV",
                                csv,
                                f"{platform.lower()}_data.csv",
                                "text/csv"
                            )
                    with col2:
                        if st.button("Export as Excel"):
                            df.to_excel("temp.xlsx", index=False)
                            with open("temp.xlsx", "rb") as f:
                                st.download_button(
                                    "Download Excel",
                                    f,
                                    f"{platform.lower()}_data.xlsx"
                                )
            except Exception as e:
                st.error(f"An error occurred while scraping: {str(e)}")

if __name__ == "__main__":
    main()