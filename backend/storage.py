import os
from pdf2image import convert_from_path
from azure.storage.blob import BlobServiceClient, BlobClient, ContainerClient
from azure.storage.blob import BlobServiceClient
from azure.core.exceptions import ResourceNotFoundError
from PyPDF2 import PdfReader, PdfWriter

account_name = "stcdzj2obpa54em"
account_key = "hemujwsQOW8eHoFE1qdrV78KyJ+24PSNj/yrJcGaxDqNRlU+291nfBMpYYpaprFBg7BZ+Ppvr1oo+ASti73PCg=="
container_name = "esstgtesting"
local_folder_path = "data"


# Create a BlobServiceClient
blob_service_client = BlobServiceClient(account_url=f"https://{account_name}.blob.core.windows.net", credential=account_key)

# Create a container
container_client = blob_service_client.get_container_client(container_name)


if not container_client.exists():
    # Create a container if it doesn't exist
    container_client.create_container()
else:
    print(f"The container '{container_name}' already exists.")




def delete_unused_blobs(local_folder_path):
    # List all blobs in the container
    blobs = container_client.list_blobs()

    # Get the list of PDF files in the local folder
    local_files = {os.path.splitext(file.lower())[0] for file in os.listdir(local_folder_path) if file.lower().endswith(".pdf")}

    # Check each blob in the container
    for blob in blobs:
        blob_name = os.path.splitext(blob.name.lower())[0]

        # If the corresponding local file doesn't exist, delete the blob
        if blob_name not in local_files:
            blob_client = container_client.get_blob_client(blob.name)

            # Check if the blob exists before attempting to delete it
            try:
                blob_client.delete_blob()
                # print(f"Blob '{blob.name}' deleted from Azure Storage.")
            except ResourceNotFoundError:
                print(f"Blob '{blob.name}' does not exist in Azure Storage.")
def upload_pdf_pages(pdf_path, blob_prefix):
    # Open the original PDF file
    with open(pdf_path, "rb") as original_pdf:
        pdf_reader = PdfReader(original_pdf)

        # Upload each page as a separate PDF
        for page_number in range(len(pdf_reader.pages)):
            pdf_writer = PdfWriter()
            pdf_writer.add_page(pdf_reader.pages[page_number])

            # Create a temporary PDF file for the current page
            temp_pdf_path = os.path.join(os.path.dirname(pdf_path), f"temp_page_{page_number + 1}.pdf")
            with open(temp_pdf_path, "wb") as temp_pdf:
                pdf_writer.write(temp_pdf)

            # Upload the temporary PDF file to Azure Storage
            blob_name = f"{blob_prefix}_page_{page_number + 1}.pdf"
            blob_client = container_client.get_blob_client(blob_name)

            # Check if the blob exists
            if blob_client.exists():
                # If it exists, delete the existing blob before uploading the new one
                blob_client.delete_blob()

            with open(temp_pdf_path, "rb") as data:
                blob_client.upload_blob(data, overwrite=True)  # Set overwrite to True

            # Clean up: Delete the temporary PDF file
            os.remove(temp_pdf_path)

    print(f"Pages of '{pdf_path}' uploaded to Azure Storage.")

# Delete unused blobs before uploading
delete_unused_blobs(local_folder_path)

# Upload PDFs from the local folder to Azure Storage, page by page
for root, dirs, files in os.walk(local_folder_path):
    for file in files:
        if file.lower().endswith(".pdf"):
            local_file_path = os.path.join(root, file)
            blob_prefix = os.path.splitext(file)[0]
            upload_pdf_pages(local_file_path, blob_prefix)