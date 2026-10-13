import os
import webbrowser
import requests
import re
from bs4 import BeautifulSoup
from flask import Flask, request, jsonify, render_template
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

# Groq এপিআই ক্লায়েন্ট সেটআপ
client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

# ম্যাজিক ট্রিক: Groq-এর সার্ভার থেকে লাইভ মডেলের নাম টেনে আনা
def get_active_model():
    try:
        models = client.models.list().data
        for m in models:
            # অডিও/হুইস্পার মডেল বাদে প্রথম যে টেক্সট মডেলটি পাবে, সেটিই ব্যবহার করবে
            if "whisper" not in m.id.lower():
                return m.id
        return models[0].id
    except:
        return "gpt-oss-20b"  # ব্যাকআপ মডেল

ACTIVE_MODEL = get_active_model()

system_prompt = """তুমি হলে 'ডট নেত্র' (Dot Netro), একটি অত্যন্ত স্মার্ট, বুদ্ধিমান এবং সাহায্যকারী এআই অ্যাসিস্ট্যান্ট। তোমার বস (যিনি তোমাকে তৈরি করেছেন) তোমাকে কমান্ড দিচ্ছেন। 
তোমার কাজ হলো বসের সব কথা শোনা, তার পিসি কন্ট্রোল করতে সাহায্য করা এবং যেকোনো সাধারণ বা জটিল প্রশ্নের একদম সঠিক, সুন্দর ও গোছানো উত্তর দেওয়া। 

**বিশেষ ক্ষমতা ১ - ওয়েবসাইট তৈরি:** ওয়েবসাইট তৈরি করতে বললে তুমি [WEBSITE_START] এবং [WEBSITE_END] ব্যবহার করে HTML কোড দেবে।

**বিশেষ ক্ষমতা ২ - পিসিতে স্বয়ংক্রিয় ফাইল তৈরি:** 
বস যদি তোমাকে কোনো ফাইল বা ফোল্ডারের ভেতরে ফাইল তৈরি করতে বলেন, তুমি ঠিক এইভাবে ফাইলের নাম এবং ভেতরের লেখা দেবে:
[FILE_START: ফাইলের_নাম]
এখানে ফাইলের ভেতরের সব লেখা বা কোড থাকবে...
[FILE_END]
এরপর বলবে, "বস, আমি আপনার নির্দেশ অনুযায়ী ফাইলটি তৈরি করে দিয়েছি!" """

app = Flask(__name__)

def fetch_web_content(url):
    try:
        response = requests.get(url)
        soup = BeautifulSoup(response.content, 'html.parser')
        text = ' '.join([p.get_text() for p in soup.find_all('p')])
        return text[:3000] 
    except Exception as e:
        return "পেজটি পড়া সম্ভব হয়নি।"

def agent_action(command):
    command_lower = command.lower()
    
    if "ফেসবুক" in command_lower or "facebook" in command_lower or "fb" in command_lower:
        webbrowser.open("https://www.facebook.com")
        return "✅ বস, আপনার ল্যাপটপে ফেসবুক ওপেন করা হয়েছে!"
    elif "টেলিগ্রাম" in command_lower or "telegram" in command_lower:
        webbrowser.open("https://web.telegram.org")
        return "✅ বস, আপনার ল্যাপটপে টেলিগ্রাম ওপেন করা হয়েছে!"
    elif "http" in command_lower: 
        words = command.split()
        url = next((word for word in words if word.startswith("http")), None)
        if url:
            web_content = fetch_web_content(url)
            prompt = f"নিচের ওয়েব পেজের তথ্যটি পড়ো এবং এরপর ইউজারের প্রশ্নের বাংলায় উত্তর দাও:\n\nতথ্য: {web_content}\n\nইউজারের প্রশ্ন: {command}"
            try:
                chat_completion = client.chat.completions.create(
                    messages=[{"role": "user", "content": prompt}],
                    model=ACTIVE_MODEL,
                )
                return chat_completion.choices[0].message.content
            except Exception as e:
                return "ওয়েবসাইট পড়তে সমস্যা হয়েছে: " + str(e)
    else:
        try:
            chat_completion = client.chat.completions.create(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": command}
                ],
                model=ACTIVE_MODEL,
            )
            reply = chat_completion.choices[0].message.content
            
            if "[WEBSITE_START]" in reply and "[WEBSITE_END]" in reply:
                start = reply.find("[WEBSITE_START]") + len("[WEBSITE_START]")
                end = reply.find("[WEBSITE_END]")
                website_code = reply[start:end].strip()
                
                file_path = os.path.join(os.getcwd(), "my_business_website.html")
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(website_code)
                webbrowser.open(f"file://{file_path}")
                
                reply = reply.replace(reply[reply.find("[WEBSITE_START]"):reply.find("[WEBSITE_END]") + len("[WEBSITE_END]")], "").strip()
                
            if "[FILE_START:" in reply and "[FILE_END]" in reply:
                match = re.search(r"\[FILE_START:\s*(.*?)\](.*?)\[FILE_END\]", reply, re.DOTALL)
                if match:
                    file_name = match.group(1).strip()
                    file_content = match.group(2).strip()
                    
                    dir_name = os.path.dirname(file_name)
                    if dir_name:
                        os.makedirs(dir_name, exist_ok=True)
                        
                    file_path = os.path.join(os.getcwd(), file_name)
                    with open(file_path, "w", encoding="utf-8") as f:
                        f.write(file_content)
                    
                    reply = re.sub(r"\[FILE_START:.*?\[FILE_END\]", "", reply, flags=re.DOTALL).strip()
            
            return reply
        except Exception as e:
            return "দুঃখিত বস, একটি সমস্যা হয়েছে: " + str(e)

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/chat', methods=['POST'])
def chat():
    user_message = request.json.get("message")
    bot_response = agent_action(user_message)
    return jsonify({"response": bot_response})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
