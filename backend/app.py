


from flask import Flask, render_template, request,jsonify
from flask_cors import CORS
import openai
import os
import requests

app = Flask(__name__)
CORS(app)
# app.static_folder = 'static'
from collections.abc import Sequence

def is_it_a_sequence(obj):
    return isinstance(obj, Sequence)
print(is_it_a_sequence([1, 2, 3])) # True
print(is_it_a_sequence('abc')) # True


openai.api_type = "azure"
openai.api_version = "2023-08-01-preview"
openai.api_base = "" # Azure open ai endpoint
openai.api_key = "" # Azure open ai key
deployment_id = "chat"

search_endpoint = ""# azure cognitive serach service end point
search_key = "" # Azure conginitive search key
search_index_name = "" # Azure serach index


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


def generate_message_text(conversation_history, user_question):
    messages = [{"role": "user", "content": user_question}]

    for entry in conversation_history:
        messages.append({"role": "assistant", "content": entry["assistant_response"]})

    return messages


@app.route("/", methods=["POST"])
def index():
    conversation_history = []
    user_question = request.json.get("user_question")

    if conversation_history:
        last_assistant_response = conversation_history[-1]["assistant_response"]
        message_text = generate_message_text(conversation_history, user_question)
        message_text.append({"role": "assistant", "content": last_assistant_response})
    else:
        message_text = generate_message_text(conversation_history, user_question)

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
    conversation_history.append({"user_question": user_question, "assistant_response": assistant_response})

    return jsonify({"user_question": user_question, "assistant_response": assistant_response})


if __name__ == "__main__":
    setup_byod(deployment_id)
    app.run(debug=True,port=8000)
