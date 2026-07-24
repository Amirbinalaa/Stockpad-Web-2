# import requests
import pandas as pd
import os
import logging
from pathlib import Path
from typing import Optional, Dict, Any
from groq import Groq

logger = logging.getLogger(__name__)

def load_data_professional_from_file(file_obj, filename):
    """
    Refactored version of load_data_professional to work with Django uploaded files.
    """
    try:
        file_extension = Path(filename).suffix.lower()

        if file_extension == '.csv':
            df = pd.read_csv(
                file_obj,
                encoding='utf-8-sig',
                dtype=str,
                keep_default_na=False,
                na_values=['', 'NULL', 'null', 'NA', 'na']
            )
        elif file_extension in ['.xlsx', '.xls']:
            df = pd.read_excel(
                file_obj,
                engine='openpyxl',
                dtype=str,
                keep_default_na=False
            )
        else:
            return f"❌ صيغة الملف غير مدعومة: {file_extension}. استخدم .csv أو .xlsx"

        # Cleaning logic from data_manager.py
        df.columns = df.columns.str.strip()
        df.columns = df.columns.str.replace(r'\s+', ' ', regex=True)

        for col in df.select_dtypes(include=['object', 'string']).columns:
            df[col] = df[col].astype(str).str.strip()
            df[col] = df[col].replace('nan', '')
            df[col] = df[col].replace('None', '')

        df = df.dropna(how='all')
        df = df.dropna(axis=1, how='all')
        df = df.reset_index(drop=True)

        return df.to_markdown(index=False)
    except Exception as e:
        return f"❌ خطأ في معالجة الملف: {str(e)}"

class GeminiAPIError(Exception):
    """Raised when the Gemini API rejects a request (e.g. invalid/missing API key)."""

    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


class InventoryChatBot:
    """
    Refactored InventoryChatBot compatible with Python 3.8 and REST API, updated to use Groq.
    """

    def __init__(self, api_key: str = None):
        # Preserve original environment setup for reference but comment out/adjust
        # self.api_key = api_key or os.environ.get("GEMINI_API_KEY", "")
        self.api_key = api_key or os.environ.get("GROQ_API_KEY", "")
        self.inventory_data: str = ""
        self.website_faq: str = "الموقع بيسمحلك ترفع ملف خطة إنتاج وتقارنها بالمخزن."
        self.uploaded_file_data: str = ""
        
        # Friendly Egyptian Arabic prompt from data_manager.py
        self.system_instruction = """
        أنت مساعد ذكي لمصنع، مهمتك تحليل البيانات المتاحة أمامك فقط.

        📌 ملاحظة مهمة: هناك نوعين من البيانات:
        1️⃣ بيانات دائمة (المخزن الرئيسي ومعلومات الموقع)
        2️⃣ بيانات مؤقتة (الملفات اللي المستخدم بيعملها Upload)

        إذا سألك المستخدم عن مادة، ابحث عنها في بيانات المخزن.
        إذا رفع المستخدم ملفاً، قارن بياناته بالملف المؤقت مع بيانات المخزن ووضح النواقص.

        تحدث باللهجة المصرية العامية الودودة جداً.
        """

    def generate_response(self, user_question: str, history=None, user_lang: str = "en") -> str:
        """Generates response using Groq, supporting multi-turn conversation."""
        raw_key = os.environ.get("GROQ_API_KEY") or self.api_key or ""
        clean_key = "".join(raw_key.split())

        if not clean_key:
            logger.error("GROQ_API_KEY is missing or empty after sanitization.")
            raise GeminiAPIError(403, "GROQ_API_KEY is not configured or is empty.")

        try:
            # 1. System instruction and context
            system_prompt = f"{self.system_instruction}\n\n"
            system_prompt += f"=== بيانات المخزن الرئيسية ===\n{self.inventory_data or 'لا توجد بيانات حالية'}\n\n"
            system_prompt += f"=== معلومات الموقع ===\n{self.website_faq}\n\n"
            
            if self.uploaded_file_data:
                system_prompt += f"{self.uploaded_file_data}\n\n"

            # 2. Build multi-turn messages for Groq
            messages = []
            
            # System instruction as a system message
            messages.append({"role": "system", "content": system_prompt})
            
            # Add previous messages
            if history:
                for msg in history:
                    messages.append({"role": "user", "content": msg['message']})
                    messages.append({"role": "assistant", "content": msg['reply']})
            
            # Add current user prompt
            user_prompt = f"❓ سؤال المستخدم: {user_question}"
            if not self.uploaded_file_data:
                user_prompt += "\n(لا يوجد ملف مرفوع حالياً - استخدم بيانات المخزن الأساسية فقط)"
            
            messages.append({"role": "user", "content": user_prompt})

            # --- Preserved Gemini Implementation for Reference ---
            # # Call API via requests directly with gemini-2.0-flash
            # api_url = (
            #     f"https://generativelanguage.googleapis.com/v1beta/models/"
            #     f"gemini-2.0-flash:generateContent?key={self.api_key}"
            # )
            # payload = {
            #     "contents": contents,
            #     "generationConfig": {
            #         "temperature": 0.7,
            #         "maxOutputTokens": 2048,
            #     }
            # }
            # try:
            #     resp = requests.post(api_url, json=payload, timeout=30)
            #     if resp.status_code == 200:
            #         data = resp.json()
            #         try:
            #             return data["candidates"][0]["content"]["parts"][0]["text"]
            #         except Exception as e:
            #             logger.exception("Failed to parse Gemini response JSON. Response: %s", data)
            #             return "تلقيت رداً لكن لم أتمكن من قراءته." if user_lang == "ar" else "I received a response but couldn't parse it."
            #     else:
            #         logger.error("Gemini API request failed...")
            # ------------------------------------------------------

            try:
                # Initialize the Groq client with the sanitized API key
                client = Groq(api_key=clean_key)
                
                # Update the chat completion logic to use model "llama-3.3-70b-versatile"
                response = client.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=messages,
                    temperature=0.7,
                )
                
                if response and response.choices:
                    return response.choices[0].message.content
                else:
                    return "تلقيت رداً فارغاً من النموذج." if user_lang == "ar" else "I received an empty response from the model."
            except Exception as e:
                logger.exception("Groq API request failed: %s", e)
                return f"❌ حصلت مشكلة في الاتصال بالنموذج (Groq): {str(e)}"

        except Exception as e:
            logger.exception("Unexpected error in chatbot logic: %s", e)
            return f"❌ حصلت مشكلة: {str(e)}"
