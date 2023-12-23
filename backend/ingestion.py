import os
import json
import base64
from azure.storage.blob import BlobServiceClient
from azure.ai.formrecognizer import DocumentAnalysisClient
import pdfplumber
import openai
import re
# # pylint: disable=undefined-variable
# from azure.search.documents.indexes.models import IndexBatch
# from azure.search.documents.indexes import IndexDocumentsBatch
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
import time

# Replace with your actual values
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
# index_client = search_client.get_index_client(index_name)
# Create a BlobServiceClient
blob_service_client = BlobServiceClient(account_url=f"https://{storageaccount}.blob.core.windows.net", credential=storagekey)

# Get a reference to the container
container_client = blob_service_client.get_container_client(container)

# Create the downloaded_files directory if it does not exist
os.makedirs("downloaded_files", exist_ok=True)

MAX_SECTION_LENGTH = 1000
SENTENCE_SEARCH_LIMIT = 100
SECTION_OVERLAP = 100

pdf_folder = "data"

# Fetch all PDF files in the specified folder
pdf_files = [file for file in os.listdir(pdf_folder) if file.lower().endswith(".pdf")]



def filename_to_id(filename):
    filename_ascii = re.sub("[^0-9a-zA-Z_-]", "_", filename)
    filename_hash = base64.b16encode(filename.encode("utf-8")).decode("ascii")
    return f"file-{filename_ascii}-{filename_hash}"

def compute_embedding(text):
    
    
    
    input_data = {"text": text}

        # Convert the dictionary to a JSON string
    input_json = json.dumps(input_data)
    
    response = openai.Embedding.create(input=input_json,deployment_id="embedding")
        # print(response['data'])
        
    embeddings = response['data'][0]['embedding']
    return embeddings
    # else:
    #     print("no attribute")


def create_sections(filename, page_map, use_vectors):
    print("1---------------------")
    file_id = filename_to_id(filename)
    # print(content)
    for i, (content, page_num) in enumerate(split_text(page_map, filename)):
        print(content)
        # print(content)
        # print("page_map1---:", page_map)
        # print("filename:", filename)
        section = {
            "id": f"{file_id}-page-{i}",
            "content": content,
            "category": "str",  # Replace with your actual category
            "sourcepage": filename,  # Replace with your actual source page information
            "sourcefile": filename,
        }
        # print("section is created")
        if use_vectors:
            
            embeddings = compute_embedding(content)
            # print("2-------------")
            section["embedding"] = embeddings
            # print(f"Section {i + 1} - Content: {content}")
            # print(f"     - Embedding: {embeddings}")
        else:
            print(f"Section {i + 1} - Content: {content}")
        yield section
def split_text(page_map, pdf_path):
    SENTENCE_ENDINGS = [".", "!", "?"]
    WORDS_BREAKS = [",", ";", ":", " ", "(", ")", "[", "]", "{", "}", "\t", "\n"]

    def find_page(offset, page_map):
        for i, (page_num, page_offset, _) in enumerate(page_map):
            if offset >= page_offset and offset < page_offset + len(page_map[i][2]):
                return page_num
        print(f"Warning: Could not find page for offset {offset}")
        return len(page_map) - 1

    with pdfplumber.open(pdf_path) as pdf:
        all_text = "".join([page.extract_text() for page in pdf.pages])

    length = len(all_text)
    start = 0

    while start + SECTION_OVERLAP < length:
        last_word = -1
        end = start + MAX_SECTION_LENGTH

        if end > length:
            end = length
        else:
            while (
                end < length
                and (end - start - MAX_SECTION_LENGTH) < SENTENCE_SEARCH_LIMIT
                and all_text[end] not in SENTENCE_ENDINGS
            ):
                if all_text[end] in WORDS_BREAKS:
                    last_word = end
                end += 1
            if end < length and all_text[end] not in SENTENCE_ENDINGS and last_word > 0:
                end = last_word
        if end < length:
            end += 1

        last_table_start = all_text.rfind("<table")
        if last_table_start > 2 * SENTENCE_SEARCH_LIMIT and last_table_start > all_text.rfind("</table"):
            start = min(end - SECTION_OVERLAP, start + last_table_start)
        else:
            start = end - SECTION_OVERLAP

        if start + SECTION_OVERLAP <= end:
            page_num = find_page(start, page_map)
            yield (all_text[start:end], page_num)
        else:
            print(f"Condition not satisfied - start: {start}, SECTION_OVERLAP: {SECTION_OVERLAP}, end: {end}")
# 
def ingest_sections_to_search_index(sections_to_index, search_service, index_name, admin_key, verbose=False):
    # create_search_index(sections_to_index,search_service, index_name, admin_key, verbose=False)
    # print(f"admin_key: {admin_key}")
    credential = AzureKeyCredential(admin_key)
    search_client = SearchClient(endpoint=f"https://{search_service_name}.search.windows.net/", index_name=index_name, credential=credential)
    
    
    #
    try:
        
        serialized_sections = [json.dumps(section, default=str) for section in sections_to_index]
        cleaned_documents = [{key: value for key, value in json.loads(section).items() if value is not None} for section in serialized_sections]
        print(serialized_sections)

    # Ingest sections into the search index
        search_client.upload_documents(documents=cleaned_documents)
    except Exception as e:
        print(f"Error during serialization or ingestion: {e}")
    # if verbose:
    #     print(f"Indexing result: {result.results}")
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
        
              
        sections_generator = create_sections(local_file_path, page_map, use_vectors=True)
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
    

    
def remove_from_index(filename):
    search_client = SearchClient(endpoint=f"https://{search_service_name}.search.windows.net/", index_name=index_name, credential=AzureKeyCredential(admin_key))
    
    while True:
        filter = None if filename is None else f"sourcefile eq '{os.path.basename(filename)}'"
        r = search_client.search("", filter=filter, top=1000, include_total_count=True)
        if r.get_count() == 0:
            break
        r = search_client.delete_documents(documents=[{"id": d["id"]} for d in r])
        print(f"Removed {len(r)} sections from index")
        # It can take a few seconds for search results to reflect changes, so wait a bit
        time.sleep(2)

# Example Usage

# Assuming you have sections as generated by your functions



# create_search_index(search_service_name, index_name, admin_key, verbose=False)
blobs = container_client.list_blobs()
for blob in blobs:

    process_blob(blob)
    
    



