import requests
import pandas as pd
import os
from pathlib import Path
from typing import Optional, Dict, Any

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
    Refactored InventoryChatBot compatible with Python 3.8 and REST API.
    """

    def __init__(self, api_key: str):
        self.api_key = api_key
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
        """Generates response using direct REST API, supporting multi-turn conversation."""
        if not self.api_key:
            raise GeminiAPIError(403, "GEMINI_API_KEY is not configured")

        try:
            # 1. System instruction and context
            system_prompt = f"{self.system_instruction}\n\n"
            system_prompt += f"=== بيانات المخزن الرئيسية ===\n{self.inventory_data or 'لا توجد بيانات حالية'}\n\n"
            system_prompt += f"=== معلومات الموقع ===\n{self.website_faq}\n\n"
            
            if self.uploaded_file_data:
                system_prompt += f"{self.uploaded_file_data}\n\n"

            # 2. Build multi-turn contents
            contents = []
            
            # Add previous messages as "user" and "model" roles
            if history:
                for msg in history:
                    contents.append({"role": "user", "parts": [{"text": msg['message']}]})
                    contents.append({"role": "model", "parts": [{"text": msg['reply']}]})
            
            # Add current user prompt with inventory context prepended
            user_prompt = system_prompt + f"\n❓ سؤال المستخدم: {user_question}"
            if not self.uploaded_file_data:
                user_prompt += "\n(لا يوجد ملف مرفوع حالياً - استخدم بيانات المخزن الأساسية فقط)"
            
            contents.append({"role": "user", "parts": [{"text": user_prompt}]})

            # Call API via requests
            api_url = (
                f"https://generativelanguage.googleapis.com/v1beta/models/"
                f"gemini-2.5-flash:generateContent?key={self.api_key}"
            )

            payload = {
                "contents": contents,
                "generationConfig": {
                    "temperature": 0.7,
                    "maxOutputTokens": 2048,
                }
            }

            resp = requests.post(api_url, json=payload, timeout=30)
            
            if resp.status_code == 200:
                data = resp.json()
                try:
                    return data["candidates"][0]["content"]["parts"][0]["text"]
                except:
                    return "تلقيت رداً لكن لم أتمكن من قراءته." if user_lang == "ar" else "I received a response but couldn't parse it."
            else:
                if resp.status_code == 429:
                    return "⚠️ تجاوزت الحد المسموح. انتظر دقيقة وحاول تاني." if user_lang == "ar" else "⚠️ AI quota exceeded. Please wait a moment."
                if resp.status_code == 403:
                    detail = resp.text[:500] if resp.text else "Forbidden"
                    raise GeminiAPIError(403, detail)
                return f"⚠️ حصل مشكلة تقنية ({resp.status_code})." if user_lang == "ar" else f"⚠️ AI error ({resp.status_code})."

        except GeminiAPIError:
            raise
        except Exception as e:
            return f"❌ حصلت مشكلة: {str(e)}"
