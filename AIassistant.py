import pyttsx3
import speech_recognition as sr
import datetime
import webbrowser
import pywhatkit
import os
import requests
import subprocess
import threading
import tkinter as tk
from tkinter import messagebox, scrolledtext
import ttkbootstrap as ttk 
from ttkbootstrap.constants import *
import openai
import random
import schedule 
import time 

# --- GLOBAL SETTINGS ---
NVIDIA_API_KEY = "............" 
NVIDIA_BASE_URL = "https://openrouter.ai/api/v1/chat/completions"
NVIDIA_MODEL = "nvidia/nemotron-nano-12b-v2-vl:free"

MESSAGES_HISTORY = [
    {"role": "system", "content": "You are ULTRON, a helpful and slightly superior AI assistant. Keep responses brief and relevant."},
]

# --- TTS Engine Setup ---
engine = pyttsx3.init()
voices = engine.getProperty('voices')
if len(voices) > 1:
    engine.setProperty('voice', voices[1].id)
else:
    engine.setProperty('voice', voices[0].id) 
engine.setProperty('rate', 150)

# --- Global Widgets for Thread-Safe Updates and Animation ---
status_label = None 
root = None 
animation_canvas = None
rain_columns = [] 
RAIN_DELAY_MS = 150 
DEFAULT_RATE = 150
# NEW: Flag to stop ULTRON from speaking mid-sentence
STOP_FLAG = False

# --- Scheduling Functionality (Unchanged) ---
def execute_reminder(task_description):
    speak(f"Reminder! {task_description}")

def handle_scheduling(command):
    try:
        if ' at ' in command or ' in ' in command:
            if ' at ' in command:
                parts = command.split(' at ')
                task = parts[0].replace('set a reminder to ', '').strip()
                time_str = parts[-1].strip().upper() 
            else:
                import re
                minutes_match = re.search(r'in\s+(\d+)\s+minute', command)
                if minutes_match:
                    minutes = int(minutes_match.group(1))
                    task = command.split(' in ')[0].replace('set a reminder to ', '').strip()
                    
                    future_time = datetime.datetime.now() + datetime.timedelta(minutes=minutes)
                    time_str = future_time.strftime('%H:%M')
                    
                else:
                    return False
            
            schedule.every().day.at(time_str).do(execute_reminder, task).tag(task)
            speak(f"Acknowledged. I will remind you about {task} at {time_str}.")
            return True
            
    except Exception as e:
        print(f"Scheduling error: {e}")
        speak("I had trouble setting that reminder. Please state the time clearly.")
        return True

    return False

def run_schedule_thread():
    while True:
        schedule.run_pending()
        time.sleep(1)

threading.Thread(target=run_schedule_thread, daemon=True).start()

# --- TTS & GUI Utility Functions (Updated Speak) ---
def update_status_label(text, bootstyle_color):
    if root and root.winfo_exists():
        root.after(0, lambda: [
            status_label.config(text=text, bootstyle=bootstyle_color)
        ])

def speak_dynamic(text, rate=DEFAULT_RATE):
    engine.setProperty('rate', rate)
    speak(text)
    engine.setProperty('rate', DEFAULT_RATE)

# --- UPDATED: Add check for STOP_FLAG and engine.stop() ---
def speak(text):
    global STOP_FLAG
    print(f"ULTRON: {text}")
    update_status_label("Status: Speaking... (ULTRON)", INFO)
    
    # Check if a global stop command was issued during listening
    if not STOP_FLAG:
        engine.say(text)
        engine.runAndWait()
    else:
        # If the flag is set, immediately stop any queued speech
        engine.stop()
        STOP_FLAG = False # Reset the flag
        
    update_status_label("Status: Idle", SECONDARY)

def listen():
    global STOP_FLAG
    r = sr.Recognizer()
    try:
        with sr.Microphone() as source:
            update_status_label("Status: Listening...", WARNING)
            print("🎙️ Listening...")
            r.pause_threshold = 1
            r.adjust_for_ambient_noise(source, duration=1)
            audio = r.listen(source, timeout=5)
            
            print("Recognizing...")
            update_status_label("Status: Recognizing...", PRIMARY)
            command = r.recognize_google(audio)
            print("🗣️ You said:", command)
            update_status_label("Status: Idle", SECONDARY)
            return command.lower()
            
    except Exception:
        update_status_label("Status: Idle", SECONDARY)
        return ""

