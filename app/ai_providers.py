# In: app/ai_providers.py

import google.generativeai as genai
from zai import ZaiClient 
from typing import Protocol, Dict, Any

class AIProvider(Protocol):

    async def ask(self, api_key: str, system_prompt: str, business_data_json: str, user_question: str ) -> str:
        ...

class GeminiProvider:
    async def ask(self, api_key: str, system_prompt: str, business_data_json: str, user_question: str) -> str:
        try:
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel('gemini-2.5-flash')
            full_prompt = f"{system_prompt}\n\n{business_data_json}\n\nUser Question: {user_question}"
            response = model.generate_content(full_prompt)
            return response.text
        except Exception as e:
            print(f"Gemini API Error: {e}")
            raise ConnectionError("Failed to get a response from the Gemini API. Please check your API key and network.")

class ZaiProvider:
    async def ask(self, api_key: str, system_prompt: str, business_data_json: str, user_question: str) -> str:
        try:

            client = ZaiClient(api_key=api_key)

            messages = [

                {"role": "system", "content": f"{system_prompt}\n\n{business_data_json}"},

                {"role": "user", "content": user_question}
            ]

            response = client.chat.completions.create(
                model="glm-4.5-flash",  
                messages=messages,
                temperature=0.5, 
                max_tokens=4096
            )

            if response.choices and response.choices[0].message:
                return response.choices[0].message.content
            else:
                raise ValueError("Received an empty or invalid response from Z.ai.")

        except Exception as e:

            print(f"Z.ai API Error: {e}")
            raise ConnectionError("Failed to get a response from the Z.ai API. Please check your API key and model configuration.")

AI_PROVIDERS: Dict[str, AIProvider] = {
    "gemini": GeminiProvider(),
    "zai": ZaiProvider()
}

def get_ai_provider(provider_name: str) -> AIProvider:
    provider = AI_PROVIDERS.get(provider_name)
    if not provider:
        raise ValueError(f"Unknown AI provider: {provider_name}")
    return provider
