import os
import json
import base64
from azure.storage.blob import BlobServiceClient
from azure.ai.formrecognizer import DocumentAnalysisClient
import pdfplumber
import openai
import re
import fitz 
import time
from azure.search.documents.indexes import SearchIndexClient

from azure.search.documents.indexes.models import (
    HnswParameters,
    HnswVectorSearchAlgorithmConfiguration,
    PrioritizedFields,
    SearchableField,
    SearchField,
    SearchFieldDataType,
    SearchIndex,
    SemanticConfiguration,
    SemanticField,
    SemanticSettings,
    SimpleField,
    VectorSearch,
    VectorSearchAlgorithmKind,
    VectorSearchProfile,
)
from azure.search.documents.indexes.models import  SearchIndex, SimpleField, SearchableField, SearchField, SearchFieldDataType, SemanticSettings, SemanticConfiguration, PrioritizedFields, SemanticField, VectorSearch, HnswVectorSearchAlgorithmConfiguration, VectorSearchAlgorithmKind, HnswParameters, VectorSearchProfile
from azure.search.documents import SearchClient
from azure.core.credentials import AzureKeyCredential
from azure.core.exceptions import ResourceNotFoundError

search_service_name = "gptkb-cdzj2obpa54em"
index_name = "escogidxtest"
admin_key = "VmM0fMtVNqbwZKbomZrZgRKnadwl12Qc3KXxMsXIzIAzSeBAgDyI"


# Load environment variables
storageaccount = "stcdzj2obpa54em"
storagekey = "hemujwsQOW8eHoFE1qdrV78KyJ+24PSNj/yrJcGaxDqNRlU+291nfBMpYYpaprFBg7BZ+Ppvr1oo+ASti73PCg=="
container = "esstgtesting"
formrecognizerservice = "cog-fr-cdzj2obpa54em"
formrecognizerkey = "6c6bbb6fadf14c73b6feee4f8b1b0f1a"
AZURE_OPENAI_MODEL = "text-embedding-ada-002"
deployment_model = "text-embedding-ada-002"  # Replace with your actual Azure OpenAI model name

# Set your OpenAI API key
openai.api_key = "825a0d3880054857a94fd70649196ad3"
openai.api_base = "https://cog-cdzj2obpa54em.openai.azure.com/" # your endpoint should look like the following https://YOUR_RESOURCE_NAME.openai.azure.com/
openai.api_type = 'azure'
openai.api_version = '2023-05-15'

search_client = SearchClient(
        endpoint=f"https://{search_service_name}.search.windows.net",
        index_name=index_name,
        credential=admin_key,
    )
index_client = SearchIndexClient(endpoint=f"https://{search_service_name}.search.windows.net/", credential=admin_key)

# Create a BlobServiceClient
blob_service_client = BlobServiceClient(account_url=f"https://{storageaccount}.blob.core.windows.net", credential=storagekey)

# Get a reference to the container
container_client = blob_service_client.get_container_client(container)

# Create the downloaded_files directory if it does not exist
os.makedirs("downloaded_files", exist_ok=True)

MAX_SECTION_LENGTH = 1000
SENTENCE_SEARCH_LIMIT = 100
SECTION_OVERLAP = 100
open_ai_token_cache = {}
CACHE_KEY_TOKEN_CRED = "openai_token_cred"
CACHE_KEY_CREATED_TIME = "created_time"
CACHE_KEY_TOKEN_TYPE = "token_type"

pdf_folder = "data"

# Fetch all PDF files in the specified folder
pdf_files = [file for file in os.listdir(pdf_folder) if file.lower().endswith(".pdf")]



def filename_to_id(filename):
    filename_ascii = re.sub("[^0-9a-zA-Z_-]", "_", filename)
    filename_hash = base64.b16encode(filename.encode("utf-8")).decode("ascii")
    return f"file-{filename_ascii}-{filename_hash}"

