from openai import OpenAI
import os
from dotenv import load_dotenv
load_dotenv()
api_key = os.getenv("API_KEY")

client = OpenAI(api_key=api_key)

models = client.models.list()
for m in models:
    print(m.id)