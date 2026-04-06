import os
import psycopg2
import json
from bs4 import BeautifulSoup
import requests
from duckduckgo_search import DDGS
from openai import OpenAI
from dotenv import load_dotenv
import time
import argparse

load_dotenv()

LM_STUDIO_BASE_URL = os.getenv("LM_STUDIO_BASE_URL", "http://localhost:1234/v1")
LM_STUDIO_API_KEY = os.getenv("LM_STUDIO_API_KEY", "lm-studio")
CHAT_MODEL_NAME = os.getenv("CHAT_MODEL_NAME", "local-model")

DB_NAME = os.getenv("POSTGRES_DB", "auto_marketer")
DB_USER = os.getenv("POSTGRES_USER", "user")
DB_PASSWORD = os.getenv("POSTGRES_PASSWORD", "password")
DB_HOST = os.getenv("POSTGRES_HOST", "localhost")
DB_PORT = os.getenv("POSTGRES_PORT", "5432")

# Initialize clients
openai_client = OpenAI(base_url=LM_STUDIO_BASE_URL, api_key=LM_STUDIO_API_KEY)
ddgs = DDGS()

def setup_postgres():
    conn = psycopg2.connect(
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
        host=DB_HOST,
        port=DB_PORT
    )
    cur = conn.cursor()
    cur.execute("""
        ALTER TABLE linkedin_profiles 
        ADD COLUMN IF NOT EXISTS research_status VARCHAR DEFAULT 'pending',
        ADD COLUMN IF NOT EXISTS is_smb BOOLEAN,
        ADD COLUMN IF NOT EXISTS needs_outsourcing_prob DECIMAL,
        ADD COLUMN IF NOT EXISTS needs_cheap_labor_prob DECIMAL,
        ADD COLUMN IF NOT EXISTS searching_vendors_prob DECIMAL,
        ADD COLUMN IF NOT EXISTS research_summary TEXT,
        ADD COLUMN IF NOT EXISTS system_confidence_score INT,
        ADD COLUMN IF NOT EXISTS confidence_rationale TEXT,
        ADD COLUMN IF NOT EXISTS search_queries_used TEXT,
        ADD COLUMN IF NOT EXISTS user_grade INT,
        ADD COLUMN IF NOT EXISTS user_feedback TEXT
    """)
    conn.commit()
    return conn

def search_web(query, max_results=3):
    print(f"    [DuckDuckGo] Searching for: '{query}'")
    results = []
    try:
        ddg_results = ddgs.text(query, max_results=max_results)
        for r in ddg_results:
            results.append({"title": r.get("title"), "url": r.get("href"), "snippet": r.get("body")})
        time.sleep(2) # Be nice to DDG
    except Exception as e:
        print(f"    [DuckDuckGo] Error: {e}")
    return results

def scrape_url(url, timeout=5):
    print(f"    [Scrape] Fetching text from: {url}")
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        response = requests.get(url, headers=headers, timeout=timeout)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'lxml')
        
        for script in soup(["script", "style"]):
            script.extract()
            
        text = soup.get_text(separator=' ', strip=True)
        return text[:1500]
    except Exception as e:
        print(f"    [Scrape] Failed to fetch {url}: {e}")
        return ""

def analyze_profile_with_react(profile_summary):
    print("  [Analyze] Starting ReAct loop for research...")
    
    system_prompt = """
    You are an expert OSINT and business research agent. 
    You are researching a LinkedIn profile to determine if they are a target for our B2B marketing.
    
    If you need to search the web for their company or background, reply with a JSON object like this:
    {
        "action": "search",
        "query": "Company Name location"
    }
    
    If you have enough information to make a final assessment, reply with this exact JSON structure:
    {
        "action": "final",
        "is_smb": boolean,
        "needs_outsourcing_prob": float,
        "needs_cheap_labor_prob": float,
        "searching_vendors_prob": float,
        "research_summary": "string",
        "system_confidence_score": integer,
        "confidence_rationale": "string"
    }
    
    CRITICAL: You MUST output valid JSON only. Do not wrap it in markdown. Do not include extra text.
    """
    
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Please research this profile:\n{json.dumps(profile_summary, indent=2)}"}
    ]
    
    queries_used = []
    
    for iteration in range(4): # Max 3 searches + 1 final
        print(f"  [Analyze] LLM Reasoning Turn {iteration + 1}...")
        try:
            response = openai_client.chat.completions.create(
                model=CHAT_MODEL_NAME,
                messages=messages,
                temperature=0.1
            )
            
            content = response.choices[0].message.content
            parsed = json.loads(content)
            
            if parsed.get("action") == "search":
                query = parsed.get("query", "")
                print(f"  [Agent Action] Decided to search for: '{query}'")
                queries_used.append(query)
                
                results = search_web(query)
                context = ""
                for i, res in enumerate(results):
                    context += f"\nResult {i+1}: {res['title']} - {res['snippet']} (URL: {res['url']})"
                    if i == 0 and res['url']:
                        page_text = scrape_url(res['url'])
                        context += f"\nScraped Content from {res['url']}: {page_text}"
                
                if not context:
                    context = "No results found. Try a different query or finalize with the data you have."
                    
                messages.append({"role": "assistant", "content": content})
                messages.append({"role": "user", "content": f"Search Results:\n{context}\n\nWhat is your next action? (Respond in JSON)"})
                
            elif parsed.get("action") == "final" or "is_smb" in parsed:
                print(f"  [Agent Action] Final analysis complete.")
                if "is_smb" in parsed:
                    # Fix LLM hallucinating percentages (e.g. 75 instead of 7)
                    conf = parsed.get("system_confidence_score")
                    if isinstance(conf, (int, float)):
                        if conf > 10:
                            parsed["system_confidence_score"] = max(1, min(10, int(round(conf / 10.0))))
                            print(f"  [Analyze] Clamped confidence score from {conf} to {parsed['system_confidence_score']}")
                        elif conf < 1:
                            parsed["system_confidence_score"] = 1
                            print(f"  [Analyze] Clamped confidence score from {conf} to 1")
                    
                    return parsed, queries_used
                else:
                    print("  [Analyze] Final JSON missing required keys.")
                    return None, queries_used
            else:
                print(f"  [Analyze] Unknown action from LLM: {parsed}")
                break
                
        except json.JSONDecodeError:
            print("  [Analyze] LLM did not return valid JSON.")
            break
        except Exception as e:
            print(f"  [Analyze] Error during ReAct loop: {e}")
            break
            
    print("  [Analyze] ReAct loop exhausted without valid final JSON.")
    return None, queries_used

