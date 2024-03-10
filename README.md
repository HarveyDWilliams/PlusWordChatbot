# PlusWordChatbot
A Python-based WhatsApp chatbot that reads in screenshots of [PlusWord](https://www.telegraph.co.uk/news/plusword/) times and stores them in a database for use with the [PlusWord Leaderboards](https://github.com/Tom-Whittington/Plusword) hosted [here](https://harve.dev/plusword).

The chatbot uses: 
    
- Flask for hosting an endpoint for the WhatsApp webhook to send data to.
- Meta's Graph API for sending and receiving data to/from WhatsApp.
- A MongoDB Atlas DB for storing data regarding times and other user config.
- Python-tesseract and OpenCV to read data from image data.
- Requests to send data to REST APIs.