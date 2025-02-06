import requests
import yfinance as yf
import xml.etree.ElementTree as ET
import matplotlib.pyplot as plt
import io
import base64
from fastapi import FastAPI, Request, WebSocket
from fastapi.responses import HTMLResponse
from jinja2 import Template
from langchain_openai import ChatOpenAI
from langchain.schema import HumanMessage
import re

# API-ключ для Together AI
TOGETHER_API_KEY = "64c2965ad385c714dba03db71b6fd40aa2253c895bbb4f20ce8f50517637b188"

# Словарь с компаниями и их тикерами
COMPANY_TICKERS = {
    "apple": "AAPL",
    "microsoft": "MSFT",
    "google": "GOOGL",
    "alphabet": "GOOGL",
    "meta": "META",
    "facebook": "META",
    "amazon": "AMZN",
    "tesla": "TSLA",
    "nvidia": "NVDA",
    "netflix": "NFLX",
    "intel": "INTC",
    "amd": "AMD",
    "ibm": "IBM",
    "twitter": "TWTR",
    "snapchat": "SNAP",
    "paypal": "PYPL",
    "starbucks": "SBUX",
    "coca-cola": "KO",
    "pepsi": "PEP",
    "boeing": "BA",
    "ford": "F",
    "general motors": "GM",
    "uber": "UBER",
    "lyft": "LYFT",
    "zoom": "ZM"
}

# FastAPI app
app = FastAPI()

# LLM модель
llm = ChatOpenAI(
    model_name="meta-llama/Llama-3.3-70B-Instruct-Turbo-Free",
    openai_api_key=TOGETHER_API_KEY,
    openai_api_base="https://api.together.xyz/v1"
)

def get_stock_price(company_name: str):
    """ Получает цену акций. """
    ticker = COMPANY_TICKERS.get(company_name.lower())

    if not ticker:
        return None, f"Компания '{company_name}' не найдена в базе."

    stock = yf.Ticker(ticker)
    data = stock.history(period="7d")

    if data.empty:
        return None, f"Не удалось найти данные по акции {ticker}."

    # Возвращаем только цену акции
    return f"Текущая цена {company_name} ({ticker}): {data['Close'].iloc[-1]:.2f} USD", f"Цена акции: {data['Close'].iloc[-1]:.2f} USD"



def get_news_summary(query: str):
    """ Получает новости и делает выжимку через LLM. """
    rss_url = f"https://news.google.com/rss/search?q={query}&hl=en-US&gl=US&ceid=US:en"
    response = requests.get(rss_url)

    if response.status_code != 200:
        return "Ошибка при получении новостей.", "", ""  # Возвращаем пустые строки, если ошибка

    root = ET.fromstring(response.content)
    items = root.findall(".//item")

    if not items:
        return "Не найдено новостей по данной теме.", "", ""  # Возвращаем пустые строки, если новостей нет

    news_texts = []
    for item in items[:3]:
        title = item.find("title").text
        description = item.find("description")
        text = description.text if description is not None else title
        news_texts.append(f"{title}: {text}")
    
    summary_prompt = f"Создай краткую сводку по этим новостям: {' '.join(news_texts)}"
    summary = chat_with_llama(summary_prompt)

    return "Новости по теме:", news_texts, summary  # Возвращаем три значения

def chat_with_llama(prompt: str):
    """ Общение с LLaMA 3 через LangChain. """
    try:
        response = llm([HumanMessage(content=prompt)])
        return response.content
    except Exception as e:
        return f"Ошибка общения с LLaMA: {str(e)}"

@app.get("/", response_class=HTMLResponse)
def home():
    template = Template("""
    <html>
        <head>
            <title>Чат с ИИ</title>
            <style>
                body {
                    font-family: Arial, sans-serif;
                    margin: 0;
                    padding: 0;
                    display: flex;
                    flex-direction: column;
                    height: 100vh;
                    background-color: #f4f4f4;
                }

                #chat {
                    flex: 1;
                    padding: 10px;
                    overflow-y: scroll;
                    display: flex;
                    flex-direction: column-reverse;
                }

                .message {
                    margin-bottom: 10px;
                    max-width: 70%;
                    padding: 10px;
                    border-radius: 15px;
                    font-size: 16px;
                    line-height: 1.5;
                    display: inline-block;
                    word-wrap: break-word;
                }

                .user {
        background-color: #e8e8e8;  /* ИИ будет серым */
        align-self: flex-end;
    }

    .ai {
        background-color: #e1f5fe;  /* Пользователь будет голубым */
        align-self: flex-start;
    }

                input[type="text"] {
                    padding: 10px;
                    border: none;
                    border-radius: 25px;
                    width: 80%;
                    margin: 10px;
                    font-size: 16px;
                }

                button {
                    padding: 10px 20px;
                    font-size: 16px;
                    border-radius: 5px;
                    background-color: #007bff;
                    color: white;
                    border: none;
                    cursor: pointer;
                }

                button:hover {
                    background-color: #0056b3;
                }
            </style>
        </head>
        <body>
            <h2 style="text-align:center; padding: 20px;">Чат с ИИ</h2>
            <div id="chat"></div>
            <div style="text-align: center; margin-bottom: 20px;">
                <input type="text" id="query" placeholder="Введите запрос" size="40">
                <button onclick="sendMessage()">Отправить</button>
            </div>
            <script>
    let ws = new WebSocket("ws://" + location.host + "/ws");

    ws.onmessage = function(event) {
        let chat = document.getElementById("chat");
        let messageDiv = document.createElement("div");
        messageDiv.classList.add('message');
        messageDiv.classList.add('ai');

        messageDiv.innerHTML = event.data;  // Печатаем только текст (не график)
        chat.prepend(messageDiv);
        chat.scrollTop = chat.scrollHeight;
    };

    function sendMessage() {
        let input = document.getElementById("query");
        let chat = document.getElementById("chat");

        // Отправляем сообщение пользователя
        let messageDiv = document.createElement("div");
        messageDiv.classList.add('message');
        messageDiv.classList.add('user');
        messageDiv.innerHTML = input.value;
        chat.prepend(messageDiv);

        // Отправляем запрос через WebSocket
        ws.send(input.value);
        input.value = "";
    }

    // Добавляем обработку Enter
    document.getElementById("query").addEventListener("keypress", function(event) {
        if (event.key === "Enter") {
            sendMessage();
        }
    });
</script>


        </body>
    </html>
    """)
    return template.render()



@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    while True:
        query = await websocket.receive_text()
        if re.search(r"как обстоят дела с\s+(.+)", query, re.IGNORECASE):
            company_name = re.search(r"как обстоят дела с\s+(.+)", query, re.IGNORECASE).group(1)
            _, price_message = get_stock_price(company_name)  # Получаем только сообщение с ценой
            _, _, summary = get_news_summary(company_name)  # Получаем только выжимку новостей

            # Формируем ответ с ценой и выжимкой новостей
            response_message = f"Цена акции: {price_message}<br>Выжимка: {summary}"
            await websocket.send_text(response_message)
        else:
            ai_response = chat_with_llama(query)  # Ответ ИИ на другие запросы
            await websocket.send_text(ai_response)





if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