def process_pending_profiles():
    conn = setup_postgres()
    cur = conn.cursor()
    
    cur.execute("SELECT id, first_name, last_name, headline, raw_data FROM linkedin_profiles WHERE research_status = 'pending' LIMIT 5")
    profiles = cur.fetchall()
    
    if not profiles:
        print("No pending profiles found to research.")
        return

    print(f"Found {len(profiles)} profiles to research.")
    
    for row in profiles:
        prof_id, first_name, last_name, headline, raw_data = row
        print(f"\\n--- Researching: {first_name} {last_name} ---")
        
        cur.execute("UPDATE linkedin_profiles SET research_status = 'researching' WHERE id = %s", (prof_id,))
        conn.commit()
        
        profile_summary = {
            "name": f"{first_name} {last_name}",
            "headline": headline,
            "about": raw_data.get("about", "") if isinstance(raw_data, dict) else ""
        }
        
        if isinstance(raw_data, dict) and raw_data.get('currentPosition'):
            company = raw_data['currentPosition'][0].get('companyName')
            if company:
                profile_summary["company_name"] = company
        
        analysis, queries_used = analyze_profile_with_react(profile_summary)
        
        if analysis:
            print(f"  [Result] Success. Confidence: {analysis.get('system_confidence_score')}/10")
            queries_str = " | ".join(queries_used) if queries_used else "None"
            
            cur.execute("""
                UPDATE linkedin_profiles 
                SET research_status = 'completed',
                    is_smb = %s,
                    needs_outsourcing_prob = %s,
                    needs_cheap_labor_prob = %s,
                    searching_vendors_prob = %s,
                    research_summary = %s,
                    system_confidence_score = %s,
                    confidence_rationale = %s,
                    search_queries_used = %s
                WHERE id = %s
            """, (
                analysis.get('is_smb'),
                analysis.get('needs_outsourcing_prob'),
                analysis.get('needs_cheap_labor_prob'),
                analysis.get('searching_vendors_prob'),
                analysis.get('research_summary'),
                analysis.get('system_confidence_score'),
                analysis.get('confidence_rationale'),
                queries_str,
                prof_id
            ))
            conn.commit()
        else:
            print("  [Result] Failed to get valid analysis.")
            cur.execute("UPDATE linkedin_profiles SET research_status = 'failed' WHERE id = %s", (prof_id,))
            conn.commit()

def interactive_grading():
    conn = setup_postgres()
    cur = conn.cursor()
    
    cur.execute("""
        SELECT id, first_name, last_name, is_smb, needs_outsourcing_prob, 
               research_summary, system_confidence_score, confidence_rationale, search_queries_used
        FROM linkedin_profiles 
        WHERE research_status = 'completed' AND user_grade IS NULL 
        LIMIT 1
    """)
    profile = cur.fetchone()
    
    if not profile:
        print("No ungraded profiles available.")
        return
        
    prof_id, first_name, last_name, is_smb, out_prob, summary, conf, conf_rationale, query_used = profile
    
    print("\\n==================================================")
    print(f" PROFILE: {first_name} {last_name}")
    print("==================================================")
    print(f"Search Queries Used: {query_used}")
    print(f"Is SMB Owner:      {'Yes' if is_smb else 'No'}")
    print(f"Outsourcing Prob:  {out_prob}")
    print(f"Research Summary:  {summary}")
    print("--------------------------------------------------")
    print(f"System Confidence: {conf}/10")
    print(f"Confidence Rationale:")
    print(f"{conf_rationale}")
    print("--------------------------------------------------")
    
    while True:
        try:
            grade = int(input("Grade this research (1-5, where 5 is perfectly accurate): "))
            if 1 <= grade <= 5:
                break
            print("Please enter a number between 1 and 5.")
        except ValueError:
            print("Invalid input. Please enter a number.")
            
    feedback = input("Any specific feedback or corrections? (Press Enter to skip): ")
    
    cur.execute("""
        UPDATE linkedin_profiles 
        SET user_grade = %s, user_feedback = %s 
        WHERE id = %s
    """, (grade, feedback, prof_id))
    conn.commit()
    print("Grade saved. Thank you!")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Auto Marketer Research Agent")
    parser.add_argument('--run', action='store_true', help='Run the research agent on pending profiles')
    parser.add_argument('--grade', action='store_true', help='Start the interactive grading CLI')
    args = parser.parse_args()

    if args.grade:
        interactive_grading()
    elif args.run:
        process_pending_profiles()
    else:
        print("Please specify an action: --run or --grade")
        parser.print_help()
