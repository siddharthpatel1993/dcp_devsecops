from django.shortcuts import render
from . import transcribe
from django.http import JsonResponse
import openai
from decouple import config
from django.views.decorators.http import require_http_methods

text = ''
result=''
openai_api_key = config('OPENAI_API_KEY')
openai.api_key = openai_api_key

@require_http_methods(["GET", "POST"])
def index(request):
    return(render(request, "index.html"))

@require_http_methods(["GET", "POST"])
def inputfile(request):
    return(render(request, "input.html"))

@require_http_methods(["GET", "POST"])
def result1(request):
    global text
    if request.method == "POST":
        text = request.POST.get("youtube_url")
        return(render(request, "result1.html", {"text": text}))

@require_http_methods(["GET", "POST"])
def result2(request):
    global result
    #if request.method == "POST":
    result = transcribe.process_input(text)
    return(render(request, "result2.html", {"result": result }))

def ask_openai(message):
    response = openai.ChatCompletion.create(
        model = 'gpt-3.5-turbo',
        messages = [
            {"role": "system", "content": "You are a Helpful Assistant and Tutor"},
            {"role": "user", "content": message}
        ]
    )
    answer = response.choices[0].message.content.strip()
    return answer

@require_http_methods(["GET", "POST"])
def chatbot(request):
    if request.method == 'POST':
        message = request.POST.get('message')
        response = ask_openai(message)
        return JsonResponse({'message': message, 'response': response})
    return render(request, 'chatbot.html')

@require_http_methods(["GET", "POST"])
def notes(request):
    result = transcribe.process_input(text)
    def comp(PROMPT, MaxToken=50, outputs=3):
        response = openai.Completion.create(
            model="text-davinci-003",
            prompt=PROMPT,
            max_tokens=MaxToken,
            n=outputs
        )
        output = list()
        for k in response['choices']:
            output.append(k['text'].strip())
        return output
    
    #Adding the word limit to 3500 on result
    PROMPT = "Summarize the below text and extract the key points. Text:"+ result[0:3500] +""
    return(render(request, "result3.html", {"a": comp(PROMPT, MaxToken=3000, outputs=1) }))
