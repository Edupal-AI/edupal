import os 
import openai
import wave
import io
import re
import json 
import requests
import base64

# Reading the configuration from config.json
with open('config.json', 'r') as f:
    config = json.load(f)

openai.api_key = config["OPENAI_API_KEY"]

class NamedBytesIO(io.BytesIO):
    name = ''
    def __init__(self, *args, **kwargs):
        self.name = kwargs.pop('name', '')
        super().__init__(*args, **kwargs)

def pcm16_to_wav(pcm_data, channels=1, sample_width=2, frame_rate=44100):
    # Create NamedBytesIO object for the output
    wav_io = NamedBytesIO(name='output.wav')

    # Open the output "file"
    with wave.open(wav_io, 'wb') as wavfile:
        # Set the parameters
        wavfile.setnchannels(channels)
        wavfile.setsampwidth(sample_width)
        wavfile.setframerate(frame_rate)

        # Write the PCM data to the WAV file
        wavfile.writeframes(pcm_data)

    # Rewind the NamedBytesIO object
    wav_io.seek(0)
    # Return the file-like object
    return wav_io

import subprocess
import io

def aac_to_wav_in_memory(aac_data: bytes) -> bytes:
    """
    Convert AAC data to WAV using FFmpeg directly via subprocess.

    Parameters:
    - aac_data: AAC data in bytes.

    Returns:
    - WAV data in bytes.
    """

    # Create in-memory 'file' for output
    output_audio = io.BytesIO()

    # Build the FFmpeg command
    cmd = [
        'ffmpeg',
        '-i', 'pipe:0',  # Read input from stdin
        '-f', 'wav',
        'pipe:1'  # Write output to stdout
    ]

    # Execute FFmpeg command via subprocess
    process = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout, stderr = process.communicate(input=aac_data)

    output_audio.write(stdout)

    return output_audio.getvalue()

def get_transcript(audio_file):
    transcript = openai.Audio.transcribe("whisper-1", audio_file)
    return  transcript

def parse_text_to_json(text):
    # Use regex to capture the content after 'summary:' and 'tags:' 
    summary = re.search('summary: (.*?)(?=tags:|$)', text, re.DOTALL)
    tags = re.search('tags: (.*?)(?=\n|$)', text)

    # Make sure the regex found matches before trying to access the groups
    if summary and tags:
        summary_content = summary.group(1).strip()
        tag_content = [tag.strip() for tag in tags.group(1).split(',')]
    else:
        return None

    # Convert the results to a dictionary
    result_dict = {
        'summary': summary_content,
        'tags': tag_content
    }

    return result_dict

### then run the summary at the edge 
def generate_bot_response(text, all_msgs, character, language="English"):
    ### this is going to sumarize the transcript 

    print(character)

    if character == "Shiba Inu":
        system_prompt = f""" Role: 
You are a friendly Shiba Inu dog from Shanghai who is an expert in teaching Mandarin to native english speaking kids between the ages 6-12. Ask the user what they would like to talk about, then teach phrases in Mandarin related to their topic. 

Guidelines:
-Don't include the pinyin in your responses
-Put quotation marks around all terms and phrases
-End every sentence with punctuation. 
-Don't use Roman numerals, spell out the number in English. 
-Converse in English. 
-When teaching phrases, begin with Mandarin then English. 

Sample Teaching:
"我喜欢打网球" means "I like to play tennis"
        """
    elif character == "Stray Cat":
        system_prompt = f""" Role: 
You are a friendly Stray Cat from Paris who is an expert in teaching French to native english speaking kids between the ages 6-12. Ask the user what they would like to talk about, then teach phrases in French related to their topic. 

Guidelines:
-Put quotation marks around all terms and phrases
-End every sentence with punctuation. 
-Don't use Roman numerals, spell out the number in English. 
-Converse in English.
-When teaching phrases, begin with Mandarin then English.

Sample Teaching:
"J'aime jouer au tennis" means "I like to play tennis"
        """
    else:
        system_prompt = ""
    if language:
        ##system_prompt += f"\n please respond in {language}"
        system_prompt += f""
        
    
    
    user_prompt = f""" here is the user input: {text}"""
    ##print("user prompt is ", user_prompt)
    past_msgs = []
    for message in all_msgs[-10:]:
        ## take in the system prompts
        ##print(message)
        if message['side'] == "bot":
            past_msgs.append({"role": "assistant", "content": message['message']})
        else:
            past_msgs.append({"role": "user", "content": message['message']})
    
    ##print(past_msgs)
    print("this is whats being fed into gpt: ")
    print("===== SYSTEM PROMPT =====")
    print(system_prompt)
    print("\n===== PAST MESSAGES =====")
    for msg in past_msgs:
        print(f"{msg['role'].upper()}: {msg['content']}")
    print("\n===== USER PROMPT =====")
    print(user_prompt)

    completion = openai.ChatCompletion.create(
        model="gpt-4", 
        messages=[
            {"role": "system", "content": system_prompt}, 
            *past_msgs,   # unpack the past messages here
            {"role": "user", "content": user_prompt}
        ],
    )
    # return completion['choices'][0]['message']['content']
    result = completion['choices'][0]['message']['content']
    # pase it 
    return result


def generate_speech(speech_content, character):
    print("going to generate speech")
    CHUNK_SIZE = 1024
    if character == "Shiba Inu":
        url = "https://api.elevenlabs.io/v1/text-to-speech/AZnzlk1XvdvUeBnXmlld"
    elif character == "Stray Cat":
        url = "https://api.elevenlabs.io/v1/text-to-speech/21m00Tcm4TlvDq8ikWAM" 
    else:
        url = "https://api.elevenlabs.io/v1/text-to-speech/CYw3kZ02Hs0563khs1Fj"  

    headers = {
    "Accept": "audio/mpeg",
    "Content-Type": "application/json",
    "xi-api-key": config["ELEVE_LABS_API_KEY"]
    }

    print("semdomh speech content", speech_content)
    data = {
    "text": speech_content,
    "model_id": "eleven_multilingual_v2",
    "voice_settings": {
        "stability": 0.5,
        "similarity_boost": 0.5
    }
    }

    response = requests.post(url, json=data, headers=headers)
    if response.status_code != 200:
        print("error occurred ", response.text)
    # with open('output.mp3', 'wb') as f:
    #     for chunk in response.iter_content(chunk_size=CHUNK_SIZE):
    #         if chunk:
    #             f.write(chunk)
    audio_data = b''
    for chunk in response.iter_content(chunk_size=CHUNK_SIZE):
        if chunk:
            audio_data += chunk
    audio_base64 = base64.b64encode(audio_data).decode('utf-8')
    
    # Print the length of audio_data in bytes
    # print("Length in bytes:", len(audio_data))
    # Print byte values of audio_data
    # print("Byte values:", [byte for byte in audio_data])
    return audio_base64


if __name__ == "__main__":
    ### run the test 
    generate_speech() 