def compute_embedding(text):
    refresh_openai_token()
    
    
    
    input_data = {"text": text}

        # Convert the dictionary to a JSON string
    input_json = json.dumps(input_data)
    
    response = openai.Embedding.create(input=input_json,deployment_id="embedding")
        # print(response['data'])
        
    embeddings = response['data'][0]['embedding']
    return embeddings
    
def split_text(page):
    SENTENCE_ENDINGS = [".", "!", "?"]
    WORDS_BREAKS = [",", ";", ":", " ", "(", ")", "[", "]", "{", "}", "\t", "\n"]

    text = page.extract_text()
    # print("Extracted Text:")
    # print(text)

    current_section = ""

    for char in text:
        current_section += char
        
        if any(current_section.endswith(se) for se in SENTENCE_ENDINGS):
            # Check if the current section is not just whitespace
            if current_section.strip():
                yield current_section.strip()
                # print(current_section)
            current_section = ""

    # Check for word breaks
    if any(char in WORDS_BREAKS for char in current_section):
        # Check if the current section is not just whitespace
        if current_section.strip():
            yield current_section.strip()


   
def create_sections(pdf_path, use_vectors):
    print("1---------------------")
    file_id = filename_to_id(pdf_path)
    
    with pdfplumber.open(pdf_path) as pdf:
        for page_num, page in enumerate(pdf.pages):
            for i, section_text in enumerate(split_text(page)):
                print("The section number is{}" .format(i),section_text)
                section = {
                    "id": f"{file_id}-page-{page_num + 1}-section-{i + 1}",  # Add +1 to page_num and i
                    "content": section_text,
                    "category": "str",  # Replace with your actual category
                    "sourcepage": pdf_path,  # Use page_num + 1 to start from page 1
                    "sourcefile": pdf_path,
                }
                if use_vectors:
                    embeddings = compute_embedding(section_text)
                    section["embedding"] = embeddings
                    time.sleep(0.5)
                    # print(f"Section {i + 1} - Content: {section_text}")
                    # print(f"     - Embedding: {embeddings}")
                else:
                    print(f"Section {i + 1} - Content: {section_text}")
                yield section
def ingest_sections_to_search_index(sections_to_index, search_service, index_name, admin_key, verbose=False):
    # create_search_index(sections_to_index,search_service, index_name, admin_key, verbose=False)
    # print(f"admin_key: {admin_key}")
    credential = AzureKeyCredential(admin_key)
    search_client = SearchClient(endpoint=f"https://{search_service_name}.search.windows.net/", index_name=index_name, credential=credential)
    
    
    #
    try:
        
        serialized_sections = [json.dumps(section, default=str) for section in sections_to_index]
        cleaned_documents = [{key: value for key, value in json.loads(section).items() if value is not None} for section in serialized_sections]
        print("Ingested section" ,serialized_sections)

    # Ingest sections into the search index
        search_client.upload_documents(documents=cleaned_documents)
    except Exception as e:
        print(f"Error during serialization or ingestion: {e}")

def process_blob(blob):
    blob_name = blob.name
    print(f"Processing blob: {blob_name}")

    # Download blob content to a local file
    local_file_path = f"downloaded_files/{blob_name}"
    with open(local_file_path, "wb") as local_file:
        blob_data = blob_service_client.get_blob_client(container=container, blob=blob_name).download_blob()
        blob_data.readinto(local_file)
    print(f"Local file path: {local_file_path}")

    # Check if the file exists
    if os.path.exists(local_file_path):
        
        create_search_index(search_service_name, index_name, admin_key, verbose=True)
        with pdfplumber.open(local_file_path) as pdf:
            page_map = []
            for page_num, page in enumerate(pdf.pages):
                page_text = page.extract_text()
                page_map.append((page_num, len(page_text), page_text))
                # print(page_map)
            pdf.close()
        
              
        sections_generator = create_sections(local_file_path,  use_vectors=True)
        sections_to_index = list(sections_generator)
        ingest_sections_to_search_index(sections_to_index, search_service_name, index_name, admin_key, verbose=True)
      
        
    else:
        print(f"File not found: {local_file_path}")

        # process_pdf(local_file_path, page_map)
    os.remove(local_file_path)
