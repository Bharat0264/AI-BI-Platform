import speech_recognition as sr


def listen_to_voice():

    recognizer = sr.Recognizer()


    with sr.Microphone() as source:

        print("Listening...")

        recognizer.adjust_for_ambient_noise(
            source
        )

        audio = recognizer.listen(source)


    try:

        query = recognizer.recognize_google(
            audio
        )

        return query


    except Exception as e:

        return f"Voice recognition error: {str(e)}"