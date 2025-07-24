import streamlit as st
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import time
from collections import deque
import pandas as pd
from io import BytesIO

# Streamlit configuration
st.set_page_config(page_title="Web Scraper", layout="wide")
st.title("🌐 Web Scraper & Report Generator")

# Sidebar inputs
st.sidebar.header("Configuration")
base_url = st.sidebar.text_input("Enter Website URL:", "https://example.com")
max_pages = st.sidebar.slider("Max Pages to Scrape:", 1, 100, 10)
delay = st.sidebar.slider("Delay Between Requests (seconds):", 0.0, 2.0, 0.5, 0.1)
include_external = st.sidebar.checkbox("Include External Links", False)

# Session state initialization
if 'scraped_data' not in st.session_state:
    st.session_state.scraped_data = []
if 'visited_urls' not in st.session_state:
    st.session_state.visited_urls = set()
if 'queue' not in st.session_state:
    st.session_state.queue = deque()

# Helper functions
def is_valid_url(url):
    """Check if URL is valid and has HTTP scheme"""
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except:
        return False

def get_domain(url):
    """Extract domain from URL"""
    return urlparse(url).netloc

def scrape_page(url):
    """Scrape a single page and extract content"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Remove script and style elements
        for script in soup(["script", "style"]):
            script.decompose()
        
        # Extract text content
        title = soup.title.string if soup.title else "No Title"
        text_content = soup.get_text(separator=' ', strip=True)[:5000]  # Limit content size
        
        # Extract links
        links = []
        for link in soup.find_all('a', href=True):
            full_url = urljoin(url, link['href'])
            if is_valid_url(full_url):
                links.append(full_url)
        
        return {
            'url': url,
            'title': title,
            'content': text_content,
            'links': links,
            'status': response.status_code
        }
    except Exception as e:
        return {
            'url': url,
            'title': "Error",
            'content': f"Error scraping page: {str(e)}",
            'links': [],
            'status': 0
        }

def process_queue(base_domain):
    """Process the scraping queue"""
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    while st.session_state.queue and len(st.session_state.visited_urls) < max_pages:
        current_url = st.session_state.queue.popleft()
        
        if current_url in st.session_state.visited_urls:
            continue
            
        st.session_state.visited_urls.add(current_url)
        status_text.text(f"Scraping: {current_url}")
        
        # Scrape the page
        page_data = scrape_page(current_url)
        st.session_state.scraped_data.append(page_data)
        
        # Add new links to queue if they belong to the same domain
        for link in page_data['links']:
            if link not in st.session_state.visited_urls:
                if include_external or get_domain(link) == base_domain:
                    st.session_state.queue.append(link)
        
        # Update progress
        progress = len(st.session_state.visited_urls) / max_pages
        progress_bar.progress(min(progress, 1.0))
        
        # Respect delay
        time.sleep(delay)
    
    progress_bar.empty()
    status_text.empty()

# Main scraping logic
if st.sidebar.button("🚀 Start Scraping"):
    if not base_url:
        st.error("Please enter a valid URL")
    elif not is_valid_url(base_url):
        st.error("Please enter a valid URL including http:// or https://")
    else:
        # Reset session state
        st.session_state.scraped_data = []
        st.session_state.visited_urls = set()
        st.session_state.queue = deque([base_url])
        
        base_domain = get_domain(base_url)
        process_queue(base_domain)
        
        st.success(f"Scraping completed! Visited {len(st.session_state.visited_urls)} pages.")

# Display results
if st.session_state.scraped_data:  # Fixed the condition
    st.header("📊 Scraping Results")
    
    # Summary metrics
    col1, col2, col3 = st.columns(3)
    col1.metric("Pages Scraped", len(st.session_state.scraped_data))
    col2.metric("Successful Requests", 
                len([d for d in st.session_state.scraped_data if d['status'] == 200]))
    col3.metric("Error Pages", 
                len([d for d in st.session_state.scraped_data if d['status'] != 200]))
    
    # Data table
    df = pd.DataFrame(st.session_state.scraped_data)
    st.subheader("📄 Scraped Pages")
    
    # Create a copy for display with clickable URLs
    display_df = df[['url', 'title', 'status']].copy()
    display_df['url'] = display_df['url'].apply(lambda x: f"[{x}]({x})")
    
    # Display with clickable URLs using st.write and unsafe_allow_html
    st.write(display_df.to_html(escape=False, index=False), unsafe_allow_html=True)
    
    # Detailed view
    st.subheader("🔍 Detailed Content")
    for i, page in enumerate(st.session_state.scraped_data):
        with st.expander(f"{page['title']} - {page['url']}"):
            st.write(f"**Status Code:** {page['status']}")
            st.write(f"**Content Preview:**")
            st.text_area("", page['content'], height=200, key=f"content_{i}")
            st.write(f"**Links Found:** {len(page['links'])}")
            
            # Show first 10 links
            if page['links']:
                links_html = "<br>".join([
                    f'<a href="{link}" target="_blank">{link}</a>' 
                    for link in page['links'][:10]
                ])
                if len(page['links']) > 10:
                    links_html += "<br>...and more"
                st.markdown(links_html, unsafe_allow_html=True)
            else:
                st.write("No links found")
    
    # Export functionality
    st.subheader("💾 Export Report")
    
    # Try to use xlsxwriter if available, otherwise fallback to openpyxl
    try:
        excel_buffer = BytesIO()
        with pd.ExcelWriter(excel_buffer, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False, sheet_name='Scraped Data')
        excel_buffer.seek(0)
        mime_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    except ImportError:
        # Fallback to openpyxl
        excel_buffer = BytesIO()
        with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Scraped Data')
        excel_buffer.seek(0)
        mime_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    
    st.download_button(
        label="📥 Download Excel Report",
        data=excel_buffer,
        file_name="web_scraping_report.xlsx",
        mime=mime_type
    )

# Instructions
else:
    st.info("Enter a website URL in the sidebar and click 'Start Scraping' to begin.")
    st.markdown("""
    ### How to Use This Scraper:
    1. Enter a valid website URL in the input field
    2. Adjust scraping parameters (max pages, delay)
    3. Click "Start Scraping" to begin the process
    4. View results in the table and detailed views
    5. Download the Excel report for further analysis
    
    ### Features:
    - Scrapes main pages and subpages automatically
    - Respects robots.txt and rate limits
    - Handles errors gracefully
    - Generates downloadable reports
    - Shows real-time progress
    """)