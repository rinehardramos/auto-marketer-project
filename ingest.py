import os
import requests
import json
import psycopg2
import uuid
from qdrant_client import QdrantClient
from qdrant_client.models import VectorParams, Distance, PointStruct
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

APIFY_URL = os.getenv("APIFY_DATASET_URL")
LM_STUDIO_BASE_URL = os.getenv("LM_STUDIO_BASE_URL")
LM_STUDIO_API_KEY = os.getenv("LM_STUDIO_API_KEY")
EMBEDDING_MODEL_NAME = os.getenv("EMBEDDING_MODEL_NAME")

DB_NAME = os.getenv("POSTGRES_DB")
DB_USER = os.getenv("POSTGRES_USER")
DB_PASSWORD = os.getenv("POSTGRES_PASSWORD")
DB_HOST = os.getenv("POSTGRES_HOST")
DB_PORT = os.getenv("POSTGRES_PORT")

QDRANT_HOST = os.getenv("QDRANT_HOST")
QDRANT_PORT = int(os.getenv("QDRANT_PORT"))

# Initialize clients
openai_client = OpenAI(base_url=LM_STUDIO_BASE_URL, api_key=LM_STUDIO_API_KEY)
qdrant = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)

# Postgres setup
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
        CREATE TABLE IF NOT EXISTS linkedin_profiles (
            id VARCHAR PRIMARY KEY,
            first_name VARCHAR,
            last_name VARCHAR,
            headline TEXT,
            about TEXT,
            raw_data JSONB
        )
    """)
    conn.commit()
    return conn

# Qdrant setup
def setup_qdrant():
    collection_name = "linkedin_profiles"
    if not qdrant.collection_exists(collection_name=collection_name):
        qdrant.create_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(size=768, distance=Distance.COSINE),
        )
    return collection_name

def get_embedding(text):
    if not text:
        return [0.0] * 768
    response = openai_client.embeddings.create(
        input=[text],
        model=EMBEDDING_MODEL_NAME
    )
    return response.data[0].embedding

def ingest_data():
    conn = setup_postgres()
    cur = conn.cursor()
    collection_name = setup_qdrant()

    print("Fetching data from Apify...")
    response = requests.get(APIFY_URL)
    response.raise_for_status()
    data = response.json()
    
    print(f"Fetched {len(data)} profiles. Ingesting...")

    for i, profile in enumerate(data):
        profile_id = profile.get("id")
        if not profile_id:
            continue
            
        first_name = profile.get("firstName", "")
        last_name = profile.get("lastName", "")
        headline = profile.get("headline", "")
        about = profile.get("about", "")
        
        # Combine text for embedding
        text_to_embed = f"{first_name} {last_name}\\nHeadline: {headline}\\nAbout: {about}"
        
        try:
            print(f"Processing {i+1}/{len(data)}: {first_name} {last_name}")
            
            # Save to Postgres
            cur.execute("""
                INSERT INTO linkedin_profiles (id, first_name, last_name, headline, about, raw_data)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (id) DO NOTHING
            """, (profile_id, first_name, last_name, headline, about, json.dumps(profile)))
            
            # Generate Embedding
            embedding = get_embedding(text_to_embed)
            
            # Save to Qdrant
            qdrant_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, profile_id))
            qdrant.upsert(
                collection_name=collection_name,
                points=[
                    PointStruct(
                        id=qdrant_id,
                        vector=embedding,
                        payload={
                            "apify_id": profile_id,
                            "first_name": first_name,
                            "last_name": last_name,
                            "headline": headline
                        }
                    )
                ]
            )
            
        except Exception as e:
            print(f"Error processing profile {profile_id}: {e}")

    conn.commit()
    cur.close()
    conn.close()
    print("Ingestion complete.")

if __name__ == "__main__":
    ingest_data()
