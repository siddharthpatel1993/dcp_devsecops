import requests
import json
import time
from youtube_transcript_api import YouTubeTranscriptApi

#Problems with youtube links, API error claim of text only and no audio on youtube videos
'''
IGNORE, COULD BE USED FOR MP# UPLOADS
aai.settings.api_key = "12c5dc58090349efb7d970b4a783d539"
YOUR_API_TOKEN = "12c5dc58090349efb7d970b4a783d539"
headers = {
    "authorization": "12c5dc58090349efb7d970b4a783d539"
} 
transcriber = aai.Transcriber() #transcriber model
def extract_audio(user_input):
    # URL of the file to transcribe, Downloaded using yt_dlp
    youtube_url = user_input
    # Create a YouTube object
    yt = YouTube(youtube_url)
    
    audio_stream = yt.streams.filter(only_audio=True).first()
    audio_stream.download(output_path='.', filename='audio')
    return 'audio.mp4'
def process_input(user_input):
    audio_url = extract_audio(user_input)
    # AssemblyAI transcript endpoint (where we submit the file)
    transcript_endpoint = "https://api.assemblyai.com/v2/transcript"
    # request parameters where Speech Recognition has been enabled
    data = {
    "audio_url": audio_url,
    }
    # HTTP request headers
    headers={
    "Authorization": YOUR_API_TOKEN,
    "Content-Type": "application/json"
    }
    # submit for transcription via HTTP request
    response = requests.post(transcript_endpoint,
                         json=data,
                         headers=headers)
    return response.text
    
    # polling for transcription completion
    polling_endpoint = f"https://api.assemblyai.com/v2/transcript/{response.json()['id']}"
    while True:
        transcription_result = requests.get(polling_endpoint, headers=headers).json()
        if transcription_result['status'] == 'completed':
        # print the results
            return json.dumps(transcription_result, indent=2)
            
        elif transcription_result['status'] == 'error':
            raise RuntimeError(f"Transcription failed: {transcription_result['error']}")
        
        else:
            time.sleep(3)
'''
def process_input(user_input): # grabs user input
    outls = [] # creates an array 
    video_id = user_input  # makes the video Id the user input
    tx = YouTubeTranscriptApi.get_transcript(video_id, languages=['en']) #gets the transcript in dict format
    for segment in tx: # for each segment in the tx dict grab the text (timestamps excluded)
        outtxt = segment['text']
        outls.append(outtxt) # each text from each segment is added to the array 
    return '\n'.join(outls) #return the combined array seperated by a newline 