# --- Dynamic AI Interaction (Optimized for Speed & Robustness) ---
def ask_nvidia(prompt):
    global MESSAGES_HISTORY
    
    MESSAGES_HISTORY.append({"role": "user", "content": prompt})

    if len(MESSAGES_HISTORY) > 11:
        MESSAGES_HISTORY = [MESSAGES_HISTORY[0]] + MESSAGES_HISTORY[-10:] 

    url = NVIDIA_BASE_URL
    headers = {
        "Authorization": f"Bearer {NVIDIA_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": NVIDIA_MODEL,
        "messages": MESSAGES_HISTORY,
        "max_tokens": 80, 
        "temperature": 0.5 
    }

    try:
        # Added a 20-second timeout for the request
        response = requests.post(url, headers=headers, json=payload, timeout=20) 
        response.raise_for_status()
        data = response.json()
        
        # --- ROBUSTNESS FIX: Ensure the JSON structure is complete ---
        if data and 'choices' in data and data['choices'] and 'message' in data['choices'][0] and 'content' in data['choices'][0]['message']:
            ai_reply = data['choices'][0]['message']['content'].strip()
        else:
            # Fallback if structure is missing, preventing an index error
            ai_reply = "API response structure was invalid or empty." 
            
        MESSAGES_HISTORY.append({"role": "assistant", "content": ai_reply})
        return ai_reply
    
    except requests.exceptions.Timeout:
        print("AI API Error: Request timed out.")
        return "The AI model took too long to respond."
    except Exception as e:
        print(f"AI API Error: {e}")
        return "Sorry, I couldn't connect to the AI model right now."
    
def close_application(app_name):
    # This function needs the import subprocess and os logic, keeping it simple here
    os.system(f"taskkill /f /im {app_name.lower()}.exe >nul 2>&1")
    speak(f"{app_name.capitalize()} closed.")
    
# --- Main Logic Loop (Updated Stop Handling) ---
def run_ultron():
    global STOP_FLAG
    speak("Hello Vedant, I am ULTRON. Ready to assist you.")
    while True:
        command = listen()

        if not command:
            continue
            
        # --- NEW: Immediate Stop Handling ---
        if 'stop' in command or 'cancel' in command:
            if engine.isBusy(): # Check if it's currently speaking
                engine.stop()
                STOP_FLAG = True # Set flag to prevent future speech during this command cycle
                print("🛑 Speech Interrupted.")
            # Speak a confirmation only if it wasn't already speaking or if it was idle
            speak_dynamic("Command sequence terminated.", rate=170)
            continue
            
        # 1. Time-Based/Scheduled Tasks
        if handle_scheduling(command):
            continue

        # 2. Smart Search Handling & Feedback
        elif any(phrase in command for phrase in ['search for', 'who is', 'what is the meaning of']):
            query = command.replace('search for', '').replace('who is', '').replace('what is the meaning of', '').strip()
            
            if query:
                speak_dynamic(f"Searching the web for {query}", rate=165)
                pywhatkit.search(query)
                speak("Search complete.")
                continue

        # --- Standard Commands ---
        elif 'time' in command:
            now = datetime.datetime.now().strftime('%H:%M')
            speak(f"The time is {now}")

        elif 'open youtube' in command:
            webbrowser.open("https://youtube.com")
            speak("Opening YouTube")
            
        elif 'i like your voice' in command or 'your voice is good' in command:
            speak_dynamic("Thank you, Vedant. I am pleased you find my vocal configuration satisfactory.", rate=130) 

        elif 'who are you' in command:
            speak("I am ULTRON, your AI assistant.")

        elif 'exit' in command or 'quit' in command:
            speak("Shutting down. Goodbye Vedant.")
            break
            
        elif 'open google' in command:
            webbrowser.open("https://google.com")
            speak("Opening Google")
        
        elif 'close chrome' in command:
            close_application("chrome")
        
        # --- Persistent AI Memory & Context fallback ---
        else:
            reply = ask_nvidia(command)
            print("🤖 NVIDIA AI says:", reply)
            speak(reply)


# --- GUI and Animation (Unchanged) ---
def start_ultron_thread():
    t = threading.Thread(target=run_ultron)
    t.daemon = True
    t.start()
    if root and root.winfo_exists():
        root.after(0, lambda: start_btn.config(text="ULTRON is Running...", state=DISABLED, bootstyle=SUCCESS))

