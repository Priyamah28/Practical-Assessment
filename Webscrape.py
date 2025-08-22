import requests
from bs4 import BeautifulSoup
import psycopg2
import os
import logging
from dotenv import load_dotenv

# --- CONFIGURATION & SETUP ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

load_dotenv()
DB_NAME = os.getenv('DB_NAME')
DB_USER = os.getenv('DB_USER')
DB_PASSWORD = os.getenv('DB_PASSWORD')
DB_HOST = os.getenv('DB_HOST', 'localhost')
DB_PORT = os.getenv('DB_PORT', '5432')

# --- DATABASE FUNCTIONS ---
def get_db_connection():
    try:
        conn = psycopg2.connect(
            dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD, host=DB_HOST, port=DB_PORT
        )
        logger.info("Database connection successful.")
        return conn
    except Exception as e:
        logger.error(f"Error connecting to database: {e}")
        return None

def setup_database(conn):
    try:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS job_listings (
                    id SERIAL PRIMARY KEY,
                    job_title VARCHAR(255),
                    company_name VARCHAR(255),
                    location VARCHAR(255),
                    job_url VARCHAR(512) UNIQUE,
                    salary_info TEXT,
                    job_description TEXT,
                    source_site VARCHAR(100),
                    scraped_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
                );
            """)
        conn.commit()
        logger.info("Table 'job_listings' created or already exists.")
    except Exception as e:
        logger.error(f"Error setting up database: {e}")

def insert_jobs(conn, jobs):
    if not jobs:
        logger.info("No jobs to insert.")
        return
    try:
        with conn.cursor() as cur:
            for job in jobs:
                cur.execute("""
                    INSERT INTO job_listings (job_title, company_name, location, job_url, salary_info, source_site)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (job_url) DO NOTHING;
                """, (job['job_title'], job['company_name'], job['location'], job['job_url'], job['salary_info'], job['source_site']))
        conn.commit()
        logger.info(f"Successfully inserted {len(jobs)} jobs.")
    except Exception as e:
        logger.error(f"Error inserting jobs: {e}")

def update_job_description(conn, job_url, job_description):
    try:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE job_listings SET job_description = %s WHERE job_url = %s;
            """, (job_description, job_url))
        conn.commit()
        logger.info(f"Updated description for {job_url}.")
    except Exception as e:
        logger.error(f"Error updating description for {job_url}: {e}")

def get_jobs_without_description(conn):
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT job_url FROM job_listings WHERE job_description IS NULL;")
            return [row[0] for row in cur.fetchall()]
    except Exception as e:
        logger.error(f"Error fetching URLs for detail scraping: {e}")
        return []

# --- SCRAPING FUNCTION FOR HACKER NEWS ---
def scrape_hacker_news():
    jobs_data = []
    url = 'https://news.ycombinator.com/jobs'
    
    try:
        response = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'})
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Selectors for Hacker News
        job_rows = soup.find_all('tr', {'class': 'athing'})
        
        if not job_rows:
            logger.warning("No jobs found with the specified selector.")
            return []
            
        for row in job_rows:
            title_elem = row.find('span', class_='titleline')
            if title_elem:
                title_link = title_elem.find('a')
                job_title = title_link.text.strip() if title_link else 'N/A'
                job_url = title_link['href'] if title_link and 'href' in title_link.attrs else 'N/A'
                
                # Hacker News job postings are simple, so we'll fill in placeholders
                jobs_data.append({
                    'job_title': job_title, 
                    'company_name': 'N/A', 
                    'location': 'N/A',
                    'job_url': job_url, 
                    'salary_info': 'N/A', 
                    'source_site': 'Hacker News'
                })
            
        return jobs_data
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Error scraping static site: {e}")
        return []

# --- MAIN SCRIPT EXECUTION ---
if __name__ == "__main__":
    conn = get_db_connection()
    if conn:
        setup_database(conn)
        
        jobs = scrape_hacker_news()
        insert_jobs(conn, jobs)
        
        conn.close()
    else:
        logger.error("Script terminated due to a database connection error.")