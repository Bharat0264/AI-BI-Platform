import os
import google.generativeai as genai

from dotenv import load_dotenv


# Load environment variables
load_dotenv()


# Configure Gemini API
genai.configure(
    api_key=os.getenv("GEMINI_API_KEY")
)


# Load Gemini Model
model = genai.GenerativeModel(
    "models/gemini-2.5-flash"
)


def ask_ai(question, df):

    try:

        # Dataset sample for AI context
        sample_data = df.head(20).to_string()


        # Prompt for business analysis
        prompt = f"""
You are an expert AI Business Intelligence Analyst.

Analyze the business dataset below.

DATASET SAMPLE:
{sample_data}

USER QUESTION:
{question}

Provide:
- Business insights
- Trend analysis
- Problems detected
- Recommendations
- Strategic suggestions

Keep the response professional and concise.
"""


        # Generate AI response
        response = model.generate_content(prompt)


        # Return AI text
        return response.text


    except Exception as e:

        return f"Error generating AI response: {str(e)}"