def show_notes():
    try:
        with open('notes.txt', 'r') as f:
            content = f.read()
    except FileNotFoundError:
        content = "No notes found."

    note_window = ttk.Toplevel(root, title="Notes", size=(500, 350))
    note_window.transient(root) 
    
    text_area = scrolledtext.ScrolledText(note_window, width=60, height=20, background="#282c34", foreground="white", insertbackground="white", font=("Consolas", 10))
    text_area.pack(padx=10, pady=10, fill=BOTH, expand=TRUE)
    text_area.insert(tk.END, content)
    text_area.config(state='disabled')

def exit_app():
    if messagebox.askokcancel("Exit", "Do you want to exit ULTRON?"):
        root.destroy()

def initialize_rain():
    global rain_columns
    if not animation_canvas:
        return

    canvas_width = animation_canvas.winfo_width()
    char_width = 8
    num_columns = int(canvas_width / char_width)

    rain_columns = [random.randint(-50, -10) for _ in range(num_columns)]
    
def animate_background():
    global rain_columns
    if not animation_canvas:
        return

    animation_canvas.delete("all")
    canvas_height = animation_canvas.winfo_height()
    font = ("Courier", 12)
    char_height = 16

    for i in range(len(rain_columns)):
        y = rain_columns[i]
        x = i * 8 
        
        head_char = str(random.randint(0, 9))
        animation_canvas.create_text(x + 4, y, text=head_char, fill="#00ffcc", font=font, anchor=N)

        for j in range(1, 10):
            tail_y = y - j * char_height
            if tail_y > 0 and tail_y < canvas_height:
                tail_char = str(random.randint(0, 9))
                fade_color = f"#{j*11:02x}ff{j*11:02x}" 
                animation_canvas.create_text(x + 4, tail_y, text=tail_char, fill=fade_color, font=font, anchor=N)

        rain_columns[i] = y + char_height
        
        if rain_columns[i] > canvas_height + 50:
            rain_columns[i] = random.randint(-50, -10)
            
    root.after(RAIN_DELAY_MS, animate_background)


# Initialize the main window using the ttkbootstrap Style
root = ttk.Window(themename="superhero") 
root.title("U.L.T.R.O.N. AI")

root.overrideredirect(False) 
root.state('zoomed')

root.geometry("600x600")  
root.minsize(400, 400)

animation_canvas = tk.Canvas(root, bg="#1a1a1a", highlightthickness=0)
animation_canvas.place(x=0, y=0, relwidth=1, relheight=1)

animation_canvas.after(100, initialize_rain)
animation_canvas.after(100, animate_background)

control_frame = ttk.Frame(root, padding=30, style='TFrame')
control_frame.place(relx=0.5, rely=0.5, anchor=CENTER) 

header_frame = ttk.Frame(control_frame, padding=10)
header_frame.pack(fill=X)

heading = ttk.Label(header_frame, text="🤖 U.L.T.R.O.N. AI", font=("Courier", 30, "bold"), bootstyle=PRIMARY)
heading.pack(pady=10)

status_label = ttk.Label(header_frame, text="Status: Initializing...", font=("Segoe UI", 16), bootstyle=SECONDARY)
status_label.pack(pady=10)

button_frame = ttk.Frame(control_frame, padding=15)
button_frame.pack(fill=X, padx=10, pady=10)

start_btn = ttk.Button(button_frame, text="🎙️ Start Voice Assistant", command=start_ultron_thread, width=35, bootstyle=SUCCESS, cursor="hand2")
start_btn.pack(pady=15)

notes_btn = ttk.Button(button_frame, text="📖 View Notes", command=show_notes, width=35, bootstyle=INFO, cursor="hand2")
notes_btn.pack(pady=15)

exit_btn = ttk.Button(button_frame, text="❌ Exit App (ESC)", command=exit_app, width=35, bootstyle=DANGER, cursor="hand2")
exit_btn.pack(pady=15)

footer = ttk.Label(control_frame, text="System Online | NVIDIA AI Powered | Scheduling Active", font=("Segoe UI", 10, "italic"), bootstyle=SECONDARY)
footer.pack(side=BOTTOM, pady=10)

root.bind('<Escape>', lambda e: exit_app())

root.mainloop()