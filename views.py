from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login, logout
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from django.conf import settings
import json
from pytube import YouTube
import os
import assemblyai as aai
import openai
from .models import BlogPost
from moviepy.editor import VideoFileClip
from pytube.exceptions import PytubeError
import imghdr
import google.generativeai as genai

# Create your views here.
@login_required
def index(request):
    return render(request, 'index.html')

def features(request):
    return render(request,'user_choice.html')

@csrf_exempt
def choose_file(request):
    if request.method == 'POST':
        try:
            uploaded_file = request.FILES.get('file')
            file_path = os.path.join(settings.MEDIA_ROOT, uploaded_file.name)
            with open(file_path, 'wb') as destination:
                for chunk in uploaded_file.chunks():
                    destination.write(chunk)
                    
            # mime = magic.Magic()
            
            # file_type = mime.from_file(file_path)
            file_type=imghdr.what(file_path)

            # Perform actions based on file type
            if 'MP4' == file_type:
                # Handle MP4 file
                print(f'The file {file_path} is an MP4 file.')
                output_path_mp3 = os.path.splitext(file_path)[0] + '.mp3'
                convert_mp4_to_mp3(file_path, output_path_mp3)
                # Your MP4-specific logic here
                if os.path.exists(file_path):
                    os.remove(file_path)
                    
                file_path=output_path_mp3

            audio_file = file_path
            aai.settings.api_key = "79e059c356024cc6b19bbf2b649273c3"

            transcriber = aai.Transcriber()
            transcript = transcriber.transcribe(audio_file)
            transcription =transcript.text
            if not transcription:
                return JsonResponse({'error': " Failed to get transcript"}, status=500)


                # use OpenAI to generate the blog
            blog_content = generate_blog_from_transcription(transcription)
            if not blog_content:
                return JsonResponse({'error': " Failed to generate blog article"}, status=500)

            # save blog article to database
            new_blog_article = BlogPost.objects.create(
                user=request.user,
                youtube_title='',
                youtube_link='',
                generated_content=blog_content,
            )
            new_blog_article.save()
            if os.path.exists(audio_file):
                os.remove(audio_file)


            # return blog article as a response
            return JsonResponse({'content': blog_content})
        except Exception as e:
            print(f"Error handling file upload: {e}")
            return JsonResponse({'status': 'error'})
            
    

           


        
def convert_mp4_to_mp3(input_path, output_path):
    # Load the video clip
    video_clip = VideoFileClip(input_path)

    # Extract audio
    audio_clip = video_clip.audio

    # Write the audio to an MP3 file
    audio_clip.write_audiofile(output_path)

    # Close the clips
    audio_clip.close()
    video_clip.close()

@csrf_exempt
def generate_blog(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            yt_link = data['link']
        except (KeyError, json.JSONDecodeError):
            return JsonResponse({'error': 'Invalid data sent'}, status=400)


        # get yt title
        title = yt_title(yt_link)

        # get transcript
        transcription = get_transcription(yt_link)
        if not transcription:
            return JsonResponse({'error': " Failed to get transcript"}, status=500)


        # use OpenAI to generate the blog
        blog_content = generate_blog_from_transcription(transcription)
        if not blog_content:
            return JsonResponse({'error': " Failed to generate blog article"}, status=500)

        # save blog article to database
        new_blog_article = BlogPost.objects.create(
            user=request.user,
            youtube_title=title,
            youtube_link=yt_link,
            generated_content=blog_content,
        )
        new_blog_article.save()

        # return blog article as a response
        return JsonResponse({'content': blog_content})
    else:
        return JsonResponse({'error': 'Invalid request method'}, status=405)

def yt_title(link):
    try:
        yt = YouTube(link)
        title = yt.title
        print(title)
        return title
    except PytubeError as e:
        # Handle the exception, e.g., log the error
        print(f"Error getting the video title: {e}")
        return None
    

def download_audio(link):
    yt = YouTube(link)
    video = yt.streams.filter(only_audio=True).first()
    out_file = video.download(output_path=settings.MEDIA_ROOT)
    base, ext = os.path.splitext(out_file)
    new_file = base + '.mp3'
    os.rename(out_file, new_file)
    return new_file

def get_transcription(link):
    audio_file = download_audio(link)
    aai.settings.api_key = "79e059c356024cc6b19bbf2b649273c3"

    transcriber = aai.Transcriber()
    transcript = transcriber.transcribe(audio_file)
    if os.path.exists(audio_file):
        os.remove(audio_file)
    
    return transcript.text

def generate_blog_from_transcription(transcription):
   

    prompt = f"Based on the following transcript from a YouTube video, write a comprehensive blog article, write it based on the transcript, but dont make it look like a youtube video, make it look like a proper blog article:\n\n{transcription}\n\nArticle:"

    genai.configure(api_key="AIzaSyAneF92Q7lTgT4xOjXu-CO5Pbk1Wj1sZ4Q")

    # Set up the model
    generation_config = {
    "temperature": 1,
    "top_p": 0.95,
    "top_k": 0,
    "max_output_tokens": 1000,
    }

    safety_settings = [
    {
        "category": "HARM_CATEGORY_HARASSMENT",
        "threshold": "BLOCK_MEDIUM_AND_ABOVE"
    },
    {
        "category": "HARM_CATEGORY_HATE_SPEECH",
        "threshold": "BLOCK_MEDIUM_AND_ABOVE"
    },
    {
        "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
        "threshold": "BLOCK_MEDIUM_AND_ABOVE"
    },
    {
        "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
        "threshold": "BLOCK_MEDIUM_AND_ABOVE"
    },
    ]

    model = genai.GenerativeModel(model_name="gemini-1.5-pro-latest",
                                generation_config=generation_config,
                                safety_settings=safety_settings)

    convo = model.start_chat(history=[
    ])

    convo.send_message(prompt)
    generated_content=convo.last.text

    return generated_content



def blog_list(request):
    blog_articles = BlogPost.objects.filter(user=request.user)
    return render(request, "all-blogs.html", {'blog_articles': blog_articles})

def blog_details(request, pk):
    blog_article_detail = BlogPost.objects.get(id=pk)
    if request.user == blog_article_detail.user:
        return render(request, 'blog-details.html', {'blog_article_detail': blog_article_detail})
    else:
        return redirect('/')

def user_login(request):
    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']

        user = authenticate(request,username=username , password=password)
        if user is not None:
            login(request, user)
            return redirect('/')
        else:
            error_message = "Invalid username or password"
            return render(request, 'login.html', {'error_message': error_message})
        
    return render(request, 'login.html')

def user_signup(request):
    if request.method == 'POST':
        username = request.POST['username']
        email = request.POST['email']
        password = request.POST['password']
        repeatPassword = request.POST['repeatPassword']
        if len(password) < 8:
            error_message = 'Password must be 8 characters or longer'
            return render(request, 'signup.html', {'error_message': error_message})

        if password == repeatPassword:
            try:
                user = User.objects.create_user(username, email, password)
                user.save()
                login(request, user)
                return redirect('/')
            except:
                error_message = 'Error creating account'
                return render(request, 'signup.html', {'error_message':error_message})
        else:
            error_message = 'Password do not match'
            return render(request, 'signup.html', {'error_message':error_message})
        
    return render(request, 'signup.html')

def user_logout(request):
    logout(request)
    return redirect('/')
