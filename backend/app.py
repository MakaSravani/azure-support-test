# import openai, os, requests

# openai.api_type = "azure"
# # Azure OpenAI on your own data is only supported by the 2023-08-01-preview API version
# openai.api_version = "2023-08-01-preview"

# # Azure OpenAI setup
# openai.api_base = "https://cog-cdzj2obpa54em.openai.azure.com/" # Add your endpoint here
# openai.api_key = "825a0d3880054857a94fd70649196ad3" # Add your OpenAI API key here
# deployment_id = "chat" # Add your deployment ID here

# # Azure AI Search setup
# search_endpoint = "https://gptkb-cdzj2obpa54em.search.windows.net"; # Add your Azure AI Search endpoint here
# search_key = "VmM0fMtVNqbwZKbomZrZgRKnadwl12Qc3KXxMsXIzIAzSeBAgDyI"; # Add your Azure AI Search admin key here
# search_index_name = "escogidxtest"; # Add your Azure AI Search index name here

# def setup_byod(deployment_id: str) -> None:
#     """Sets up the OpenAI Python SDK to use your own data for the chat endpoint.

#     :param deployment_id: The deployment ID for the model to use with your own data.

#     To remove this configuration, simply set openai.requestssession to None.
#     """

#     class BringYourOwnDataAdapter(requests.adapters.HTTPAdapter):

#         def send(self, request, **kwargs):
#             request.url = f"{openai.api_base}/openai/deployments/{deployment_id}/extensions/chat/completions?api-version={openai.api_version}"
#             return super().send(request, **kwargs)

#     session = requests.Session()

#     # Mount a custom adapter which will use the extensions endpoint for any call using the given `deployment_id`
#     session.mount(
#         prefix=f"{openai.api_base}/openai/deployments/{deployment_id}",
#         adapter=BringYourOwnDataAdapter()
#     )

#     openai.requestssession = session

# setup_byod(deployment_id)
# def generate_message_text(user_question: str):
#     return [{"role": "user", "content": Question}]

# Question = input("Enter your Question?  ")
# message_text = generate_message_text(Question)

# completion = openai.ChatCompletion.create(
#     messages=message_text,
#     deployment_id=deployment_id,
#     dataSources=[  # camelCase is intentional, as this is the format the API expects
#         {
#             "type": "AzureCognitiveSearch",
#             "parameters": {
#                 "endpoint": search_endpoint,
#                 "key": search_key,
#                 "indexName": search_index_name,
#             }
#         }
#     ]
# )
# # print(completion)
# Answer= completion['choices'][0]['message']['content']
# print("Answer:" , Answer)



from flask import Flask, render_template, request
import openai
import os
import requests

app = Flask(__name__)
app.static_folder = 'static'

openai.api_type = "azure"
openai.api_version = "2023-08-01-preview"
openai.api_base = "https://cog-cdzj2obpa54em.openai.azure.com/"
openai.api_key = "825a0d3880054857a94fd70649196ad3"
deployment_id = "chat"

search_endpoint = "https://gptkb-cdzj2obpa54em.search.windows.net"
search_key = "VmM0fMtVNqbwZKbomZrZgRKnadwl12Qc3KXxMsXIzIAzSeBAgDyI"
search_index_name = "escogidxtest"


def setup_byod(deployment_id: str) -> None:
    class BringYourOwnDataAdapter(requests.adapters.HTTPAdapter):

        def send(self, request, **kwargs):
            request.url = f"{openai.api_base}/openai/deployments/{deployment_id}/extensions/chat/completions?api-version={openai.api_version}"
            return super().send(request, **kwargs)

    session = requests.Session()
    session.mount(
        prefix=f"{openai.api_base}/openai/deployments/{deployment_id}",
        adapter=BringYourOwnDataAdapter()
    )
    openai.requestssession = session


def generate_message_text(user_question: str):
    return [{"role": "user", "content": user_question}]


@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        user_question = request.form["user_question"]
        message_text = generate_message_text(user_question)

        completion = openai.ChatCompletion.create(
            messages=message_text,
            deployment_id=deployment_id,
            dataSources=[
                {
                    "type": "AzureCognitiveSearch",
                    "parameters": {
                        "endpoint": search_endpoint,
                        "key": search_key,
                        "indexName": search_index_name,
                    }
                }
            ]
        )

        assistant_response = completion['choices'][0]['message']['content']
        return render_template("index.html", user_question=user_question, assistant_response=assistant_response)

    return render_template("index.html", user_question=None, assistant_response=None)


if __name__ == "__main__":
    setup_byod(deployment_id)
    app.run(debug=True)
