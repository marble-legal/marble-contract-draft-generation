from langchain_openai import OpenAIEmbeddings
from langchain_chroma import Chroma
from dotenv import load_dotenv
import os
from flask import Flask, jsonify,request,abort
from openai import OpenAI
import time
import json
# Load environment variables
load_dotenv()

# Configuration placeholders
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
VALID_API_KEYS = {os.getenv("FLASK_API_KEY")}
app = Flask(__name__)

class SelectDocument:
    def __init__(self,query,contract_type,database=None):
        self.query = query
        self.database = database
        self.contract_type = contract_type
        
    def load_db(self,directory):
        embeddings = OpenAIEmbeddings(model="text-embedding-3-large",openai_api_key=OPENAI_API_KEY)
        if self.database:
            loaded_db = self.database
        else:
            loaded_db = Chroma(persist_directory=directory, embedding_function=embeddings)
        self.database = loaded_db
    
    def select_document(self):
        doc = self.database.similarity_search(self.query,k=1)
        doc_name_matched = doc[0].metadata['source']
        return doc_name_matched

class Assistant:
    def __init__(self,query,selected_document):
        self.query = query
        self.selected_document = selected_document
        self.client = OpenAI(
        api_key=OPENAI_API_KEY,
        )
        self.generated_obj = None
    def generate_document(self):
        my_file = self.client.files.create(
            file=open(self.selected_document, "rb"),
            purpose='assistants'
        )
        my_assistant = self.client.beta.assistants.create(
            model="gpt-4o",
            instructions="You are legal contract writting expert.",
            name="Leagl AI",
            tools=[{"type": "file_search"}],
            tool_resources={
            "code_interpreter": {
            "file_ids": [my_file.id]
            }
        }
        )
        
        my_thread = self.client.beta.threads.create(
        messages=[
            {
            "role": "user",
            "content": self.query,
            "attachments": [
                {
                "file_id": my_file.id,
                "tools": [{"type": "file_search"}]
                }
            ]
            }
        ]
        )
        my_run = self.client.beta.threads.runs.create(
            thread_id=my_thread.id,
            assistant_id=my_assistant.id,
            )
        keep_retrieving_run = self.client.beta.threads.runs.retrieve(
            thread_id=my_thread.id,
            run_id=my_run.id
        )
        while True:
            all_messages = self.client.beta.threads.messages.list(
                thread_id=my_thread.id
            )
            try:
                if all_messages.data[0].content == []:
                    time.sleep(1)
                elif str(all_messages.data[0].content[0].text.value) == self.query:
                    time.sleep(1)
                else:
                    break
            except:
                return None
            
        
        return all_messages.data[0].content[0].text.value
    
    def generate_summary_title(self,draft):
        completion = self.client.chat.completions.create(
            model="gpt-4o",
            temperature=0,
            messages=[
                    {"role": "system", "content": f"You are a legal expert, use this contract draft in html format- {draft} and generate a title and summary in JSON format. For example - {{'title': 'contract title', 'summary':'conract summary'}}, generate only the JSON and no other text not even 'json' string strictly."},
                    {"role":"user", "content": "Generate title and summary"}]
        )
        res = completion.choices[0].message.content
        res_dic = json.loads(res)
        return res_dic['title'], res_dic['summary']

        
        
@app.route('/chat', methods=['POST'])
def get_document():
    if request.headers.get('x-api-key') and request.headers.get('x-api-key') in VALID_API_KEYS:
        pass
    else:
        abort(401)
    if request.is_json:
        # Get the JSON data
        data = request.get_json()
    # Extract the query parameter from the request
    try:
        query = data.get('query') + " generate a contract in the same html format as the attached file, return only html page and nothing else (any other text or instruction)."
        # print(history)
    except:
        query = None
    try:
        contract_type = data.get('contract_type')
    except:
        contract_type = None
    
    if query is None:
        return jsonify({'error': 'No query provided'}), 400
    if contract_type is None:
        return jsonify({'error': 'No type provided'}), 400
    select_doc_obj = SelectDocument(query,contract_type)
    select_doc_obj.load_db(contract_type)
    selected_doc = select_doc_obj.select_document()
    assistant = Assistant(query,selected_doc)
    response = assistant.generate_document()
    title,summary = assistant.generate_summary_title(response)
    if response:
        return jsonify({"title":title,"summary":summary,"html":response}),200
    else:
        return jsonify("This is out of my scope"),200
    
                
if __name__ == '__main__':
    app.run(host="0.0.0.0",debug=True,port=8002)