def create_search_index(search_service, index_name, search_creds, verbose=True):
    if verbose:
        print(f"Ensuring search index {index_name} exists")
    # index_client = SearchClient(endpoint=f"https://{search_service_name}.search.windows.net/", index_name=index_name, credential=AzureKeyCredential(admin_key))
    credential = AzureKeyCredential(search_creds)
   
    index_client = SearchIndexClient(endpoint=f"https://{search_service}.search.windows.net/", credential=credential)
    
    fields = [
        SimpleField(name="id", type="Edm.String", key=True),
        SearchableField(name="content", type="Edm.String", analyzer_name="en.microsoft"),
        SearchField(
                    name="embedding",
                    type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
                    hidden=False,
                    searchable=True,
                    filterable=False,
                    sortable=False,
                    facetable=False,
                    vector_search_dimensions=1536,
                    vector_search_profile="embedding_config",
                ),
        SimpleField(name="category", type="Edm.String", filterable=True, facetable=True),
        SimpleField(name="sourcepage", type="Edm.String", filterable=True, facetable=True),
        SimpleField(name="sourcefile", type="Edm.String", filterable=True, facetable=True),
    ]
    index = SearchIndex(
                name=index_name,
                fields=fields,
                semantic_settings=SemanticSettings(
                    configurations=[
                        SemanticConfiguration(
                            name="default",
                            prioritized_fields=PrioritizedFields(
                                title_field=None, prioritized_content_fields=[SemanticField(field_name="content")]
                            ),
                        )
                    ]
                ),
                vector_search=VectorSearch(
                    algorithms=[
                        HnswVectorSearchAlgorithmConfiguration(
                            name="hnsw_config",
                            kind=VectorSearchAlgorithmKind.HNSW,
                            parameters=HnswParameters(metric="cosine"),
                        )
                    ],
                    profiles=[
                        VectorSearchProfile(
                            name="embedding_config",
                            algorithm="hnsw_config",
                        ),
                    ],
                ),
            )

    # index = SearchIndex(name=index_name, fields=fields, cors_options=CorsOptions(allowed_origins=["*"]))

    # Check if the index already exists
    if index_name not in [index.name for index in index_client.list_indexes()]:
        index = SearchIndex(
            name=index_name,
            fields=fields,
            semantic_settings=SemanticSettings(
                configurations=[
                    SemanticConfiguration(
                        name="default",
                        prioritized_fields=PrioritizedFields(
                            title_field=None, prioritized_content_fields=[SemanticField(field_name="content")]
                        ),
                    )
                ]
            ),
            # Add other index configurations as needed
             vector_search=VectorSearch(
                    algorithms=[
                        HnswVectorSearchAlgorithmConfiguration(
                            name="hnsw_config",
                            kind=VectorSearchAlgorithmKind.HNSW,
                            parameters=HnswParameters(metric="cosine"),
                        )
                    ],
                    profiles=[
                        VectorSearchProfile(
                            name="embedding_config",
                            algorithm="hnsw_config",
                        ),
                    ],
                ),
            )

        

        if verbose:
            print(f"Creating {index_name} search index")
        
        index_client.create_index(index)
    else:
        if verbose:
            print(f"Search index {index_name} already exists")
    


        
def refresh_openai_token():
    """
    Refresh OpenAI token every 5 minutes
    """
    if (
        CACHE_KEY_TOKEN_TYPE in open_ai_token_cache
        and open_ai_token_cache[CACHE_KEY_TOKEN_TYPE] == "azure_ad"
        and open_ai_token_cache[CACHE_KEY_CREATED_TIME] + 300 < time.time()
    ):
        token_cred = open_ai_token_cache[CACHE_KEY_TOKEN_CRED]
        openai.api_key = token_cred.get_token("https://cognitiveservices.azure.com/.default").token
        open_ai_token_cache[CACHE_KEY_CREATED_TIME] = time.time()



blobs = container_client.list_blobs()
for blob in blobs:
    process_blob(blob)
    
    



